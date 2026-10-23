"""Production entry point (hand-written orchestration of the evaluated components; no new logic).

    report = run_safety_check(age=72, medications=["195700013", "196900031"])

`medications` must be item_seq values the user has confirmed (see drug_lookup). The call chain is the
one evaluated in 06-E:

    02 screen_patient(medications, age, include_evidence=True)
    -> 05 findings_from_screening_result(result)          # one ScreeningFinding per 02 record
    -> for each finding: 05 generate_explanation(finding)
           = 04 build_query + retrieve_hybrid (top_k=5)   (via 05 retrieve_evidence)
           -> 05 prepare_evidence_context -> build_prompt -> call_llm -> validate_output
    -> structured result

Only orchestration-level additions (documented): an exception raised while explaining one finding is
caught and reported for that finding (status PIPELINE_ERROR) instead of aborting the whole report, and
`warnings` collects fields the components already produce. No clinical judgement, filtering or guardrail
is added. The full prompt / raw LLM response are not included unless include_records=True, and nothing
is logged or written to disk.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from . import resources
from .screening import screen_patient, ENGINE_NAME, ENGINE_VERSION
from .findings import findings_from_screening_result
from .generation import (generate_explanation, call_llm, retrieve_evidence, GENERATION_CONFIG,
                         PROMPT_VERSION, OUTPUT_SCHEMA_VERSION)
from .retrieval import HYBRID_PARAMS

PIPELINE_NAME = "dur_safety_pipeline"
PIPELINE_VERSION = "0.1.0"
RUN_TYPE = "production"


def _finding_entry(finding, rec, include_records):
    out = rec.get("output") or {}
    entry = {
        "finding_id": finding.finding_id,
        "risk_type": finding.risk_type,
        "rule_source": finding.rule_source,
        "target_item_seqs": list(finding.target_item_seqs),
        "drugs": [asdict(d) for d in finding.drugs],
        "dur_rule_texts": list(finding.dur_rule_texts),
        "canonical_pair_id": finding.canonical_pair_id,
        "effect_name": finding.effect_name,
        "retrieval": {
            "status": rec.get("retrieval_status"), "reason": rec.get("retrieval_reason"),
            "warnings": list(rec.get("retrieval_warnings") or []), "method": rec.get("retrieval_method"),
            "query": rec.get("retrieval_query"), "n_retrieved": rec.get("n_retrieved"),
            "candidate_info": rec.get("candidate_info"),
        },
        "evidence": rec.get("evidence") or [],
        "dropped_evidence": rec.get("dropped_evidence") or [],
        "evidence_errors": rec.get("evidence_errors") or [],
        "generation": {
            "status": rec.get("generation_status"),
            "llm_called": rec.get("llm_called"),
            "output": rec.get("output"),
            "evidence_status": out.get("evidence_status"),
            "cited_evidence_ids": list(rec.get("cited_evidence_ids") or []),
            "schema_errors": list(rec.get("schema_errors") or []),
            "citation_errors": list(rec.get("citation_errors") or []),
            "citation_warnings": list(rec.get("citation_warnings") or []),
            "directive_flags": list(rec.get("directive_flags") or []),
            "llm_error": rec.get("llm_error"),
            "stop_reason": rec.get("stop_reason"),
            "user_prompt_sha256": rec.get("user_prompt_sha256"),
        },
    }
    if include_records:
        entry["record"] = rec
    return entry


def run_safety_check(age, medications, llm_fn=call_llm, *, retrieval_fn=None, include_records=False):
    """Run screening -> per-finding retrieval -> generation -> validation for confirmed item_seq values."""
    if not resources.is_loaded():
        raise RuntimeError("call dur_safety.resources.load_resources() before run_safety_check()")
    retrieval_fn = retrieval_fn or retrieve_evidence
    screening = screen_patient(medications, age=age, include_evidence=True)
    findings = findings_from_screening_result(screening)

    entries, errors = [], []
    for f in findings:
        try:
            rec = generate_explanation(f, llm_fn=llm_fn, retrieval_fn=retrieval_fn, run_type=RUN_TYPE)
            entries.append(_finding_entry(f, rec, include_records))
        except Exception as e:  # noqa: BLE001 — reported per finding, other findings continue
            msg = f"{type(e).__name__}: {str(e)[:300]}"
            errors.append({"finding_id": f.finding_id, "error": msg})
            entries.append({"finding_id": f.finding_id, "risk_type": f.risk_type,
                            "target_item_seqs": list(f.target_item_seqs),
                            "drugs": [asdict(d) for d in f.drugs], "dur_rule_texts": list(f.dur_rule_texts),
                            "retrieval": None, "evidence": [], "generation": {"status": "PIPELINE_ERROR",
                                                                              "error": msg}})

    patient, summary = screening["patient"], screening["summary"]
    warnings = []
    if patient["invalid_inputs"]:
        warnings.append({"code": "INVALID_INPUTS", "detail": patient["invalid_inputs"]})
    if patient["duplicate_inputs"]:
        warnings.append({"code": "DUPLICATE_INPUTS", "detail": patient["duplicate_inputs"]})
    if patient["not_found_in_dur_tables"]:
        warnings.append({"code": "NOT_FOUND_IN_DUR_TABLES", "detail": patient["not_found_in_dur_tables"]})
    if summary["elderly_check_status"] != "evaluated":
        warnings.append({"code": "ELDERLY_CHECK_" + summary["elderly_check_status"].upper(), "detail": None})
    for e in entries:
        r = e.get("retrieval") or {}
        for w in r.get("warnings") or []:
            warnings.append({"code": "RETRIEVAL_" + w, "detail": e["finding_id"]})
        if r.get("status") not in (None, "OK"):
            warnings.append({"code": "RETRIEVAL_STATUS_" + str(r.get("status")), "detail": e["finding_id"]})
        st = e["generation"]["status"]
        if st != "GENERATED":
            warnings.append({"code": "GENERATION_" + str(st), "detail": e["finding_id"]})
        if e["generation"].get("directive_flags"):
            warnings.append({"code": "DIRECTIVE_LANGUAGE_FLAGGED", "detail": e["finding_id"]})

    return {
        "pipeline": {"name": PIPELINE_NAME, "version": PIPELINE_VERSION,
                     "screening_engine": f"{ENGINE_NAME} {ENGINE_VERSION}",
                     "retrieval": {"method": "hybrid", "top_k": HYBRID_PARAMS["default_top_k"]},
                     "generation": {"model": GENERATION_CONFIG["model"], "prompt_version": PROMPT_VERSION,
                                    "output_schema_version": OUTPUT_SCHEMA_VERSION},
                     "scope_note": screening["scope_note"]},
        "screening": screening,
        "findings": entries,
        "summary": {
            "n_findings": len(entries),
            "by_risk_type": dict(Counter(e["risk_type"] for e in entries)),
            "generation_status_counts": dict(Counter(e["generation"]["status"] for e in entries)),
            "llm_calls": sum(1 for e in entries if e["generation"].get("llm_called")),
            "elderly_check_status": summary["elderly_check_status"],
        },
        "warnings": warnings,
        "errors": errors,
    }

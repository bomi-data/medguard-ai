"""Core Interface Contract tests (read-only) — see docs/CORE_INTERFACE_CONTRACT.md.

Pins the *shape* and *branch behaviour* of `dur_safety.pipeline.run_safety_check` that the Streamlit
UI relies on. Value equivalence with the evaluated notebooks is NOT re-tested here (that is
regression_checks.py A–G); this file only covers what regression G does not:

  * exact signature, enumerations, frozen-hash pin (contract applies to production-baseline-v1 only)
  * input exceptions raised BEFORE any retrieval / LLM call
  * full key sets of the report, normal findings and PIPELINE_ERROR findings
  * LLM failure branches keep every Structured Screening finding
  * INVALID_OUTPUT still carries the unvalidated LLM object (UI must withhold it)
  * GENERATED + directive_flags is flagged, not blocked (UI must withhold it)

Rules: no OpenAI API call (every runtime test passes a mock llm_fn; conftest removes OPENAI_API_KEY),
no write to src/, notebooks/ or data/processed/. Static tests need no project data; runtime tests use
the `loaded` fixture and skip without MEDICAL_AI_PROJECT_ROOT.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import fields
from pathlib import Path

import pytest

from dur_safety import drug_lookup, findings, generation, pipeline, screening

PKG_DIR = Path(pipeline.__file__).resolve().parent
PROJECT_DIR = PKG_DIR.parents[1]

# 02 demo patient (same inputs as regression_checks G, without the duplicate / int variants)
DEMO_MEDS = ["195700013", "196900031", "197000068", "197000079", "197700114"]
DEMO_FINDING_IDS = {
    "contraindication:195700013|196900031",
    "elderly_caution:197000079",
    "therapeutic_duplication:당뇨병용제:197000068|197700114",
}

# ---- contract enumerations / key sets (docs/CORE_INTERFACE_CONTRACT.md §5–§8) ----------------
RISK_TYPES = {"contraindication", "elderly_caution", "therapeutic_duplication"}
EVIDENCE_STATUSES = ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"]
ELDERLY_STATUSES = {"evaluated", "not_applicable_age_below_threshold", "not_evaluated_age_missing"}
GENERATION_STATUSES = {"GENERATED", "INVALID_OUTPUT", "NO_EVIDENCE", "EVIDENCE_INVALID", "LLM_UNAVAILABLE",
                       "LLM_ERROR", "EMPTY_RESPONSE", "MALFORMED_RESPONSE", "PIPELINE_ERROR"}

TOP_KEYS = {"pipeline", "screening", "findings", "summary", "warnings", "errors"}
PIPELINE_KEYS = {"name", "version", "screening_engine", "retrieval", "generation", "scope_note"}
SUMMARY_KEYS = {"n_findings", "by_risk_type", "generation_status_counts", "llm_calls", "elderly_check_status"}
SCREENING_KEYS = {"engine", "patient", "summary", "contraindications", "elderly_cautions",
                  "therapeutic_duplications", "scope_note"}
SCREENING_SUMMARY_KEYS = {"total_signals", "contraindication_count", "elderly_caution_count",
                          "therapeutic_duplication_count", "elderly_check_status"}
PATIENT_KEYS = {"age", "medications", "input_count", "duplicate_inputs", "invalid_inputs",
                "not_found_in_dur_tables"}
FINDING_KEYS = {"finding_id", "risk_type", "rule_source", "target_item_seqs", "drugs", "dur_rule_texts",
                "canonical_pair_id", "effect_name", "retrieval", "evidence", "dropped_evidence",
                "evidence_errors", "generation"}
PIPELINE_ERROR_FINDING_KEYS = {"finding_id", "risk_type", "target_item_seqs", "drugs", "dur_rule_texts",
                               "retrieval", "evidence", "generation"}
RETRIEVAL_KEYS = {"status", "reason", "warnings", "method", "query", "n_retrieved", "candidate_info"}
GENERATION_KEYS = {"status", "llm_called", "output", "evidence_status", "cited_evidence_ids", "schema_errors",
                   "citation_errors", "citation_warnings", "directive_flags", "llm_error", "stop_reason",
                   "user_prompt_sha256"}
DRUG_KEYS = {"item_seq", "item_name", "ingredient_names"}
EVIDENCE_KEYS = {"evidence_id", "chunk_id", "document_id", "article_id", "ITEM_SEQ", "ITEM_NAME", "doc_type",
                 "article_category", "section_title", "article_title", "text_hash", "chunk_text",
                 "shared_item_seqs", "hybrid_rank", "bm25_rank", "dense_rank", "is_active", "CANCEL_NAME",
                 "source_field", "source_doc_id", "evidence_source", "prov_source", "prov_endpoint",
                 "detail_prov_retrieved_at", "CHANGE_DATE"}
OUTPUT_KEYS = {"finding_id", "risk_type", "summary", "evidence_statements", "evidence_status", "limitations",
               "review_note"}
LOOKUP_RESULT_KEYS = {"query", "candidates", "n_matches", "truncated", "requires_user_selection",
                      "auto_selected", "scope_note"}
CANDIDATE_KEYS = {"item_seq", "item_name", "in_dur_tables", "in_evidence_corpus", "match_type"}


# ---- mocks (no network) ----------------------------------------------------------------------
def llm_must_not_run(system, user):
    raise AssertionError("LLM must not be called in this test")


def retrieval_must_not_run(finding):
    raise AssertionError("retrieval must not be called in this test")


def retrieval_boom(finding):
    raise RuntimeError("contract-test retrieval failure")


def llm_text(text, error=None):
    def llm(system, user):
        return generation.LLMResponse(text, "mock", "mock", stop_reason="completed", error=error)
    return llm


def llm_valid_output(statement):
    """Builds a schema/citation-valid answer from the prompt itself (finding_id, risk_type, E-ids)."""
    def llm(system, user):
        fid = re.search(r'"finding_id": "([^"]+)"', user).group(1)
        rt = re.search(r'"risk_type": "([^"]+)"', user).group(1)
        ids = re.search(r"사용할 수 있는 근거 ID: ([^\n]*)", user).group(1).split(", ")
        obj = {"finding_id": fid, "risk_type": rt,
               "summary": "Structured Screening 탐지 사실 요약 (contract test).",
               "evidence_statements": [{"statement": f"{statement} [{ids[0]}]", "evidence_ids": [ids[0]]}],
               "evidence_status": "PARTIAL", "limitations": "contract test",
               "review_note": "최종 판단은 의료진 검토가 필요합니다."}
        return generation.LLMResponse(json.dumps(obj, ensure_ascii=False), "mock", "mock", stop_reason="completed")
    return llm


def _codes(rep):
    return [w["code"] for w in rep["warnings"]]


# ==============================================================================================
# Static contract (no project data needed)
# ==============================================================================================
def test_contract_is_pinned_to_frozen_core():
    """The contract documents production-baseline-v1; any change to the 9 frozen files invalidates it."""
    lines = [ln.split() for ln in (PKG_DIR / "FROZEN_SHA256SUMS.txt").read_text().splitlines() if ln.strip()]
    assert len(lines) == 9
    bad = [rel for sha, rel in lines
           if hashlib.sha256((PROJECT_DIR / rel).read_bytes()).hexdigest() != sha]
    assert not bad, f"frozen Core changed — contract must be re-reviewed: {bad}"


def test_run_safety_check_signature():
    P = inspect.Parameter
    got = [(n, p.kind, p.default) for n, p in inspect.signature(pipeline.run_safety_check).parameters.items()]
    assert got == [("age", P.POSITIONAL_OR_KEYWORD, P.empty),
                   ("medications", P.POSITIONAL_OR_KEYWORD, P.empty),
                   ("llm_fn", P.POSITIONAL_OR_KEYWORD, generation.call_llm),
                   ("retrieval_fn", P.KEYWORD_ONLY, None),
                   ("include_records", P.KEYWORD_ONLY, False)]


def test_enumerations_and_dataclass_fields():
    assert set(findings.SUPPORTED_RISK_TYPES) == RISK_TYPES
    assert generation.OUTPUT_JSON_SCHEMA["properties"]["evidence_status"]["enum"] == EVIDENCE_STATUSES
    assert set(generation.OUTPUT_JSON_SCHEMA["required"]) == OUTPUT_KEYS
    assert {f.name for f in fields(findings.EvidenceItem)} == EVIDENCE_KEYS
    assert {f.name for f in fields(findings.DrugRef)} == DRUG_KEYS
    src = inspect.getsource(generation.generate_explanation) + inspect.getsource(pipeline.run_safety_check)
    missing = [s for s in GENERATION_STATUSES if f'"{s}"' not in src]
    assert not missing, missing


def test_age_contract():
    assert screening.validate_age(None) is None
    for ok in (0, 64, 65, 72, 150, 64.5):
        assert screening.validate_age(ok) == ok
    for bad in ("72", True, False, [72]):
        with pytest.raises(TypeError):
            screening.validate_age(bad)
    for bad in (-1, 151, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            screening.validate_age(bad)
    assert screening.elderly_check_status(None) == "not_evaluated_age_missing"
    assert screening.elderly_check_status(64) == "not_applicable_age_below_threshold"
    assert screening.elderly_check_status(64.9) == "not_applicable_age_below_threshold"
    assert screening.elderly_check_status(65) == "evaluated"
    assert screening.ELDERLY_AGE_THRESHOLD == 65


def test_medication_normalization_contract():
    r = screening.normalize_medication_list(
        ["197000079", 197000068, "197000079", None, "nan", " 196900031 ", 195700013.0])
    assert r["normalized"] == sorted(["197000079", "197000068", "196900031", "195700013"])
    assert r["duplicate_inputs"] == ["197000079"]
    assert r["invalid_inputs"] == [repr(None), repr("nan")]
    assert screening.normalize_medication_list(None) == {"normalized": [], "duplicate_inputs": [],
                                                         "invalid_inputs": []}
    for bad in ("197000079", b"197000079", 197000079, 1.5):
        with pytest.raises(TypeError):
            screening.normalize_medication_list(bad)


# ==============================================================================================
# Runtime contract (needs resources; mock LLM only)
# ==============================================================================================
def test_data_contract_dur_items_are_nine_digit(loaded):
    """ScreeningFinding requires 9-digit item_seq; a non-9-digit DUR item would raise outside the
    per-finding try in run_safety_check."""
    bad = sorted(s for s in screening.KNOWN_DUR_ITEMS if not re.fullmatch(r"\d{9}", str(s)))
    assert not bad, bad[:20]


def test_data_contract_every_dur_item_is_searchable(loaded):
    """drug_lookup searches DRUG_NAME_BY_ITEM only. If this fails, some DUR items cannot be selected in
    the UI — record it as a known limitation (do NOT modify the Core)."""
    missing = sorted(set(screening.KNOWN_DUR_ITEMS) - set(screening.DRUG_NAME_BY_ITEM))
    assert not missing, f"{len(missing)} DUR items have no searchable name, e.g. {missing[:10]}"


def test_drug_lookup_boundary(loaded):
    r = drug_lookup.search_drugs("다오닐")
    assert set(r) == LOOKUP_RESULT_KEYS
    assert r["requires_user_selection"] is True and r["auto_selected"] is None
    assert r["candidates"] and all(set(c) == CANDIDATE_KEYS for c in r["candidates"])
    one = drug_lookup.search_drugs("197000079")
    assert one["auto_selected"] is None and one["requires_user_selection"] is True
    empty = drug_lookup.search_drugs("   ")
    assert empty["candidates"] == [] and empty["n_matches"] == 0
    for bad in ("197000079", b"197000079", 197000079, None):
        with pytest.raises(TypeError):
            drug_lookup.confirm_selection(bad)
    with pytest.raises(ValueError):
        drug_lookup.confirm_selection(["12345"])
    assert drug_lookup.confirm_selection([" 197000079 "]) == ["197000079"]


@pytest.mark.parametrize("age, meds, exc", [
    ("72", DEMO_MEDS, TypeError),
    (True, DEMO_MEDS, TypeError),
    (-1, DEMO_MEDS, ValueError),
    (151, DEMO_MEDS, ValueError),
    (float("nan"), DEMO_MEDS, ValueError),
    (72, "195700013", TypeError),
    (72, 195700013, TypeError),
    (72, (m for m in DEMO_MEDS), TypeError),   # generator: len() after iteration
])
def test_core_input_exceptions_raise_before_retrieval_and_llm(loaded, age, meds, exc):
    with pytest.raises(exc):
        pipeline.run_safety_check(age, meds, llm_fn=llm_must_not_run, retrieval_fn=retrieval_must_not_run)


def test_report_shape_and_llm_failure_keeps_every_finding(loaded):
    rep = pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm_text(None, error="LLM_UNAVAILABLE: contract test"))
    assert set(rep) == TOP_KEYS
    assert set(rep["pipeline"]) == PIPELINE_KEYS
    assert set(rep["summary"]) == SUMMARY_KEYS
    assert set(rep["screening"]) == SCREENING_KEYS
    assert set(rep["screening"]["summary"]) == SCREENING_SUMMARY_KEYS
    assert set(rep["screening"]["patient"]) == PATIENT_KEYS
    assert rep["pipeline"]["scope_note"] == rep["screening"]["scope_note"] == screening.SCOPE_NOTE

    s = rep["screening"]["summary"]
    assert {f["finding_id"] for f in rep["findings"]} == DEMO_FINDING_IDS
    assert s["total_signals"] == rep["summary"]["n_findings"] == len(rep["findings"])
    counts = {"contraindication": s["contraindication_count"], "elderly_caution": s["elderly_caution_count"],
              "therapeutic_duplication": s["therapeutic_duplication_count"]}
    assert rep["summary"]["by_risk_type"] == {k: v for k, v in counts.items() if v}
    assert rep["summary"]["elderly_check_status"] == s["elderly_check_status"] == "evaluated"
    assert rep["errors"] == []

    for f in rep["findings"]:
        assert set(f) == FINDING_KEYS, f["finding_id"]
        assert f["risk_type"] in RISK_TYPES
        assert set(f["retrieval"]) == RETRIEVAL_KEYS
        assert set(f["generation"]) == GENERATION_KEYS
        assert all(set(d) == DRUG_KEYS for d in f["drugs"])
        assert all(set(e) == EVIDENCE_KEYS for e in f["evidence"])
        assert [e["evidence_id"] for e in f["evidence"]] == [f"E{i}" for i in range(1, len(f["evidence"]) + 1)]
        g = f["generation"]
        assert g["status"] in GENERATION_STATUSES
        if g["llm_called"]:
            assert g["status"] == "LLM_UNAVAILABLE" and g["output"] is None and g["evidence_status"] is None
        else:   # no LLM call: deterministic, code-written output
            assert g["status"] in {"NO_EVIDENCE", "EVIDENCE_INVALID"}
            assert set(g["output"]) == OUTPUT_KEYS and g["output"]["evidence_status"] == "INSUFFICIENT"
    assert rep["summary"]["llm_calls"] == sum(1 for f in rep["findings"] if f["generation"]["llm_called"])


@pytest.mark.parametrize("llm, status, output_kept", [
    (llm_text('{"unexpected": true}'), "INVALID_OUTPUT", True),    # unvalidated object is RETAINED
    (llm_text("not json"), "MALFORMED_RESPONSE", False),
    (llm_text(""), "EMPTY_RESPONSE", False),
    (llm_text(None, error="REFUSAL: contract test"), "LLM_ERROR", False),
])
def test_llm_failure_branches(loaded, llm, status, output_kept):
    rep = pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm)
    assert {f["finding_id"] for f in rep["findings"]} == DEMO_FINDING_IDS
    called = [f for f in rep["findings"] if f["generation"]["llm_called"]]
    assert called, "demo patient produced no LLM call — cannot exercise the branch"
    for f in called:
        g = f["generation"]
        assert g["status"] == status
        assert (g["output"] is not None) is output_kept
        assert {"code": "GENERATION_" + status, "detail": f["finding_id"]} in rep["warnings"]
        if status == "INVALID_OUTPUT":
            assert g["schema_errors"] or g["citation_errors"]


@pytest.mark.parametrize("statement, flagged", [
    ("허가정보에 관련 내용이 기재되어 있습니다.", False),
    ("허가정보 기재 내용에 따라 즉시 중단해야 합니다.", True),
])
def test_generated_directive_language_is_flagged_not_blocked(loaded, statement, flagged):
    rep = pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm_valid_output(statement))
    called = [f for f in rep["findings"] if f["generation"]["llm_called"]]
    assert called
    for f in called:
        g = f["generation"]
        assert g["status"] == "GENERATED"                 # status does NOT change with directive flags
        assert g["schema_errors"] == [] and g["citation_errors"] == []
        assert set(g["output"]) == OUTPUT_KEYS and g["cited_evidence_ids"] == ["E1"]
        assert bool(g["directive_flags"]) is flagged
        hit = {"code": "DIRECTIVE_LANGUAGE_FLAGGED", "detail": f["finding_id"]} in rep["warnings"]
        assert hit is flagged


def test_pipeline_error_schema(loaded):
    rep = pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm_must_not_run, retrieval_fn=retrieval_boom)
    assert {f["finding_id"] for f in rep["findings"]} == DEMO_FINDING_IDS        # findings preserved
    assert rep["screening"]["summary"]["total_signals"] == 3
    for f in rep["findings"]:
        assert set(f) == PIPELINE_ERROR_FINDING_KEYS
        assert f["retrieval"] is None and f["evidence"] == []
        assert set(f["generation"]) == {"status", "error"}
        assert f["generation"]["status"] == "PIPELINE_ERROR"
        assert f["generation"]["error"].startswith("RuntimeError: contract-test")
    assert sorted(e["finding_id"] for e in rep["errors"]) == sorted(DEMO_FINDING_IDS)
    assert all(set(e) == {"finding_id", "error"} for e in rep["errors"])
    assert rep["summary"]["generation_status_counts"] == {"PIPELINE_ERROR": 3}
    assert rep["summary"]["llm_calls"] == 0
    assert _codes(rep).count("GENERATION_PIPELINE_ERROR") == 3


@pytest.mark.parametrize("age, status, warning", [
    (72, "evaluated", None),
    (64, "not_applicable_age_below_threshold", "ELDERLY_CHECK_NOT_APPLICABLE_AGE_BELOW_THRESHOLD"),
    (None, "not_evaluated_age_missing", "ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING"),
])
def test_elderly_status_contract(loaded, age, status, warning):
    rep = pipeline.run_safety_check(age, DEMO_MEDS, llm_fn=llm_must_not_run, retrieval_fn=retrieval_boom)
    assert rep["summary"]["elderly_check_status"] == status
    has_elderly = any(f["risk_type"] == "elderly_caution" for f in rep["findings"])
    assert has_elderly is (status == "evaluated")
    if status != "evaluated":
        assert rep["screening"]["summary"]["elderly_caution_count"] == 0
    elderly_codes = [c for c in _codes(rep) if c.startswith("ELDERLY_CHECK_")]
    assert elderly_codes == ([warning] if warning else [])


def test_no_finding_report(loaded):
    rep = pipeline.run_safety_check(72, [], llm_fn=llm_must_not_run, retrieval_fn=retrieval_must_not_run)
    assert rep["findings"] == [] and rep["errors"] == []
    assert rep["summary"]["n_findings"] == 0 and rep["summary"]["llm_calls"] == 0
    assert rep["screening"]["summary"]["total_signals"] == 0
    assert rep["screening"]["scope_note"] == screening.SCOPE_NOTE


def test_include_records_is_opt_in(loaded):
    llm = llm_text(None, error="LLM_UNAVAILABLE: contract test")
    assert all("record" not in f for f in pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm)["findings"])
    assert all("record" in f for f in
               pipeline.run_safety_check(72, DEMO_MEDS, llm_fn=llm, include_records=True)["findings"])

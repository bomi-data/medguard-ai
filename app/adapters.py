"""UI Adapter — the only layer between the Frozen Core (dur_safety, production-baseline-v1) and the UI.

    selection = MedicationSelection()
    selection.register_search(drug_lookup.search_drugs("다이아벡스"))   # candidates shown to the user
    selection.add("197000079")                                       # user clicked a candidate
    vm = run_safety_check_view({"age": 72}, selection)               # validate → Core → ViewModel

Input Adapter   validate_input()     age / medication checks; Core is NOT called on failure
Execution       execute()            calls core_fn(age, medications) exactly once, measures wall-clock
Output Adapter  build_view_model()   validates report shape + count invariant, builds the ViewModel

Boundaries (enforced here, tested in tests/test_ui_adapter.py)
  * No Frozen Core file is modified; Core objects are only read. The report is deep-copied, never mutated.
  * No medical judgement: findings are never added / removed / re-typed; counts are never recomputed or
    "fixed"; LLM text and evidence are copied verbatim or withheld — never edited, summarised or renumbered.
  * LLM text reaches the user ViewModel only when display_mode == EXPLANATION (ui_policy.decide_display_mode).
  * The raw LLM response is never requested (include_records is never passed) and withheld LLM text is
    excluded from the debug block unless explicitly requested.
"""
from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import ui_policy as P
from .view_models import (CountTile, DebugInfo, DrugView, ElderlyStatusView, ErrorView, EvidenceSectionView,
                          EvidenceView, ExplanationView, FindingView, InputIssue, InputValidationResult,
                          MedicationView, MetadataView, NoFindingView, Notice, PatientView,
                          SafetyCheckViewModel, StatementView, SummaryView)


def _core():
    """Import the Frozen Core lazily (read-only use)."""
    from dur_safety import drug_lookup, findings, pipeline, resources
    return drug_lookup, findings, pipeline, resources


def _utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# =====================================================================================================
# Input Adapter
# =====================================================================================================
class MedicationSelection:
    """Ledger of what the user selected, restricted to candidates the UI actually offered.

    * `register_search()` records the candidates returned by drug_lookup.search_drugs (what was offered).
    * `add()` appends exactly what the user clicked. Duplicates are KEPT so validation can report them —
      the adapter never silently de-duplicates.
    * Same ingredient / different product (different item_seq) is NOT a duplicate.
    """

    def __init__(self):
        self._offered = {}      # item_seq -> candidate dict (copy)
        self._items = []        # item_seq strings in the order the user selected them

    def register_search(self, search_result):
        for c in (search_result or {}).get("candidates") or []:
            seq = c.get("item_seq") if isinstance(c, dict) else None
            if isinstance(seq, str):
                self._offered[seq] = dict(c)
        return self

    def add(self, item_seq):
        self._items.append(item_seq)
        return self

    def remove(self, index):
        del self._items[index]
        return self

    def clear(self):
        self._items.clear()
        return self

    @property
    def items(self):
        return tuple(self._items)

    def was_offered(self, item_seq):
        return isinstance(item_seq, str) and item_seq in self._offered

    def name_of(self, item_seq):
        c = self._offered.get(item_seq) if isinstance(item_seq, str) else None
        return c.get("item_name") if c else None

    def duplicates(self):
        # Exact item_seq string identity only. Non-string entries are keyed by (type, repr) so that e.g. the
        # int 100000001 is never confused with the string "100000001" (it is reported as INVALID_MEDICATION).
        seen, dup = set(), []
        for s in self._items:
            key = s if isinstance(s, str) else (type(s).__name__, repr(s))
            if key in seen and key not in dup:
                dup.append(key)
            seen.add(key)
        return [k if isinstance(k, str) else k[1] for k in dup]


def _validate_age(patient):
    """Returns (age, issues). Accepts only int (not bool) in [0, 150], or None with age_unknown=True."""
    patient = patient or {}
    age = patient.get("age")
    unknown = patient.get("age_unknown", False) is True
    if age is None:
        if unknown:
            return None, []
        return None, [InputIssue(P.INVALID_AGE, P.INPUT_MESSAGES["AGE_REQUIRED"], "age")]
    if unknown:
        return None, [InputIssue(P.INVALID_AGE, P.INPUT_MESSAGES["AGE_CONFLICT"], "age")]
    if isinstance(age, bool) or type(age) is not int:
        # bool, str ("72"), float (72.0 / nan), numpy types … are rejected; the adapter never coerces.
        return None, [InputIssue(P.INVALID_AGE, P.INPUT_MESSAGES["AGE_TYPE"], "age", detail=type(age).__name__)]
    if not (P.AGE_MIN <= age <= P.AGE_MAX):
        return None, [InputIssue(P.INVALID_AGE, P.INPUT_MESSAGES["AGE_RANGE"], "age")]
    return age, []


def validate_input(patient, selection, *, lookup=None):
    """Input Adapter. Never calls run_safety_check.

    patient   : {"age": int | None, "age_unknown": bool}
    selection : MedicationSelection
    lookup    : drug_lookup module (injectable for tests); default = dur_safety.drug_lookup
    """
    issues, dev = [], []
    age, age_issues = _validate_age(patient)
    issues += age_issues

    if not isinstance(selection, MedicationSelection):
        issues.append(InputIssue(P.INVALID_MEDICATION, P.INPUT_MESSAGES[P.INVALID_MEDICATION], "medications",
                                 detail="selection must be a MedicationSelection"))
        items = ()
    else:
        items = selection.items

    if isinstance(selection, MedicationSelection):
        n = len(items)
        if n < P.MIN_MEDICATIONS:
            issues.append(InputIssue(P.EMPTY_MEDICATIONS, P.INPUT_MESSAGES[P.EMPTY_MEDICATIONS], "medications"))
        if n > P.MAX_MEDICATIONS:
            issues.append(InputIssue(P.TOO_MANY_MEDICATIONS, P.INPUT_MESSAGES[P.TOO_MANY_MEDICATIONS],
                                     "medications", detail={"selected": n, "max": P.MAX_MEDICATIONS}))
        dups = selection.duplicates()
        if dups:
            issues.append(InputIssue(P.DUPLICATE_SELECTION, P.INPUT_MESSAGES[P.DUPLICATE_SELECTION],
                                     "medications", detail=dups))
        not_offered = [i for i, s in enumerate(items) if not selection.was_offered(s)]
        if not_offered:
            issues.append(InputIssue(P.INVALID_MEDICATION, P.INPUT_MESSAGES[P.INVALID_MEDICATION],
                                     "medications", detail={"positions": not_offered}))

        # Core-side confirmation (drug_lookup.confirm_selection) — only for well-formed, offered strings.
        if items and not not_offered:
            confirmed, lk_issue, lk_dev = _confirm_with_lookup(list(items), lookup)
            dev += lk_dev
            if lk_issue:
                issues.append(lk_issue)
            elif confirmed != list(items):
                # confirm_selection returns values unchanged; anything else is a contract violation.
                issues.append(InputIssue(P.LOOKUP_VALIDATION_FAILED, P.INPUT_MESSAGES[P.LOOKUP_VALIDATION_FAILED],
                                         "medications"))
                dev.append("confirm_selection returned a different list than submitted")

    status = P.VALID
    codes = {i.code for i in issues}
    for code in P.INPUT_STATUS_PRIORITY:
        if code in codes:
            status = code
            break
    ok = status == P.VALID
    meds = tuple(items) if ok else ()
    names = tuple((s, selection.name_of(s)) for s in meds) if ok else ()
    return InputValidationResult(status=status, issues=tuple(issues), age=age if ok else None,
                                 medications=meds, medication_names=names, dev_log=tuple(dev))


def _confirm_with_lookup(items, lookup):
    """Wrap drug_lookup.confirm_selection. Returns (confirmed, issue|None, dev_log list)."""
    try:
        if lookup is None:
            drug_lookup, _, _, resources = _core()
            if not resources.is_loaded():
                # confirm_selection needs screening.DRUG_NAME_BY_ITEM, which exists only after load_resources;
                # calling it earlier raises AttributeError (contract gap, reported). Check first.
                return None, InputIssue(P.LOOKUP_VALIDATION_FAILED, P.INPUT_MESSAGES[P.LOOKUP_VALIDATION_FAILED],
                                        "medications", detail="RESOURCES_NOT_LOADED"), ["resources not loaded"]
            lookup = drug_lookup
        return list(lookup.confirm_selection(items)), None, []
    except ValueError as e:      # unknown / non-9-digit item_seq
        return None, InputIssue(P.INVALID_MEDICATION, P.INPUT_MESSAGES[P.INVALID_MEDICATION], "medications"), \
            [f"ValueError: {str(e)[:300]}"]
    except TypeError as e:
        return None, InputIssue(P.INVALID_MEDICATION, P.INPUT_MESSAGES[P.INVALID_MEDICATION], "medications"), \
            [f"TypeError: {str(e)[:300]}"]
    except Exception as e:  # noqa: BLE001 — AttributeError before load, RuntimeError, …
        return None, InputIssue(P.LOOKUP_VALIDATION_FAILED, P.INPUT_MESSAGES[P.LOOKUP_VALIDATION_FAILED],
                                "medications"), [f"{type(e).__name__}: {str(e)[:300]}"]


# =====================================================================================================
# Execution
# =====================================================================================================
@dataclass(frozen=True)
class ExecutionResult:
    called: bool
    report: Optional[dict]
    error_code: Optional[str]           # None | RESOURCES_NOT_LOADED | CORE_EXCEPTION
    error_dev_log: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    elapsed_s: Optional[float]


def execute(input_result, core_fn: Optional[Callable] = None, *, resources_module=None):
    """Call the Core exactly once with (age, medications) if and only if the input is VALID.

    core_fn defaults to dur_safety.pipeline.run_safety_check (production defaults: real retrieval,
    real call_llm, include_records=False). Tests inject a partial with mock llm_fn / retrieval_fn.
    """
    if not isinstance(input_result, InputValidationResult) or not input_result.is_valid:
        return ExecutionResult(False, None, None, None, None, None, None)
    if core_fn is None or resources_module is None:
        _, _, pipeline, resources = _core()
        core_fn = core_fn or pipeline.run_safety_check
        resources_module = resources_module or resources
    if not resources_module.is_loaded():
        return ExecutionResult(False, None, "RESOURCES_NOT_LOADED", "resources.is_loaded() is False",
                               None, None, None)
    started = _utcnow()
    t0 = time.perf_counter()
    try:
        report = core_fn(input_result.age, list(input_result.medications))
    except Exception as e:  # noqa: BLE001 — the whole report is unavailable
        el = round(time.perf_counter() - t0, 3)
        msg = f"{type(e).__name__}: {str(e)[:300]}"
        code = "RESOURCES_NOT_LOADED" if isinstance(e, RuntimeError) and "load_resources" in str(e) \
            else "CORE_EXCEPTION"
        return ExecutionResult(True, None, code, msg, started, _utcnow(), el)
    el = round(time.perf_counter() - t0, 3)
    return ExecutionResult(True, report, None, None, started, _utcnow(), el)


# =====================================================================================================
# Output Adapter — report validation
# =====================================================================================================
TOP_KEYS = ("pipeline", "screening", "findings", "summary", "warnings", "errors")
_INT = lambda v: isinstance(v, int) and not isinstance(v, bool)   # noqa: E731


def validate_report(R):
    """Structural check against the contract. Returns (structure_problems, invariant_problems).

    Only shape and internal count consistency are checked; no value is corrected or recomputed for display.
    """
    s_err, i_err = [], []
    if not isinstance(R, dict):
        return ["REPORT_NOT_A_DICT"], []
    for k in TOP_KEYS:
        if k not in R:
            s_err.append(f"MISSING:{k}")
    if s_err:
        return s_err, []
    S, sm, F = R["screening"], R["summary"], R["findings"]
    if not isinstance(S, dict) or not isinstance(sm, dict) or not isinstance(F, list):
        return ["TYPE:screening/summary/findings"], []
    if not isinstance(R["warnings"], list) or not isinstance(R["errors"], list):
        s_err.append("TYPE:warnings/errors")
    ss, pt = S.get("summary"), S.get("patient")
    if not isinstance(ss, dict) or not isinstance(pt, dict):
        return s_err + ["MISSING:screening.summary/patient"], []
    for k in ("total_signals", "contraindication_count", "elderly_caution_count", "therapeutic_duplication_count"):
        if not _INT(ss.get(k)):
            s_err.append(f"TYPE:screening.summary.{k}")
    if ss.get("elderly_check_status") not in P.ELDERLY_STATUS_VIEW:
        s_err.append("ENUM:screening.summary.elderly_check_status")
    if not _INT(sm.get("n_findings")):
        s_err.append("TYPE:summary.n_findings")
    for k in ("medications", "not_found_in_dur_tables", "duplicate_inputs", "invalid_inputs"):
        if not isinstance(pt.get(k), list):
            s_err.append(f"TYPE:screening.patient.{k}")
    if not isinstance(S.get("scope_note"), str):
        s_err.append("TYPE:screening.scope_note")
    for n, f in enumerate(F):
        if not isinstance(f, dict):
            s_err.append(f"FINDING[{n}]:NOT_A_DICT")
            continue
        if not isinstance(f.get("finding_id"), str):
            s_err.append(f"FINDING[{n}]:finding_id")
        if f.get("risk_type") not in P.RISK_ORDER:
            s_err.append(f"FINDING[{n}]:UNKNOWN_RISK_TYPE:{f.get('risk_type')!r}")
        if not isinstance(f.get("generation"), dict):
            s_err.append(f"FINDING[{n}]:generation")
        for k in ("drugs", "dur_rule_texts", "evidence"):
            if not isinstance(f.get(k), list):
                s_err.append(f"FINDING[{n}]:{k}")
        for j, d in enumerate(f.get("drugs") or []):
            if not isinstance(d, dict) or not isinstance(d.get("item_seq"), str):
                s_err.append(f"FINDING[{n}].drugs[{j}]")
        for j, e in enumerate(f.get("evidence") or [] if isinstance(f.get("evidence"), list) else []):
            if not (isinstance(e, dict) and isinstance(e.get("evidence_id"), str)
                    and isinstance(e.get("chunk_text"), str)):
                s_err.append(f"FINDING[{n}].evidence[{j}]")
    if s_err:
        return s_err, []

    # ---- invariants (REPORT_INCONSISTENT) -----------------------------------------------------------
    if not (ss["total_signals"] == sm["n_findings"] == len(F)):
        i_err.append(f"COUNT_INVARIANT:total_signals={ss['total_signals']},n_findings={sm['n_findings']},"
                     f"len(findings)={len(F)}")
    for rt in P.RISK_ORDER:
        n_rt = sum(1 for f in F if f["risk_type"] == rt)
        if ss[P.SCREENING_COUNT_KEYS[rt]] != n_rt:
            i_err.append(f"RISK_COUNT:{rt}:screening={ss[P.SCREENING_COUNT_KEYS[rt]]},findings={n_rt}")
    if ss["total_signals"] != sum(ss[P.SCREENING_COUNT_KEYS[rt]] for rt in P.RISK_ORDER):
        i_err.append("TOTAL_NOT_SUM_OF_TYPES")
    ids = [f["finding_id"] for f in F]
    if len(ids) != len(set(ids)):
        i_err.append("DUPLICATE_FINDING_ID")
    if sm.get("elderly_check_status") != ss["elderly_check_status"]:
        i_err.append("ELDERLY_STATUS_MISMATCH")
    return [], i_err


# =====================================================================================================
# Output Adapter — ViewModel construction
# =====================================================================================================
def _dur_lines(texts):
    lines = []
    for t in texts or []:
        if isinstance(t, str):
            lines += [ln for ln in t.splitlines() if ln.strip()]
    return tuple(lines)


def _location(e):
    loc = " / ".join(x for x in [e.get("doc_type"), e.get("section_title"), e.get("article_title")] if x)
    return loc or P.LOCATION_EMPTY_TEXT


def _license_badge(e):
    if e.get("is_active") is False or e.get("CANCEL_NAME"):
        name = e.get("CANCEL_NAME")
        return P.LICENSE_BADGE_TEMPLATE.format(cancel_name=name) if name else P.LICENSE_BADGE_NO_NAME
    return None


def _evidence_view(e, cited_ids, explanation_mode):
    shared = e.get("shared_item_seqs") or []
    shared = tuple(shared) if isinstance(shared, (list, tuple)) and len(shared) >= 2 else ()
    name = e.get("ITEM_NAME")
    seq = e.get("ITEM_SEQ")
    return EvidenceView(
        evidence_id=e["evidence_id"], item_seq=seq, item_name=name, display_name=name or str(seq),
        location=_location(e), chunk_text=e["chunk_text"], evidence_source=e.get("evidence_source"),
        cited=bool(explanation_mode and e["evidence_id"] in cited_ids), license_badge=_license_badge(e),
        change_date=e.get("CHANGE_DATE"), shared_item_seqs=shared)


def _explanation_view(o, g):
    stmts = tuple(StatementView(s["statement"], tuple(s["evidence_ids"])) for s in o["evidence_statements"])
    lim = o["limitations"] if o["limitations"].strip() else None
    return ExplanationView(
        summary=o["summary"], statements=stmts, no_statements_text=None if stmts else P.NO_STATEMENTS_TEXT,
        evidence_status=g["evidence_status"], evidence_status_label=P.EVIDENCE_STATUS_LABEL[g["evidence_status"]],
        evidence_status_tooltip=P.EVIDENCE_STATUS_TOOLTIP, limitations=lim, review_note=o["review_note"])


def _finding_view(f, rule_source_table, include_withheld_text):
    """Returns (FindingView, debug_dict, error_or_None)."""
    rt = f["risk_type"]
    g = f["generation"]
    status = g.get("status")
    is_pipeline_error = status == "PIPELINE_ERROR"
    evidence = f.get("evidence") or []
    ev_ids = [e["evidence_id"] for e in evidence]
    mode, reasons = P.decide_display_mode(g, ev_ids, finding_id=f["finding_id"], risk_type=rt)

    rule_source = f.get("rule_source")
    if rule_source is None and is_pipeline_error:
        rule_source = rule_source_table.get(rt)               # contract §4 fallback
    pair_id = f.get("canonical_pair_id")
    effect = f.get("effect_name")
    if is_pipeline_error and ":" in f["finding_id"]:           # contract §4 fallbacks (from finding_id)
        tail = f["finding_id"].split(":", 1)[1]
        if rt == "contraindication" and pair_id is None:
            pair_id = tail
        if rt == "therapeutic_duplication" and effect is None and ":" in tail:
            effect = tail.rsplit(":", 1)[0]

    drugs = tuple(DrugView(d["item_seq"], d.get("item_name"), d.get("item_name") or d["item_seq"],
                           tuple(d.get("ingredient_names") or ())) for d in f.get("drugs") or [])
    r_warn = ((f.get("retrieval") or {}).get("warnings") or [])
    r_notices = tuple(P.RETRIEVAL_NOTICE_MESSAGES[w] for w in P.RETRIEVAL_NOTICE_MESSAGES if w in r_warn)

    explanation = _explanation_view(g["output"], g) if mode == P.EXPLANATION else None
    ev_section = None
    if mode in P.EVIDENCE_VISIBLE_MODES and evidence:
        cited = set(g.get("cited_evidence_ids") or [])
        ev_section = EvidenceSectionView(
            title=P.EVIDENCE_TITLE_EXPLANATION if mode == P.EXPLANATION else P.EVIDENCE_TITLE_RAW,
            items=tuple(_evidence_view(e, cited, mode == P.EXPLANATION) for e in evidence))
    msg, sev = P.MODE_MESSAGES.get(mode, (None, None))

    view = FindingView(
        finding_id=f["finding_id"], risk_type=rt, risk_label=P.RISK_LABEL_KO[rt], risk_icon=P.RISK_BADGE_ICON[rt],
        rule_source=rule_source, drugs=drugs, canonical_pair_id=pair_id, effect_name=effect,
        dur_rule_label=P.DUR_RULE_LABEL, dur_rule_lines=_dur_lines(f.get("dur_rule_texts")) or (P.DUR_RULE_EMPTY_TEXT,),
        retrieval_notices=r_notices, display_mode=mode, status_message=msg, status_severity=sev,
        explanation_title=P.EXPLANATION_SECTION_TITLE, explanation=explanation, evidence=ev_section,
        clinician_review_text=P.CLINICIAN_REVIEW_TEXT)

    r = f.get("retrieval") or {}
    dbg = {
        "finding_id": f["finding_id"], "display_mode": mode, "display_mode_reasons": list(reasons),
        "generation_status": status, "llm_called": g.get("llm_called"),
        "schema_errors": list(g.get("schema_errors") or []), "citation_errors": list(g.get("citation_errors") or []),
        "citation_warnings": list(g.get("citation_warnings") or []),
        "directive_flags": list(g.get("directive_flags") or []), "llm_error": g.get("llm_error"),
        "stop_reason": g.get("stop_reason"), "user_prompt_sha256": g.get("user_prompt_sha256"),
        "pipeline_error": g.get("error") if is_pipeline_error else None,
        "retrieval": {k: copy.deepcopy(r.get(k)) for k in ("status", "reason", "warnings", "method", "query",
                                                             "n_retrieved", "candidate_info")} if r else None,
        "evidence_errors": copy.deepcopy(f.get("evidence_errors") or []),
        "dropped_evidence": copy.deepcopy(f.get("dropped_evidence") or []),
        "evidence_dev_fields": [{k: e.get(k) for k in ("evidence_id", "chunk_id", "document_id", "hybrid_rank",
                                                       "bm25_rank", "dense_rank", "text_hash", "prov_source",
                                                       "prov_endpoint", "detail_prov_retrieved_at")}
                                for e in evidence],
        "canonical_pair_id": pair_id,
    }
    if include_withheld_text and mode != P.EXPLANATION and g.get("output") is not None:
        dbg["withheld_llm_output"] = copy.deepcopy(g.get("output"))      # developer opt-in only

    err = None
    if mode in (P.EVIDENCE_INVALID, P.LLM_UNAVAILABLE, P.GENERATION_FAILED, P.PROCESSING_ERROR):
        dev = g.get("error") if is_pipeline_error else (g.get("llm_error") or status)
        err = ErrorView(code="FINDING_" + mode, layer=P.L4_FINDING, user_message=msg, abort=False,
                        partial_result=True, finding_id=f["finding_id"], dev_log=str(dev) if dev else None)
    return view, dbg, err


def _elderly_view(code):
    v = P.ELDERLY_STATUS_VIEW[code]
    return ElderlyStatusView(code=code, label=v["label"], message=v["message"], show_count=v["show_count"])


def _metadata(R, execution, runtime_info):
    core = {}
    if isinstance(R, dict) and isinstance(R.get("pipeline"), dict):
        pl = R["pipeline"]
        core = {"pipeline_name": pl.get("name"), "pipeline_version": pl.get("version"),
                "screening_engine": pl.get("screening_engine"),
                "retrieval_config": copy.deepcopy(pl.get("retrieval")),
                "generation": copy.deepcopy(pl.get("generation"))}
        eng = (R.get("screening") or {}).get("engine") if isinstance(R.get("screening"), dict) else None
        if isinstance(eng, dict):
            core["data_snapshot"] = copy.deepcopy(eng.get("data_snapshot"))
    ri = dict(runtime_info or {})
    device = ri.get("device")
    adapter = {
        "adapter_name": P.ADAPTER_NAME, "adapter_version": P.ADAPTER_VERSION, "contract": P.CONTRACT_VERSION,
        "core_called": bool(execution and execution.called),
        "started_at": execution.started_at if execution else None,
        "finished_at": execution.finished_at if execution else None,
        "elapsed_s": execution.elapsed_s if execution else None,     # adapter wall-clock around the Core call
        "device": device,
        "device_note": P.DEVICE_MISMATCH_TEXT if isinstance(device, str) and device.lower().startswith("cpu") else None,
        "deployment": copy.deepcopy(ri.get("deployment")),
        "medication_limit_note": P.MEDICATION_LIMIT_NOTE,
    }
    return MetadataView(core=core, adapter=adapter)


def _empty_vm(state, errors, input_result, execution, runtime_info, R=None, debug=None):
    return SafetyCheckViewModel(
        state=state, can_display_results=False, patient=None, medications=(), summary=None, findings=(),
        no_finding=None, notices=(), errors=tuple(errors),
        input_issues=tuple(input_result.issues) if isinstance(input_result, InputValidationResult) else (),
        scope_note=None, input_scope_note=P.INPUT_SCOPE_NOTE_UI,
        metadata=_metadata(R, execution, runtime_info), debug=debug or DebugInfo())


def build_view_model(report=None, *, input_result=None, execution=None, runtime_info=None,
                     include_withheld_text_in_debug=False, rule_source_table=None):
    """Output Adapter. Pure function of its inputs; `report` is deep-copied and never mutated.

    Order of precedence: input invalid (L0) → resource (L1) → Core exception (L2) → report structure /
    invariant (L3) → per-finding (L4, partial result).
    """
    # ---- L0 ---------------------------------------------------------------------------------------
    if isinstance(input_result, InputValidationResult) and not input_result.is_valid:
        err = ErrorView("INPUT_INVALID", P.L0_INPUT, P.ERROR_MESSAGES["INPUT_INVALID"], abort=True,
                        partial_result=False, dev_log="; ".join(input_result.dev_log) or input_result.status)
        return _empty_vm(P.STATE_INPUT_INVALID, [err], input_result, execution, runtime_info)
    # ---- L1 / L2 ----------------------------------------------------------------------------------
    if execution is not None and execution.error_code:
        if execution.error_code == "RESOURCES_NOT_LOADED":
            err = ErrorView("RESOURCES_NOT_LOADED", P.L1_RESOURCE, P.ERROR_MESSAGES["RESOURCES_NOT_LOADED"],
                            abort=True, partial_result=False, dev_log=execution.error_dev_log)
            return _empty_vm(P.STATE_RESOURCE_ERROR, [err], input_result, execution, runtime_info)
        err = ErrorView("CORE_EXCEPTION", P.L2_CORE, P.ERROR_MESSAGES["CORE_EXCEPTION"], abort=True,
                        partial_result=False, dev_log=execution.error_dev_log)
        return _empty_vm(P.STATE_CORE_ERROR, [err], input_result, execution, runtime_info)
    if report is None and execution is not None:
        report = execution.report
    # ---- L3 ---------------------------------------------------------------------------------------
    R = copy.deepcopy(report)
    s_err, i_err = validate_report(R)
    if s_err:
        err = ErrorView("REPORT_INVALID", P.L3_REPORT, P.ERROR_MESSAGES["REPORT_INVALID"], abort=True,
                        partial_result=False, dev_log="; ".join(s_err)[:2000])
        return _empty_vm(P.STATE_REPORT_INVALID, [err], input_result, execution, runtime_info,
                         R if isinstance(R, dict) else None, DebugInfo(validation_failures=tuple(s_err)))
    if i_err:
        err = ErrorView("REPORT_INCONSISTENT", P.L3_REPORT, P.ERROR_MESSAGES["REPORT_INCONSISTENT"], abort=True,
                        partial_result=False, dev_log="; ".join(i_err)[:2000])
        return _empty_vm(P.STATE_REPORT_INCONSISTENT, [err], input_result, execution, runtime_info, R,
                         DebugInfo(validation_failures=tuple(i_err)))

    # ---- COMPLETED --------------------------------------------------------------------------------
    if rule_source_table is None:
        rule_source_table = dict(_core()[1].RULE_SOURCE)
    S, sm = R["screening"], R["summary"]
    ss, pt = S["summary"], S["patient"]
    elderly = _elderly_view(ss["elderly_check_status"])

    names = dict(input_result.medication_names) if isinstance(input_result, InputValidationResult) else {}
    not_found = set(pt["not_found_in_dur_tables"])
    meds = tuple(MedicationView(s, names.get(s), names.get(s) or s, s not in not_found) for s in pt["medications"])
    age = pt.get("age")
    patient = PatientView(age=age, age_display=P.AGE_MISSING_TEXT if age is None else str(age), elderly=elderly)

    tiles = []
    for rt in P.RISK_ORDER:
        cnt = ss[P.SCREENING_COUNT_KEYS[rt]]
        if rt == "elderly_caution" and not elderly.show_count:
            tiles.append(CountTile(rt, P.RISK_LABEL_KO[rt], P.RISK_BADGE_ICON[rt], None, elderly.label))
        else:
            tiles.append(CountTile(rt, P.RISK_LABEL_KO[rt], P.RISK_BADGE_ICON[rt], cnt, f"{cnt}건"))

    order = {rt: i for i, rt in enumerate(P.RISK_ORDER)}
    ordered = sorted(R["findings"], key=lambda f: order[f["risk_type"]])          # stable within a type
    fviews, fdbg, errors = [], [], []
    for f in ordered:
        v, d, e = _finding_view(f, rule_source_table, include_withheld_text_in_debug)
        fviews.append(v)
        fdbg.append(d)
        if e:
            errors.append(e)

    banner = P.LLM_UNAVAILABLE_BANNER if fviews and all(v.display_mode == P.LLM_UNAVAILABLE for v in fviews) else None
    summary = SummaryView(total_signals=ss["total_signals"], tiles=tuple(tiles), legend=P.BADGE_LEGEND,
                          llm_unavailable_banner=banner)
    no_finding = NoFindingView(P.NO_FINDING_TEXT, S["scope_note"]) if ss["total_signals"] == 0 else None

    notices = []
    if pt["duplicate_inputs"]:
        lvl, msg = P.NOTICE_MESSAGES["DUPLICATE_INPUTS"]
        notices.append(Notice("DUPLICATE_INPUTS", lvl, msg, tuple(pt["duplicate_inputs"])))
    if pt["not_found_in_dur_tables"]:
        lvl, msg = P.NOTICE_MESSAGES["NOT_FOUND_IN_DUR_TABLES"]
        notices.append(Notice("NOT_FOUND_IN_DUR_TABLES", lvl, msg, tuple(pt["not_found_in_dur_tables"])))
    if ss["elderly_check_status"] == "not_evaluated_age_missing":
        lvl, msg = P.NOTICE_MESSAGES["ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING"]
        notices.append(Notice("ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING", lvl, msg))

    debug = DebugInfo(report_warnings=tuple(copy.deepcopy(R["warnings"])), report_errors=tuple(copy.deepcopy(R["errors"])),
                      invalid_inputs=tuple(pt["invalid_inputs"]), findings=tuple(fdbg),
                      error_logs=tuple({"code": e.code, "finding_id": e.finding_id, "dev_log": e.dev_log} for e in errors),
                      generation_status_counts=copy.deepcopy(sm.get("generation_status_counts") or {}),
                      llm_calls=sm.get("llm_calls"))
    return SafetyCheckViewModel(
        state=P.STATE_COMPLETED, can_display_results=True, patient=patient, medications=meds, summary=summary,
        findings=tuple(fviews), no_finding=no_finding, notices=tuple(notices), errors=tuple(errors),
        input_issues=(), scope_note=S["scope_note"], input_scope_note=P.INPUT_SCOPE_NOTE_UI,
        metadata=_metadata(R, execution, runtime_info), debug=debug)


# =====================================================================================================
# Convenience
# =====================================================================================================
def run_safety_check_view(patient, selection, *, core_fn=None, lookup=None, resources_module=None,
                          runtime_info=None, include_withheld_text_in_debug=False):
    """validate_input → execute → build_view_model. Core is called only for VALID input."""
    inp = validate_input(patient, selection, lookup=lookup)
    exe = execute(inp, core_fn, resources_module=resources_module) if inp.is_valid else None
    return build_view_model(input_result=inp, execution=exe, runtime_info=runtime_info,
                            include_withheld_text_in_debug=include_withheld_text_in_debug)


def runtime_info_from_load_report(load_report, deployment=None):
    """Pick the execution device from resources.load_resources()'s return value (not part of the report)."""
    dense = (load_report or {}).get("dense_state") if isinstance(load_report, dict) else None
    return {"device": (dense or {}).get("device"), "deployment": deployment}


def read_deployment_info(path):
    """Read a few identifying fields from production_baseline.json. Returns None if unreadable."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    pkg = d.get("package") or {}
    return {"baseline_version": d.get("baseline_version"), "freeze_timestamp": d.get("freeze_timestamp"),
            "status": d.get("status"), "package_version": pkg.get("package_version"),
            "pipeline_version": pkg.get("pipeline_version")}

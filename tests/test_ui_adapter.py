"""UI Adapter / ViewModel tests — see docs/UI_ADAPTER_DESIGN.md.

How the Core is exercised
  * The REAL Frozen Core functions run (pipeline.run_safety_check → screen_patient → findings →
    generate_explanation → prepare_evidence_context → validate_output), so every report has the real schema.
  * Project data is NOT loaded and no model is loaded. Instead the module-level lookup tables that
    resources.load_resources() would normally set are replaced, for the duration of one test, by a tiny
    SYNTHETIC table (pytest monkeypatch; restored afterwards). All identifiers/names below are fake test
    data ("테스트약…", 1000000xx) and carry no medical meaning.
  * retrieval_fn and llm_fn are mocks injected through core_fn = partial(run_safety_check, ...).
    No OpenAI call, no network, no file written. No Frozen Core file is modified (checked by sha256).

Failure classification used in the report: ADAPTER (app/ bug) | FIXTURE (this file's synthetic data/mocks)
| CONTRACT (Core behaves differently from the docs) | ENVIRONMENT (python/pandas/path).
"""
from __future__ import annotations

import copy
import dataclasses
import functools
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dur_safety import drug_lookup, findings, generation, pipeline, resources, retrieval, screening  # noqa: E402

from app import adapters, ui_policy as P  # noqa: E402

# ------------------------------------------------------------------------------------- synthetic data
A, B, C, D, E, F, G = (f"10000000{i}" for i in range(1, 8))
EXTRA = [f"1000001{i:02d}" for i in range(30)]            # 30 more fake products (limit tests)
NAMES = {A: "테스트약A정", B: "테스트약B정", C: "테스트약C정", D: "테스트약D정", E: "테스트약E정",
         F: "테스트약A서방정", G: "테스트약G정"}
NAMES.update({s: f"테스트추가약{i:02d}정" for i, s in enumerate(EXTRA)})
PAIR = f"{A}|{B}"
EFFECT = "테스트효능군"
DUR_ITEMS = {A, B, C, D, E, F}                               # G and EXTRA are not in any DUR table
FID_CONTRA = f"contraindication:{PAIR}"
FID_ELDERLY = f"elderly_caution:{C}"
FID_THERA = f"therapeutic_duplication:{EFFECT}:{D}|{E}"
ALL_FIDS = {FID_CONTRA, FID_ELDERLY, FID_THERA}


def _chunk(seq, k=1):
    text = f"[테스트 허가정보 원문] 품목 {seq} 문단 {k}. 이 문장은 합성 테스트 데이터입니다."
    return {"chunk_id": f"chunk-{seq}-{k}", "document_id": f"doc-{seq}", "ITEM_SEQ": seq,
            "text_hash": hashlib.sha1(text.encode("utf-8")).hexdigest(), "chunk_text": text}


CHUNKS = {seq: [_chunk(seq, 1), _chunk(seq, 2)] for seq in NAMES}


@pytest.fixture
def core(monkeypatch):
    """Install the synthetic lookup tables into the Frozen Core modules (restored after the test)."""
    sp = lambda name, value: monkeypatch.setattr(screening, name, value, raising=False)  # noqa: E731
    sp("CONTRAINDICATION_PAIR_IDS", {PAIR})
    sp("EVIDENCE_PAIR_IDS", {PAIR})
    sp("evidence_indexed", pd.DataFrame({"_evidence_id": ["ev-1"], "_dur_seq": ["dur-1"],
                                         "_text": ["[테스트 DUR 병용금기 문구]"]}, index=pd.Index([PAIR])))
    sp("ELDERLY_RULES_BY_ITEM", {C: [
        {"prohbt_content": "[테스트 노인주의 문구 1]", "item_name": NAMES[C], "ingr_code": "T-C",
         "ingredient_name_kor": "테스트성분C"},
        {"prohbt_content": "[테스트 노인주의 문구 2]", "item_name": NAMES[C], "ingr_code": "T-C",
         "ingredient_name_kor": "테스트성분C"}]})
    sp("THERAPEUTIC_EFFECTS_BY_ITEM", {D: {EFFECT}, E: {EFFECT}})
    sp("THERAPEUTIC_DETAIL", {(s, EFFECT): {"item_name": NAMES[s], "ingr_codes": [f"T-{s}"],
                                            "ingredient_names": [f"테스트성분{s[-1]}"], "sers_names": ["테스트계열"],
                                            "dur_seqs": ["dur-t"], "source_record_count": 1,
                                            "prohbt_contents": ["[테스트 효능군중복 문구]"]} for s in (D, E)})
    sp("DRUG_NAME_BY_ITEM", dict(NAMES))
    sp("KNOWN_DUR_ITEMS", set(DUR_ITEMS))
    sp("DATA_SNAPSHOT", {"synthetic_test_data": True})
    monkeypatch.setattr(findings, "cevi_lu", pd.DataFrame({
        "canonical_pair_id": [PAIR], "item_seq": [A], "mixture_item_seq": [B],
        "ingredient_name_kor": ["테스트성분A"], "mixture_ingredient_name_kor": ["테스트성분B"]}))
    rows = [c for cs in CHUNKS.values() for c in cs]
    monkeypatch.setattr(generation, "CHUNK_META",
                        pd.DataFrame(rows).set_index("chunk_id")[["document_id", "ITEM_SEQ", "text_hash"]])
    monkeypatch.setattr(retrieval, "ITEM_INDEX", {s: np.asarray([0]) for s in NAMES if s != G}, raising=False)
    monkeypatch.setitem(resources._STATE, "loaded", True)
    return True


# ------------------------------------------------------------------------------------- mocks
def make_retrieval(mode="ok", warnings=(), fail_for=None, n_chunks=2):
    """mode: ok | empty | tampered | boom. fail_for: finding_id prefix that raises (others ok)."""
    def fn(finding):
        if mode == "boom" or (fail_for and finding.finding_id.startswith(fail_for)):
            raise RuntimeError("ui-adapter-test retrieval failure")
        if mode == "empty":
            df = pd.DataFrame(columns=retrieval.RESULT_COLS)
            return generation.to_retrieval_result("q", [], df, {"status": "NO_EVIDENCE", "reason": "NO_CANDIDATES"})
        recs, rank = [], 0
        for seq in finding.target_item_seqs:
            for c in CHUNKS[seq][:n_chunks]:
                rank += 1
                r = {k: None for k in retrieval.RESULT_COLS}
                r.update(c, rank=rank, retrieval_method="hybrid", risk_type=finding.risk_type,
                         ITEM_NAME=NAMES[seq], doc_type="허가정보", section_title="사용상의 주의사항",
                         article_title=f"조항 {rank}", shared_item_seqs=[seq], is_active=True,
                         evidence_source="식약처 의약품 제품 허가정보 (approval_chunks)", hybrid_rank=float(rank))
                if mode == "tampered":
                    r["chunk_text"] = r["chunk_text"] + " (변조)"
                recs.append(r)
        df = pd.DataFrame(recs, columns=retrieval.RESULT_COLS)
        return generation.to_retrieval_result("q", [], df, {"status": "OK", "warnings": list(warnings)})
    return fn


def llm_text(text, error=None):
    def llm(system, user):
        return generation.LLMResponse(text, "mock", "mock", stop_reason="completed", error=error)
    return llm


def llm_raises(system, user):
    raise ConnectionError("ui-adapter-test llm failure")


def _prompt_fields(user):
    fid = re.search(r'"finding_id": "([^"]+)"', user).group(1)
    rt = re.search(r'"risk_type": "([^"]+)"', user).group(1)
    ids = re.search(r"사용할 수 있는 근거 ID: ([^\n]*)", user).group(1).split(", ")
    return fid, rt, ids


def llm_valid(statement="[테스트 설명 문장] 허가정보에 관련 내용이 기재되어 있습니다.", status="PARTIAL",
              limitations="[테스트 한계]", no_statements=False):
    def llm(system, user):
        fid, rt, ids = _prompt_fields(user)
        obj = {"finding_id": fid, "risk_type": rt, "summary": f"[테스트 요약] {fid}",
               "evidence_statements": [] if no_statements else
               [{"statement": f"{statement} [{ids[0]}]", "evidence_ids": [ids[0]]}],
               "evidence_status": status, "limitations": limitations,
               "review_note": "[테스트 검토 문구] 최종 판단은 의료진 검토가 필요합니다."}
        return generation.LLMResponse(json.dumps(obj, ensure_ascii=False), "mock", "mock", stop_reason="completed")
    return llm


def llm_must_not_run(system, user):
    raise AssertionError("LLM must not be called")


def core_fn(llm=None, retr=None):
    return functools.partial(pipeline.run_safety_check, llm_fn=llm or llm_valid(), retrieval_fn=retr or make_retrieval())


def select(*seqs, offer=None):
    sel = adapters.MedicationSelection()
    offered = offer if offer is not None else [s for s in dict.fromkeys(seqs) if isinstance(s, str)]
    sel.register_search({"candidates": [{"item_seq": s, "item_name": NAMES.get(s), "in_dur_tables": s in DUR_ITEMS,
                                         "in_evidence_corpus": True, "match_type": "name_contains"} for s in offered]})
    for s in seqs:
        sel.add(s)
    return sel


def run_vm(meds=(A, B, C, D, E), age=72, llm=None, retr=None, **kw):
    return adapters.run_safety_check_view({"age": age, "age_unknown": age is None}, select(*meds),
                                          core_fn=core_fn(llm, retr), **kw)


def raw_report(meds=(A, B, C, D, E), age=72, llm=None, retr=None):
    return core_fn(llm, retr)(age, list(meds))


def user_json(vm):
    return json.dumps(vm.to_dict(), ensure_ascii=False)


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        raise AssertionError("Core must not be called")


# =====================================================================================================
# Static / boundary
# =====================================================================================================
def test_frozen_core_files_unchanged():
    lines = [ln.split() for ln in (ROOT / "src/dur_safety/FROZEN_SHA256SUMS.txt").read_text().splitlines() if ln.strip()]
    assert len(lines) == 9
    bad = [rel for sha, rel in lines if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != sha]
    assert not bad, f"Frozen Core changed: {bad}"


def test_adapter_source_boundaries():
    src = "\n".join((ROOT / "app" / n).read_text(encoding="utf-8") for n in
                    ("__init__.py", "adapters.py", "view_models.py", "ui_policy.py"))
    assert "import streamlit" not in src and "from streamlit" not in src
    assert "include_records=True" not in src
    assert not re.search(r"\b(screening|findings|generation|pipeline|retrieval|resources|drug_lookup)\.[A-Za-z_]+\s*=[^=]",
                         src), "adapter must not assign Core module attributes"


def test_policy_constants_match_core():
    assert P.ELDERLY_AGE_THRESHOLD_TEXT == screening.ELDERLY_AGE_THRESHOLD
    assert P.RISK_LABEL_KO == findings.RISK_LABEL_KO
    assert set(P.RISK_ORDER) == set(findings.SUPPORTED_RISK_TYPES)
    assert set(P.EVIDENCE_STATUS_LABEL) == set(generation.OUTPUT_JSON_SCHEMA["properties"]["evidence_status"]["enum"])
    assert P.OUTPUT_KEYS == set(generation.OUTPUT_JSON_SCHEMA["required"])
    assert (P.AGE_MIN, P.AGE_MAX, P.MIN_MEDICATIONS, P.MAX_MEDICATIONS) == (0, 150, 1, 20)
    assert "임상적으로 검증된 기준이 아닙니다" in P.MEDICATION_LIMIT_NOTE


def test_mode_messages_match_view_mapping_doc():
    doc = ROOT / "docs" / "STREAMLIT_VIEW_MAPPING.md"
    if not doc.exists():
        pytest.skip("docs/STREAMLIT_VIEW_MAPPING.md not present in this checkout")
    text = doc.read_text(encoding="utf-8")
    for mode, (msg, sev) in P.MODE_MESSAGES.items():
        assert f"| `{mode}` | {msg} | {sev} |" in text, mode
    for s in (P.NO_FINDING_TEXT, P.CLINICIAN_REVIEW_TEXT, P.BADGE_LEGEND, *P.EVIDENCE_STATUS_LABEL.values(),
              P.EVIDENCE_TITLE_EXPLANATION, P.EVIDENCE_TITLE_RAW, P.NO_STATEMENTS_TEXT):
        assert s in text, s


@pytest.mark.parametrize("status, mode", [
    ("INVALID_OUTPUT", "WITHHELD_INVALID"), ("NO_EVIDENCE", "NO_EVIDENCE"), ("EVIDENCE_INVALID", "EVIDENCE_INVALID"),
    ("LLM_UNAVAILABLE", "LLM_UNAVAILABLE"), ("LLM_ERROR", "GENERATION_FAILED"), ("EMPTY_RESPONSE", "GENERATION_FAILED"),
    ("MALFORMED_RESPONSE", "GENERATION_FAILED"), ("PIPELINE_ERROR", "PROCESSING_ERROR"),
    ("SOMETHING_NEW", "PROCESSING_ERROR"), (None, "PROCESSING_ERROR")])
def test_display_mode_table(status, mode):
    assert P.decide_display_mode({"status": status}, [])[0] == mode


def _gen_ok(**over):
    o = {"finding_id": "x:1", "risk_type": "elderly_caution", "summary": "s",
         "evidence_statements": [{"statement": "t [E1]", "evidence_ids": ["E1"]}], "evidence_status": "PARTIAL",
         "limitations": "", "review_note": "r"}
    g = {"status": "GENERATED", "output": o, "evidence_status": "PARTIAL", "cited_evidence_ids": ["E1"],
         "schema_errors": [], "citation_errors": [], "directive_flags": []}
    g.update(over)
    return g


@pytest.mark.parametrize("over, mode", [
    ({}, "EXPLANATION"),
    ({"directive_flags": ["절대"]}, "WITHHELD_DIRECTIVE"),
    ({"cited_evidence_ids": ["E9"]}, "WITHHELD_INVALID"),
    ({"evidence_status": "SUFFICIENT"}, "WITHHELD_INVALID"),
    ({"output": None}, "WITHHELD_INVALID"),
    ({"output": {"summary": "only"}}, "WITHHELD_INVALID"),
    ({"schema_errors": ["X"]}, "WITHHELD_INVALID"),
])
def test_allowlist_is_fail_closed(over, mode):
    assert P.decide_display_mode(_gen_ok(**over), ["E1"], "x:1", "elderly_caution")[0] == mode
    assert P.decide_display_mode(_gen_ok(), ["E1"], "x:2", "elderly_caution")[0] == "WITHHELD_INVALID"
    assert P.decide_display_mode("not a dict", ["E1"])[0] == "PROCESSING_ERROR"


def _gen_text(field, text):
    g = _gen_ok()
    if field == "statement":
        g["output"]["evidence_statements"] = [{"statement": f"{text} [E1]", "evidence_ids": ["E1"]}]
    else:
        g["output"][field] = text
    return g


@pytest.mark.parametrize("field, text, mode", [            # STEP 7-R representative cases
    ("summary", "의사와 상의하지 말고 약을 중단하세요.", "WITHHELD_DIRECTIVE"),
    ("review_note", "당분간 이 약은 복용하지 마십시오.", "WITHHELD_DIRECTIVE"),
    ("statement", "용량을 하루 1정으로 줄이시면 됩니다.", "WITHHELD_DIRECTIVE"),
    ("summary", "이 두 약물은 함께 복용해도 안전합니다.", "WITHHELD_INVALID"),
    ("summary", "Screening 결과와 달리 이 조합은 병용금기가 아닙니다.", "WITHHELD_INVALID"),
    ("review_note", "의사와 상의하지 않고 약을 중단하지 마세요.", "EXPLANATION"),
    ("review_note", "두 약물의 병용금기가 확인되므로 의료진의 검토가 필요합니다.", "EXPLANATION"),
    ("review_note", "임의로 복용을 중단하거나 용량을 바꾸지 말고 의사·약사와 상의하세요.", "EXPLANATION"),
    ("statement", "허가정보에는 증상이 나타나면 투여를 중지하고 적절한 처치를 한다고 기재되어 있습니다", "EXPLANATION"),
    ("limitations", "제공된 근거에서는 병용금기 사유가 직접 확인되지 않습니다.", "EXPLANATION"),
    ("limitations", "근거만으로는 두 약을 함께 사용해도 안전한지 판단할 수 없습니다.", "EXPLANATION"),
])
def test_llm_text_directive_reassurance_denial(field, text, mode):
    assert P.decide_display_mode(_gen_text(field, text), ["E1"], "x:1", "elderly_caution")[0] == mode


# =====================================================================================================
# Input Adapter
# =====================================================================================================
@pytest.mark.parametrize("age", [0, 1, 64, 65, 72, 150])
def test_valid_ages(core, age):
    r = adapters.validate_input({"age": age}, select(A))
    assert r.status == "VALID" and r.age == age and r.medications == (A,)


def test_age_unknown_rules(core):
    assert adapters.validate_input({"age": None, "age_unknown": True}, select(A)).status == "VALID"
    assert adapters.validate_input({"age": None}, select(A)).status == "INVALID_AGE"
    assert adapters.validate_input({}, select(A)).status == "INVALID_AGE"
    assert adapters.validate_input({"age": 70, "age_unknown": True}, select(A)).status == "INVALID_AGE"
    assert adapters.validate_input({"age": None, "age_unknown": "yes"}, select(A)).status == "INVALID_AGE"


@pytest.mark.parametrize("age", [True, False, "72", "", 72.0, 64.5, float("nan"), float("inf"), -1, 151,
                                 np.int64(72), [72], None])
def test_invalid_ages_never_reach_core(core, age):
    spy = Spy()
    vm = adapters.run_safety_check_view({"age": age}, select(A, B), core_fn=spy)
    assert spy.calls == []
    assert vm.state == "INPUT_INVALID" and not vm.can_display_results
    assert [i.code for i in vm.input_issues] == ["INVALID_AGE"]
    assert vm.findings == () and vm.summary is None and vm.no_finding is None


def test_empty_and_limits(core):
    assert adapters.validate_input({"age": 70}, select()).status == "EMPTY_MEDICATIONS"
    assert adapters.validate_input({"age": 70}, select(*EXTRA[:20])).status == "VALID"
    r = adapters.validate_input({"age": 70}, select(*EXTRA[:21]))
    assert r.status == "TOO_MANY_MEDICATIONS" and r.medications == ()
    assert r.issues[0].detail == {"selected": 21, "max": 20}


def test_duplicate_selection_is_reported_not_removed(core):
    sel = select(A, B, A)
    spy = Spy()
    vm = adapters.run_safety_check_view({"age": 70}, sel, core_fn=spy)
    assert spy.calls == [] and vm.state == "INPUT_INVALID"
    issue = [i for i in vm.input_issues if i.code == "DUPLICATE_SELECTION"]
    assert issue and issue[0].detail == [A]
    assert sel.items == (A, B, A)                          # nothing silently removed
    sel.remove(2)
    assert adapters.validate_input({"age": 70}, sel).status == "VALID"


def test_same_ingredient_different_product_is_not_duplicate(core):
    r = adapters.validate_input({"age": 70}, select(A, F))   # 테스트약A정 vs 테스트약A서방정 (different item_seq)
    assert r.status == "VALID" and r.medications == (A, F)


def test_only_offered_candidates_are_accepted(core):
    sel = select(A, B, offer=[A])                            # B typed/injected, never offered
    r = adapters.validate_input({"age": 70}, sel)
    assert r.status == "INVALID_MEDICATION" and r.issues[0].detail == {"positions": [1]}
    for bad in (int(A), None, f" {A} ", "12345"):
        r = adapters.validate_input({"age": 70}, select(A, bad, offer=[A]))
        assert r.status == "INVALID_MEDICATION"
    assert adapters.validate_input({"age": 70}, [A]).status == "INVALID_MEDICATION"   # raw list is not a selection


def test_confirm_selection_is_the_final_gate(core):
    class Rejects:
        @staticmethod
        def confirm_selection(items):
            raise ValueError("not a known item_seq")

    class Broken:
        @staticmethod
        def confirm_selection(items):
            raise AttributeError("module has no attribute DRUG_NAME_BY_ITEM")

    class Rewrites:
        @staticmethod
        def confirm_selection(items):
            return list(reversed(items))

    assert adapters.validate_input({"age": 70}, select(A), lookup=Rejects).status == "INVALID_MEDICATION"
    r = adapters.validate_input({"age": 70}, select(A), lookup=Broken)
    assert r.status == "LOOKUP_VALIDATION_FAILED" and "AttributeError" in r.dev_log[0]
    assert adapters.validate_input({"age": 70}, select(A, B), lookup=Rewrites).status == "LOOKUP_VALIDATION_FAILED"
    # real drug_lookup with the synthetic name table
    assert adapters.validate_input({"age": 70}, select(A, G)).status == "VALID"


def test_selection_from_real_search_drugs(core):
    res = drug_lookup.search_drugs("테스트약A")
    assert res["requires_user_selection"] is True and res["auto_selected"] is None
    sel = adapters.MedicationSelection().register_search(res)
    assert sel.items == ()                                   # nothing auto-selected
    sel.add(res["candidates"][0]["item_seq"])
    r = adapters.validate_input({"age": 70}, sel)
    assert r.status == "VALID" and r.medication_names[0][1] == res["candidates"][0]["item_name"]


def test_lookup_before_resources_loaded(monkeypatch):
    monkeypatch.setitem(resources._STATE, "loaded", False)
    monkeypatch.delattr(screening, "DRUG_NAME_BY_ITEM", raising=False)
    with pytest.raises(AttributeError):                      # CONTRACT GAP (reported): raw Core behaviour
        drug_lookup.confirm_selection([A])
    r = adapters.validate_input({"age": 70}, select(A))      # adapter: no exception, explicit status
    assert r.status == "LOOKUP_VALIDATION_FAILED" and r.medications == ()
    spy = Spy()
    vm = adapters.run_safety_check_view({"age": 70}, select(A), core_fn=spy)
    assert spy.calls == [] and vm.state == "INPUT_INVALID"


def test_core_receives_exactly_age_and_list(core):
    seen = []

    def fake(*a, **k):
        seen.append((a, k))
        return raw_report((A, B), 70)

    vm = adapters.run_safety_check_view({"age": 70}, select(B, A), core_fn=fake)
    assert seen == [((70, [B, A]), {})]                       # user order kept; no kwargs (no include_records)
    assert vm.state == "COMPLETED"


# =====================================================================================================
# Output Adapter — normal path
# =====================================================================================================
def test_completed_report_full(core):
    rep = raw_report()
    before = copy.deepcopy(rep)
    inp = adapters.validate_input({"age": 72}, select(A, B, C, D, E))
    vm = adapters.build_view_model(rep, input_result=inp)
    assert rep == before                                      # report never mutated
    assert vm.state == "COMPLETED" and vm.can_display_results and vm.errors == ()
    assert [f.risk_type for f in vm.findings] == ["contraindication", "elderly_caution", "therapeutic_duplication"]
    assert {f.finding_id for f in vm.findings} == ALL_FIDS
    s = rep["screening"]["summary"]
    assert vm.summary.total_signals == s["total_signals"] == 3
    assert [t.count for t in vm.summary.tiles] == [s["contraindication_count"], s["elderly_caution_count"],
                                                   s["therapeutic_duplication_count"]]
    assert vm.summary.legend == P.BADGE_LEGEND and vm.no_finding is None
    assert vm.scope_note == screening.SCOPE_NOTE
    by_id = {f["finding_id"]: f for f in rep["findings"]}
    for fv in vm.findings:
        f = by_id[fv.finding_id]
        o = f["generation"]["output"]
        assert fv.display_mode == "EXPLANATION" and fv.status_message is None
        assert fv.explanation.summary == o["summary"]                       # verbatim
        assert [st.text for st in fv.explanation.statements] == [x["statement"] for x in o["evidence_statements"]]
        assert fv.explanation.review_note == o["review_note"] and fv.explanation.limitations == o["limitations"]
        assert fv.explanation.evidence_status_label == "설명 근거: 일부만 관련"
        assert [e.evidence_id for e in fv.evidence.items] == [e["evidence_id"] for e in f["evidence"]]
        assert [e.chunk_text for e in fv.evidence.items] == [e["chunk_text"] for e in f["evidence"]]
        assert [e.cited for e in fv.evidence.items] == [e["evidence_id"] in f["generation"]["cited_evidence_ids"]
                                                        for e in f["evidence"]]
        assert fv.evidence.title == "설명에 사용된 허가정보 근거"
        assert [d.item_seq for d in fv.drugs] == f["target_item_seqs"]
        assert [list(d.ingredient_names) for d in fv.drugs] == [d["ingredient_names"] for d in f["drugs"]]
        assert fv.rule_source == f["rule_source"] and fv.clinician_review_text == P.CLINICIAN_REVIEW_TEXT
    contra = vm.findings[0]
    assert contra.canonical_pair_id == PAIR and contra.dur_rule_lines == ("[테스트 DUR 병용금기 문구]",)
    assert vm.findings[1].dur_rule_lines == ("[테스트 노인주의 문구 1]", "[테스트 노인주의 문구 2]")
    assert vm.findings[2].effect_name == EFFECT
    assert [m.display_name for m in vm.medications] == [NAMES[s] for s in sorted([A, B, C, D, E])]
    json.dumps(vm.to_dict(include_debug=True), ensure_ascii=False)          # serialisable


def test_viewmodel_is_immutable(core):
    vm = run_vm()
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.state = "X"
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.findings[0].display_mode = "EXPLANATION"
    assert isinstance(vm.findings, tuple)


def test_finding_order_is_fixed_and_stable(core):
    rep = raw_report()
    rep["findings"] = list(reversed(rep["findings"]))
    vm = adapters.build_view_model(rep)
    assert [f.risk_type for f in vm.findings] == ["contraindication", "elderly_caution", "therapeutic_duplication"]


@pytest.mark.parametrize("status, label", [("SUFFICIENT", "설명 근거: 직접 관련 근거 있음"),
                                           ("PARTIAL", "설명 근거: 일부만 관련"),
                                           ("INSUFFICIENT", "설명 근거: 직접 관련 근거 없음")])
def test_evidence_status_label_is_not_a_risk_level(core, status, label):
    vm = run_vm(llm=llm_valid(status=status))
    for fv in vm.findings:
        assert fv.display_mode == "EXPLANATION"
        assert fv.explanation.evidence_status == status and fv.explanation.evidence_status_label == label
        assert "위험도나 중증도를 뜻하지 않습니다" in fv.explanation.evidence_status_tooltip
        assert fv.risk_label in P.RISK_LABEL_KO.values()                  # risk label independent of status
    assert all(label not in t.display_text for t in vm.summary.tiles)


def test_empty_statements_and_blank_limitations(core):
    vm = run_vm(llm=llm_valid(status="INSUFFICIENT", no_statements=True, limitations="  "))
    for fv in vm.findings:
        assert fv.display_mode == "EXPLANATION"
        assert fv.explanation.statements == () and fv.explanation.no_statements_text == P.NO_STATEMENTS_TEXT
        assert fv.explanation.limitations is None


# =====================================================================================================
# Output Adapter — withheld / failure modes
# =====================================================================================================
def test_invalid_output_text_never_reaches_user(core):
    secret = "[금지된-미검증-텍스트-1234]"
    bad = json.dumps({"finding_id": "wrong", "risk_type": "elderly_caution", "summary": secret,
                      "evidence_statements": [], "evidence_status": "PARTIAL", "limitations": secret,
                      "review_note": secret}, ensure_ascii=False)
    rep = raw_report(llm=llm_text(bad))
    assert all(f["generation"]["status"] == "INVALID_OUTPUT" for f in rep["findings"])
    assert all(f["generation"]["output"]["summary"] == secret for f in rep["findings"])   # Core keeps it
    vm = adapters.build_view_model(rep)
    for fv in vm.findings:
        assert fv.display_mode == "WITHHELD_INVALID" and fv.explanation is None
        assert fv.status_message == P.MODE_MESSAGES["WITHHELD_INVALID"][0]
        assert fv.evidence.title == "검색된 허가정보 원문 (자동 설명 없음)"
        assert not any(e.cited for e in fv.evidence.items)
    assert secret not in user_json(vm)
    assert secret not in json.dumps(vm.to_dict(include_debug=True), ensure_ascii=False)     # not even debug
    vm2 = adapters.build_view_model(rep, include_withheld_text_in_debug=True)
    assert secret not in user_json(vm2)
    assert secret in json.dumps(vm2.debug.to_dict(), ensure_ascii=False)                     # explicit opt-in only


def test_directive_language_is_withheld_even_when_generated(core):
    phrase = "허가정보 기재 내용에 따라 즉시 중단해야 합니다."
    rep = raw_report(llm=llm_valid(statement=phrase))
    assert all(f["generation"]["status"] == "GENERATED" and f["generation"]["directive_flags"]
               for f in rep["findings"])
    vm = adapters.build_view_model(rep)
    for fv in vm.findings:
        assert fv.display_mode == "WITHHELD_DIRECTIVE" and fv.explanation is None
        assert fv.status_message == P.MODE_MESSAGES["WITHHELD_DIRECTIVE"][0]
        assert fv.evidence is not None and not any(e.cited for e in fv.evidence.items)
    assert "즉시 중단해야" not in user_json(vm)
    assert "[테스트 요약]" not in user_json(vm)


def test_no_evidence(core):
    vm = run_vm(llm=llm_must_not_run, retr=make_retrieval("empty"))
    for fv in vm.findings:
        assert fv.display_mode == "NO_EVIDENCE" and fv.explanation is None and fv.evidence is None
        assert fv.status_severity == "warning"
    out = user_json(vm)
    assert "Structured Screening에서" not in out and "사유:" not in out          # deterministic output not shown
    assert not any(lbl in out for lbl in P.EVIDENCE_STATUS_LABEL.values())
    assert vm.state == "COMPLETED" and vm.summary.total_signals == 3


def test_evidence_invalid(core):
    vm = run_vm(llm=llm_must_not_run, retr=make_retrieval("tampered"))
    for fv in vm.findings:
        assert fv.display_mode == "EVIDENCE_INVALID" and fv.evidence is None and fv.explanation is None
    assert {e.code for e in vm.errors} == {"FINDING_EVIDENCE_INVALID"}
    assert all(e.layer == "L4_FINDING" and not e.abort and e.partial_result for e in vm.errors)


def test_llm_unavailable_banner_once(core):
    vm = run_vm(llm=llm_text(None, error="LLM_UNAVAILABLE: API key not found"))
    assert all(f.display_mode == "LLM_UNAVAILABLE" for f in vm.findings)
    assert vm.summary.llm_unavailable_banner == P.LLM_UNAVAILABLE_BANNER
    assert all(f.evidence is not None and f.evidence.title == P.EVIDENCE_TITLE_RAW for f in vm.findings)
    assert len({f.finding_id for f in vm.findings}) == 3                           # findings all kept


@pytest.mark.parametrize("llm", [llm_text(None, error="REFUSAL: x"), llm_text(""), llm_text("not json"), llm_raises])
def test_generation_failed_modes(core, llm):
    vm = run_vm(llm=llm)
    assert {f.finding_id for f in vm.findings} == ALL_FIDS
    assert all(f.display_mode == "GENERATION_FAILED" and f.explanation is None for f in vm.findings)
    assert vm.summary.llm_unavailable_banner is None
    assert all(e.code == "FINDING_GENERATION_FAILED" for e in vm.errors)
    assert "REFUSAL" not in user_json(vm) and "ConnectionError" not in user_json(vm)


def test_pipeline_error_no_keyerror_and_no_invented_info(core):
    rep = raw_report(llm=llm_must_not_run, retr=make_retrieval("boom"))
    assert all(f["generation"]["status"] == "PIPELINE_ERROR" for f in rep["findings"])
    vm = adapters.build_view_model(rep)
    assert vm.state == "COMPLETED" and vm.can_display_results
    by_id = {f["finding_id"]: f for f in rep["findings"]}
    for fv in vm.findings:
        f = by_id[fv.finding_id]
        assert fv.display_mode == "PROCESSING_ERROR" and fv.explanation is None and fv.evidence is None
        assert fv.rule_source == findings.RULE_SOURCE[fv.risk_type]               # contract §4 fallback
        assert [list(d.ingredient_names) for d in fv.drugs] == [d["ingredient_names"] for d in f["drugs"]]
        assert [d.item_name for d in fv.drugs] == [d["item_name"] for d in f["drugs"]]
    assert vm.findings[0].canonical_pair_id == PAIR and vm.findings[2].effect_name == EFFECT
    assert vm.findings[1].canonical_pair_id is None and vm.findings[1].effect_name is None
    assert len(vm.errors) == 3 and all(e.code == "FINDING_PROCESSING_ERROR" and e.partial_result for e in vm.errors)
    assert "ui-adapter-test retrieval failure" not in user_json(vm)                # dev log stays out
    assert "ui-adapter-test retrieval failure" in json.dumps(vm.to_dict(include_debug=True), ensure_ascii=False)


def test_partial_pipeline_error(core):
    vm = run_vm(retr=make_retrieval(fail_for="elderly_caution"))
    modes = {f.risk_type: f.display_mode for f in vm.findings}
    assert modes == {"contraindication": "EXPLANATION", "elderly_caution": "PROCESSING_ERROR",
                     "therapeutic_duplication": "EXPLANATION"}
    assert [e.finding_id for e in vm.errors] == [FID_ELDERLY]


def test_retrieval_notices_on_card(core):
    vm = run_vm(retr=make_retrieval(warnings=["NO_RISK_SPECIFIC_ARTICLE", "SOME_ITEM_SEQ_NOT_IN_CORPUS",
                                              "DENSE_UNAVAILABLE"]))
    for fv in vm.findings:
        assert fv.retrieval_notices == (P.RETRIEVAL_NOTICE_MESSAGES["NO_RISK_SPECIFIC_ARTICLE"],
                                        P.RETRIEVAL_NOTICE_MESSAGES["SOME_ITEM_SEQ_NOT_IN_CORPUS"])
    assert "DENSE_UNAVAILABLE" not in user_json(vm)


# =====================================================================================================
# Output Adapter — report validation / invariants
# =====================================================================================================
@pytest.mark.parametrize("tamper", [
    lambda r: r["screening"]["summary"].__setitem__("total_signals", 2),
    lambda r: r["summary"].__setitem__("n_findings", 4),
    lambda r: r["findings"].pop(),
    lambda r: r["screening"]["summary"].__setitem__("elderly_caution_count", 0),
    lambda r: r["findings"].append(copy.deepcopy(r["findings"][0])) or r["summary"].__setitem__("n_findings", 4)
    or r["screening"]["summary"].update(total_signals=4, contraindication_count=2),
])
def test_count_invariant_failure_is_not_corrected(core, tamper):
    rep = raw_report()
    tamper(rep)
    before = copy.deepcopy(rep)
    vm = adapters.build_view_model(rep)
    assert rep == before
    assert vm.state == "REPORT_INCONSISTENT" and not vm.can_display_results
    assert vm.findings == () and vm.summary is None and vm.no_finding is None
    assert [(e.code, e.layer, e.abort) for e in vm.errors] == [("REPORT_INCONSISTENT", "L3_REPORT", True)]


@pytest.mark.parametrize("tamper", [
    lambda r: r.pop("findings"),
    lambda r: r["screening"].pop("summary"),
    lambda r: r["findings"][0].__setitem__("risk_type", "new_type"),
    lambda r: r["findings"][0].__setitem__("generation", None),
    lambda r: r["findings"][0].pop("drugs"),
    lambda r: r["findings"][0]["evidence"][0].pop("chunk_text"),
    lambda r: r["screening"]["summary"].__setitem__("elderly_check_status", "maybe"),
    lambda r: r["screening"]["summary"].__setitem__("total_signals", True),
    lambda r: r.clear(),
])
def test_invalid_report_structure_fails_closed(core, tamper):
    rep = raw_report()
    tamper(rep)
    vm = adapters.build_view_model(rep)                       # must not raise (no KeyError)
    assert vm.state == "REPORT_INVALID" and not vm.can_display_results and vm.findings == ()
    assert vm.errors[0].code == "REPORT_INVALID" and vm.errors[0].abort


@pytest.mark.parametrize("bad", [None, [], "report", 3])
def test_non_dict_report(core, bad):
    vm = adapters.build_view_model(bad)
    assert vm.state == "REPORT_INVALID"


# =====================================================================================================
# Elderly / no-finding / notices
# =====================================================================================================
@pytest.mark.parametrize("age, code, count", [(72, "evaluated", 1),
                                              (40, "not_applicable_age_below_threshold", None),
                                              (None, "not_evaluated_age_missing", None)])
def test_elderly_three_states(core, age, code, count):
    vm = run_vm(age=age)
    assert vm.patient.elderly.code == code
    tile = [t for t in vm.summary.tiles if t.risk_type == "elderly_caution"][0]
    assert tile.count == count
    if count is None:
        assert tile.display_text == P.ELDERLY_STATUS_VIEW[code]["label"] and "0" not in tile.display_text
        assert not any(f.risk_type == "elderly_caution" for f in vm.findings)
    assert vm.patient.age_display == ("미입력" if age is None else str(age))
    has_notice = any(n.code == "ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING" for n in vm.notices)
    assert has_notice is (code == "not_evaluated_age_missing")


def test_no_finding_message_only_on_normal_completion(core):
    vm = run_vm(meds=(G,), llm=llm_must_not_run, retr=make_retrieval("boom"))
    assert vm.state == "COMPLETED" and vm.findings == ()
    assert vm.no_finding.message == P.NO_FINDING_TEXT and vm.no_finding.scope_note == screening.SCOPE_NOTE
    assert [n.code for n in vm.notices] == ["NOT_FOUND_IN_DUR_TABLES"] and vm.notices[0].item_seqs == (G,)
    assert vm.medications[0].in_dur_tables is False
    rep = raw_report(meds=(G,), llm=llm_must_not_run, retr=make_retrieval("boom"))
    rep["summary"]["n_findings"] = 1
    assert adapters.build_view_model(rep).no_finding is None                 # inconsistent → no message
    vm_in = adapters.run_safety_check_view({"age": 70}, select(), core_fn=Spy())
    assert vm_in.no_finding is None


def _all_user_vms(core_ok):
    yield run_vm()
    yield run_vm(meds=(G,), llm=llm_must_not_run, retr=make_retrieval("boom"))
    yield run_vm(meds=(D, G), age=None, retr=make_retrieval("empty"), llm=llm_must_not_run)
    yield run_vm(llm=llm_text(None, error="LLM_UNAVAILABLE: x"))
    yield run_vm(llm=llm_valid(statement="절대 복용하면 안 됩니다"))
    yield adapters.run_safety_check_view({"age": "x"}, select(A), core_fn=Spy())


def test_forbidden_reassurance_phrases_absent(core):
    for vm in _all_user_vms(core):
        out = user_json(vm)
        for phrase in P.FORBIDDEN_USER_PHRASES:
            assert phrase not in out, (vm.state, phrase)


def test_duplicate_inputs_notice_from_report(core):
    rep = raw_report(meds=(A, B, A))                          # adapter would block this; report built directly
    vm = adapters.build_view_model(rep)
    assert [n for n in vm.notices if n.code == "DUPLICATE_INPUTS"][0].item_seqs == (A,)


# =====================================================================================================
# Execution errors / metadata
# =====================================================================================================
def test_resources_not_loaded_core_not_called(core, monkeypatch):
    monkeypatch.setitem(resources._STATE, "loaded", False)
    inp = adapters.InputValidationResult("VALID", (), 70, (A,), ((A, NAMES[A]),))
    spy = Spy()
    exe = adapters.execute(inp, spy)
    assert spy.calls == [] and exe.error_code == "RESOURCES_NOT_LOADED"
    vm = adapters.build_view_model(input_result=inp, execution=exe)
    assert vm.state == "RESOURCE_ERROR" and vm.errors[0].layer == "L1_RESOURCE"


@pytest.mark.parametrize("exc, state, layer", [
    (RuntimeError("call dur_safety.resources.load_resources() before run_safety_check()"), "RESOURCE_ERROR", "L1_RESOURCE"),
    (ValueError("boom"), "CORE_ERROR", "L2_CORE"),
    (KeyError("x"), "CORE_ERROR", "L2_CORE")])
def test_core_exception_mapping(core, exc, state, layer):
    def bad(age, meds):
        raise exc
    vm = adapters.run_safety_check_view({"age": 70}, select(A), core_fn=bad)
    assert vm.state == state and vm.errors[0].layer == layer and vm.errors[0].abort
    assert not vm.can_display_results and vm.findings == ()
    assert "dev_log" not in user_json(vm)
    assert vm.metadata.adapter["core_called"] is True and vm.metadata.adapter["elapsed_s"] is not None


def test_metadata_core_vs_adapter(core):
    vm = run_vm(runtime_info={"device": "cpu", "deployment": {"baseline_version": "production-baseline-v1"}})
    core_md, ad = vm.metadata.core, vm.metadata.adapter
    assert core_md["pipeline_name"] == pipeline.PIPELINE_NAME and core_md["pipeline_version"] == pipeline.PIPELINE_VERSION
    assert core_md["generation"]["model"] == generation.GENERATION_CONFIG["model"]
    assert core_md["data_snapshot"] == {"synthetic_test_data": True}
    assert "elapsed_s" not in core_md and "started_at" not in core_md
    assert ad["core_called"] and isinstance(ad["elapsed_s"], float) and ad["elapsed_s"] >= 0
    assert ad["started_at"] <= ad["finished_at"]
    assert ad["device_note"] == P.DEVICE_MISMATCH_TEXT and ad["deployment"]["baseline_version"] == "production-baseline-v1"
    assert adapters.runtime_info_from_load_report({"dense_state": {"device": "cuda"}})["device"] == "cuda"


def test_read_deployment_info(tmp_path):
    p = tmp_path / "production_baseline.json"
    p.write_text(json.dumps({"baseline_version": "production-baseline-v1", "freeze_timestamp": "t",
                             "status": "S", "package": {"package_version": "0.1.0", "pipeline_version": "0.1.0"}}))
    assert adapters.read_deployment_info(p)["baseline_version"] == "production-baseline-v1"
    assert adapters.read_deployment_info(tmp_path / "missing.json") is None


# =====================================================================================================
# Optional: real project data (Colab). Opt-in so that a plain run never loads data or models.
# Requires MEDICAL_AI_PROJECT_ROOT (conftest `loaded` fixture) AND DUR_UI_ADAPTER_REAL_DATA=1.
# LLM is still a mock (LLM_UNAVAILABLE) — no API call.
# =====================================================================================================
REAL_DEMO_MEDS = ["195700013", "196900031", "197000068", "197000079", "197700114"]


@pytest.fixture
def real_loaded(request):
    import os
    if os.environ.get("DUR_UI_ADAPTER_REAL_DATA") != "1":
        pytest.skip("set DUR_UI_ADAPTER_REAL_DATA=1 (and MEDICAL_AI_PROJECT_ROOT) to run against real data")
    return request.getfixturevalue("loaded")


def test_real_data_end_to_end_with_mock_llm(real_loaded):
    sel = adapters.MedicationSelection()
    for seq in REAL_DEMO_MEDS:
        sel.register_search(drug_lookup.search_drugs(seq))
        sel.add(seq)
    llm = llm_text(None, error="LLM_UNAVAILABLE: ui adapter real-data test")
    vm = adapters.run_safety_check_view({"age": 72}, sel,
                                        core_fn=functools.partial(pipeline.run_safety_check, llm_fn=llm),
                                        runtime_info=adapters.runtime_info_from_load_report(real_loaded))
    assert vm.state == "COMPLETED" and vm.summary.total_signals == len(vm.findings) == 3
    assert {f.finding_id for f in vm.findings} == {
        "contraindication:195700013|196900031", "elderly_caution:197000079",
        "therapeutic_duplication:당뇨병용제:197000068|197700114"}
    assert all(f.explanation is None for f in vm.findings)
    assert all(f.display_mode in {"LLM_UNAVAILABLE", "NO_EVIDENCE"} for f in vm.findings)
    assert all(n.code != "DUPLICATE_INPUTS" for n in vm.notices)
    json.dumps(vm.to_dict(include_debug=True), ensure_ascii=False)

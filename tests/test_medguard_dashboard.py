"""STEP 9 — MEDGUARD dashboard tests (app/medguard_dashboard.py run headless with streamlit.testing AppTest).

MOCK tier only (no project data): the real Frozen Core runs over the SYNTHETIC lookup tables of
tests/test_ui_adapter.py (fixture `core`, fake identifiers 1000000xx); retrieval and LLM are mocks. Audit files
used here are SYNTHETIC fixtures written to tmp_path. Passing these tests shows that the dashboard displays what the
ViewModel / audit files say and never reads "no rule" as "safe" — it is NOT a clinical validation and NOT a
substitute for the opt-in real-data run described in reports/ui_validation/.
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from test_ui_adapter import (A, B, C, D, E, G, NAMES, core, llm_raises, llm_valid, make_retrieval)  # noqa: E402,F401

from dur_safety import drug_lookup, pipeline  # noqa: E402
from app import adapters, ui_policy as P, ui_runtime  # noqa: E402
from app.utils import audit_reader as AR, ui_helpers as H  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "medguard_dashboard.py")
APP_DIR = Path(__file__).resolve().parents[1] / "app"
NEW_FILES = [APP_DIR / "medguard_dashboard.py", *(APP_DIR / "components").glob("*.py"), *(APP_DIR / "utils").glob("*.py")]


# ------------------------------------------------------------------------------------------- fixtures
def write_audit(root: Path, name="run_20261012_183621", gates=None, option="C"):
    """SYNTHETIC audit run (not a real audit result)."""
    d = root / "reports" / "ingredient_coverage_audit" / name
    d.mkdir(parents=True, exist_ok=True)
    gates = gates or {"1": "WARN", "2": "WARN", "3": "PASS"}
    (d / "audit_manifest.json").write_text(json.dumps({"run_ts": name[4:], "baseline_run": "run_20261011_152938",
                                                       "option": option, "gates": gates,
                                                       "protected_files_unchanged": True, "regression_hash_equal": True}),
                                           encoding="utf-8")
    (d / "11_feasibility_decision.json").write_text(json.dumps({
        "option": option, "option_text": f"OPTION {option} — 성분 연결 확장 보류(합성 테스트)", "reason": "합성 테스트 근거",
        "gates": gates, "official_link_table": False, "auto_apply": False, "engine_change_allowed": False,
        "inferred_additional_products": 11, "candidate_upper_products": 22, "inferred_mapping_pairs_not_official": 3,
        "note": "합성 테스트 파일"}), encoding="utf-8")
    (d / "09_medical_safety_validation.csv").write_text(
        "Test Case,Product,Mapping Method,Rule Type,Evidence,Expected Result,Actual Result,PASS/WARN/FAIL,Explanation\n"
        "F-1 테스트 항목,(전체),m,공통,ev.csv,기대결과 텍스트,실제결과 텍스트,PASS,설명\n"
        "F-2 경고 항목,(전체),m,공통,ev2.csv,기대2,실제 경고 내용,WARN,설명2\n", encoding="utf-8-sig")
    (d / "12_ingredient_coverage_report.md").write_text(
        "## 부록\n| step | check | result | detail |\n|---|---|---|---|\n"
        "| B1 | GATE1-12 구조화 컬럼 존재 | WARN | 합성 경고 1 |\n| GATE2 | GATE2-8 공식 연결표 | WARN | 합성 경고 2 |\n",
        encoding="utf-8")
    b = root / "reports" / "ui_coverage_audit" / "run_20261011_152938"
    b.mkdir(parents=True, exist_ok=True)
    (b / "03_coverage_metrics.csv").write_text(
        "metric_id,metric,basis,type,numerator,denominator,value_%,formula,note\n"
        "M2b,DUR 규칙 테이블 등장 제품,UI,EXACT,750,1000,75.0,|U ∩ KNOWN| / U,합성\n"
        "M4a,U 중 병용금기 pair에 등장하는 제품,UI,EXACT,500,1000,50.0,f,\n"
        "M5a,노인주의,UI,EXACT,120,1000,12.0,f,\nM6a,효능군,UI,EXACT,430,1000,43.0,f,\n", encoding="utf-8-sig")
    return d


def make_dash(monkeypatch, tmp_path, *, llm=None, retr=None, core_fn=None, ready=True, search=None, with_audit=True):
    if with_audit:
        write_audit(tmp_path)
    monkeypatch.setenv("MEDICAL_AI_PROJECT_ROOT", str(tmp_path))
    if core_fn is None:
        core_fn = functools.partial(pipeline.run_safety_check, llm_fn=llm or llm_valid(), retrieval_fn=retr or make_retrieval())
    if ready:
        rt = ui_runtime.Runtime(ready=True, search=search or (lambda q: drug_lookup.search_drugs(q, limit=20)),
                                core_fn=core_fn, runtime_info={"device": "cpu"})
    else:
        rt = ui_runtime.Runtime(ready=False, error_user=ui_runtime.LOAD_FAILED_TEXT, error_dev="RuntimeError: test")
    monkeypatch.setattr(ui_runtime, "load_runtime", lambda: rt)
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    return at


def search(at, query):
    at.text_input(key="d_query").input(query)
    at.button(key="search_btn").click()
    at.run()


def add(at, *seqs):
    for s in seqs:
        search(at, NAMES.get(s, s))
        at.button(key=f"add_d_{s}").click()
        at.run()


def set_age(at, age):
    if age is None:
        at.checkbox(key="d_age_unknown").check()
    else:
        at.number_input(key="d_age").set_value(age)
    at.run()


def run_check(at):
    at.button(key="run_check").click()
    at.run()
    assert not at.exception, at.exception


def page_text(at):
    out = []
    for coll in (at.markdown, at.caption, at.info, at.warning, at.error, at.success, at.subheader, at.header, at.title,
                 at.text, at.code, at.button):
        out += [str(getattr(e, "value", None) or getattr(e, "label", "")) for e in coll]
    out += [str(e.label) for e in at.expander]
    out += [str(o) for sb in at.selectbox for o in sb.options]
    return "\n".join(out)


def scenario(monkeypatch, tmp_path, meds, age=72, **kw):
    at = make_dash(monkeypatch, tmp_path, **kw)
    set_age(at, age)
    add(at, *meds)
    run_check(at)
    return at


def assert_never_reassuring(at):
    t = re.sub(r"<[^>]+>", " ", page_text(at))
    for phrase in H.FORBIDDEN_UI_PHRASES:
        assert phrase not in t, phrase
    assert len(at.success) == 0


# ======================================================================================= static safety
def test_new_files_do_not_touch_engine_or_inferred_data():
    """The dashboard talks to the Core only through app.adapters / app.ui_runtime and never names the quarantine folders."""
    for f in NEW_FILES:
        src = f.read_text(encoding="utf-8")
        assert not re.search(r"from\s+dur_safety|import\s+dur_safety|screening\.|screen_patient", src), f.name
        assert "internal_inferred" not in src and "candidate_quarantine" not in src, f.name
        assert "dm_bridge" not in src, f.name
        if f.name != "audit_reader.py":
            assert "ingredient_coverage_audit" not in src, f.name


def test_audit_reader_is_read_only_and_allowlisted():
    src = (APP_DIR / "utils" / "audit_reader.py").read_text(encoding="utf-8")
    assert not re.search(r"write_text|open\([^)]*['\"]w|\.unlink|rmtree|rglob|os\.walk|glob\(", src)


def test_existing_ui_files_untouched():
    """First UI + adapter layer are not modified by this step (compared to the files tracked in FROZEN checks)."""
    for name in ("streamlit_main.py", "adapters.py", "ui_render.py", "ui_policy.py", "ui_runtime.py", "view_models.py"):
        assert (APP_DIR / name).exists()


def test_no_forbidden_phrase_in_component_sources():
    for f in NEW_FILES:
        src = f.read_text(encoding="utf-8")
        for phrase in ("안전합니다", "문제 없음", "문제없음", "이상 없음", "이상없음", "안전함"):
            assert phrase not in src, (f.name, phrase)


# ======================================================================================= audit reader
def test_audit_reader_parses_gates_and_checks(tmp_path):
    write_audit(tmp_path)
    runs = AR.list_runs(tmp_path)
    assert runs == ["run_20261012_183621"]
    a = AR.load_run(tmp_path, runs[0])
    assert a["gates"] == {"1": "WARN", "2": "WARN", "3": "PASS"} and a["option"] == "C" and a["auto_apply"] is False
    assert [c["status"] for c in a["gate_checks"]["3"]] == ["PASS", "WARN"]
    assert a["gate_checks"]["3"][1]["warning"] == "실제 경고 내용"
    assert a["gate_checks"]["1"][0]["warning"] == "합성 경고 1" and a["gate_checks"]["2"][0]["status"] == "WARN"
    assert a["gate_checks_complete"] == {"1": False, "2": False, "3": True}


def test_audit_reader_missing_is_not_invented(tmp_path):
    assert AR.list_runs(tmp_path) == [] and AR.load_run(tmp_path, None) is None
    assert AR.load_run(tmp_path, "run_20260101_000000") is None
    assert AR.load_run(tmp_path, "../../etc") is None
    assert AR.load_baseline_metrics(tmp_path, "run_20260101_000000") == []
    d = write_audit(tmp_path)
    (d / "11_feasibility_decision.json").unlink()
    (d / "09_medical_safety_validation.csv").unlink()
    a = AR.load_run(tmp_path, "run_20261012_183621")
    assert a["gates"] == {"1": "WARN", "2": "WARN", "3": "PASS"}      # falls back to the manifest's gates, nothing invented
    assert a["gate_checks"]["3"] == [] and a["gate_checks_complete"]["3"] is False
    (d / "audit_manifest.json").write_text(json.dumps({"gates": {"1": "PASS"}}), encoding="utf-8")
    a = AR.load_run(tmp_path, "run_20261012_183621")
    assert a["gates"] == {"1": "PASS", "2": "NOT RUN", "3": "NOT RUN"}


def test_gate_missing_is_not_run(tmp_path):
    d = write_audit(tmp_path, gates={"1": "PASS"})
    (d / "11_feasibility_decision.json").write_text(json.dumps({"option": "C", "gates": {"1": "PASS"}}), encoding="utf-8")
    a = AR.load_run(tmp_path, "run_20261012_183621")
    assert a["gates"] == {"1": "PASS", "2": "NOT RUN", "3": "NOT RUN"}


# ======================================================================================= pure helpers
def test_ratio_formatting_never_invents_numbers():
    assert H.fmt_ratio(None, 10) == "N/A" and H.fmt_ratio(5, None) == "N/A" and H.fmt_ratio(5, 0) == "N/A"
    assert H.fmt_ratio(750, 1000) == "750 / 1,000 (75.00%)"


def test_search_states():
    assert H.query_state("x", None, False, False) == "LOAD_FAILED"
    assert H.query_state("x", {"candidates": []}, True, False) == "NOT_SEARCHABLE"
    assert H.query_state("12345", {"candidates": []}, True, False) == "ID_UNCONFIRMED"
    assert H.query_state("123456789", {"candidates": []}, True, False) == "ID_UNCONFIRMED"
    assert H.query_state("x", {"candidates": [{"item_seq": "1"}]}, True, False) is None
    assert H.candidate_state({"in_dur_tables": True}) == "RULE_PRESENT" and H.candidate_state({"in_dur_tables": False}) == "NO_RULE"


# ======================================================================================= app behaviour
def test_initial_state_has_no_invented_values(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path, with_audit=False)
    t = page_text(at)
    assert "실행 기록 없음" in t and "READY" in t and "Audit 실행 기록 없음" in t
    assert "99.1" not in t and "OPTION C" not in t
    assert_never_reassuring(at)


def test_no_audit_gates_are_not_run(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path, with_audit=False)
    html = "\n".join(m.value for m in at.markdown)
    assert html.count("NOT RUN") >= 3 and "mg-gate pass" not in html


def test_audit_shown_as_separate_from_patient_status(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    html = "\n".join(m.value for m in at.markdown)
    assert "OPTION C" in html and "환자·약물 조합의 안전성 판정이 아닙니다" in html
    assert "[A] 환자·약물 조합 분석 상태" in html and "[B] Coverage Audit 구현 판정" in html
    assert "분석 전" in html


def test_gates_drawn_only_from_audit(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    html = "\n".join(m.value for m in at.markdown)
    assert html.count('class="mg-gate ') == 3 and "GATE 4" not in html
    assert H.GATE_NOT_CLINICAL_NOTE in html


def test_coverage_donut_uses_numerator_denominator(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    html = "\n".join(m.value for m in at.markdown)
    assert "75.0%" in html and "750 / 1,000 (75.00%)" in html and "1,000" in html
    assert "합산하지 않습니다" in html


def test_search_card_states_and_no_auto_select(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    search(at, "테스트약A")
    assert at.button(key=f"add_d_{A}") is not None
    assert at.session_state["selection"].items == ()
    search(at, "존재하지않는약")
    assert "검색 불가" in page_text(at)
    search(at, "123456789")
    assert "식별자 불일치 또는 확인 불가" in page_text(at)
    assert_never_reassuring(at)


def test_search_failure_and_load_failure(core, monkeypatch, tmp_path):
    def boom(q):
        raise RuntimeError("down")
    at = make_dash(monkeypatch, tmp_path, search=boom)
    search(at, "테스트약A")
    assert "데이터 로딩 실패" in page_text(at)
    at2 = make_dash(monkeypatch, tmp_path, ready=False)
    assert "FAILED" in page_text(at2) and ui_runtime.LOAD_FAILED_TEXT in page_text(at2)
    assert at2.button(key="search_btn").disabled


def test_select_remove_clear(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    add(at, A, B)
    assert at.session_state["selection"].items == (A, B)
    at.button(key=f"rm_0_{A}").click()
    at.run()
    assert at.session_state["selection"].items == (B,)
    at.button(key="clear_all").click()
    at.run()
    assert at.session_state["selection"].items == ()


def test_three_risk_types_matrix_and_kpis(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72)
    vm = at.session_state["vm"]
    assert vm.state == P.STATE_COMPLETED
    rows = {r["item_seq"]: r["cells"] for r in H.matrix_rows(vm)}
    assert rows[A]["contraindication"]["status"] == "FOUND" and rows[B]["contraindication"]["status"] == "FOUND"
    assert rows[C]["elderly_caution"]["status"] == "FOUND"
    assert rows[D]["therapeutic_duplication"]["status"] == "FOUND" and rows[E]["therapeutic_duplication"]["status"] == "FOUND"
    assert rows[C]["contraindication"]["status"] == "NONE_FOUND"
    kp = {c["key"]: c for c in H.kpi_cards(vm)}
    assert kp["contraindication"]["value"] == "1건" and kp["elderly_caution"]["value"] == "1건" and kp["therapeutic_duplication"]["value"] == "1건"
    html = "\n".join(m.value for m in at.markdown)
    assert "주의 항목 발견" in html and "mg-cell found" in html
    assert_never_reassuring(at)


def test_ui_screening_equals_direct_adapter_and_core(core, monkeypatch, tmp_path):
    """REGRESSION: the dashboard returns the same screening as calling the adapter / the Core directly."""
    cf = functools.partial(pipeline.run_safety_check, llm_fn=llm_valid(), retrieval_fn=make_retrieval())
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72, core_fn=cf)
    ui_vm = at.session_state["vm"]
    sel = adapters.MedicationSelection()
    sel.register_search(drug_lookup.search_drugs("테스트", limit=50))
    for s in (A, B, C, D, E):
        sel.add(s)
    ref = adapters.run_safety_check_view({"age": 72}, sel, core_fn=cf)

    def norm(vm):
        d = vm.to_dict(include_debug=False)
        d["metadata"]["adapter"].pop("started_at", None); d["metadata"]["adapter"].pop("finished_at", None)
        for k in ("elapsed_s", "device", "device_note"):
            d["metadata"]["adapter"].pop(k, None)
        return d
    assert norm(ui_vm) == norm(ref)
    raw = cf(72, [A, B, C, D, E])
    assert [t.count for t in ui_vm.summary.tiles] == [raw["screening"]["summary"][k] for k in (
        "contraindication_count", "elderly_caution_count", "therapeutic_duplication_count")]
    assert [f.finding_id for f in ui_vm.findings] == [f["finding_id"] for f in sorted(
        raw["findings"], key=lambda f: P.RISK_ORDER.index(f["risk_type"]))]


def test_not_in_dur_is_not_safe(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, G], age=72)           # G is searchable but not in any DUR table
    vm = at.session_state["vm"]
    rows = {r["item_seq"]: r["cells"] for r in H.matrix_rows(vm)}
    assert all(c["status"] == "NOT_IN_DATA" for c in rows[G].values())
    cs = H.combination_status(vm)
    assert cs.code in ("FOUND", "PARTIAL") and cs.limitation_text == H.INCOMPLETE_LIMIT_TEXT
    assert H.analysis_status(True, vm)[0] == "PARTIAL"
    kp = {c["key"]: c for c in H.kpi_cards(vm)}
    assert kp["review"]["value"] == "1개"
    assert any(r.kind == "not_in_data" for r in H.finding_rows(vm))
    assert_never_reassuring(at)


def test_no_finding_is_not_labelled_safe(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A], age=40)             # one product, age < 65 → nothing to find by construction
    vm = at.session_state["vm"]
    cs = H.combination_status(vm)
    assert cs.code == "PARTIAL" and "평가 불가" in cs.label                    # 1 drug: pair rules not evaluated; age<65
    cells = H.matrix_rows(vm)[0]["cells"]
    assert cells["contraindication"]["status"] == "UNDETERMINED" and cells["elderly_caution"]["status"] == "UNDETERMINED"
    assert H.kpi_cards(vm)[1]["value"] == "—"                                   # elderly not evaluated is never shown as 0
    assert_never_reassuring(at)


def test_age_unknown_elderly_undetermined(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C], age=None)
    vm = at.session_state["vm"]
    assert vm.patient.elderly.code == "not_evaluated_age_missing"
    assert H.matrix_rows(vm)[2]["cells"]["elderly_caution"]["status"] == "UNDETERMINED"
    assert any(r.kind == "elderly_not_evaluated" for r in H.finding_rows(vm))
    assert H.kpi_cards(vm)[1]["value"] == "—"


def test_llm_failure_keeps_screening_and_separates_llm(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72, llm=llm_raises)
    vm = at.session_state["vm"]
    assert vm.summary.total_signals == 3 and all(f.explanation is None for f in vm.findings)
    at.button(key="nav_result").click()
    at.run()
    assert not at.exception, at.exception
    html = "\n".join(m.value for m in at.markdown)
    assert "LLM-GENERATED EXPLANATION" in html               # the (empty) LLM panel is labelled
    assert "검증을 통과한 자동 생성 설명이 없습니다" in html
    assert_never_reassuring(at)


def test_llm_text_only_in_explanation_panel(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72)
    at.button(key="nav_result").click()
    at.run()
    assert not at.exception, at.exception
    t = page_text(at)
    assert "테스트 설명 문장" in t


def test_evidence_only_from_retrieval(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72)
    docs = H.evidence_docs(at.session_state["vm"])
    assert docs and all(d["chunk_text"] and d["source"] for d in docs)
    at2 = make_dash(monkeypatch, tmp_path)
    assert "현재 검색된 근거 자료가 없습니다." in page_text(at2)


def test_input_change_hides_stale_result(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B], age=72)
    assert at.session_state["vm"] is not None
    add(at, C)
    html = "\n".join(m.value for m in at.markdown)
    assert "입력이 변경되어 이전 결과를 숨겼습니다" in html and "mg-cell found" not in html
    assert H.analysis_status(True, None)[0] == "READY"


def test_core_error_shows_failed(core, monkeypatch, tmp_path):
    def boom(age, meds):
        raise RuntimeError("core down")
    at = scenario(monkeypatch, tmp_path, [A, B], age=72, core_fn=boom)
    html = "\n".join(m.value for m in at.markdown)
    assert "FAILED" in html and "분석 실패" in html
    assert H.matrix_rows(at.session_state["vm"])[0]["cells"]["contraindication"]["status"] == "FAILED_LOOKUP"
    assert_never_reassuring(at)


def test_all_pages_render_and_navigate(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72)
    for key, label, _ in H.NAV_ITEMS:
        at.button(key=f"nav_{key}").click()
        at.run()
        assert not at.exception, (key, at.exception)
        assert at.session_state["page"] == key
        assert_never_reassuring(at)


def test_gate_detail_fields(core, monkeypatch, tmp_path):
    at = make_dash(monkeypatch, tmp_path)
    at.button(key="nav_gates").click()
    at.run()
    assert not at.exception, at.exception
    t = page_text(at)
    assert "F-2 경고 항목" in t and "실제 경고 내용" in t and "합성 경고 1" in t
    assert "PASS 항목의 상세가 결과 파일에 저장되어 있지 않아" in t


def test_report_download_content(core, monkeypatch, tmp_path):
    at = scenario(monkeypatch, tmp_path, [A, B, C, D, E], age=72)
    md = H.build_report_markdown(at.session_state["vm"], {"run_name": "r", "option": "C", "gates": {"1": "WARN"}})
    assert "주의 항목 발견" in md and "RULE-BASED RESULT" in md and "AUDIT RESULT" in md
    js = json.loads(H.build_report_json(at.session_state["vm"], None))
    assert js["screening"]["state"] == "COMPLETED" and "debug" not in js["screening"]
    for phrase in H.FORBIDDEN_UI_PHRASES:
        assert phrase not in md


def test_html_injection_is_escaped(core, monkeypatch, tmp_path):
    evil = "<script>alert(1)</script>"
    assert "<script>" not in H.esc(evil) and "&lt;script&gt;" in H.esc(evil)

"""MEDGUARD AI dashboard (STEP 9). Entry point:

    streamlit run app/medguard_dashboard.py --theme.base dark

Presentation layer only. Flow:  widgets → MedicationSelection → adapters.run_safety_check_view → ViewModel →
components. The Frozen Core, the first UI (app/streamlit_main.py) and every existing app/ module are used as-is.
Audit files (STEP 8-1.5 / 8-1.6) are read through app.utils.audit_reader for DISPLAY only; nothing inferred by the
audits is ever passed to the Screening Engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

from app import adapters, ui_runtime  # noqa: E402
from app.components import (coverage_page, drug_search, drug_table, evidence_panel, findings, gate_timeline,  # noqa: E402
                            header, pages, safety_matrix, sidebar, summary_cards)
from app.utils import audit_reader as AR  # noqa: E402
from app.utils import ui_helpers as H  # noqa: E402

st.set_page_config(page_title="MEDGUARD AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

CSS_PATH = Path(__file__).resolve().parent / "styles" / "medguard.css"


def load_css() -> str:
    try:
        css = CSS_PATH.read_text(encoding="utf-8")
    except Exception:                                        # noqa: BLE001 — unstyled but functional
        return ""
    return "\n".join(ln for ln in css.splitlines() if ln.strip())     # a blank line would end the HTML block


@st.cache_resource(show_spinner="DUR 데이터와 검색 모델을 불러오는 중입니다 (처음 1회, 수 분 소요)…")
def get_runtime():
    return ui_runtime.load_runtime()


def init_state(ss):
    ss.setdefault("page", "dashboard")
    ss.setdefault("selection", adapters.MedicationSelection())
    ss.setdefault("candidates", None)
    ss.setdefault("search_error", False)
    ss.setdefault("last_query", "")
    ss.setdefault("vm", None)
    ss.setdefault("vm_sig", None)
    ss.setdefault("age", None)
    ss.setdefault("age_unknown", False)
    ss.setdefault("running", False)
    ss.setdefault("developer", False)


def main():
    ss = st.session_state
    init_state(ss)
    css = load_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    rt = get_runtime()
    root = ui_runtime.project_root()
    runs = AR.list_runs(root)
    chosen = ss.get("audit_run_sel")
    run_name = chosen if chosen in runs else (runs[0] if runs else None)
    audit = AR.load_run(root, run_name)
    metrics = AR.load_baseline_metrics(root, audit.get("baseline_run") if audit else None)

    sig = drug_search.current_sig(ss)
    vm_active = ss.vm if (ss.vm is not None and ss.vm_sig == sig) else None
    stale = ss.vm is not None and vm_active is None

    audit_summary = None if not audit else dict(
        run_name=audit["run_name"], option=audit.get("option"), option_text=audit.get("option_text"),
        gates=audit.get("gates"), auto_apply=audit.get("auto_apply"), engine_change_allowed=audit.get("engine_change_allowed"))
    report_md = H.build_report_markdown(vm_active, audit_summary)
    report_js = H.build_report_json(vm_active, audit_summary)

    sidebar.render(st, ss, rt, vm_active, audit, root)
    status_ph = header.render(st, ss, rt, vm_active, runs, audit, report_md, report_js)

    def render_status(ph, running=False):
        code, tone, tip = H.analysis_status(bool(rt and rt.ready), vm_active, running)
        ph.markdown(H.badge(code, tone, tip), unsafe_allow_html=True)

    if rt is not None and not rt.ready:
        st.error(rt.error_user)
        if ss.developer and rt.error_dev:
            st.code(rt.error_dev)
        if st.button("다시 시도", key="retry_load"):
            get_runtime.clear()
            st.rerun()

    def go(page):
        ss.page = page
        st.rerun()

    page = ss.page
    if page == "dashboard":
        c1, c2, c3 = st.columns([3.1, 3.9, 3.0])
        with c1:
            drug_search.render(st, ss, rt, vm_active, status_ph, render_status, prefix="d")
        with c2:
            summary_cards.render_coverage_donut(st, ss, metrics, vm_active)
        with c3:
            summary_cards.render_final(st, vm_active, stale, audit)
        summary_cards.render_kpis(st, vm_active)
        c4, c5 = st.columns([6.8, 3.2])
        with c4:
            gate_timeline.render_card(st, audit, lambda: go("gates"))
        with c5:
            findings.render(st, vm_active, stale)
        c6, c7, c8 = st.columns([4.3, 4.3, 3.4])
        with c6:
            safety_matrix.render(st, vm_active, stale)
        with c7:
            drug_table.render(st, vm_active, stale)
        with c8:
            evidence_panel.render(st, vm_active, stale)
    elif page == "search":
        c1, c2 = st.columns([4, 6])
        with c1:
            drug_search.render(st, ss, rt, vm_active, status_ph, render_status, prefix="p", with_run=True)
        with c2:
            findings.render(st, vm_active, stale)
    elif page == "run":
        pages.render_run_page(st, ss, rt, vm_active, status_ph, render_status)
    elif page == "result":
        pages.render_result_page(st, ss, vm_active, stale, ss.developer)
        evidence_panel.render(st, vm_active, stale)
    elif page == "gates":
        gate_timeline.render_detail_page(st, audit)
    elif page == "coverage":
        coverage_page.render(st, audit, metrics)
    elif page == "report":
        pages.render_report_page(st, vm_active, audit, report_md, report_js)
    elif page == "settings":
        pages.render_settings_page(st, ss, rt, root, audit)

    st.markdown(f'<div class="mg-sub" style="margin-top:14px">{H.esc(H.PROTOTYPE_NOTICE)} {H.esc(H.NO_RULE_NOT_SAFE_NOTE)}</div>',
                unsafe_allow_html=True)


main()

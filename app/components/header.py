"""Main header — title, run selector (real audit runs), execution time, report download, status badge."""
from __future__ import annotations

from app.utils import audit_reader as AR
from app.utils import ui_helpers as H

TITLE = "의약품 안전성 분석"
SUBTITLE = ("DUR 규칙 데이터와 근거 기반 AI 분석을 통해 의약품의 병용 위험, 노인주의, 효능군 중복 등을 검토합니다.")


def status_badge_html(code: str, label: str, tone: str, tip: str) -> str:
    return H.badge(label, tone, tip)


def render(st, ss, rt, vm_active, runs, audit, report_md, report_json):
    """Returns the placeholder holding the status badge (so the runner can show RUNNING while the Core is called)."""
    c_title, c_run, c_time, c_dl, c_stat = st.columns([5.2, 2.4, 1.9, 1.7, 1.5], vertical_alignment="center")
    with c_title:
        st.markdown(f'<h1 class="mg-title">{H.esc(TITLE)}</h1><div class="mg-subtitle">{H.esc(SUBTITLE)}</div>',
                    unsafe_allow_html=True)
    with c_run:
        st.markdown('<div class="mg-hmeta">Audit 실행 기록 (Run)</div>', unsafe_allow_html=True)
        if runs:
            st.selectbox("Audit run", runs, key="audit_run_sel", label_visibility="collapsed",
                         format_func=AR.run_label)
        else:
            st.markdown('<div class="mg-hval">실행 기록 없음</div>', unsafe_allow_html=True)
    with c_time:
        st.markdown('<div class="mg-hmeta">Execution Time</div>', unsafe_allow_html=True)
        el = vm_active.metadata.adapter.get("elapsed_s") if (vm_active is not None and vm_active.metadata) else None
        txt = f"분석 {el}초" if el is not None else ("실행 기록 없음" if not audit else "분석 미실행")
        sub = f'<div class="mg-sub">Audit {H.esc(audit["run_label"])}</div>' if audit else ""
        st.markdown(f'<div class="mg-hval">{H.esc(txt)}</div>{sub}', unsafe_allow_html=True)
    with c_dl:
        st.markdown('<div class="mg-hmeta">Report</div>', unsafe_allow_html=True)
        st.download_button("보고서 다운로드", data=report_md, file_name="medguard_report.md", mime="text/markdown",
                           key="dl_header", disabled=(vm_active is None and not audit), **H.stretch())
    with c_stat:
        st.markdown('<div class="mg-hmeta">Analysis Status</div>', unsafe_allow_html=True)
        ph = st.empty()
        code, label, tone, tip = _status(rt, vm_active, ss)
        ph.markdown(status_badge_html(code, label, tone, tip), unsafe_allow_html=True)
    return ph


def _status(rt, vm_active, ss):
    code, tone, tip = H.analysis_status(bool(rt and rt.ready), vm_active, bool(ss.get("running")))
    return code, code, tone, tip

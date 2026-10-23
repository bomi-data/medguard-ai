"""Pages other than the dashboard grid: 분석 결과 (full detail), 분석 실행, 보고서 생성, 설정."""
from __future__ import annotations

from app import ui_policy as P
from app import ui_render as R
from app.components import drug_search, evidence_panel, findings, safety_matrix, drug_table
from app.utils import ui_helpers as H


def render_result_page(st, ss, vm_active, stale, developer):
    if vm_active is None:
        st.info("입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요." if stale else R.NOT_RUN_TEXT)
        return
    safety_matrix.render(st, vm_active, stale)
    drug_table.render(st, vm_active, stale)
    findings.render(st, vm_active, stale)
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">상세 결과 (Core 결과 전체)</h3>{H.tag("RULE")}</div>',
                    unsafe_allow_html=True)
        R.render_view_model(st, vm_active, developer=developer)
    evidence_panel.render_llm_panel(st, vm_active)


def render_run_page(st, ss, rt, vm_active, status_ph, render_status):
    drug_search.render(st, ss, rt, vm_active, status_ph, render_status, prefix="r", with_run=True)
    st.markdown(f'<div class="mg-note">검사는 기존 Structured Screening Engine을 그대로 호출합니다. '
                f'추정 성분 연결은 적용되지 않으며, 약물 수는 {P.MIN_MEDICATIONS}~{P.MAX_MEDICATIONS}개로 제한됩니다 (MVP 임시 제한).</div>',
                unsafe_allow_html=True)


def render_report_page(st, vm_active, audit, md, js):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">보고서 생성</h3>{H.tag("RULE")}{H.tag("AUDIT")}</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="mg-sub">현재 화면의 분석 결과와 선택한 Audit 실행 기록만 내보냅니다. '
                    '새로운 내용은 생성하지 않으며, 분석을 실행하지 않았다면 그렇게 표시됩니다.</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.download_button("Markdown 다운로드", data=md, file_name="medguard_report.md", mime="text/markdown",
                           key="dl_md", **H.stretch())
        c2.download_button("JSON 다운로드", data=js, file_name="medguard_report.json", mime="application/json",
                           key="dl_json", **H.stretch())
        with st.expander("미리보기", expanded=True):
            st.code(md, language="markdown")


def render_settings_page(st, ss, rt, project_root, audit):
    with st.container(border=True):
        st.markdown('<div class="mg-card-head"><h3 class="mg-card-title">설정 · 시스템 정보</h3></div>', unsafe_allow_html=True)
        st.checkbox("개발자 정보 표시", value=bool(ss.get("developer")), key="dev_mode_w",
                    on_change=lambda: ss.__setitem__("developer", bool(ss.get("dev_mode_w"))))
        theme = None
        try:
            theme = st.get_option("theme.base")
        except Exception:                                    # noqa: BLE001
            pass
        info = [("Project root", str(project_root)), ("Runtime", "READY" if (rt and rt.ready) else "데이터 로딩 실패"),
                ("Device", (rt.runtime_info or {}).get("device") if rt else None),
                ("Adapter", f"{P.ADAPTER_NAME} {P.ADAPTER_VERSION} · {P.CONTRACT_VERSION}"),
                ("Streamlit theme.base", theme or "미설정 (실행 시 --theme.base dark 권장)"),
                ("Audit run", audit["run_name"] if audit else "실행 기록 없음")]
        rows = "".join(f"<tr><td>{H.esc(k)}</td><td>{H.esc(v)}</td></tr>" for k, v in info)
        st.markdown(f'<div class="mg-table-wrap"><table class="mg-table"><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
        if theme != "dark":
            st.warning("테이블(표) 색상은 Streamlit 테마를 따릅니다. 어두운 배경에 맞추려면 --theme.base dark 옵션으로 실행하세요.")
        if rt is not None and not rt.ready and rt.error_dev and ss.get("developer"):
            st.code(rt.error_dev)
        st.markdown(f'<div class="mg-note">{H.esc(H.PROTOTYPE_NOTICE)}</div>', unsafe_allow_html=True)

"""Gate timeline + gate detail. Gates, names and statuses come from the audit result files; a missing gate is
NOT RUN. Only the gates that exist in the audit are drawn (no placeholder stages)."""
from __future__ import annotations

from app import ui_render as R
from app.utils import audit_reader as AR
from app.utils import ui_helpers as H

_TONE = {"PASS": "ok", "WARN": "warn", "FAIL": "danger", "NOT RUN": "neutral"}
_CLS = {"PASS": "pass", "WARN": "warn", "FAIL": "fail", "NOT RUN": "notrun"}


def timeline_html(audit) -> str:
    gates = {k: "NOT RUN" for k in AR.GATE_NAMES} if not audit else audit["gates"]
    out = '<div class="mg-gates">'
    for k, name in AR.GATE_NAMES.items():
        s = gates.get(k, "NOT RUN")
        out += (f'<div class="mg-gate {_CLS[s]}"><div class="mg-gate-circle">{H.esc(k)}</div>'
                f'<div class="mg-gate-name">GATE {H.esc(k)}<br>{H.esc(name)}</div>'
                f'<div class="mg-gate-desc">{H.esc(AR.GATE_DESC[k])}</div>{H.badge(s, _TONE[s])}</div>')
    return out + '</div>'


def render_checks(st, audit, gate_key, key_prefix="gd"):
    checks = (audit or {}).get("gate_checks", {}).get(gate_key, [])
    complete = (audit or {}).get("gate_checks_complete", {}).get(gate_key, False)
    if not checks:
        st.markdown('<div class="mg-empty">표시할 검사 항목이 결과 파일에 없습니다.</div>', unsafe_allow_html=True)
    for i, c in enumerate(checks):
        head = f'{c["name"]}'
        with st.expander(f'[{c["status"]}] {head}'):
            st.markdown(f"**Gate / Check**: GATE {gate_key} · " + R._md(c["name"]))
            st.markdown(f'**Status**: {c["status"]}')
            st.markdown("**Description**: " + R._md(c.get("description") or "결과 파일에 저장된 설명 없음"))
            st.markdown("**Evidence**: " + R._md(c.get("evidence") or "결과 파일에 저장된 근거 없음"))
            if c.get("status") == "WARN":
                st.warning(R._md(c.get("warning") or "경고 내용 없음"))
            elif c.get("status") == "FAIL":
                st.error(R._md(c.get("failure") or "실패 사유가 결과 파일에 없음"))
            else:
                st.markdown("**Warning / Failure Reason**: 해당 없음 (PASS)")
            if c.get("explanation"):
                st.caption(R._md(c["explanation"]))
    if not complete:
        st.caption("이 Gate는 PASS 항목의 상세가 결과 파일에 저장되어 있지 않아, 기록된 경고·실패 항목만 표시됩니다.")


def render_card(st, audit, go_detail):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">게이트별 결과 현황</h3>{H.tag("AUDIT")}</div>',
                    unsafe_allow_html=True)
        if not audit:
            st.markdown('<div class="mg-empty">Audit 실행 기록 없음 — 모든 Gate는 NOT RUN으로 간주됩니다.</div>',
                        unsafe_allow_html=True)
        st.markdown(timeline_html(audit), unsafe_allow_html=True)
        st.markdown(f'<div class="mg-note">{H.esc(H.GATE_NOT_CLINICAL_NOTE)}</div>', unsafe_allow_html=True)
        if st.button("Gate 상세 보기", key="gate_detail_btn"):
            go_detail()


def render_detail_page(st, audit):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">게이트별 상세</h3>{H.tag("AUDIT")}</div>',
                    unsafe_allow_html=True)
        st.markdown(timeline_html(audit), unsafe_allow_html=True)
        st.markdown(f'<div class="mg-note">{H.esc(H.GATE_NOT_CLINICAL_NOTE)}</div>', unsafe_allow_html=True)
    if not audit:
        st.info("Audit 실행 기록이 없어 Gate 상세를 표시할 수 없습니다.")
        return
    tabs = st.tabs([f"GATE {k} · {n}" for k, n in AR.GATE_NAMES.items()])
    for (k, n), tab in zip(AR.GATE_NAMES.items(), tabs):
        with tab:
            st.markdown(f'{H.badge(audit["gates"][k], _TONE[audit["gates"][k]])} <span class="mg-sub">{H.esc(AR.GATE_DESC[k])}</span>',
                        unsafe_allow_html=True)
            render_checks(st, audit, k)

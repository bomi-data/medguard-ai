"""'주요 발견 사항' — only real findings and ViewModel-reported gaps; each row opens its evidence details."""
from __future__ import annotations

from app import ui_render as R
from app.utils import ui_helpers as H


def _detail(st, vm, row):
    if row.kind == "finding":
        f = next((x for x in vm.findings if x.finding_id == row.finding_id), None)
        if f is None:
            st.write("상세 정보를 찾을 수 없습니다 (확인 불가).")
            return
        dbg = next((d for d in vm.debug.findings if d["finding_id"] == f.finding_id), {})
        ret = (dbg.get("retrieval") or {})
        snap = vm.metadata.core.get("data_snapshot")
        st.markdown(f"**관련 제품**: " + R._md(", ".join(f"{d.display_name} ({d.item_seq})" for d in f.drugs)))
        st.markdown(f"**규칙 유형**: {f.risk_label}")
        st.markdown(f"**규칙 출처**: {R._md(f.rule_source) if f.rule_source else '확인 불가'}")
        ids = ", ".join(d.item_seq for d in f.drugs)
        extra = f.canonical_pair_id or f.effect_name
        st.markdown(f"**적용된 식별자**: itemSeq {ids}" + (f" · {R._md(extra)}" if extra else ""))
        st.markdown(f"**원본 근거 ({f.dur_rule_label})**")
        for ln in f.dur_rule_lines:
            st.markdown(f"> {R._md(ln)}")
        st.markdown("**데이터 버전**: " + (R._md(str(snap)) if snap else "확인 불가 (결과에 데이터 버전 정보 없음)"))
        st.markdown("**조회 상태**: " + (R._md(f"근거 검색 {ret.get('status')}" + (f" ({ret.get('reason')})" if ret.get("reason") else ""))
                                      if ret else "확인 불가"))
        for n in f.retrieval_notices:
            st.info(n)
        if f.explanation is None and f.status_message:
            st.warning(f.status_message)
        st.caption(f.clinician_review_text)
    elif row.kind == "not_in_data":
        st.markdown("**규칙 데이터 미포함**: 이 약물은 DUR 규칙 테이블에 없어 병용금기·노인주의·효능군 중복 규칙 검사 대상이 아닙니다.")
        st.markdown("**의미**: 규칙이 없다는 것은 안전하다는 뜻이 아니라 **판단 근거가 없다**는 뜻입니다.")
        st.markdown("**식별자**: itemSeq " + ", ".join(row.item_seqs))
        st.markdown("**원본 근거**: 근거 없음")
    else:
        st.markdown(R._md(row.desc))
        st.markdown("**조회 상태**: 판단 불가 (평가하지 않음)")


def render(st, vm_active, stale):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">주요 발견 사항</h3>{H.tag("RULE")}</div>',
                    unsafe_allow_html=True)
        if vm_active is None:
            msg = "입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요." if stale else "아직 검사를 실행하지 않았습니다."
            st.markdown(f'<div class="mg-empty">{H.esc(msg)}</div>', unsafe_allow_html=True)
            return
        if not vm_active.can_display_results:
            for i in vm_active.input_issues:
                st.warning(R._md(i.message))
            st.markdown('<div class="mg-empty">결과를 표시할 수 없는 상태입니다. 위험이 없다는 의미가 아닙니다.</div>',
                        unsafe_allow_html=True)
            return
        rows = H.finding_rows(vm_active)
        if not rows:
            st.markdown(f'<div class="mg-empty">{H.esc(vm_active.no_finding.message if vm_active.no_finding else "표시할 항목이 없습니다.")}'
                        f'<br><span class="mg-sub">{H.esc(H.NO_RULE_NOT_SAFE_NOTE)}</span></div>', unsafe_allow_html=True)
            return
        for i, r in enumerate(rows, 1):
            left, right = st.columns([6, 2.2], vertical_alignment="center")
            with left:
                st.markdown(f'<div class="mg-row" style="border:0;padding:6px 0"><div class="mg-row-n">{i}</div><div class="mg-row-body">'
                            f'<div class="mg-row-title">{H.esc(r.title)}</div><div class="mg-row-desc">{H.esc(r.desc)}</div>'
                            f'<div style="margin-top:5px">{H.badge(r.badge_text, r.badge_tone)}</div></div></div>',
                            unsafe_allow_html=True)
            with right:
                with st.popover("상세", **H.stretch()):
                    _detail(st, vm_active, r)

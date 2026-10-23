"""Drug search + selection card and the analysis runner. Backend: existing drug_lookup (via ui_runtime) and
adapters.run_safety_check_view → Frozen Core. Only search modes the engine supports are enabled
(product-name substring, 9-digit itemSeq). Nothing is auto-selected; the user clicks 추가."""
from __future__ import annotations

from app import adapters
from app import ui_render as R
from app.utils import ui_helpers as H

SEARCH_PLACEHOLDER = "제품명 또는 9자리 제품식별번호(itemSeq)를 입력하세요."
SEARCH_SCOPE_CAPTION = ("검색은 제품명(부분 일치)과 9자리 품목기준코드(itemSeq)만 지원합니다. "
                        "성분명 검색은 현재 엔진에서 지원하지 않아 비활성화했습니다.")


def current_sig(ss):
    return (bool(ss.get("age_unknown")), ss.get("age"), tuple(ss.selection.items))


def _sync_age(prefix):
    import streamlit as st
    ss = st.session_state
    ss["age"] = ss.get(f"{prefix}_age")


def _sync_unknown(prefix):
    import streamlit as st
    ss = st.session_state
    ss["age_unknown"] = bool(ss.get(f"{prefix}_age_unknown"))


def render_patient_inputs(st, ss, prefix):
    c1, c2 = st.columns([1.2, 1.4], vertical_alignment="bottom")
    unknown = bool(ss.get("age_unknown"))
    with c2:
        st.checkbox("나이를 모릅니다", value=unknown, key=f"{prefix}_age_unknown", on_change=_sync_unknown, args=(prefix,))
    with c1:
        if not bool(ss.get(f"{prefix}_age_unknown", unknown)):
            st.number_input("나이 (세)", min_value=0, max_value=150, value=ss.get("age"), step=1, key=f"{prefix}_age",
                            placeholder="예: 72", on_change=_sync_age, args=(prefix,))
        else:
            ss["age"] = None


def run_check(st, ss, rt, status_ph=None, render_status=None):
    """Call the existing adapter → Core exactly as the first UI does. No screening logic here."""
    sig = current_sig(ss)
    ss.running = True
    if status_ph is not None and render_status is not None:
        render_status(status_ph, running=True)
    try:
        with st.spinner("DUR 안전성 검사 중입니다…"):
            ss.vm = adapters.run_safety_check_view(
                {"age": ss.get("age"), "age_unknown": bool(ss.get("age_unknown"))}, ss.selection,
                core_fn=rt.core_fn, resources_module=rt.resources_module, runtime_info=rt.runtime_info)
            ss.vm_sig = sig
    finally:
        ss.running = False
    st.rerun()


def _do_search(ss, rt, query):
    ss.search_error = False
    ss.candidates = None
    ss.last_query = query
    if query and query.strip():
        try:
            res = rt.search(query)
            ss.selection.register_search(res)
            ss.candidates = res
        except Exception:                                    # noqa: BLE001
            ss.search_error = True


def render_candidates(st, ss, rt, prefix):
    state = H.query_state(ss.get("last_query"), ss.candidates, bool(rt and rt.ready), bool(ss.get("search_error")))
    if ss.get("search_error"):
        st.error(R.SEARCH_FAILED_TEXT)
    if ss.candidates is None and not ss.get("search_error"):
        return
    if state is not None:
        label, tone = H.SEARCH_STATES[state]
        st.markdown(H.badge(label, tone), unsafe_allow_html=True)
        if state == "NOT_SEARCHABLE":
            st.caption(R.SEARCH_NO_RESULT_TEXT)
        elif state == "ID_UNCONFIRMED":
            st.caption("입력한 번호가 이 시스템의 약물 목록에서 확인되지 않습니다. 9자리 품목기준코드를 다시 확인하세요.")
        return
    cands = ss.candidates.get("candidates") or []
    if ss.candidates.get("truncated"):
        st.caption(R.SEARCH_TRUNCATED_TEMPLATE.format(n=ss.candidates.get("n_matches"), shown=len(cands)))
    box = st.container(height=270) if len(cands) > 3 else st.container()
    for c in cands:
        label, tone = H.SEARCH_STATES[H.candidate_state(c)]
        left, right = box.columns([5, 1.6], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div class="mg-cand"><div class="mg-cand-name">{H.esc(c.get("item_name") or c["item_seq"])}</div>'
                f'<div class="mg-cand-meta">itemSeq {H.esc(c["item_seq"])} · 성분 정보: 검색 결과에 없음</div>'
                f'{H.badge(label, tone)}</div>', unsafe_allow_html=True)
        with right:
            if st.button("추가", key=f"add_{prefix}_{c['item_seq']}", **H.stretch()):
                ss.selection.add(c["item_seq"])
                st.rerun()


def render_selected(st, ss, vm_active):
    items = ss.selection.items
    st.markdown(f'<div class="mg-sub"><b>선택한 의약품 {len(items)}개</b></div>', unsafe_allow_html=True)
    ing = H.ingredient_map(vm_active)
    if not items:
        st.markdown('<div class="mg-empty">선택한 의약품이 없습니다.<br>검색 후 목록에서 \'추가\'를 누르세요.</div>',
                    unsafe_allow_html=True)
        return
    for i, s in enumerate(items):
        name = ss.selection.name_of(s) or s
        ingr = ", ".join(ing[s]) if s in ing else "확인 불가 (검사 결과에서 확인)"
        left, right = st.columns([5, 1.7], vertical_alignment="center")
        with left:
            st.markdown(f'<div class="mg-med"><div class="mg-med-n">{i + 1}</div><div>'
                        f'<div class="mg-med-name">{H.esc(name)}</div>'
                        f'<div class="mg-med-meta">성분: {H.esc(ingr)}<br>제품식별번호: {H.esc(s)}</div></div></div>',
                        unsafe_allow_html=True)
        with right:
            if st.button("삭제", key=f"rm_{i}_{s}", **H.stretch()):
                ss.selection.remove(i)
                st.rerun()
    if st.button("전체 삭제", key="clear_all"):
        ss.selection.clear()
        st.rerun()
    dups = ss.selection.duplicates()
    if dups:
        st.warning(R.DUPLICATE_WARNING_TEMPLATE.format(items=", ".join(dups)))


def render(st, ss, rt, vm_active, status_ph, render_status, prefix="d", with_run=True):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">의약품 검색 및 선택</h3></div>',
                    unsafe_allow_html=True)
        if not (rt and rt.ready):
            st.error(rt.error_user if rt else "런타임을 불러오지 못했습니다.")
            st.markdown(H.badge(*H.SEARCH_STATES["LOAD_FAILED"]), unsafe_allow_html=True)
        q = st.text_input("검색어", key=f"{prefix}_query", placeholder=SEARCH_PLACEHOLDER,
                          label_visibility="collapsed", disabled=not (rt and rt.ready))
        if st.button("검색", key="search_btn" if prefix == "d" else "search_btn_p", **H.stretch(),
                     disabled=not (rt and rt.ready)):
            _do_search(ss, rt, q)
        st.caption(SEARCH_SCOPE_CAPTION)
        render_candidates(st, ss, rt, prefix)
        st.markdown('<hr/>', unsafe_allow_html=True)
        render_selected(st, ss, vm_active)
        st.markdown('<hr/>', unsafe_allow_html=True)
        render_patient_inputs(st, ss, prefix)
        if with_run:
            key = {"d": "run_check", "p": "run_check_p"}.get(prefix, "run_check_r")
            if st.button("DUR 안전성 검사 실행", key=key, **H.stretch(), disabled=not (rt and rt.ready)):
                run_check(st, ss, rt, status_ph, render_status)
        st.markdown(f'<div class="mg-sub">{H.esc(H.NO_RULE_NOT_SAFE_NOTE)}</div>', unsafe_allow_html=True)

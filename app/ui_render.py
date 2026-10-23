"""Streamlit rendering of the ViewModel (STEP 6). Presentation only.

Rules (docs/STREAMLIT_UI.md §3):
  * Branch ONLY on vm.state / vm.can_display_results / FindingView.display_mode and on whether
    explanation / evidence are None. Never read the raw Core report, never recompute counts.
  * Never use st.success (a green "OK" next to screening results can read as "safe").
  * Structured Screening content of every finding card is rendered in every display_mode.
  * LLM text appears only through FindingView.explanation (set by the Adapter only in EXPLANATION mode).
"""
from __future__ import annotations

from app import ui_policy as P

# ---- UI-only texts (input stage; no medical meaning) -------------------------------------------------
SEARCH_NO_RESULT_TEXT = ("검색 결과가 없습니다. 제품명 일부 또는 9자리 품목기준코드(item_seq)로 다시 검색하세요. "
                         "검색되지 않는 약물은 이 시스템에서 검사할 수 없습니다.")
SEARCH_TRUNCATED_TEMPLATE = "검색 결과 {n}건 중 {shown}건만 표시합니다. 검색어를 더 구체적으로 입력하세요."
SEARCH_FAILED_TEXT = "약물 검색 중 오류가 발생했습니다. 잠시 후 다시 시도하세요."
CANDIDATE_NOT_IN_DUR_TEXT = "DUR 규칙 데이터 미포함 — 규칙 검사 대상이 아님"
DUPLICATE_WARNING_TEMPLATE = "같은 제품이 중복 선택되었습니다: {items}. 중복 항목을 삭제한 뒤 검사하세요."
STALE_RESULT_TEXT = "입력이 변경되었습니다. 이전 결과는 숨겼습니다. 다시 검사하세요."
NOT_RUN_TEXT = "아직 검사를 실행하지 않았습니다."
RESULT_STATE_TITLE = {
    P.STATE_INPUT_INVALID: "입력값 오류 — 검사가 실행되지 않았습니다",
    P.STATE_RESOURCE_ERROR: "검사 시스템 준비 안 됨 — 결과 없음",
    P.STATE_CORE_ERROR: "검사 실행 오류 — 결과 없음",
    P.STATE_REPORT_INVALID: "결과 형식 오류 — 결과를 표시할 수 없음",
    P.STATE_REPORT_INCONSISTENT: "결과 일관성 오류 — 결과를 표시할 수 없음",
}
NO_RESULT_IS_NOT_SAFE_TEXT = "결과를 표시할 수 없는 상태입니다. 위험이 없다는 의미가 아닙니다."
CITED_MARK = "설명에서 인용됨"


_MD_SPECIAL = "\\`*_{}[]()#+-.!|<>~"


def _md(text):
    """Escape Markdown so Core / LLM / data text is shown verbatim (no formatting injected or lost)."""
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in str(text))


def _sev(st, severity, text):
    (st.error if severity == "error" else st.warning)(text)


def render_errors_only(st, vm):
    """Result screen when vm.can_display_results is False (L0–L3)."""
    st.error(RESULT_STATE_TITLE.get(vm.state, "결과를 표시할 수 없습니다"))
    for e in vm.errors:
        st.error(e.user_message)
    for i in vm.input_issues:
        st.warning(i.message)
    st.caption(NO_RESULT_IS_NOT_SAFE_TEXT)


def render_summary(st, vm):
    s = vm.summary
    if s.llm_unavailable_banner:
        st.error(s.llm_unavailable_banner)
    elif any(e.layer == P.L4_FINDING for e in vm.errors):
        st.warning(P.ERROR_MESSAGES["FINDING_PROCESSING_ERROR"])
    cols = st.columns(len(s.tiles) + 1)
    for col, t in zip(cols, s.tiles):
        col.metric(f"{t.icon} {t.label}", t.display_text)
    cols[-1].metric("전체 탐지 신호", f"{s.total_signals}건")
    st.caption(s.legend)


def render_patient_and_meds(st, vm):
    p = vm.patient
    st.markdown(f"**나이:** {p.age_display}  ·  **노인주의 평가:** {p.elderly.label}")
    if p.elderly.message:
        st.info(p.elderly.message)
    st.markdown("**검사한 약물**")
    for m in vm.medications:
        tail = "" if m.in_dur_tables else f"  — {CANDIDATE_NOT_IN_DUR_TEXT}"
        st.markdown(f"- {_md(m.display_name)} ({_md(m.item_seq)}){_md(tail)}")
    for n in vm.notices:
        if n.code == "ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING":
            continue                                      # already shown as elderly message
        items = f" ({', '.join(n.item_seqs)})" if n.item_seqs else ""
        (st.warning if n.level == "warning" else st.info)(n.message + items)


def render_evidence(st, ev):
    st.markdown(f"**{ev.title}**")
    for e in ev.items:
        head = f"[{e.evidence_id}] {e.display_name} · {e.location}"
        if e.cited:
            head += f"  — {CITED_MARK}"
        with st.expander(head):
            if e.license_badge:
                st.warning(e.license_badge)
            st.text(e.chunk_text)
            meta = [f"출처: {e.evidence_source}"]
            if e.change_date:
                meta.append(f"변경일: {e.change_date}")
            if e.shared_item_seqs:
                meta.append("같은 원문을 공유하는 품목: " + ", ".join(e.shared_item_seqs))
            st.caption(" · ".join(meta))


def render_finding(st, f):
    with st.container(border=True):
        st.subheader(f"{f.risk_icon} {f.risk_label}")
        if f.rule_source:
            st.caption(f"근거 규칙: {_md(f.rule_source)}")
        # [Structured Screening] — always shown, independent of LLM status
        if f.risk_type == "contraindication" and len(f.drugs) == 2:
            st.markdown(f"**{_md(f.drugs[0].display_name)}** ↔ **{_md(f.drugs[1].display_name)}**")
        else:
            st.markdown("  ·  ".join(f"**{_md(d.display_name)}**" for d in f.drugs))
        if f.effect_name:
            st.markdown(f"효능군: {_md(f.effect_name)}")
        for d in f.drugs:
            if d.ingredient_names:
                st.caption(f"{_md(d.display_name)} 성분: {_md(', '.join(d.ingredient_names))}")
        st.markdown(f"**{f.dur_rule_label}**")
        for line in f.dur_rule_lines:
            st.markdown(f"> {_md(line)}")
        for n in f.retrieval_notices:
            st.info(n)
        # [근거 기반 설명 (자동 생성)]
        st.markdown(f"**{f.explanation_title}**")
        x = f.explanation
        if x is not None:
            st.markdown(_md(x.summary))
            for s in x.statements:
                st.markdown(f"- {_md(s.text)}")
            if x.no_statements_text:
                st.caption(x.no_statements_text)
            st.caption(x.evidence_status_label, help=x.evidence_status_tooltip)
            if x.limitations:
                st.markdown(f"한계: {_md(x.limitations)}")
            st.caption(x.review_note)
        else:
            _sev(st, f.status_severity, f.status_message)
        st.caption(f.clinician_review_text)
        # [허가정보 원문]
        if f.evidence is not None:
            render_evidence(st, f.evidence)


def render_footer(st, vm):
    st.divider()
    if vm.scope_note and vm.no_finding is None:
        st.caption(vm.scope_note)
    st.caption(vm.input_scope_note)
    c, a = vm.metadata.core, vm.metadata.adapter
    parts = []
    if c.get("pipeline_name"):
        parts.append(f"{c['pipeline_name']} {c.get('pipeline_version')}")
    if c.get("generation"):
        g = c["generation"]
        parts.append(f"생성 모델 {g.get('model')} · prompt {g.get('prompt_version')}")
    if a.get("elapsed_s") is not None:
        parts.append(f"검사 소요 {a['elapsed_s']}초")
    if parts:
        st.caption(" | ".join(parts))
    if a.get("device_note"):
        st.caption(f"실행 장치: {a.get('device')} ({a['device_note']})")
    st.caption(a.get("medication_limit_note", ""))


def render_view_model(st, vm, developer=False):
    if not vm.can_display_results:
        render_errors_only(st, vm)
    else:
        render_summary(st, vm)
        render_patient_and_meds(st, vm)
        if vm.no_finding is not None:
            st.info(vm.no_finding.message)
            st.caption(vm.no_finding.scope_note)
        for f in vm.findings:
            render_finding(st, f)
        render_footer(st, vm)
    if developer:
        with st.expander("개발자 정보 (debug)"):
            st.json(vm.to_dict(include_debug=True))

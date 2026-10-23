"""'관련 근거 자료 (RAG)' — only documents the existing retrieval actually returned. LLM text is shown in a
separate panel, labelled, never mixed with the original evidence."""
from __future__ import annotations

from app import ui_render as R
from app.utils import ui_helpers as H


def _doc_detail(st, d):
    st.markdown(f"{H.tag('EVIDENCE')}", unsafe_allow_html=True)
    st.markdown("**원문 발췌 (검색된 Chunk)**")
    st.text(d["chunk_text"])
    st.markdown("**출처**: " + R._md(d["source"]))
    st.markdown("**관련 약물**: " + R._md(d["related"]) + f" · {R._md(d['risk_label'])}")
    ids = [f"evidence_id {d['evidence_id']}"]
    if d.get("document_id"):
        ids.append(f"document_id {d['document_id']}")
    if d.get("chunk_id"):
        ids.append(f"chunk_id {d['chunk_id']}")
    st.markdown("**문서 식별자**: " + R._md(" · ".join(ids)))
    ranks = {k: d.get(k) for k in ("hybrid_rank", "bm25_rank", "dense_rank") if d.get(k) is not None}
    st.markdown("**Retrieval 순위**: " + (R._md(", ".join(f"{k}={v}" for k, v in ranks.items())) if ranks
                                         else "확인 불가 (Retrieval Score는 결과에 포함되지 않음)"))
    if d.get("change_date"):
        st.markdown("**변경일**: " + R._md(d["change_date"]))
    if d.get("shared"):
        st.caption("같은 원문을 공유하는 품목: " + R._md(", ".join(d["shared"])))
    if d.get("license_badge"):
        st.warning(d["license_badge"])
    if d.get("cited"):
        st.caption(R.CITED_MARK)


def render(st, vm_active, stale):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">관련 근거 자료 (RAG)</h3>{H.tag("EVIDENCE")}</div>',
                    unsafe_allow_html=True)
        docs = H.evidence_docs(vm_active)
        if vm_active is None or not docs:
            msg = ("입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요." if stale
                   else "현재 검색된 근거 자료가 없습니다.")
            st.markdown(f'<div class="mg-empty">{H.esc(msg)}</div>', unsafe_allow_html=True)
            return
        for i, d in enumerate(docs[:12]):
            left, right = st.columns([5, 2.2], vertical_alignment="center")
            with left:
                date = f" · 변경일 {H.esc(d['change_date'])}" if d.get("change_date") else ""
                st.markdown(f'<div class="mg-row" style="border:0;padding:5px 0"><span class="mg-doc-ico">{H.icon("doc", 20)}</span>'
                            f'<div class="mg-row-body"><div class="mg-row-title">{H.esc(d["title"])}</div>'
                            f'<div class="mg-doc-meta">출처 {H.esc(d["source"])}{date} · 유형 {H.esc(d["ev_type"])}</div></div></div>',
                            unsafe_allow_html=True)
            with right:
                with st.popover("상세", **H.stretch()):
                    _doc_detail(st, d)
        if len(docs) > 12:
            st.caption(f"근거 {len(docs)}건 중 12건만 표시합니다. 전체는 '분석 결과'에서 확인하세요.")


def render_llm_panel(st, vm_active):
    """Separate panel for LLM-generated explanations (present only when the Adapter allowed EXPLANATION mode)."""
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">LLM 설명 (자동 생성)</h3>{H.tag("LLM")}</div>',
                    unsafe_allow_html=True)
        if vm_active is None or not vm_active.can_display_results:
            st.markdown('<div class="mg-empty">표시할 설명이 없습니다.</div>', unsafe_allow_html=True)
            return
        shown = False
        for f in vm_active.findings:
            if f.explanation is None:
                continue
            shown = True
            x = f.explanation
            st.markdown(f"**{R._md(f.risk_label)}** — " + R._md(" + ".join(d.display_name for d in f.drugs)))
            st.markdown(R._md(x.summary))
            for s in x.statements:
                st.markdown(f"- {R._md(s.text)} ({R._md(', '.join(s.evidence_ids))})")
            st.caption(x.evidence_status_label, help=x.evidence_status_tooltip)
            if x.limitations:
                st.markdown("한계: " + R._md(x.limitations))
            st.caption(x.review_note)
        if not shown:
            st.markdown('<div class="mg-empty">검증을 통과한 자동 생성 설명이 없습니다. '
                        '(설명이 생성되지 않았거나 검증 단계에서 표시가 보류됨) 탐지 결과와 원문 근거를 직접 확인하세요.</div>',
                        unsafe_allow_html=True)
        st.caption("자동 생성 설명은 DUR 원문이 아니며, 위 '관련 근거 자료'의 원문과 구분해서 보세요.")

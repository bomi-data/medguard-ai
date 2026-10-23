"""'선택 의약품 상세 정보' — sortable / filterable dark table with row selection and a detail expansion."""
from __future__ import annotations

import pandas as pd

from app import ui_render as R
from app.utils import ui_helpers as H

COLS = ["제품명", "성분명", "itemSeq", "주요 발견 사항", "DUR 포함 상태", "분석 상태"]
_FIND_COLOR = {"병용금기": ("rgba(255,100,124,0.20)", "#FF647C"), "노인주의": ("rgba(255,188,85,0.20)", "#FFBC55"),
               "효능군 중복": ("rgba(54,135,255,0.22)", "#6FA8FF"), "규칙 데이터 미포함": ("rgba(112,133,163,0.22)", "#9BAFCB"),
               "데이터 미포함": ("rgba(112,133,163,0.22)", "#9BAFCB"), "규칙 검사 대상 아님": ("rgba(132,87,255,0.20)", "#A98BFF")}


def _style(df):
    def one(v):
        s = str(v)
        for k, (bg, fg) in _FIND_COLOR.items():
            if k in s:
                return f"background-color:{bg};color:{fg};font-weight:600"
        return ""
    return df.style.map(one, subset=["주요 발견 사항", "DUR 포함 상태", "분석 상태"])


def render(st, vm_active, stale):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">선택 의약품 상세 정보</h3>{H.tag("RULE")}</div>',
                    unsafe_allow_html=True)
        rows = H.drug_table_rows(vm_active)
        if not rows:
            msg = "입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요." if stale else "검사 결과가 없습니다."
            st.markdown(f'<div class="mg-empty">{H.esc(msg)}</div>', unsafe_allow_html=True)
            return
        df = pd.DataFrame(rows, columns=COLS)
        opts = sorted(set(df["DUR 포함 상태"]))
        pick = st.multiselect("DUR 포함 상태 필터", opts, default=opts, key="tbl_filter")
        view = df[df["DUR 포함 상태"].isin(pick)].reset_index(drop=True)
        selected = None
        try:
            ev = st.dataframe(_style(view), **H.stretch(), hide_index=True, key="drug_tbl",
                              on_select="rerun", selection_mode="single-row")
            idx = list(ev.selection.rows) if ev is not None else []
            selected = idx[0] if idx else None
        except TypeError:                                    # older Streamlit: no row selection
            st.dataframe(_style(view), **H.stretch(), hide_index=True)
            names = list(view["제품명"])
            choice = st.selectbox("상세 보기 약물", ["선택 안 함"] + names, key="tbl_choice")
            selected = None if choice == "선택 안 함" else names.index(choice)
        st.caption("열 제목을 눌러 정렬하고, 행을 선택하면 상세가 아래에 펼쳐집니다. 표는 가로로 스크롤됩니다.")
        if selected is not None and selected < len(view):
            r = view.iloc[selected]
            with st.expander(f"상세: {r['제품명']}", expanded=True):
                st.markdown(f"**제품명**: {R._md(r['제품명'])}")
                st.markdown(f"**성분명**: {R._md(r['성분명'])}")
                st.markdown(f"**itemSeq**: {R._md(r['itemSeq'])}")
                st.markdown(f"**주요 발견 사항**: {R._md(r['주요 발견 사항'])}")
                st.markdown(f"**DUR 포함 상태**: {R._md(r['DUR 포함 상태'])}")
                if r["DUR 포함 상태"] == "데이터 미포함":
                    st.info("규칙 데이터 미포함은 안전하다는 뜻이 아니라 판단 근거가 없다는 뜻입니다.")

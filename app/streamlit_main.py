"""DUR Polypharmacy Safety — Streamlit UI (STEP 6). Entry point: `streamlit run app/streamlit_main.py`.

Flow:  input widgets → MedicationSelection (only candidates the user clicked) → adapters.run_safety_check_view
       → SafetyCheckViewModel → app.ui_render.render_view_model.
No medical logic here: validation is the Input Adapter's, results come only from the ViewModel.
The previous skeleton (app/streamlit_app.py, STEP 1–5) is kept unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

from app import adapters, ui_render as R, ui_runtime  # noqa: E402

st.set_page_config(page_title="DUR 다약제 안전성 검토", page_icon="💊", layout="wide")


@st.cache_resource(show_spinner="DUR 데이터와 검색 모델을 불러오는 중입니다 (처음 1회, 수 분 소요)…")
def get_runtime():
    return ui_runtime.load_runtime()


ss = st.session_state
ss.setdefault("selection", adapters.MedicationSelection())
ss.setdefault("candidates", None)
ss.setdefault("search_error", False)
ss.setdefault("vm", None)
ss.setdefault("vm_sig", None)

with st.sidebar:
    developer = st.checkbox("개발자 정보 표시", key="dev_mode")
    st.caption("연구·교육용 프로토타입입니다. 실제 처방·복약 변경 판단에 사용하지 마세요.")

st.title("💊 DUR 기반 다약제 복용 안전성 검토")
st.caption("식약처 DUR 규칙(병용금기·노인주의·효능군 중복) 탐지 결과와 허가정보 근거를 보여 줍니다. "
           "최종 판단은 의료진의 검토가 필요합니다.")

rt = get_runtime()
if not rt.ready:
    st.error(rt.error_user)
    if developer and rt.error_dev:
        st.code(rt.error_dev)
    if st.button("다시 시도", key="retry_load"):
        get_runtime.clear()
        st.rerun()

# ---------------------------------------------------------------- 1. patient
st.header("1. 환자 정보")
age_unknown = st.checkbox("나이를 모릅니다", key="age_unknown")
age = None
if not age_unknown:
    age = st.number_input("나이 (세)", min_value=0, max_value=150, value=None, step=1, key="age",
                          placeholder="예: 72")

# ---------------------------------------------------------------- 2. medications
st.header("2. 복용 약물")
q = st.text_input("약물 검색 (제품명 또는 9자리 품목기준코드)", key="search_query", disabled=not rt.ready)
if st.button("검색", key="search_btn", disabled=not rt.ready):
    ss.search_error = False
    ss.candidates = None
    if q and q.strip():
        try:
            res = rt.search(q)
            ss.selection.register_search(res)
            ss.candidates = res
        except Exception:  # noqa: BLE001
            ss.search_error = True

if ss.search_error:
    st.error(R.SEARCH_FAILED_TEXT)
elif ss.candidates is not None:
    cands = ss.candidates.get("candidates") or []
    if not cands:
        st.info(R.SEARCH_NO_RESULT_TEXT)
    else:
        if ss.candidates.get("truncated"):
            st.caption(R.SEARCH_TRUNCATED_TEMPLATE.format(n=ss.candidates.get("n_matches"), shown=len(cands)))
        for c in cands:
            c1, c2 = st.columns([5, 1])
            badge = "" if c.get("in_dur_tables") else f"  — {R.CANDIDATE_NOT_IN_DUR_TEXT}"
            c1.markdown(f"{R._md(c.get('item_name') or c['item_seq'])} ({R._md(c['item_seq'])}){R._md(badge)}")
            if c2.button("추가", key=f"add_{c['item_seq']}"):
                ss.selection.add(c["item_seq"])

items = ss.selection.items
st.subheader(f"선택한 약물 ({len(items)}개)")
if not items:
    st.caption("선택한 약물이 없습니다. 검색 후 '추가'를 누르세요.")
for i, s in enumerate(items):
    c1, c2 = st.columns([5, 1])
    c1.markdown(f"{i + 1}. {R._md(ss.selection.name_of(s) or s)} ({R._md(s)})")
    if c2.button("삭제", key=f"remove_{i}"):
        ss.selection.remove(i)
        st.rerun()
dups = ss.selection.duplicates()
if dups:
    st.warning(R.DUPLICATE_WARNING_TEMPLATE.format(items=", ".join(dups)))

# ---------------------------------------------------------------- 3. run
st.header("3. 안전성 검사")
sig = (bool(age_unknown), age, tuple(ss.selection.items))
if st.button("안전성 검사 실행", key="run_check", type="primary", disabled=not rt.ready):
    with st.spinner("검사 중입니다…"):
        ss.vm = adapters.run_safety_check_view(
            {"age": age, "age_unknown": bool(age_unknown)}, ss.selection,
            core_fn=rt.core_fn, resources_module=rt.resources_module, runtime_info=rt.runtime_info)
        ss.vm_sig = sig

# ---------------------------------------------------------------- 4. result
st.header("4. 검사 결과")
if ss.vm is None:
    st.caption(R.NOT_RUN_TEXT)
elif ss.vm_sig != sig:
    st.info(R.STALE_RESULT_TEXT)
else:
    R.render_view_model(st, ss.vm, developer=developer)

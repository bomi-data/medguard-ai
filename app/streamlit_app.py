
import streamlit as st

st.set_page_config(
    page_title="DUR Polypharmacy Safety",
    page_icon="💊",
    layout="wide"
)

st.title("💊 DUR 기반 다약제 복용 안전성 검사")

st.caption(
    "한국 DUR 데이터를 활용한 약물 안전성 검토 및 근거 기반 설명 시스템"
)

st.warning(
    "본 시스템은 연구 및 교육용 프로토타입입니다. "
    "실제 처방이나 복약 변경을 위한 의료적 판단에 사용해서는 안 됩니다."
)

st.divider()

# -----------------------------
# 환자 정보
# -----------------------------

st.header("1. 환자 정보")

age_unknown = st.checkbox("나이를 모릅니다.")

age = None

if not age_unknown:

    age = st.number_input(
        "환자 나이",
        min_value=0,
        max_value=150,
        value=65,
        step=1
    )

st.divider()

# -----------------------------
# 약물 선택
# -----------------------------

st.header("2. 복용 약물")

drug_query = st.text_input(
    "약물 검색",
    placeholder="약물 이름을 입력하세요"
)

st.info(
    "현재는 UI 기본 구조만 구현된 상태입니다. "
    "실제 DUR 약물 검색은 다음 단계에서 연결합니다."
)

st.divider()

# -----------------------------
# 검사 실행
# -----------------------------

st.header("3. 약물 안전성 검사")

check_button = st.button(
    "안전성 검사 실행",
    type="primary",
    use_container_width=True
)

if check_button:

    st.warning(
        "아직 Core와 연결되지 않았습니다. "
        "현재는 화면 동작만 확인합니다."
    )

st.divider()

# -----------------------------
# 결과 영역
# -----------------------------

st.header("4. 검사 결과")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("병용금기", "—")

with col2:
    st.metric("노인주의", "—")

with col3:
    st.metric("효능군 중복", "—")

st.info(
    "안전성 검사를 실행하면 이 영역에 결과가 표시됩니다."
)

st.divider()

st.caption(
    "DUR Polypharmacy Safety RAG | Research Prototype"
)

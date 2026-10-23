"""MEDGUARD AI — 배포용 Streamlit 진입점 (19번 노트북이 생성).

기존 ui_integration/app_v2.py 를 수정하지 않고 runpy 로 '한 번만' 실행합니다.
  streamlit run app.py
- 연구용 데모입니다. 임상 의사결정 지원 목적이 아니며 CLINICAL_VALIDATION_STATUS=NOT_VALIDATED 입니다.
- 필수 데이터가 없으면 앱을 시작하지 않고 안내만 표시합니다(검사 결과가 없는 상태이며 '위험 없음'이 아님).
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MEDICAL_AI_PROJECT_ROOT", str(ROOT))   # config.py / ui_runtime.py 가 읽는 변수
os.environ.setdefault("MEDGUARD_ROOT", str(ROOT))
_NB15 = ROOT / "notebooks" / "15_ingredient_duplicate_candidates_prototype.ipynb"
if _NB15.is_file():   # 19b: 폴더가 중첩/중복돼도 이 배포본 자신의 15번 노트북을 명시(AMBIGUOUS_FILE 방지, 로직 무변경)
    os.environ.setdefault("MEDGUARD_NB15_PATH", str(_NB15))             # ingredient_dur_ui_adapter.py 가 읽는 변수
for _p in (ROOT, ROOT / "src", ROOT / "ui_integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SECRET_NAMES = ['OPENAI_API_KEY']


def _bridge_streamlit_secrets() -> None:
    """Streamlit Secrets 에 있는 값을 환경변수로 옮긴다(이미 환경변수가 있으면 그대로). 값을 출력하지 않는다."""
    try:
        import streamlit as st
    except Exception:
        return
    for name in SECRET_NAMES:
        if os.environ.get(name):
            continue
        try:
            value = st.secrets.get(name)
        except Exception:  # secrets.toml 이 없으면 예외 — 키 없이 계속(LLM 설명만 비활성)
            value = None
        if value:
            os.environ[name] = str(value)


_bridge_streamlit_secrets()

REQUIRED_FILES = [
    "data/processed/evidence/drug_approval_items.parquet",
    "data/processed/evidence/easy_drug_canonical.parquet",
    "data/processed/generation/generation_config.json",
    "data/processed/rag/approval_chunks.parquet",
    "data/processed/retrieval/dense/BAAI__bge-m3/embedding_meta.json",
    "data/processed/retrieval/dense/BAAI__bge-m3/unique_text_embeddings.npy",
    "data/processed/retrieval/retrieval_config.json",
    "data/processed/retrieval/text_hash_mapping.parquet",
    "data/processed/retrieval/unique_text_index.parquet",
    "data/processed/screening/contraindication_evidence.parquet",
    "data/processed/screening/contraindication_pairs.parquet",
    "data/processed/screening/elderly_caution_rules.parquet",
    "data/processed/screening/therapeutic_group_mapping.parquet",
    "notebooks/15_ingredient_duplicate_candidates_prototype.ipynb",
    "production_baseline.json",
    "src/dur_safety/screening.py"
]
_missing = [r for r in REQUIRED_FILES if not (ROOT / r).is_file()]
if _missing:
    import streamlit as st

    st.set_page_config(page_title="MEDGUARD AI", page_icon="🛡️", layout="wide")
    st.error("필수 데이터 파일을 찾을 수 없어 앱을 시작하지 않았습니다. 검사 결과가 없는 상태이며, 이는 위험이 없다는 의미가 아닙니다. "
             "README 의 '데이터 준비' 절차를 확인하세요.")
    st.code("\n".join(_missing))
    st.stop()

runpy.run_path(str(ROOT / "ui_integration" / "app_v2.py"), run_name="__main__")

# MEDGUARD AI

이 프로젝트는 **연구·포트폴리오용 데모**이며 임상 의사결정 지원 도구가 아닙니다.

> `CLINICAL_VALIDATION_STATUS = NOT_VALIDATED` · `OFFICIAL_INGREDIENT_IDENTITY_STATUS = NO_GO / NOT_VERIFIED`
> 실제 환자 정보를 입력하지 마세요. 화면의 결과는 진단·처방·복용 판단을 대신하지 않습니다.

## 1. 프로젝트 소개
한국 DUR(의약품 사용 평가) 공공데이터를 기반으로 여러 의약품을 함께 선택했을 때 **규칙에 해당하는 항목**을 찾아 보여주는 다제약물(polypharmacy) 안전 점검 연구용 프로토타입입니다.

## 2. 프로젝트 목적
간호학 지식과 AI/데이터 기술을 연결하는 포트폴리오 프로젝트로, 규칙 기반 점검 + 근거 검색(RAG) + 설명 생성의 구조를 연구합니다.

## 3. 주요 기능 (코드로 확인된 것)
- 의약품 검색 및 선택(`src/dur_safety/drug_lookup.py`, 후보만 제시하고 자동 선택하지 않음)
- DUR 병용금기 / 노인주의 / 효능군 중복 Screening(`src/dur_safety/screening.py`)
- 의약품 **성분 중복 후보** 탐지(15번 노트북 코드를 읽어 실행: `notebooks/15_*.ipynb`, `ui_integration/ingredient_dur_ui_adapter.py`)
- Gate 상태 / Coverage Audit 화면(`app/utils/audit_reader.py`가 `reports/` 결과 파일을 읽어 표시)
- RAG 근거 조회 및 LLM 설명 경로(`src/dur_safety/retrieval.py`, `generation.py`) — **배포 환경에서는 검증되지 않았습니다(NOT_VERIFIED)**

## 4. 시스템 아키텍처
```
app.py ─ runpy ─> ui_integration/app_v2.py ──> app/ (화면 컴포넌트)
                       │                          └ utils/audit_reader.py ─ reports/ (읽기 전용)
                       ├─> ingredient_dur_ui_adapter.py ─> notebooks/15_*.ipynb (성분 후보 코드)
                       └─> app/ui_runtime.py ─> src/dur_safety/{resources,screening,retrieval,generation,pipeline}
                                                         └ data/processed/** (SHA256 검증 후 로드)
```

## 5. DUR Screening 구조
공식 DUR 데이터(병용금기 쌍, 노인주의, 효능군)를 `screening.py` 가 규칙 그대로 조회합니다. 규칙에 해당하지 않으면 **"현재 규칙에서 발견되지 않음"** 이며 **안전하다는 뜻이 아닙니다**.

## 6. Ingredient Candidate Screening 구조
허가정보의 성분명/성분 코드(M코드)가 같은 제품 쌍을 **미검증 후보(UNVERIFIED_CANDIDATE)** 로 보여줍니다. 공식 DUR 병용금기가 아니며, DUR D코드와 M코드를 연결하는 공식 매핑이 없어 공식 성분 동일성은 NO-GO 입니다. 두 결과는 서로 독립적으로 표시되고 합산하지 않습니다.

## 7. RAG/LLM 구조
BM25 + 밀집 임베딩(`BAAI/bge-m3`) 하이브리드 검색으로 근거를 찾고, LLM 은 **DUR 판정을 만들지 않고** 이미 찾은 항목의 근거를 설명합니다(`pipeline.run_safety_check`). 성분 후보 결과는 LLM/RAG 로 전달하지 않습니다. 이 경로는 외부 API 키와 큰 모델이 필요하며 **배포 환경 동작은 검증되지 않았습니다**.

## 8. 기술 스택
Python, Streamlit, pandas/pyarrow, scikit-learn/scipy, sentence-transformers(torch), OpenAI API(선택).

## 9. 데이터 출처
식품의약품안전처 DUR·의약품 허가정보 등 공공데이터를 가공해 사용했습니다. **정확한 출처·이용 조건·재배포 가능 여부는 확인이 필요합니다(NOT_VERIFIED)**. 라이선스 파일은 아직 없습니다(사용자 선택).

## 10. 설치 방법
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt            # 테스트까지: pip install -r requirements-dev.txt
```
의존성(생성 당시): jsonschema>=4.26,<5, numpy==2.1.3, openai==2.54.0, pandas==2.2.3, pyarrow==23.0.1, scipy==1.16.3, sentence-transformers==5.7.0, scikit-learn==1.6.1, streamlit   # VERSION_UNSPECIFIED, torch==2.11.0

## 11. 실행 방법
```bash
streamlit run app.py
```

## 12. 환경변수 설정
`.env.example` 을 참고하세요(실제 값은 `.env` 에만, Git 에 올리지 않음).
- `MEDICAL_AI_PROJECT_ROOT` / `MEDGUARD_ROOT`: 비우면 저장소 루트
- API 키: 설정하지 않으면 DUR/성분 점검은 동작하고 LLM 설명만 사용할 수 없습니다(검증은 아래 참고).

## 13. Streamlit 배포 방법
> STEP 9-1 기준 배포 준비 절차(데이터·모델 준비, Linux CPU 설치, 사전 점검)는 `DEPLOYMENT.md` 를 따르세요. 아래 1–4는 기존 안내이며, 데이터는 현재 Git 에서 제외되어 있습니다.

1. 데이터 준비: `DATA_STRATEGY.md` 를 읽고 큰 파일의 배포 방식을 정합니다(`python tools/fetch_runtime_data.py --verify` 로 해시 확인).
2. Streamlit Community Cloud 에서 이 저장소를 연결하고 Main file path 를 `app.py` 로 지정합니다.
3. 앱 설정의 **Secrets** 에 `.streamlit/secrets.toml.example` 형식으로 키를 입력합니다(키는 저장소에 넣지 않음). `app.py` 가 Secrets 를 환경변수로 옮깁니다.
4. **주의**: torch 와 임베딩 모델(bge-m3)이 필요해 무료 환경의 메모리 한도를 넘을 수 있습니다. 이 저장소는 Streamlit Cloud 에서 **검증되지 않았습니다(CLOUD_NOT_TESTED)**.

## 14. 테스트 방법
```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
```
기존 테스트 대부분은 mock 기반이며 실제 데이터·RAG·LLM·브라우저 동작의 증거가 아닙니다.

## 15. 연구적 한계
- 임상 검증 없음(`NOT_VALIDATED`). 공식 성분 동일성 NO-GO. 성분 후보는 미검증 후보.
- 규칙 미매칭/데이터 부족을 안전 판정으로 해석하지 않습니다. Coverage 부족은 정상이 아닙니다.
- 검증하지 않은 성능 수치는 기재하지 않았습니다.

## 16. 의료 안전성 고지
이 프로젝트는 **연구·포트폴리오용 데모**이며 임상 의사결정 지원 도구가 아닙니다. 환자 치료 결정에 사용하지 마십시오. 약물 복용·중단은 반드시 의사·약사와 상담하세요.

## 17. 향후 개선 방향
공식 성분 매핑 검증, 임상 전문가 평가, 배포 환경 메모리 최적화, 수동 브라우저 시험(B3·B5·B10·B12·K2·K4·K6) 완료, 라이선스·데이터 이용조건 정리.

# STEP 5 — 기존 회귀 테스트 복구 및 재검증 보고서

- 작성일: 2026-10-23
- 대상: MEDGUARD AI (한국 DUR 기반 Polypharmacy Safety RAG) — 연구·포트폴리오용 프로토타입, **임상 검증 아님** (`CLINICAL_VALIDATION_STATUS = NOT_VALIDATED`, `OFFICIAL_INGREDIENT_IDENTITY_STATUS = NO_GO / NOT_VERIFIED` 유지)
- PROJECT_ROOT: `C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer` (이번 세션에서 실제 확인, STEP 4와 동일)
- 상태 표기: PASS(실제 실행·성공) / FAIL / INCOMPLETE / BLOCKED / NOT_RUN

## 0. 판정 요약

| 항목 | 결과 |
|---|---|
| STEP 4 FAIL 8건 | **7건 해결** (원인: 평가 기준 자료 누락 → 검증된 원본 복원), 1건 잔존 |
| 최종 pytest (dense 필수, 운영 기본값) | 170 수집 / **168 PASS / 1 FAIL / 0 ERROR / 1 SKIP** |
| 잔존 FAIL 1건 | `test_retrieval_regression_vs_06A_and_04_smoke` — CPU(fp32)와 평가 기준 GPU(fp16)의 dense **점수 값** 차이(최대 0.0007). 순위·근거·Top-10은 33/33 동일. 동결 기준 문서의 CPU 기록(3/33 strict)과 **정확히 동일한 결과** |
| 테스트 삭제·skip 추가·기대값/허용오차 변경 | **없음** |
| **STEP5_STATUS** | **INCOMPLETE** — 회귀 기준 자료는 모두 복구되었고 의료 판단 회귀는 전부 PASS이나, 엄격 retrieval 회귀 1건은 이 하드웨어(CPU)에서 통과할 수 없음(GPU 재실행 또는 판정 기준에 대한 사용자 결정 필요) |

## 1. 작업 목적

STEP 4에서 기준 자료 누락으로 FAIL 처리된 연구용 회귀 테스트 8건을 복구하고, 실제 traceback으로 원인을 재검증한다. 의료 판단 로직·테스트 기준은 변경하지 않는다.

## 2. 실제 실행 환경

| 항목 | 값 |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| Python | 3.12.10 (MSC v.1943 64 bit), `.venv\Scripts\python.exe` (venv 활성 확인: sys.prefix ≠ base_prefix) |
| `pip check` | No broken requirements found (시작·종료 시 2회) |
| 주요 패키지 | STEP 4와 동일 (torch 2.11.0 CPU, sentence-transformers 5.7.0, transformers 5.20.2, huggingface_hub 2.2.0, pandas 2.2.3, numpy 2.1.3, pyarrow 23.0.1, streamlit 1.66.0, pytest 8.4.2) — **패키지 추가 설치 없음** |
| GPU | 없음 (CPU) |
| RAM / 디스크 | 15.7GB / C: 여유 약 147GB |
| 공통 실행 환경변수 | `PYTHONUTF8=1`, `-X utf8`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `OPENAI_API_KEY` 제거, `MEDICAL_AI_PROJECT_ROOT=<PROJECT_ROOT>`, `DUR_UI_ADAPTER_REAL_DATA=1` |

## 3. 실행한 명령어

```bash
# 환경·무결성
.venv/Scripts/python.exe -m pip check
sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt
python -X utf8 -c "<data_manifest.json 35개 sha256 재계산>"

# (1) 복원 후 실데이터 + BM25-only (STEP 4 실행 (2)와 동일 조건)
DUR_ALLOW_NO_DENSE=1 python -X utf8 -m pytest tests -q -rfEs -p no:cacheprovider \
  --junitxml=reports/step5_6_validation/step5_run_bm25only.xml

# (2) 실데이터 + dense 필수 (운영 기본값, STEP 6에서 bge-m3 설치 후)
python -X utf8 -m pytest tests -v -rfEs -p no:cacheprovider \
  --junitxml=reports/step5_6_validation/step6_run_dense.xml

# 잔존 FAIL 분해 (읽기 전용)
python -X utf8 reports/step5_6_validation/retrieval_diff_breakdown.py <root> retrieval_diff_breakdown.json
```

`-p no:cacheprovider`는 `.pytest_cache` 생성을 막기 위한 옵션이며 테스트 동작에는 영향이 없다.

## 4. 누락 평가 데이터 탐색 및 복원

### 4.1 탐색

| 경로 | 결과 |
|---|---|
| `data/processed/evaluation/` | 없음 (STEP 4와 동일) |
| `notebooks/02,04,05` | 없음 (15번만 존재) |
| Google Drive MCP | 이 계정은 인증되지 않음 → 사용하지 않음 |
| 로컬 Drive 동기화 폴더 | 없음 |
| **사용자 Downloads 폴더** | Drive 내보내기 ZIP 2개 발견: `medical-ai-project-20261019T062627Z-1-001.zip` (1.39GB, 2026-10-19), `medical-ai-project_BACKUP_20261012.zip` (0.76GB, 2026-10-12) |

### 4.2 검증 절차

1. ZIP을 풀지 않고 목록·CRC만 조회 → 필요한 파일이 **두 스냅샷 모두에 존재하고 크기·CRC32가 완전히 동일**.
2. scratchpad(프로젝트 외부)에 격리 추출 (경로 traversal 검사 포함), `evaluation/` 240개 + 노트북 3개 = 243개.
3. 기준 해시와 대조:

| 파일 | 기준 | 결과 |
|---|---|---|
| `notebooks/02_structured_screening.ipynb` | `production_baseline.json` `source_notebooks_sha256` | **MATCH** (dc8ac42b…) |
| `notebooks/04_retrieval.ipynb` | 동일 | **MATCH** (c604e46d…) |
| `notebooks/05_rag_generation.ipynb` | 동일 | **MATCH** (bf73407f…) |
| `evaluation_queries.parquet` | 06-B/06-D/06-E config의 입력 sha256 | **MATCH** (bea01e7f…) |
| `evaluation_retrieval_raw.parquet` | 06-B/06-D config | **MATCH** (59979960…) |
| `evaluation_retrieval_runs.parquet` | 06-B/06-D config | **MATCH** (aec11b33…) |
| `evaluation_pool_master.parquet` | 06-B/06-D/06-E config | **MATCH** (b853127d…) |
| `evaluation_annotation_completed.parquet` | 06-B/06-D/06-E config | **MATCH** (c1c9fe6a…) |
| `generation_eval_results.parquet` | 06-D v2 / 06-E config | **MATCH** (f75fd472…) |
| `generation_eval_evidence.parquet` | 06-D v2 / 06-E config | **MATCH** (7c81ca0d…) |
| `end_to_end_screening_runs.parquet` | 하위 단계 기록 해시 **없음** (06-E 최종 산출물) | 두 독립 스냅샷 CRC 동일 + 크기 25,179B = STEP 4가 Drive에서 확인한 크기. 해시 기준 검증이 아니라 **교차 스냅샷 일치**로만 확인됨 |

참고: config 파일들도 같은 ZIP에서 나온 것이므로, 위 MATCH는 "평가 노트북이 기록한 값과 일치"를 의미한다(Drive 원본과의 독립 대조는 아님).

4. `cp -rn` / `cp -n`(덮어쓰기 금지)으로 프로젝트에 배치 후 243/243 sha256 재대조 → 동일.
5. 모든 테스트 실행 후 다시 대조 → 243/243 동일 (테스트가 기준 자료를 변경하지 않음).

임의 생성·샘플링·수정한 평가 데이터: **없음**. `data_manifest.json` 수정: **없음** (복원 파일은 manifest 범위 밖의 평가 산출물).

## 5. pytest 결과

| 실행 | 수집 | PASS | FAIL | ERROR | SKIP |
|---|---|---|---|---|---|
| STEP 4 (2) 실데이터·BM25-only | 170 | 159 | 8 | 0 | 3 |
| **STEP 5 (1)** 복원 후·BM25-only | 170 | **166** | **1** | 0 | 3 |
| **STEP 5 (2)** 복원 후·dense 필수 | 170 | **168** | **1** | 0 | **1** |

### 5.1 STEP 4 FAIL 8건의 변화

| 테스트 | STEP 4 | 원인(traceback 확인) | 이번 결과 |
|---|---|---|---|
| test_screening_regression_vs_06E | FAIL | A. 평가 데이터 누락 | **PASS** (06-E `engine_result_json` 바이트 비교) |
| test_finding_parity_real_02_output_vs_evaluated_finding | FAIL | A | **PASS** |
| test_generation_input_parity[evaluated_finding+frozen_evidence] | FAIL | A | **PASS** |
| test_generation_input_parity[production_finding+frozen_evidence] | FAIL | A | **PASS** |
| test_output_validation_regression | FAIL | A | **PASS** |
| test_pipeline_integration_mock_llm[replay] | FAIL | A | **PASS** |
| test_source_parity | FAIL | A (노트북 02/04/05 누락) | **PASS** (Core 코드 == 노트북 셀) |
| test_retrieval_regression_vs_06A_and_04_smoke | FAIL | A → 복원 후 C(dense 미로딩) → dense 로딩 후 **D/G(장치 수치 차이)** | **FAIL** (5.2 참조) |

추가로 dense 로딩 후 STEP 4에서 SKIP이던 `test_generation_input_parity[production_live]`, `test_pipeline_integration_mock_llm[live]` 2건이 **PASS**.

### 5.2 잔존 FAIL — 원인 분석 (분류: D. 실행 장치 차이 / G. 기타 — 코드 오류·의료 판단 불일치 아님)

`retrieval_diff_breakdown.json` (33개 케이스 = 06-A 평가 30 + 04 smoke 3):

| 방법 | strict ok | Top-5 동일 | Top-10 동일 | 순위 동일 | 점수 외 필드 차이 | 최대 점수 차 |
|---|---|---|---|---|---|---|
| bm25 | 33/33 | 33/33 | 33/33 | 33/33 | 없음 | 0.0 |
| dense | 3/33 | 33/33 | 33/33 | 33/33 | 없음 | 0.0007 |
| hybrid | 3/33 | 33/33 | 33/33 | 33/33 | 없음 | 0.0007 (dense_score 열) |

- 질의 문자열, 후보 집합, status, 근거 chunk_id·순서는 전부 동일. 06-A 기준 대비 Top-5 일치 30/30, 관련 근거 손실 0건, 직접 근거 손실 0건.
- 원인: 04/05 코드는 CUDA에서만 `dense_model.half()`를 적용하므로 CPU에서는 질의를 fp32로 인코딩 → dense_score가 소수 넷째 자리에서 달라짐. 테스트는 점수를 `==`로 비교(strict).
- `production_baseline.json` `retrieval_regression_detail`에 동결 당시 CPU 결과가 "3/33 under strict exact-equality", 차이 범위 [0.0001, 0.0007]로 **이미 기록되어 있으며 이번 결과와 정확히 같다**.
- 조치: **테스트 기준(허용 오차) 변경하지 않음.** 이 테스트는 평가 구성(GPU fp16)에서만 PASS 가능. 허용 오차 도입 여부는 기존 검증 기준과 관련된 결정이므로 사용자 판단 사항.

### 5.3 SKIP 1건

`test_ui_adapter.py:224` — `docs/STREAMLIT_VIEW_MAPPING.md`가 이 체크아웃에 없음. Drive ZIP에서도 확인하지 않았으며 이번 범위(회귀 기준 자료) 밖. BLOCKED(문서 부재)로 기록.

### 5.4 범주별 회귀 결과 (dense 필수 실행 기준)

| 범주 | 테스트 | 결과 |
|---|---|---|
| Screening Regression | test_screening_regression_vs_06E | PASS |
| Finding Regression | test_finding_parity_real_02_output_vs_evaluated_finding | PASS |
| Retrieval Regression | test_retrieval_regression_vs_06A_and_04_smoke | FAIL (strict 점수, 5.2) — 순위·근거 parity는 33/33 |
| Generation Regression | test_generation_input_parity ×3, test_output_validation_regression | PASS (4/4) |
| Pipeline Regression | test_pipeline_integration_mock_llm[replay/live], test_drug_lookup_adapter | PASS (3/3) |
| Source Parity | test_source_parity | PASS |
| Core contract / UI adapter / Dashboard | test_core_contract, test_ui_adapter, test_medguard_dashboard | PASS (1 SKIP: 문서 부재) |

주의: Generation/Pipeline 회귀는 **mock LLM(저장된 응답 replay)** 기반이며 실제 LLM 호출 검증이 아니다(실제 API 호출 0회).

## 6. 변경 파일 목록

| 파일 | 종류 |
|---|---|
| `data/processed/evaluation/` (240개, 13MB) | **복원** (Drive ZIP, 해시 검증, 신규 배치) |
| `notebooks/02_structured_screening.ipynb`, `04_retrieval.ipynb`, `05_rag_generation.ipynb` | **복원** (기준 sha256 MATCH) |
| `reports/STEP5_REGRESSION_RECOVERY.md` | 본 보고서 (신규) |
| `reports/step5_6_validation/step5_run_bm25only.{log,xml}`, `step6_run_dense.{log,xml}` | pytest 원본 출력 (신규) |
| `reports/step5_6_validation/retrieval_diff_breakdown.{py,json}` | 읽기 전용 분석 스크립트·결과 (신규) |

`src/`, `tests/`, `app/`, `ui_integration/`, 기존 `data/processed/**`, `FROZEN_SHA256SUMS.txt`, `production_baseline.json`, `data_manifest.json`: **변경 없음**.

## 7. Core SHA256 검증

`sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt` — 작업 시작 시 9/9 OK, 모든 테스트 종료 후 **9/9 OK**.

## 8. 데이터 무결성

| 검증 | 결과 |
|---|---|
| `data_manifest.json` 35개 sha256 (시작/종료) | 35/35 / **35/35** |
| `load_resources()` 런타임 해시·config parity (pytest 내부) | PASS |
| 복원 파일 243개 (배치 직후/테스트 종료 후) | 243/243 / **243/243** |
| 기존 `notebooks/15_*.ipynb` | 변경 없음 |

## 9. 미해결 문제

1. Retrieval 회귀 strict 비교 1건 FAIL (CPU 수치 차이, 동결 기준 기록과 동일) — GPU 환경 재실행 또는 판정 기준에 대한 사용자 결정 필요.
2. `docs/STREAMLIT_VIEW_MAPPING.md` 부재로 1건 SKIP.
3. `end_to_end_screening_runs.parquet`는 기록 해시가 없어 교차 스냅샷 일치로만 확인.
4. Generation/Pipeline 회귀는 mock LLM 기반 — 실제 LLM 충실도는 STEP 7 범위.
5. `PYTHONUTF8` 영구 설정 안 됨 (명령마다 `-X utf8` 필요, STEP 4와 동일).

## 10. 다음 단계 진행 가능 여부

- 회귀 기준 자료가 복구되어 Screening·Finding·Generation 입력·Pipeline·Source parity 회귀를 로컬에서 재현 가능 → **STEP 6·7 진행 가능**.
- 단, 엄격 retrieval 회귀를 PASS로 만들려면 GPU 실행이 필요하며, 이를 근거 없이 PASS로 표기하지 않았다.

```
STEP5_STATUS   = INCOMPLETE
CORE_INTEGRITY = PASS
DATA_INTEGRITY = PASS
```

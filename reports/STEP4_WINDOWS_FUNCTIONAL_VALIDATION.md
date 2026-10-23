# STEP 4 — Windows 환경 실제 실행 검증 보고서

- 작성일: 2026-10-20
- 대상: MEDGUARD AI (한국 DUR 기반 Polypharmacy Safety RAG) — 연구·포트폴리오용 프로토타입, **임상 검증 아님**
- PROJECT_ROOT: `C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer`
- 상태 표기: PASS(실제 실행·성공) / FAIL / INCOMPLETE / BLOCKED / NOT_RUN

## 0. 판정 요약

| 항목 | 상태 | 한 줄 근거 |
|---|---|---|
| ENVIRONMENT_STATUS | **PASS** | `.venv` Python 3.12.10 64bit, 필수 패키지 전부 설치, `pip check` 정상. 단 `PYTHONUTF8`는 영구 설정 안 됨(명령마다 전달) |
| SCREENING_STATUS | **PASS** (범위 한정) | 실데이터 초기화, 무결성 플래그 5/5, 로컬 기준 레코드 3/3 필드 완전 일치, 경계·실패 처리 확인. 06-E 32건 회귀는 BLOCKED |
| PYTEST_STATUS | **INCOMPLETE** | 170 수집 / 159 PASS / 8 FAIL / 0 ERROR / 3 SKIP. FAIL 8건 전부 기준 자료 누락 |
| RAG_STATUS | **INCOMPLETE** | BM25 경로 실행·근거 연결 확인. bge-m3 미캐시로 평가 구성(hybrid) 실행 불가(다운로드 승인 대기) |
| GENERATION_STATUS | **INCOMPLETE** | mock LLM 경로 PASS, 실제 API 호출 NOT_RUN(API 키 없음) |
| GUARDRAIL_STATUS | **PASS** (구조 검증 범위) | 환각 근거 ID·무인용 문장·지시형 문구 차단, 양성 대조 확인. 의미적 사실 일치는 검증 대상 아님 |
| STREAMLIT_READINESS | **PARTIAL** | `app.py` 헤드리스 실행 예외 0, 안전 실패 화면 표시. 모델 없이는 검색·검사 버튼 비활성 |
| **STEP4_STATUS** | **INCOMPLETE** | 기능 결함은 발견되지 않았으나 dense 모델·실제 LLM·06-E 회귀가 미실행 |

## 1. 실행 환경

| 항목 | 값 |
|---|---|
| Python | 3.12.10 (MSC v.1943 64 bit), `.venv\Scripts\python.exe` (sys.prefix ≠ base_prefix) |
| pip | 25.1.1, `pip check`: No broken requirements found |
| 주요 패키지 | streamlit 1.66.0, pandas 2.2.3, numpy 2.1.3, pyarrow 23.0.1, scipy 1.16.3, scikit-learn 1.6.1, torch 2.11.0+cpu, sentence-transformers 5.7.0, transformers 5.20.2, huggingface_hub 2.2.0, openai 2.54.0, jsonschema 4.26.0, pytest 8.4.2 |
| GPU | 없음 (torch.cuda.is_available() = False) |
| PYTHONUTF8 | 셸·사용자 환경변수 모두 **미설정** → 기본 `sys.flags.utf8_mode = 0`. `PYTHONUTF8=1` 전달 시 1 |
| RAM / 디스크 | 총 15.7GB (측정 시 여유 3.8GB) / C: 여유 142.7GB |
| PyCharm 인터프리터 | `.venv\Scripts\python.exe` 지정 확인 (STEP 2) |

**주의(이번에 확인된 함정)**: `python -I`(격리 모드) 또는 `-E`는 `PYTHON*` 환경변수를 무시하므로 `PYTHONUTF8=1`이 적용되지 않는다. 이 경우 cp949 `UnicodeDecodeError`가 재현된다. `-X utf8` 플래그 또는 `-I` 미사용으로 해결.

## 2. 실제 실행한 명령 (요약)

모든 명령은 `.venv\Scripts\python.exe`로 실행. 공통 환경: `PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`, `OPENAI_API_KEY` 제거.

```
python -m pip check
python -m pytest --collect-only -q tests
# (1) mock 모드 (MEDICAL_AI_PROJECT_ROOT 미설정)
python -m pytest tests -q -rfEs --junitxml=run1_mock.xml
# (2) 실데이터 모드 (BM25-only)
MEDICAL_AI_PROJECT_ROOT=<root> DUR_ALLOW_NO_DENSE=1 DUR_UI_ADAPTER_REAL_DATA=1 \
  python -X utf8 -m pytest tests -q -rfEs --junitxml=run2_real.xml
python -I screen_check.py <root>          # Screening 단독 (parquet만 사용)
python -I ing_check.py <root>             # 성분 후보 엔진
python -X utf8 -I res_check.py <root>     # load_resources (dense 필수 / BM25-only)
python -X utf8 gen_probe.py <root>        # Generation·Guardrail probe (mock LLM, OpenAI 클라이언트 생성 차단)
python -X utf8 apptest.py <root>          # streamlit.testing AppTest로 app.py 1회 실행 (서버 미기동)
sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt
```

스크립트·결과 원본: `reports/step4_validation_scripts/` (읽기 전용 검증 코드, 의료 로직 없음)

## 3. 데이터 무결성

| 검증 | 상태 | 결과 |
|---|---|---|
| data_manifest 35개 SHA256 | PASS (STEP 1·2 실행, 이후 변경 없음) | 35/35 일치 |
| `load_resources()` 런타임 해시 검증 | **PASS** | 기록 해시 보유 10개 MATCH, easy_drug_canonical = NO_RECORDED_HASH(설계상), generation_config = CONTENT_CHECKED |
| 런타임 설정 parity (`verify_runtime`) | **PASS** | 20/20 (프롬프트 버전·SYSTEM_PROMPT sha256·스키마·DIRECTIVE_PATTERNS·store=False 등) |
| Frozen Core 9개 | **PASS** | `sha256sum -c` 9/9 OK (STEP 4 종료 시점 재확인) |
| Parquet 로딩 | **PASS** | corpus 323,676행, unique text 36,988 |

## 4. Screening 검증 (LLM/RAG 없이)

`screening.init_screening()` 단독 실행 — 초기화 후 `openai`, `torch`, `sentence_transformers`, `dur_safety.generation`, `dur_safety.retrieval` **모두 미로딩** 확인 → Screening은 LLM 없이 생성됨.

| # | 검증 | 입력 유형 | 상태 | 결과 |
|---|---|---|---|---|
| 1 | DUR 데이터 존재·로딩 | 실데이터 | PASS | pairs 322,816 / evidence 796,668 / elderly dedup 1,980 / therapeutic lookup 7,056 |
| 2 | 데이터 무결성 플래그 | 실데이터 | PASS | PAIRS_NORMALIZATION / ELDERLY_DEDUP / THERAPEUTIC_CANONICAL / CONTRAINDICATION_LOOKUP / EVIDENCE_LINKAGE 모두 True (02 노트북 EDA 기대값 기준) |
| 3 | 병용금기 | 기준 레코드 Q2 (195700013+196900031) | **PASS** | 05 smoke 저장 레코드와 13개 필드 완전 일치 |
| 4 | 노인주의 | 기준 레코드 Q1 (197000079, 72세) | **PASS** | 10개 필드 완전 일치 |
| 5 | 효능군 중복 | 기준 레코드 Q3 (197000068+197700114) | **PASS** | 9개 필드 완전 일치 |
| 6 | 알 수 없는 약물 | 999999999 | PASS (실행 검증) | `not_found_in_dur_tables`에 기록, 신호 0, scope_note(“신호가 없다는 것이 안전하다는 의미는 아님”) 포함 |
| 7 | 연령 처리 | None / 40 / -1 / 151 / True | PASS (실행 검증) | not_evaluated_age_missing / not_applicable_age_below_threshold / ValueError / ValueError / TypeError |
| 8 | 중복·무효 입력 | ["abc", None, X, X] | PASS (실행 검증) | None → invalid_inputs, 중복 → duplicate_inputs. **관찰**: Core는 비숫자 문자열 "abc"를 무효로 거르지 않음(정규화만) — UI 어댑터가 “검색으로 제시된 후보만 허용”하여 차단 (`test_only_offered_candidates_are_accepted` PASS). Core 변경 없음 |
| 9 | 필수 데이터 누락 | 빈 data/processed 임시 루트 | PASS | `FileNotFoundError("필수 파일이 없습니다")` — 결과를 만들지 않고 실패 |
| 10 | 성분 중복 후보 | 아세트아미노펜 3제품 등 5개 입력 | PASS (**실행 검증**, 정확성 아님) | 엔진 로드(42,977제품) 성공, 5/5 status=OK, 스키마·의미 검사 오류 0. TYPE_A 1쌍 = `UNVERIFIED_CANDIDATE`, 형태 차이(TYPE_D)는 후보 아님. 미확인 제품은 `NOT_EVALUATED_INSUFFICIENT_DATA` + overall `PARTIAL`(안전 판정 아님). 이 엔진의 입력별 정답 기준 자료는 프로젝트에 없음 |
| 11 | 06-E 32건 전체 회귀 (`engine_result_json` 바이트 일치) | — | **BLOCKED** | `data/processed/evaluation/end_to_end_screening_runs.parquet` 로컬 없음. Drive에 존재(25,179B). 커넥터 base64 수동 전사 시도 → 파일 손상(19,952B, parquet 해석 실패) → **즉시 삭제**, 사용하지 않음 |

판단: 근거 없는 금기 관계 생성은 관찰되지 않음(모든 신호가 DUR 테이블 키 일치에서만 발생, 기준 레코드와 완전 일치). 데이터 부족 시 “안전” 단정 문구 없음.

## 5. pytest 결과

| 실행 | 수집 | PASS | FAIL | ERROR | SKIP |
|---|---|---|---|---|---|
| (1) mock 모드 | 170 | 133 | 0 | 0 | 37 (실데이터 루트 미설정 35, 문서 부재 1, opt-in 1) |
| (2) 실데이터·BM25-only | 170 | **159** | **8** | **0** | 3 |

범주별 (실행 (2) 기준):

| 범주 | 파일 | 결과 |
|---|---|---|
| A. Core / Screening | test_core_contract.py | 29/29 PASS (frozen 해시 고정 테스트 포함) |
| B. UI Adapter | test_ui_adapter.py | 98 PASS / 1 SKIP (`docs/STREAMLIT_VIEW_MAPPING.md` 없음) — 실데이터 E2E(mock LLM) PASS |
| C. RAG / Retrieval | test_retrieval_regression.py | 1 FAIL — 기준 자료 누락 |
| D. Generation / Guardrail | test_generation_regression.py | 3 FAIL (기준 자료 누락) / 1 SKIP (dense 미로딩) — Guardrail 단위 테스트는 A·B·F에 포함되어 PASS |
| E. 연구용 회귀 | test_screening/finding/pipeline_regression.py, test_source_parity.py | FAIL 4 (기준 자료 누락), pipeline: drug_lookup PASS, live SKIP(dense) |
| F. 배포 환경(UI) | test_medguard_dashboard.py | 31/31 PASS (Streamlit AppTest, `app/medguard_dashboard.py` 대상) |

FAIL 8건 원인 분류 — **전부 “4. 기존 기준 자료 누락”**, 기능 결함·의료 판단 불일치 0건:

| 테스트 | 누락 파일 |
|---|---|
| test_screening_regression_vs_06E | evaluation/end_to_end_screening_runs.parquet |
| test_finding_parity_real_02_output_vs_evaluated_finding | evaluation/evaluation_queries.parquet |
| test_retrieval_regression_vs_06A_and_04_smoke | evaluation/evaluation_retrieval_raw.parquet |
| test_generation_input_parity ×2 | evaluation/evaluation_retrieval_raw.parquet |
| test_output_validation_regression | evaluation/generation_eval_evidence.parquet |
| test_pipeline_integration_mock_llm[replay] | evaluation/generation_eval_evidence.parquet |
| test_source_parity | notebooks/02_structured_screening.ipynb (04, 05도 필요) |

테스트 삭제·skip 추가·기대값 변경: 없음.

## 6. RAG 검증

| 항목 | 상태 | 결과 |
|---|---|---|
| 검색 인덱스 | PASS | approval_chunks, unique_text_index, text_hash_mapping, 임베딩 (36,988×1024 fp16) 존재·해시 일치 |
| 임베딩 모델 설정 | 확인 | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181` (config·retrieval_config·generation_config 3중 고정) |
| 모델 캐시 | **없음** | `~/.cache/huggingface/hub`에 bge-m3 없음 (e5-small, Llama-3.2-1B만 존재) |
| 추가 다운로드 | **승인 필요** | bge-m3 가중치 약 2.3GB(+토크나이저 수십 MB) — 이번 단계에서 **다운로드하지 않음** |
| 운영 기본값(require_dense=True) | PASS (fail-closed) | 모델 부재 시 `ResourceVerificationError: dense retrieval unavailable` — 평가되지 않은 DEGRADED 모드로 조용히 넘어가지 않음 |
| BM25-only 검색 실행 | PASS (실행 검증) | Q2 병용금기: status=DEGRADED, method=hybrid_bm25_only, 근거 5건, 모든 근거에 evidence_id·chunk_id·ITEM_SEQ(입력 약물) 연결 |
| 결과 없음 처리 | PASS (테스트) | `test_no_evidence` → deterministic INSUFFICIENT 출력, LLM 미호출 |
| 기존 평가 결과 비교 | NOT_RUN | 평가 구성은 hybrid(GPU fp16). BM25-only 결과는 비교 대상 아님 + 기준 파일 누락 |
| 메모리 | 측정 | BM25-only 로딩 최대 작업 집합 약 **3.4GB**. bge-m3 CPU fp32 추가 시 약 +2.3GB 이상 예상(추정, 미측정) |

검색이 실행되었다는 사실은 근거의 의학적 적합성을 의미하지 않음.

## 7. Generation 검증

| 항목 | 상태 | 결과 |
|---|---|---|
| API 키 로딩 방식 | 확인 | `generation.get_secret`: Colab Secrets(로컬 비활성) → `OPENAI_API_KEY` 환경변수. `app.py`가 Streamlit secrets → 환경변수로 전달. `.env`는 읽지 않음 |
| 실제 키 존재 | **없음** | 프로세스·사용자 환경변수·`.env`·`.streamlit/secrets.toml` 모두 없음 (값 출력 없음) |
| 실제 API 호출 | **NOT_RUN** | 키 없음 + 비용 발생 가능 → 호출하지 않음 |
| 키 없는 실제 `call_llm` 경로 | PASS | `LLM_UNAVAILABLE: API key not found`, 네트워크 미접속, Screening finding 유지 |
| mock LLM 정상 출력 | PASS | GENERATED, 인용 ID ⊂ 제공 근거, 화면에 문장 표시(양성 대조) |
| LLM 예외·빈 응답·비JSON | PASS (테스트) | LLM_ERROR / EMPTY_RESPONSE / MALFORMED_RESPONSE, Screening 유지 |
| 근거 부족 시 불확실성 | PASS (테스트) | NO_EVIDENCE/EVIDENCE_INVALID → “근거만으로는 설명을 생성할 수 없습니다” + INSUFFICIENT |

**“LLM이 Evidence에 없는 의료정보를 새로 만들었는가?”** — 실제 LLM을 호출하지 않았으므로 **판단 불가(NOT_RUN)**. 아래 Guardrail은 이를 *구조적으로* 막는 장치이며, 실제 모델의 충실도 자체를 증명하지 않는다.

## 8. Guardrail 검증 (실데이터 + BM25 + mock LLM, OpenAI 클라이언트 생성 차단)

| 시나리오 | Core 판정 | 화면(ViewModel) | 상태 |
|---|---|---|---|
| 정상: 제공 근거 ID 인용 | GENERATED | 문장 **표시됨** (양성 대조) | PASS |
| 환각: 검색되지 않은 근거 ID `E_FAKE_999` 인용 + “새로운 금기 관계” 문장 | INVALID_OUTPUT (`INVALID_EVIDENCE_ID`) | 문장 **미표시**, Screening 유지 | PASS |
| 인용 없는 단정 문장 | INVALID_OUTPUT (`STATEMENT_WITHOUT_CITATION`, `NO_CITATIONS`) | **미표시** | PASS |
| 지시형 문구 “즉시 중단해야” (유효 인용) | GENERATED + directive_flags 2개 (Core는 표시만, 설계상) | **미표시** (UI 정책이 보류) | PASS |
| 금지 안심 문구 / “DUR 미등재 = 안전” 표기 | — | 테스트 PASS (`test_forbidden_reassurance_phrases_absent`, `test_not_in_dur_is_not_safe`, `test_no_finding_is_not_labelled_safe`) | PASS |

한계: Guardrail은 인용 ID 유효성·인용 존재·지시형 패턴을 검사한다. **유효한 근거 ID를 인용하면서 그 근거에 없는 내용을 말하는 경우(의미적 불일치)는 자동 검출 대상이 아니다** → 실제 LLM 출력에 대한 사람 검토 또는 별도 평가가 필요.

## 9. Streamlit 실행 준비

`streamlit.testing.v1.AppTest`로 `app.py` 1회 실행 (서버 미기동, 67.7초): 예외 0, 연구용 고지 표시, 오류 메시지 “DUR 데이터를 불러오지 못했습니다… 이는 위험이 없다는 의미가 아닙니다.”

| 단계 | 충족 | 근거 |
|---|---|---|
| A. 화면만 실행 | **YES** | AppTest 예외 0, 레이아웃·버튼 렌더링 |
| B. Screening까지 실행 | **NO (현재)** | 엔진 자체는 정상(§4)이나, UI의 약물 검색·검사 버튼이 `rt.ready`에 묶여 있고(`app/components/drug_search.py:139-155`) `rt.ready`는 dense 모델 로딩 성공 시에만 True → 모델 없이는 UI에서 검사 불가 |
| C. RAG·LLM 통합 | **NO** | bge-m3 미다운로드, API 키 없음 |
| D. 배포 준비 완료 | **NO** | 위 + 데이터 배포 방식 미정, 라이선스 미확인, 메모리 요구량 |

STREAMLIT_READINESS = **PARTIAL**

## 10. 변경한 파일

| 파일 | 내용 |
|---|---|
| `reports/STEP4_WINDOWS_FUNCTIONAL_VALIDATION.md` | 본 보고서 (신규) |
| `reports/step4_validation_scripts/` | 검증 스크립트 6개 + JUnit XML 2개 + screening_check.json (신규, 읽기 전용 검증 코드) |
| `_incoming_drive_originals/evaluation/` | 임시 생성 → 손상 확인 후 **삭제**(현재 없음) |

코드·데이터·테스트·FROZEN_SHA256SUMS.txt·production_baseline.json: **변경 없음**.

## 11. 기존 의료 판단 로직 변경 여부

**변경 없음.** Frozen Core 9개 SHA256 = 동결 기준 (작업 종료 시 재확인 9/9 OK). Screening·Retrieval·Generation·프롬프트·Guardrail 기준 수정 없음.

## 12. 해결된 문제

- 패키지 미설치 → 해결(사용자 설치 반영 확인, pip check 정상)
- cp949 오류 → `PYTHONUTF8=1`(또는 `-X utf8`)로 해결 확인, 코드 무수정
- `load_resources()` 미검증 → BM25-only 실행 성공, 해시·런타임 parity 전부 통과, dense 필수 모드 fail-closed 확인
- pytest 미실행 → 170개 실행, 기능 결함 0건 확인
- Screening 실제 실행 미검증 → 실데이터 실행, 기준 레코드 3/3 일치
- Guardrail 미검증 → 구조적 Guardrail 실데이터 경로에서 확인

## 13. 미해결 문제

1. bge-m3 모델 미다운로드 (≈2.3GB, 승인 필요) → 평가 구성 RAG·UI 검색 불가
2. 06-A~06-E 평가 기준 파일 + 노트북 02/04/05 로컬 부재 → 연구용 회귀 8건 FAIL
3. 실제 LLM 호출 미검증 (API 키 없음, 비용)
4. `PYTHONUTF8` 영구 설정 안 됨 (PyCharm 실행 구성·터미널마다 필요)
5. CPU 실행은 평가 구성(GPU fp16)과 다름 — 동결 기준 문서상 CPU retrieval 회귀 FAIL(3/33) 기록, 인접 점수 차이로 근거 순위가 달라질 수 있음
6. 성분 후보 엔진의 입력별 정답 기준 없음(실행 검증만 가능)

## 14. 배포 차단 요인

| 심각도 | 요인 |
|---|---|
| HIGH | dense 모델 부재 시 UI 검색·검사 불가 (fail-closed 설계) |
| HIGH | 메모리: BM25만으로 약 3.4GB, 모델 포함 시 더 큼 — 무료 클라우드 한도 초과 가능성 높음 |
| HIGH | 데이터 라이선스·재배포 가능 여부 미확인, 100MB 초과 파일 2개 배포 방식 미정 |
| MEDIUM | 실제 LLM 출력 충실도 미평가, `streamlit` 버전 미고정, `PYTHONUTF8` 의존 |

## 15. 다음 단계 권장 작업

1. **(사용자 승인)** bge-m3 revision `5617a9f…` 다운로드(≈2.3GB) → `require_dense=True`로 `load_resources()` 재검증, 메모리 측정
2. **(사용자 작업)** Drive `medical-ai-project/data/processed/evaluation/` 파일들과 `medical-ai-project/notebooks/02,04,05` 를 브라우저로 직접 다운로드하여 동일 경로에 배치 → 회귀 테스트 재실행 (커넥터 경유 바이너리 전사는 신뢰 불가로 확인됨)
3. PyCharm Run/Debug 구성(Streamlit·pytest)에 `PYTHONUTF8=1` 추가, 또는 사용자 환경변수 등록
4. 1 완료 후 `streamlit run app.py` 로컬 실행 → 검색·Screening·근거 패널 수동 확인
5. 실제 LLM 검증은 키·비용 승인 후 소수 케이스로, 출력의 근거 충실도를 사람이 검토

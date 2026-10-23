# STEP 9-1 — 배포용 프로젝트 구조 정리 및 Deployment Readiness Audit

- 작성일: 2026-10-23 / 대상: MEDGUARD AI (연구·교육용 프로토타입, **임상 검증 아님**)
- 산출물: `reports/step9_1_validation/`
- 표기: **확인됨**(실제 실행·파일로 확인) / **추정**(근거를 밝힌 판단) / **NOT_VERIFIED**(확인 못 함) / **NOT_RUN**(실행 안 함)
- 이번 단계에서 GitHub push, 저장소 생성, 클라우드 배포, 데이터·모델 외부 업로드, 의료 판단 로직 변경, 모델 교체: **하지 않음**

## 1. Executive Summary

1. 실제 `app.py`를 Streamlit AppTest로 실행하며 import된 모듈과 열린 파일을 audit hook으로 기록했다. 런타임 의존성은 **프로젝트 Python 모듈 33개 + 데이터 13개(638.1 MB) + 노트북 15(코드 셀 실행) + `production_baseline.json` + `reports/` 감사 결과 5개 + bge-m3 모델(2.27 GB)** 이다.
2. 비밀정보: 작업 트리 전체에서 실제 API 키·토큰 **0건**이다. Git 저장소가 아니어서 커밋 이력 노출 가능성은 없다. 다만 Colab 노트북 메타데이터에 **개발자 Google 표시 이름·userId**가, 보고서 등에 Windows 사용자 경로가 들어 있다(17개 파일, 공개 저장소 전 처리 필요).
3. 기존 `.gitignore`는 `.venv/`·`.idea/`를 제외하지 않았고 데이터도 기본 포함이었다(100 MB 초과 파일 2개). 보강 후 `git add .` 시뮬레이션 결과 **186개 파일, 4.85 MB**만 추적된다.
4. 의존성: `streamlit` 미고정과 임베딩 관련 전이 의존성 미고정을 검증된 버전으로 고정했다. Linux(py3.12/3.13) wheel 해석은 성공했다. PyPI torch는 Linux에서 CUDA 13 패키지 7종을 끌어오므로 CPU 인덱스용 `requirements-server-cpu.txt`를 추가했다(`torch 2.11.0+cpu`, CUDA 의존성 0).
5. 메모리(STEP 8 측정, 커밋 약 6.6 GB)와 콜드 스타트(약 90–160 s), 모델 2.3 GB 다운로드 때문에 Streamlit Community Cloud 적합성은 **NOT_VERIFIED**(공식 한도 미확인)이며 권장하지 않는다. 권장 구조는 **영구 디스크가 있는 단일 VM/컨테이너 + 비공개 데이터 배치**다.
6. 데이터 재배포 조건(식약처 DUR·허가정보·e약은요)은 **NOT_VERIFIED**다. bge-m3는 모델 카드상 **MIT**(확인됨)다.
7. Frozen Core 9/9, manifest 35/35, 런타임 동작은 변경 전후가 같다. 의료 판단 코드·데이터·테스트 변경은 0이다.

**판정: CONDITIONAL_PASS** (§12)

## 2. Deployment File Inventory

근거: `step9_1_validation/runtime_trace{,_after}.json`(실제 실행 추적), `dependency_report.md`(기존 정적 분석), git 시뮬레이션(§9 V7).

### A. DEPLOY_REQUIRED

| 항목 | 파일 | 근거 |
|---|---|---|
| 진입점 | `app.py` → `runpy` `ui_integration/app_v2.py` | 실행 추적 |
| UI | `app/__init__.py`, `adapters.py`, `ui_policy.py`, `ui_render.py`, `ui_runtime.py`, `view_models.py`, `components/*.py`(12), `utils/{__init__,audit_reader,ui_helpers}.py`, `styles/medguard.css` | import·open 추적 |
| Screening / RAG / Generation / Guardrail (Frozen Core) | `src/dur_safety/{__init__,config,screening,findings,retrieval,generation,pipeline,resources,drug_lookup}.py` (+ `FROZEN_SHA256SUMS.txt`) | import 추적. Guardrail = `generation.validate_output` + `app/ui_policy.py` |
| 성분 후보 엔진 | `ui_integration/ingredient_dur_ui_adapter.py`, **`notebooks/15_ingredient_duplicate_candidates_prototype.ipynb`**(코드 셀을 읽어 실행) | open 추적, 어댑터 코드 L396–413 |
| 설정 | `.streamlit/config.toml`, `production_baseline.json`, `data/processed/generation/generation_config.json`, `data/processed/retrieval/retrieval_config.json` | open 추적 |
| 화면용 감사 결과 | `reports/ingredient_coverage_audit/run_20261012_184823/{09_*.csv,11_*.json,12_*.md,audit_manifest.json}`, `reports/ui_coverage_audit/run_20261011_152938/03_coverage_metrics.csv` | `app/utils/audit_reader.py`, open 추적. **`reports/` 전체를 빼면 Gate/Coverage 화면이 빈다** |
| 데이터 13개 (638.1 MB) | §4.1 | open 추적 |
| 모델 | `BAAI/bge-m3` @ `5617a9f6…` (HF 캐시, 저장소 밖) | HF 캐시 open 추적 |
| 의존성 | `requirements.txt` (Linux CPU 서버: `requirements-server-cpu.txt`) | §3 |
| 비밀값 | `OPENAI_API_KEY` (환경변수 또는 Streamlit Secrets) | `app.py` 브리지, `generation.get_secret` |

### B. DEVELOPMENT_ONLY (실행 시 import·open 되지 않음)

`tests/`(12), `requirements-dev.txt`, `tools/nbsource.py`, `tools/fetch_runtime_data.py`·`tools/deploy_preflight.py`(배포 보조, 런타임 아님), `notebooks/02,04,05_*.ipynb`(source parity 테스트 기준, `production_baseline.json`에 SHA 고정), `app/streamlit_app.py`·`app/streamlit_main.py`·`app/medguard_dashboard.py`(이전 진입점, 테스트에서 사용), `data/processed/evaluation/`(12.9 MB, 회귀 테스트 기준), manifest 중 런타임 미사용 데이터 16개(약 20.6 MB, 예: `evidence_candidates.parquet` 15.95 MB), `reports/STEP*.md`·`reports/step*_validation/` 등 검증 기록, `DATA_STRATEGY.md`, `MERGE_NOTE.txt`

### C. EXCLUDE_FROM_GIT

`.venv/`, `.idea/`(workspace.xml에 사용자 경로), `__pycache__/`, `*.log`, `.pytest_cache/`, `.streamlit/secrets.toml`, `.env`, `_backup_*/`, `_incoming_drive_originals/`, `.playwright-mcp/`, `reports/*/playwright_artifacts/`, **`data/`**(기본 제외, §6), HF 모델 캐시(저장소 밖)

### D. REVIEW_REQUIRED

| 파일 | 이유 |
|---|---|
| `notebooks/02,04,05,15_*.ipynb` | Colab 셀 메타데이터에 개발자 Google 표시 이름·userId. 02/04/05는 SHA 고정(수정 시 parity 테스트 깨짐), 15는 런타임 필수. 공개 전 처리 방식 결정 필요 |
| `reports/` 하위 13개 파일 + `STEP4–8` 보고서 | Windows 사용자 경로(사용자 이름) 포함 |
| `data/processed/evidence/drug_approval_items.parquet`, `rag/approval_chunks.parquet`, `easy_drug_canonical.parquet` 등 | 재배포 조건 NOT_VERIFIED, 일부 100 MB 초과 |
| `data/processed/evidence/easy_drug_canonical.parquet` (`itemImage`) | 식약처 이미지 URL 2,778건(이미지 자체는 없음, 외부 링크) — 화면에서 쓰는지와 링크 이용 조건 확인 필요 |
| 제약사 사업자등록번호(`BIZRNO`) 컬럼 | 개인정보는 아닌 공개 법인 정보로 판단(추정). 공개 시 원본 데이터 조건과 함께 확인 |

### 최종 정리

- 배포 진입점: `streamlit run app.py`
- 필수 외부 패키지(직접 import): streamlit, pandas, numpy, pyarrow, scipy, scikit-learn, sentence-transformers(→ torch, transformers, huggingface_hub, tokenizers, safetensors), openai, jsonschema. 런타임 로드 서드파티 최상위 모듈 59개(전이 포함)
- 필수 설정: `.streamlit/config.toml`, `generation_config.json`, `retrieval_config.json`, `production_baseline.json`
- 필수 데이터: 13개 638.1 MB / 필수 모델: bge-m3 2.27 GB

## 3. Dependency Audit

| 항목 | 값 (확인됨) |
|---|---|
| Python | 3.12.10 (`.venv`, `C:\…\medguard-pycharm-transfer\.venv`). 데이터 생성은 Colab 3.13.15(`generation_config.json`) |
| 주요 버전 | streamlit 1.66.0 · torch 2.11.0(CPU) · sentence-transformers 5.7.0 · transformers 5.20.2 · huggingface_hub 2.2.0 · tokenizers 0.23.3 · safetensors 0.8.0 · openai 2.54.0 · numpy 2.1.3 · pandas 2.2.3 · pyarrow 23.0.1 · scipy 1.16.3 · scikit-learn 1.6.1 · jsonschema 4.26.0 (`pip_freeze_windows.txt`, 81개) |
| `pip check` | No broken requirements (변경 전·후) |
| requirements.txt만으로 실행 가능? | 필요한 직접 의존성은 모두 포함. 문제: `streamlit` 버전 미지정(→ 고정함), 임베딩 계산 관련 전이 의존성 미고정(→ 고정함) |
| 개발 전용 패키지 혼입 | 없음(pytest는 `requirements-dev.txt`에만) |
| Windows 전용 코드·절대경로 | 런타임 모듈에서 **0건**. Colab 경로는 주석·`find_spec` 보호 분기뿐. 경로는 `Path(__file__)` / `MEDICAL_AI_PROJECT_ROOT` 기준 |
| Linux 설치 가능성 | `pip install --dry-run --platform manylinux… --python-version 3.12/3.13 --only-binary=:all:` 로 **해석 성공(78 패키지)**. 실제 Linux 설치·실행은 NOT_RUN |
| torch on Linux | PyPI wheel `torch-2.11.0-cp312-manylinux_2_28` 은 `cuda-toolkit==13.0.2`, `nvidia-cudnn-cu13` 등 **CUDA 의존성 7개** 선언(`platform_system=="Linux"`). CPU 서버에 불필요하게 설치됨 → `requirements-server-cpu.txt`(CPU 인덱스, `2.11.0+cpu`, CUDA 의존성 0) |
| Python 버전 충돌 | streamlit `requires_python >=3.11`. 3.12 권장(로컬 검증). 3.13은 wheel 해석만 확인 |
| 시스템 라이브러리 | CPU 실행에 별도 시스템 패키지 요구는 발견되지 않음(manylinux wheel). `torchvision` 미설치 → STEP 8에서 watcher 로그 오류 원인, `fileWatcherType="none"`으로 해결됨 |
| 참고 | pip `--platform` dry-run은 환경 마커를 실행 중인 Windows로 평가하므로, Linux 전용 의존성은 wheel 메타데이터로 별도 확인했다 |

## 4. Data & Model Audit

### 4.1 런타임 데이터 (13개, 638.1 MB, `app.py` `REQUIRED_FILES` + 실행 추적)

| 파일 | 크기 | GitHub 100 MB 제한 |
|---|---|---|
| `evidence/drug_approval_items.parquet` | 392.5 MB | **초과** |
| `rag/approval_chunks.parquet` | 129.6 MB | **초과** |
| `retrieval/dense/BAAI__bge-m3/unique_text_embeddings.npy` | 75.8 MB | 이하(50 MB 경고 대상) |
| `screening/contraindication_evidence.parquet` | 26.2 MB | |
| `retrieval/text_hash_mapping.parquet` | 6.4 MB | |
| `screening/contraindication_pairs.parquet` | 2.9 MB | |
| `evidence/easy_drug_canonical.parquet` | 2.2 MB | |
| `retrieval/unique_text_index.parquet` | 1.8 MB | |
| `screening/therapeutic_group_mapping.parquet`, `elderly_caution_rules.parquet` | 0.5 / 0.2 MB | |
| `generation_config.json`, `retrieval_config.json`, `embedding_meta.json` | < 0.1 MB | |

- 로딩: `resources.load_resources(verify_hashes=True)`가 프로세스당 1회 로드하고 SHA256·런타임 parity를 검사한다(불일치 시 실행 중단). Streamlit에서는 `@st.cache_resource`로 세션 간 공유된다(STEP 8: 새 세션 4.8 s). 임베딩은 fp16 `.npy` mmap(STEP 6).
- 절대경로·Google Drive·Windows 경로 의존: **없음**(확인됨). 경로는 저장소 루트 기준이다.
- 배포 환경에서 파일 찾기: 같은 상대경로로 배치하면 된다. 누락 시 `app.py`가 시작을 막고 "위험이 없다는 의미가 아닙니다" 안내를 표시한다.

### 4.2 RAG 모델

| 항목 | 값 |
|---|---|
| 모델 | `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181` (`config.EXPECTED_DENSE_*`, retrieval/generation config 3중 검사) |
| 실제 사용 파일 | `pytorch_model.bin` 2,271.1 MB, `tokenizer.json` 17.1 MB, `sentencepiece.bpe.model` 5.1 MB, 설정 JSON 7개 (캐시 총 2,293 MB) |
| 다운로드 | `SentenceTransformer(…, revision=…)` → HF Hub. 캐시가 없으면 **최초 실행 시 약 2.3 GB 다운로드** |
| 캐시 위치 | `HF_HOME`(기본 `~/.cache/huggingface`). 임시 파일시스템 호스트는 재시작마다 재다운로드 가능(추정) |
| 오프라인 + 캐시 없음 | 앱이 BM25로 축소하지 않고 **시작 거부**(`ResourceVerificationError`) — 실행 확인(V6) |
| CPU 실행 | 가능(STEP 6·8, fp32). GPU면 fp16(평가 구성)으로, 점수 미세 차이는 기존 알려진 사항 |
| 메모리 | STEP 8 측정(Windows): 서버 프로세스 작업 집합 4.56–4.61 GB, **커밋 6.56–6.61 GB**. STEP 6: dense 로딩 직후 커밋 5.93 GB, BM25-only 약 3.4 GB(축소는 금지 사항) |
| 라이선스 | **MIT** — HF 모델 카드 메타데이터(2026-10-23 확인). 기반 모델(XLM-RoBERTa) 조건은 NOT_VERIFIED |

### 4.3 판단

| 질문 | 답 |
|---|---|
| Community Cloud 실행 가능 구조? | 코드상으로는 가능하다(상대경로, Secrets 브리지, requirements). **자원 측면은 NOT_VERIFIED**: 공식 한도를 확인하지 못함(§7). 측정 메모리 6.6 GB와 2.3 GB 모델 다운로드는 무료 공유 환경에 큰 부담으로 판단(추정) |
| 메모리 부족 가능성 | 높음(추정). 측정값 기준 최소 8 GB RAM 이상 권장(측정 커밋 6.6 GB + 여유, 클라우드 미검증) |
| 매번 재다운로드 | 영구 디스크 없는 호스트에서는 콜드 부팅마다 발생 가능(추정). `HF_HOME`을 영구 경로로 두고 사전 다운로드 후 `HF_HUB_OFFLINE=1` 권장(DEPLOYMENT.md §4) |
| 데이터·모델을 GitHub에 넣어야 하나 | 아니오. 데이터는 크기 제한 초과 + 이용 조건 미확인, 모델은 HF에서 revision 고정으로 받는 구조 |
| 외부 다운로드 구조 필요 | 예. `tools/fetch_runtime_data.py --fetch`(해시 검증, URL 미설정 템플릿)가 이미 있다. 비공개 저장 위치는 사용자 결정 사항 |
| 캐싱 적절성 | 적절(프로세스 1회 로드, 세션 공유, 해시 검증). 남은 문제는 영구 디스크 여부뿐 |

## 5. Security Audit

| 점검 | 결과 | 근거 |
|---|---|---|
| API 키 하드코딩 | **없음** | 작업 트리(.venv 제외) 전체 `sk-…` 패턴: 실제 키 0. 유일한 일치는 STEP 8 보고서의 의도적 가짜 키 `sk-step8-fake-not-a-real-key` |
| 기타 토큰(AWS, GitHub, HF, Google, Slack, 개인키) | 없음 | 패턴 스캔 0 |
| 데이터·설정의 `api_key` | 값 없음 | 104건 모두 `"api_key_name": "OPENAI_API_KEY"` 또는 설명 문장. parquet 전 컬럼 스캔(serviceKey/api_key/token/sk-) 0건 |
| data.go.kr serviceKey 노출 | 없음 | `prov_endpoint`에 엔드포인트만 저장(`…/DrugPrdtPrmsnInfoService08`), 키 파라미터 없음 |
| `.env` / `secrets.toml` / 인증서 | 없음 | `.env.example`만 존재(값 없음) |
| Git 이력 | 해당 없음 | 저장소가 아님(`git rev-parse` 실패) → 커밋된 비밀정보 가능성 없음 |
| 로그·평가 결과의 비밀값 | 없음 | 키 값은 `_redact` 처리, STEP 8 ledger·이번 로그 모두 `sk-` 0건 |
| `.gitignore` | **보강함** | 기존: `.venv/`·`.idea/` 미제외, 데이터 기본 포함 → §8 |
| 업로드 시뮬레이션 | 186 파일, 4.85 MB, `.venv`/`.idea`/`data`/secrets/백업 0 | V7 |
| Streamlit Secrets | 가능(코드상) | `app.py`가 `st.secrets` → 환경변수(이미 설정 시 덮어쓰지 않음, 값 미출력). Cloud 실제 동작 NOT_VERIFIED |
| **개인정보** | **주의** | ① 노트북 02/04/05/15 Colab 메타데이터: 개발자 Google 표시 이름·userId ② 보고서·검증 스크립트·`.idea`: Windows 사용자 이름이 들어간 절대경로(추적 대상 17개 파일). 환자 정보는 없음(입력은 공개 itemSeq·나이) |
| 오탐 | 전화번호·주민번호 패턴 일치는 모두 SHA16진·실수값, 이메일 패턴은 `@pytest.mark` | 수동 확인 |
| 로컬 HF 토큰 | 사용자 홈 HF 캐시에 토큰 파일 존재(프로젝트 밖, 값 미확인·미출력). 저장소와 무관 | 실행 추적 |

**실제 비밀정보 노출: 확인되지 않음 → 키 폐기·재발급 불필요.**

## 6. Licensing & Redistribution

조직 정책에 따라 외부 문서 조회가 일부 거부되었다(Streamlit 문서, data.go.kr 페이지). 확인하지 못한 조건은 추정하지 않는다.

| 대상 | 출처(프로젝트 기록) | 사용 목적 | 저장 형태 | 공개 가능 | 원본 재배포 | 서비스 활용 | 출처표시·라이선스 | 확인 경로 |
|---|---|---|---|---|---|---|---|---|
| 의약품 제품 허가정보 | data.go.kr **15095677** 식품의약품안전처_의약품 제품 허가정보, API `DrugPrdtPrmsnInfoService08` (`prov_source`·`prov_endpoint`) | 허가정보 원문 근거(RAG), 성분 후보 | 가공 parquet(`drug_approval_items` 392.5 MB, `approval_chunks` 129.6 MB) + 임베딩 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED (화면에 원문 표시함) | NOT_VERIFIED | data.go.kr 데이터셋 15095677 상세의 '이용허락범위', 식약처 의약품안전나라 이용약관 |
| 허가정보 첨부문서(PDF 기반 chunk) | `source_doc_id` = nedrug.mfds.go.kr PDF 다운로드 URL | RAG chunk 본문 | `approval_chunks.parquet` | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | 의약품안전나라(nedrug.mfds.go.kr) 저작권·이용 정책 |
| DUR (병용금기·노인주의·효능군중복) | 식약처 DUR. **데이터셋 ID 기록 없음** | Screening 판정 기준 | parquet 4개(29.8 MB) | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | data.go.kr '식품의약품안전처 DUR' 데이터셋의 이용허락범위 — 원본 수집 노트북에서 실제 데이터셋 ID 확인 필요 |
| e약은요 | 식약처 의약품개요정보(e약은요) 추정. **ID 기록 없음** | 제품명 정규화(검색 보조) | `easy_drug_canonical.parquet` 2.2 MB (+ 이미지 URL 컬럼) | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | data.go.kr e약은요 데이터셋 이용허락범위. 이미지 링크 사용 조건 별도 확인 |
| 파생 임베딩 | bge-m3로 허가정보 텍스트를 인코딩 | Dense 검색 | `.npy` 75.8 MB | 원본 데이터 조건에 종속(추정) | — | — | — | 위 원본 조건 |
| BAAI/bge-m3 | Hugging Face `BAAI/bge-m3` | Dense 임베딩 | HF 캐시(저장소 밖) | — | **MIT**(모델 카드, 확인) | 가능(MIT 조건) | MIT 고지 유지 | HF 모델 카드 확인됨. 기반 XLM-RoBERTa 조건은 NOT_VERIFIED |
| OpenAI gpt-5.4-mini | OpenAI API | 설명 생성 | 저장 안 함(`store=False`) | — | — | 사용자 계정 약관에 따름 | — | OpenAI 이용약관·사용 정책(사용자 확인) |
| Python 패키지 | PyPI | 런타임 | `.venv`(배포 안 함) | — | 각 패키지 라이선스 | — | NOT_RUN(라이선스 일괄 점검 안 함) | `pip-licenses` 등으로 점검 가능 |

**결론: DATA_REDISTRIBUTION_STATUS = NOT_VERIFIED.** 데이터는 저장소에서 기본 제외했다. 공개 서비스는 원문을 화면에 표시하므로, 공개 배포 전에 '서비스 내 활용'과 '출처 표시' 조건 확인이 필요하다.

## 7. Hosting Feasibility

기준: STEP 8 로컬 측정값(커밋 약 6.6 GB, 작업 집합 약 4.6 GB, 콜드 스타트 88.7–139.8 s, 모델 2.3 GB). **클라우드에서 실행한 적 없음.**

| 기준 | A. Streamlit Community Cloud | B. 별도 클라우드 서버(VM/컨테이너, 영구 디스크) | C. UI와 RAG 실행 환경 분리 |
|---|---|---|---|
| 현재 코드 호환성 | 높음(코드 수정 불필요) | **높음**(코드 수정 불필요, `requirements-server-cpu.txt`) | 낮음(검색/생성 API 계층 신설 필요 → 대규모 변경) |
| 메모리 | 공식 한도 **NOT_VERIFIED**. 측정 6.6 GB 대비 부족 가능성 높음(추정) | 사양 선택 가능(≥ 8 GB 권장, 추정) | UI는 작음, RAG 서버는 B와 동일 |
| 초기 로딩 | 90–160 s + 모델 2.3 GB 다운로드(캐시 유지 여부 NOT_VERIFIED) | 영구 디스크·사전 다운로드로 90–100 s 수준(로컬 기준) | B와 비슷 + 네트워크 홉 |
| 비용 | 무료(조건 NOT_VERIFIED) | 유료(VM 사양에 비례, 금액 NOT_VERIFIED) | 유료, 서버 2개 |
| 운영 복잡도 | 낮음 | 중간(OS·프로세스 관리, HTTPS) | 높음 |
| 데이터·모델 관리 | 저장소에 데이터 불가(100 MB 초과, 조건 미확인) → 매 부팅 외부 다운로드 필요 | 비공개 디스크에 1회 배치 + SHA 검증 | B와 동일 |
| 보안 | Secrets 지원 | 직접 관리(비공개 접근 제어 가능) | 내부 통신 보안 추가 |
| 포트폴리오 데모 | 링크 공유 편리하나 실패·휴면 위험 | 안정적, 접근 제한 가능 | 과함 |
| 의료 로직·RAG 품질 보존 | 메모리 부족 시 축소 유혹 → 금지 사항 위배 위험 | **그대로 보존** | 보존 가능하나 코드 변경 큼 |

## 8. Changes Made

백업: `_backup_step9_1_20261023/` (`.gitignore`, `requirements.txt`, `.env.example`, `README.md` 원본)

| 파일 | 종류 | 변경 | 이유 | 영향 |
|---|---|---|---|---|
| `requirements.txt` | 수정 | `streamlit` → `==1.66.0`. `transformers==5.20.2`, `huggingface_hub==2.2.0`, `tokenizers==0.23.3`, `safetensors==0.8.0` 추가(주석 포함) | 미고정 시 배포 환경에서 STEP 6/8과 다른 버전 설치 가능(임베딩 계산·UI API) | 모두 현재 `.venv` 설치 버전과 같음 → 재설치 불필요, `pip check` OK, Linux 해석 OK |
| `requirements-server-cpu.txt` | 신규 | `--extra-index-url https://download.pytorch.org/whl/cpu` + `-r requirements.txt` | Linux에서 CUDA 13 패키지 7종 설치 방지 | Linux CPU 서버 전용. Windows 영향 없음. 같은 `torch==2.11.0` 고정 충족(`2.11.0+cpu`) |
| `.gitignore` | 수정 | `.venv/`, `venv/`, `env/`, `.idea/`, `.vscode/`, `.playwright-mcp/`, `reports/*/playwright_artifacts/`, **`data/`** 추가 | 가상환경·IDE(사용자 경로) 추적 위험, 100 MB 초과 파일과 재배포 조건 미확인 데이터의 실수 업로드 방지 | 실행 영향 없음. 데이터를 저장소에 넣으려면 사용자가 `data/` 줄을 지우고 LFS 선택 |
| `.env.example` | 수정 | 실제로 읽히는 변수만 남김(`OPENAI_API_KEY`, 경로 3개), 모델 재정의 금지 안내, `.env` 자동 로딩 없음 명시, HF 캐시 옵션 | 기존 파일은 환경변수가 아닌 이름(`CANCEL_NAME`, `ITEM_SEQ` 등)을 나열하고 키 이름을 NOT_VERIFIED로 표기 | 문서 전용, 실행 영향 없음 |
| `tools/deploy_preflight.py` | 신규 | 읽기 전용 사전 점검(Python, `REQUIRED_FILES`, manifest SHA, 감사 결과, 모델 재정의, 모델 캐시, 오프라인 모드, 키 존재 여부만) | 이번 감사에서 찾은 배포 실패 원인을 실행 전에 잡기 위함 | 런타임 아님. 키 값 미출력 확인 |
| `DEPLOYMENT.md` | 신규 | 실행 필수 항목, 설치(Windows/Linux CPU), 데이터·모델 준비, Secrets, 점검·실행, 금지 사항 | 배포 가이드 부재 | 문서 |
| `README.md` | 수정(2줄) | §13에 `DEPLOYMENT.md` 안내와 데이터 Git 제외 사실 추가 | 기존 안내와 새 구조의 불일치 방지 | 문서 |
| `reports/STEP9_1_DEPLOYMENT_READINESS.md`, `reports/step9_1_validation/*` | 신규 | 본 보고서, 실행 추적 스크립트·결과, pip freeze, preflight 로그 | 기록 | — |

**변경하지 않은 것**: `src/dur_safety/`(Frozen Core), `app/`, `ui_integration/`, `app.py`, `tests/`, `notebooks/`, `data/`, `data_manifest.json`, `production_baseline.json`, `.streamlit/config.toml`(STEP 8 설정 유지), Guardrail·평가 기준·모델·검색 구조.

## 9. Validation Results

| # | 검증 | 명령 / 방법 | 결과 |
|---|---|---|---|
| V1 | 모듈 import·진입점 | `runtime_trace.py` — `AppTest.from_file("app.py").run()` + 실행 버튼과 같은 어댑터 경로 1회(CE001, 키 없음) + 성분 엔진 | **PASS** (변경 전·후): 예외 0, 오류 요소 0, `runtime.ready=True`, VM `COMPLETED`, `LLM_UNAVAILABLE`, 통합 `OK`. 첫 실행 163.6 s → 157.7 s. import 모듈·열린 파일 목록 **변경 전후 동일** |
| V2 | 필수 데이터 경로 | `tools/deploy_preflight.py` | **PASS** `REQUIRED_FILES` 16/16, manifest SHA256 **35/35** |
| V3 | 모델 로딩 경로 | 실행 추적(HF 캐시 snapshot `5617a9f6…` 사용) + preflight 캐시 확인 | **PASS** |
| V4 | 키 없음 처리 | V1(키 제거) + preflight(키 없음) | **PASS**: 판정 유지, "설명 생성 서비스를 사용할 수 없습니다", 로그·결과 `sk-` 0건 |
| V5 | 모델 재정의 차단 | `RETRIEVAL_DENSE_MODEL=intfloat/multilingual-e5-small` preflight | **PASS** (FAIL로 검출) |
| V6 | 캐시 없음 + 오프라인 (클라우드 첫 부팅 근사) | 빈 `HF_HOME` + `HF_HUB_OFFLINE=1` → `ui_runtime.load_runtime()` | **PASS(fail-closed)**: `ready=False`, `ResourceVerificationError`, BM25 축소 없음, 사용자 문구 "…위험이 없다는 의미가 아닙니다" (문구가 '데이터'로 표기되는 점은 LOW) |
| V7 | Git 추적 대상 | scratchpad의 bare repo로 `git ls-files --others --exclude-standard` (프로젝트에 `.git` 생성 안 함) | 186 파일 / 4.85 MB. `.venv`·`.idea`·`data`·secrets·백업 0. 화면용 감사 결과 5개·노트북 15 포함 확인 |
| V8 | Linux 의존성 해석 | `pip install --dry-run --platform manylinux_2_28_x86_64 … --python-version 3.12/3.13 --only-binary=:all:` | **PASS**(해석) `requirements.txt` 78 패키지(CUDA 의존성 7), `requirements-server-cpu.txt` 78 패키지(`torch 2.11.0+cpu`, CUDA 0). 실제 Linux 설치·실행 **NOT_RUN** |
| V9 | Windows 환경 보존 | `pip check` | **PASS** No broken requirements |
| V10 | Frozen Core | `sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt` | **PASS 9/9** |
| V11 | 보호 파일 무변경 | 작업 전 65개 파일 해시 스냅샷 대조 | 변경 4개 = 의도한 문서·설정(§8)만. 코드·데이터·테스트·노트북 0 |
| V12 | 비밀정보 스캔 | 정규식 스캔(작업 트리, parquet 컬럼, JSON, 노트북) | 실제 비밀값 0 |
| V13 | pytest | — | **NOT_RUN** (코드·테스트·데이터 무변경. 직전 STEP 8: 179 PASS / 1 FAIL(CPU/GPU 기존) / 1 SKIP, UI 169/1) |
| V14 | 실제 LLM 호출 | — | **NOT_RUN** (유료 호출 불필요) |
| V15 | 클라우드 실행·Secrets·LFS | — | **NOT_RUN** |

이전 단계 수치의 출처 확인: 30/30 Screening·RAG, 실제 LLM 5/5, pytest 179/1/1, 메모리 6.6 GB는 `STEP8_STREAMLIT_INTEGRATION_VALIDATION.md` §6–§9, §13에서, Frozen 9/9·manifest 35/35는 이번에 재실행해 확인했다. 지시문의 "후속 검사 약 4.8초"는 STEP 8 기준 **새 브라우저 세션이 화면을 표시하기까지의 시간**이다(LLM 포함 검사 1회는 5.5–16 s).

## 10. Remaining Blockers

| 등급 | 문제 | 영향 | 조치 |
|---|---|---|---|
| CRITICAL | (비공개 저장소 기준) 없음 | — | — |
| HIGH | 공공데이터 재배포·서비스 이용 조건 NOT_VERIFIED | 공개 서비스·공개 저장소에 데이터·원문 노출 불가 | 사용자가 data.go.kr 각 데이터셋 이용허락범위 확인, DUR·e약은요 데이터셋 ID 기록 |
| HIGH | 메모리 커밋 약 6.6 GB, 모델 2.3 GB | 무료/소형 호스트에서 실행 실패 가능 | B 구조(≥ 8 GB, 영구 디스크) — 실제 사양 검증 필요 |
| HIGH | STEP 8 F1: 근거와 모순되는 LLM 설명이 표시됨(CE001, 3회 재현) | 공개 의료 데모의 정보 정확성 | 공개 전 정책 결정(LLM 설명 비활성 / 의미 검증 / 사람 검토). F2·F3·R1도 미결 |
| HIGH(공개 시) | 노트북 메타데이터의 개발자 Google 이름·userId, 사용자 경로 17개 파일 | 공개 저장소에 개인정보 노출 | 비공개 저장소는 허용 가능. 공개 전 메타데이터 제거 사본·보고서 경로 마스킹 결정(노트북 02/04/05는 SHA 고정이라 테스트 기준 갱신 문제와 함께 결정 필요) |
| MEDIUM | 공개 데모의 LLM 비용·남용 제어 없음(finding당 1회 호출, 요청 제한 없음) | 비용 | OpenAI 사용 한도 설정, 접근 제한 또는 LLM 비활성 공개 모드 |
| MEDIUM | 콜드 스타트 90–160 s | 데모 첫인상 | 상시 실행(B), 사전 다운로드 |
| MEDIUM | 클라우드에서 실제 실행·Secrets·LFS 미검증 | 배포 성공 보장 불가 | STEP 9-2 이후 비공개 환경에서 검증 |
| LOW | 모델 로딩 실패 시 문구가 "DUR 데이터를 불러오지 못했습니다" | 원인 안내 부정확 | 선택 |
| LOW | 매니페스트 미사용 데이터 16개(20.6 MB)가 data/에 섞여 있음 | 정리 문제 | 삭제 금지, 분류만 |
| LOW | STEP 8 UI 경미 문제 U1–U5 | 사용성 | 기존 보고서 참고 |

## 11. Recommended Deployment Architecture

**권장: B — 영구 디스크가 있는 단일 Linux VM/컨테이너(비공개)**
- `requirements-server-cpu.txt` 설치, 데이터 13개를 비공개로 1회 배치(`fetch_runtime_data.py --verify`), bge-m3를 `HF_HOME`(영구 경로)에 사전 다운로드 후 `HF_HUB_OFFLINE=1`, `tools/deploy_preflight.py` FAIL 0 확인 후 `streamlit run app.py`.
- 선택 이유: 코드·Frozen Core·Hybrid 검색·모델을 **그대로** 쓰면서 측정된 메모리(약 6.6 GB)를 수용할 수 있는 유일한 후보다. 데이터를 공개 저장소에 올리지 않아도 된다.
- 사양: 측정값 기준 RAM ≥ 8 GB(여유 고려 시 16 GB), 디스크 ≥ 10 GB(데이터 0.64 GB + 모델 2.3 GB + 패키지)로 추정. 구체 공급자·비용·한도는 NOT_VERIFIED.
- 접근: 공개 전까지 인증·IP 제한으로 비공개 운영.

**대안: A — Streamlit Community Cloud (조건부)**
- 공식 문서에서 메모리 한도가 측정 요구량(약 6.6 GB 커밋)을 넘는다는 것과 앱 컨테이너의 모델 캐시 유지 여부를 사용자가 확인한 경우에만 시도한다. 데이터는 비공개 외부 저장소에서 부팅 시 `--fetch`(해시 검증)로 받는다.
- 메모리를 맞추려고 모델 교체·BM25-only 축소를 하는 것은 금지 사항이므로, 한도가 부족하면 이 대안은 쓰지 않는다.
- C(분리 구조)는 코드 변경 범위가 커서 이번 목표(기존 로직 보존 배포)에 맞지 않아 후순위로 둔다.

## 12. STEP 9-1 Final Decision

**STEP9_1_STATUS = CONDITIONAL_PASS**

배포용 구조 정리(필수 파일 식별, 의존성 고정, Linux CPU 설치 파일, `.gitignore`, 사전 점검, 가이드)와 로컬 무결성 검증은 끝났다. 데이터 이용 조건, 호스팅 자원, 공개 시 개인정보·LLM 설명 정책이 남아 있다.

```
STEP9_1_STATUS              = CONDITIONAL_PASS
GITHUB_PRIVATE_REPO_READY   = YES   (조건: 현재 .gitignore 그대로 — data/ 제외, 비공개 저장소, 사용자가 직접 생성·push)
PUBLIC_REPOSITORY_READY     = NO    (데이터 조건 NOT_VERIFIED, 노트북 개인정보 메타데이터, 사용자 경로)
STREAMLIT_CLOUD_FEASIBILITY = NOT_VERIFIED (공식 자원 한도 미확인. 측정 6.6 GB·모델 2.3 GB 기준 부적합 가능성 높음 — 권장하지 않음)
DATA_REDISTRIBUTION_STATUS  = NOT_VERIFIED
SECURITY_STATUS             = PASS_WITH_NOTES (비밀값 노출 0, 키 재발급 불필요 / 공개 전 개인정보 메타데이터 처리 필요)
CORE_INTEGRITY_STATUS       = PASS  (Frozen Core 9/9, manifest 35/35, 런타임 동작 변경 전후 동일)
RECOMMENDED_NEXT_STEP       = STEP 9-2: 비공개 GitHub 저장소 생성(사용자 실행) + 데이터 보관 위치·호스팅(B) 결정 + 데이터 이용 조건 확인
```

## 부록. 재현 명령

```bash
# 공통: 프로젝트 루트, PYTHONUTF8=1
env -u OPENAI_API_KEY HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/Scripts/python.exe -X utf8 reports/step9_1_validation/runtime_trace.py . reports/step9_1_validation/runtime_trace_after.json
.venv/Scripts/python.exe -X utf8 tools/deploy_preflight.py
sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m pip install --dry-run --ignore-installed --only-binary=:all: --platform manylinux_2_28_x86_64 --python-version 3.12 --implementation cp --target <tmp> -r requirements-server-cpu.txt --report <tmp>/report.json
git --git-dir=<scratch>/probe.git --work-tree=. ls-files --others --exclude-standard   # git init --bare <scratch>/probe.git 후
```

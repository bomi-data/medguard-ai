# STEP 10-1 — GitHub 포트폴리오 저장소 점검 및 정리

- 작성일: 2026-10-27 / 대상: MEDGUARD AI (연구·포트폴리오용 프로토타입, **임상 검증 아님**)
- 선행: STEP 9-3 `CONDITIONAL_READY` (`reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, 2026-10-24, **아직 커밋되지 않음**)
- 방향: 공개 웹 배포 보류, GitHub 중심 기술 포트폴리오로 완성. 실행 구조는 향후 배포가 가능하도록 그대로 유지.
- 표기
  - **실측**: 이번 세션(컴퓨터 재시작 후)에서 직접 실행·확인함
  - **기존**: 이전 보고서의 기록(출처 표기). 이번에 다시 검증하지 않음
  - **코드**: 소스를 읽어 확인한 사실(실행하지 않음)
  - **추정**: 근거를 밝힌 판단
  - **NOT_VERIFIED**: 확인하지 못함
- 이번 단계에서 하지 않은 것: 코드·설정·데이터·모델·평가 결과 수정/삭제, commit / push / pull / fetch / reset, 저장소 공개 전환, LLM·유료 API 호출, 모델 다운로드, 앱 실행, pytest 실행, 가상환경 생성, 패키지 설치
- 이번 단계에서 만든 파일: 이 보고서 1개(+ 프로젝트 밖 임시 폴더의 `git archive` 사본, §7 참고)

---

## 0. 최종 판정

```
STEP10_1_STATUS = CONDITIONAL_READY
```

포트폴리오 정리 단계(STEP 10-2)는 바로 진행할 수 있다. 다만 아래 항목을 STEP 10-2~10-5 안에서 처리해야 한다.

| 구분 | 내용 | 차단 여부 |
|---|---|---|
| C1 | STEP 9-3 보고서와 산출물이 아직 커밋되지 않음(작업 트리에만 있음) | 비차단. 사용자가 검토 후 커밋 |
| C2 | 저장소 루트의 `er.email` 이 실수로 커밋됨. 내용은 추적 파일 목록(186줄)이며 비밀정보는 없음 | 비차단. 정리 대상 |
| C3 | README가 STEP 7~9 결과(평가 수치, Linux 실행, 화면)를 반영하지 않고, 배포 안내가 새 방향(배포 보류)과 맞지 않음 | STEP 10-2 핵심 작업 |
| C4 | 데이터 이용 조건(특히 의약품 제품 허가정보) **NOT_VERIFIED**. LICENSE 없음 | **공개 전환 차단**(비공개 유지 시 비차단) |
| C5 | 커밋 작성자 메타데이터에 개인 이메일 주소가 있음(값은 기록하지 않음) | 공개 전환 전에 사용자가 결정 |

`BLOCKED` 가 아닌 이유: 실제 비밀정보 0건, Frozen Core 9/9 · data manifest 35/35 무결성 통과(실측), 원격 저장소는 비공개 상태로 추정되며 로컬과 동기화됨(실측).

---

## 1. 컴퓨터 재시작 후 환경 점검 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 프로젝트 루트 | `C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer` 존재 | 실측 |
| 예상 파일·폴더 | `app.py`, `app/`, `src/`, `ui_integration/`, `requirements.txt`, `README.md`, `reports/`, `notebooks/`, `.gitignore` 모두 존재. 그 밖에 `tests/`, `tools/`, `data/`, `.streamlit/` 존재 | 실측 |
| 시스템 Python | 3.12.10 | 실측 |
| `.venv` | 존재, `.venv\Scripts\python.exe` 실행 가능(3.12.10) | 실측 |
| 주요 라이브러리 | streamlit 1.66.0, torch 2.11.0, transformers 5.20.2, sentence-transformers 5.7.0, numpy 2.1.3, pandas 2.2.3, scikit-learn 1.6.1, openai 2.54.0, huggingface-hub 2.2.0, pytest 8.4.2 | 실측(`importlib.metadata`) |
| 요구사항 대비 | 위 버전이 `requirements.txt` 고정값과 일치. 설치·재설치 하지 않음 | 실측 |
| bge-m3 모델 캐시 | `BAAI/bge-m3@5617a9f6` 로컬 HF 캐시에 있음(로드는 하지 않음) | 실측(`deploy_preflight.py`, `try_to_load_from_cache`) |
| `OPENAI_API_KEY` | 현재 세션 환경변수에 **없음**. `.env`, `.streamlit/secrets.toml` 파일도 없음 | 실측. STEP 10-1에는 불필요하므로 설정 요청하지 않음 |
| 로컬 사전 점검 | `tools/deploy_preflight.py`(전체 모드, `HF_HUB_OFFLINE=1`): **FAIL 0 / WARN 1 / OK 9**. WARN은 API 키 없음 | 실측 |

**결론**: 재시작 후 실행 환경은 정상이다. LLM 설명 기능만 키가 없어 비활성 상태이며, 이는 이번 단계 범위 밖이다.

### 1-1. Git / GitHub 연결 상태

| 항목 | 결과 | 근거 |
|---|---|---|
| Git 저장소 | 정상 | 실측 |
| 현재 브랜치 | `main` (upstream `origin/main`) | 실측 |
| 원격 | `origin` → `https://github.com/bomi-data/medguard-ai`. URL에 토큰 없음 | 실측 |
| 커밋 | 1개: `23c5376 Initial MEDGUARD AI deployment preparation` | 실측 |
| 원격 동기화 | `git ls-remote origin`: 원격 `refs/heads/main` = `23c5376…` = 로컬 HEAD | 실측(읽기 전용, fetch 아님) |
| 비공개 여부 | 자격증명 없이 접근하면 인증을 요구하며 거부됨 → **비공개로 추정**. `gh` CLI가 없어 visibility 값은 직접 조회하지 못함 | 추정 / visibility API 값은 NOT_VERIFIED |
| 커밋되지 않은 변경 | 추적 파일 변경 **0건**. 미추적 2건: `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, `reports/step9_3_validation/` | 실측 |

---

## 2. 프로젝트 현재 상태

### 2-1. 단계별 판정 (기존 보고서 기준, 이번에 재검증하지 않음)

| 단계 | 판정 | 핵심 내용 | 출처 |
|---|---|---|---|
| STEP 4 | (Windows 기능 검증) | Windows에서 실행 경로 확인 | `STEP4_WINDOWS_FUNCTIONAL_VALIDATION.md` |
| STEP 5 | INCOMPLETE | 남은 FAIL은 CPU 엄격 검색 회귀 1건. Frozen baseline의 CPU 기록(3/33)과 같음 | `STEP5_REGRESSION_RECOVERY.md` |
| STEP 6 | PASS | RAG 런타임(bge-m3 고정 revision) | `STEP6_RAG_RUNTIME_VALIDATION.md` |
| STEP 7 | BLOCKED | 저장된 실제 출력 30건: Groundedness 265/274 = 96.7%, Hallucination 2/274 = 0.73%(LLM judge, 사람 검토 0건). 합성 위험 응답에서 표현 기반 위험이 Guardrail을 통과 | `STEP7_GENERATION_GUARDRAIL_VALIDATION.md` |
| STEP 7-R | INCOMPLETE | 문장 단위 `unsafe_text_reasons()` 추가. 규칙 밖의 바꿔 쓴 표현은 여전히 통과 | `STEP7_R_GUARDRAIL_REVALIDATION.md` |
| STEP 7-FINAL | CONDITIONAL_PASS | 실제 gpt-5.4-mini 호출 10/10 성공. 7/10 표시, 3건은 Frozen Core 규칙에 의한 fail-closed 보류. CE001 근거 모순 문장 재현(MAJOR) | `STEP7_FINAL_REAL_LLM_VALIDATION.md` |
| STEP 8 | CONDITIONAL_PASS | Streamlit 통합. UI 어댑터↔Core 30/30 일치. CE001 근거 모순이 3회 연속 발생 | `STEP8_STREAMLIT_INTEGRATION_VALIDATION.md` |
| STEP 9-1 | CONDITIONAL_PASS | `.gitignore`, 요구사항 고정, preflight 도구, `DEPLOYMENT.md` | `STEP9_1_DEPLOYMENT_READINESS.md` |
| STEP 9-2 | CONDITIONAL_PASS | Git 준비, 개인정보 정리, `PUBLIC_REPOSITORY_READY = NO` | `STEP9_2_GITHUB_PREPARATION.md` |
| STEP 9-3 | CONDITIONAL_READY | Linux(WSL2 Ubuntu 24.04)에서 clean clone 실행: RSS 4.98 GiB, 콜드 스타트 74.9 s, 2 vCPU 정상 | `STEP9_3_DEPLOYMENT_ARCHITECTURE.md` (**미커밋**) |

사용자 요청서에 적힌 "메모리 약 5GiB, 첫 접속 후 약 75초"는 STEP 9-3 보고서의 **기존** 수치(4.98 GiB, 74.9 s)와 일치한다. 이번 세션에서는 앱을 실행하지 않았으므로 **다시 측정하지 않았다**.

### 2-2. 이번 세션 무결성 확인 (실측)

| 항목 | 결과 |
|---|---|
| Frozen Core (`sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt`) | **9/9 OK** |
| `src/` 와 HEAD 차이 | 없음 |
| data manifest (`deploy_preflight.py` 전체 모드) | **35/35 SHA256 일치** |
| `app.py` REQUIRED_FILES | 16/16 존재 |
| 감사 결과(Gate/Coverage 화면용) | `ingredient_coverage_audit` 1 run, `ui_coverage_audit` 1 run |
| 추적 파일 변경 | 0건 → 평가 결과·검증 자료 변경 없음 |

**의료 판단 로직(Screening 규칙, 위험 등급, Guardrail, 프롬프트) 변경: 없음.**

---

## 3. GitHub 저장소 구조 분석

### 3-1. 추적 현황 (실측)

- 추적 파일 187개, 합계 약 **3.8 MB**. 1 MB를 넘는 파일 없음.
- `data/`, `.venv/`, `.idea/`, `_backup_*/`, `_incoming_*/`, 노트북 02/04/05, 로그·JUnit XML·runtime trace JSON은 **추적되지 않음**(`.gitignore` 동작 확인).
- 데이터·임베딩·모델 가중치는 Git에 **없음**(실측: `git ls-files` 에 `data/` 0건, 대용량 파일 0건).

```
app.py                      진입점 (runpy → ui_integration/app_v2.py)
app/                        Streamlit 화면 컴포넌트, ui_policy(Guardrail 표시 정책), ui_runtime, adapters, styles
ui_integration/             app_v2.py, ingredient_dur_ui_adapter.py
src/dur_safety/             Frozen Core 9개 모듈 + FROZEN_SHA256SUMS.txt
notebooks/15_*.ipynb        성분 중복 후보 코드(런타임에서 읽음)
tests/                      회귀·계약·UI 어댑터 테스트(12개 파일)
tools/                      deploy_preflight.py, fetch_runtime_data.py, nbsource.py
reports/                    STEP 4~9 보고서, 검증 스크립트·지표·화면, 감사 결과
data_manifest.json          데이터 35개 파일 경로·SHA256
production_baseline.json    Frozen baseline(모델 revision, 설정 sha256, 회귀 증거)
requirements*.txt           고정 의존성(+ CPU 서버용)
.streamlit/                 config.toml, secrets.toml.example
README.md, DEPLOYMENT.md, DATA_STRATEGY.md, .env.example, .gitattributes(* -text)
```

### 3-2. 로컬에만 있는 항목 (Git 제외, 정상)

| 항목 | 크기·내용 | 비고 |
|---|---|---|
| `data/` | 642 MB. 100 MB 초과 2개(`drug_approval_items.parquet` 392.5 MB, `approval_chunks.parquet` 129.6 MB), 임베딩 `unique_text_embeddings.npy` 75.8 MB | 런타임 필수, Git 제외 유지 |
| `_backup_step2/7r/8/9_1/9_2_*` | 단계별 수정 전 백업 | 로컬 보존. 삭제하지 않음 |
| `_incoming_drive_originals/` | Drive 원본 | 로컬 보존 |
| `notebooks/02, 04, 05` | Colab 메타데이터에 개발자 Google 표시 이름·ID (STEP 9-2) | Git 제외 유지 |
| `reports/**/*.log`, `*.xml`, `*runtime_trace*.json`, `playwright_artifacts/` | 로컬 절대경로 포함 가능 | Git 제외 유지 |

---

## 4. 파일 유지·제외 권장 목록

| 분류 | 대상 | 이유 |
|---|---|---|
| **KEEP_RUNTIME** | `app.py`, `app/**`, `ui_integration/**`, `src/dur_safety/**`(Frozen), `notebooks/15_ingredient_duplicate_candidates_prototype.ipynb`, `.streamlit/config.toml`, `requirements.txt`, `requirements-server-cpu.txt`, `data_manifest.json`, `reports/ingredient_coverage_audit/run_20261012_184823/**`, `reports/ui_coverage_audit/run_20261011_152938/**`, `.gitattributes` | 실행 경로에서 직접 읽음. 감사 run 폴더 6개 파일은 manifest에 포함되며 Gate/Coverage 화면이 읽음. `.gitattributes` (`* -text`)는 Windows clone에서 Frozen SHA가 깨지는 것을 막음 |
| **KEEP_PORTFOLIO** | `README.md`, `DEPLOYMENT.md`, `DATA_STRATEGY.md`, `.env.example`, `.streamlit/secrets.toml.example`, `reports/STEP*.md`, `reports/step8_validation/screens/*.png`(5장) | 시스템 설명·한계·실행 화면 근거 |
| **KEEP_VALIDATION** | `tests/**`, `tools/**`, `production_baseline.json`, `src/dur_safety/FROZEN_SHA256SUMS.txt`, `requirements-dev.txt`, `reports/step4_validation_scripts/`, `reports/step5_6_validation/`, `reports/step7_validation/`(사전 등록 기준 `STEP7_CRITERIA_PREREGISTERED.md`, `step7_metrics.json`), `reports/step7r_validation/`, `reports/step7final_validation/`(호출 ledger 포함), `reports/step8_prep/`, `reports/step8_validation/`, `reports/step9_1_validation/`, `reports/step9_2_validation/`, `reports/data_integrity_report.json`, `reports/final_checks.json` | 평가 재현·무결성 증거. 변경·삭제 금지 |
| **KEEP_VALIDATION (커밋 필요)** | `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, `reports/step9_3_validation/`(profile json/out, `resource_profile.py`, `streamlit_linux_server.txt`) | 현재 미추적. 이번 점검에서 사용자 경로·이름·이메일 패턴 0건(실측). `playwright_artifacts/` 는 `.gitignore` 규칙으로 자동 제외됨 |
| **REVIEW** | `er.email` | 실수로 커밋된 파일로 추정. 내용은 `git ls-files` 결과와 같은 파일 목록이며 비밀정보 0건(실측). 포트폴리오 가치가 없으므로 사용자 승인 후 `git rm` 권장 |
| **REVIEW** | `MERGE_NOTE.txt` | ZIP 병합 안내 1줄. 현재 Git 기반 흐름에서는 의미 없음 |
| **REVIEW** | `reports/transfer_summary.md`, `transfer_manifest.csv`, `excluded_files.csv`, `unresolved_files.csv`, `read_errors.csv`, `dependency_report.md` | Drive→PyCharm 이전 기록. 이력 증거로 가치가 있지만, 포트폴리오 독자에게는 혼란스러울 수 있음. `read_errors.csv` 에 Colab 경로(`/content/drive/MyDrive/medical-ai-project`, 개인 이름 없음) 포함. `reports/archive/` 로 옮기거나 README에서 설명 권장 |
| **REVIEW** | `.gitattributes.lfs.example` | LFS를 쓰지 않기로 하면 불필요. `.gitignore` 주석이 참조하므로 유지해도 무방 |
| **EXCLUDE (현행 유지)** | `data/`, `.venv/`, `.idea/`, `_backup_*/`, `_incoming_*/`, `notebooks/02·04·05`, `*.log`, `reports/**/*.xml`, `*runtime_trace*.json`, `playwright_artifacts/`, `.env`, `.streamlit/secrets.toml`, `__pycache__/` | 대용량, 이용 조건 미확인, 개인정보·로컬 경로 포함, 비밀정보 |

중복 파일: 추적 파일 안에서 의미 있는 중복은 없다. `er.email` 이 파일 목록을 중복 보관하는 정도다. 로컬의 `_backup_*` 은 의도된 백업이며 Git 밖에 있다.

---

## 5. 보안 및 개인정보 점검 결과

검사 범위: HEAD 추적 파일 187개 + Git 기록(커밋 1개, 모든 ref) + 미추적 STEP 9-3 산출물. 원문 값은 출력하거나 기록하지 않았다.

| 항목 | 결과 | 위험 | 권장 조치 |
|---|---|---|---|
| OpenAI 키 형식(`sk-…`) | 실제 키 **0건**. STEP 8 오류 처리 시험용 **가짜 키** 문자열이 보고서 3곳에 있음(`STEP8_…md`, `STEP9_1_…md`, `STEP9_2_…md`) | 없음(가짜 값) | 유지. 공개 시 비밀 스캐너가 경고할 수 있으므로 README 또는 보고서에서 가짜 키임을 밝힐 것(이미 보고서에 명시됨) |
| GitHub/HF/AWS/Google 토큰, 개인키 | 0건 | — | — |
| `api_key = "<literal>"` 하드코딩 | 0건 | — | 키는 환경변수/Streamlit secrets로만 읽음(코드) |
| `.env`, `secrets.toml` | Git 기록에 **없음**(모든 커밋에서 파일명 검사), 로컬에도 없음. `.gitignore` 에 규칙 있음 | — | 유지 |
| 원격 URL 토큰 | 없음 | — | — |
| 개발자 실명·Google ID | 추적 파일에서 0건. 노트북 15의 `executionInfo` 에는 `elapsed/status/timestamp/user_tz` 만 남음(`user` 블록은 STEP 9-2에서 제거됨) | 낮음 | 유지 |
| Windows 사용자 경로 | STEP 4~9 보고서의 경로는 `<USER>` 로 가려져 있음(실측: 사용자 이름 문자열 0건) | 낮음 | 유지 |
| Colab 경로 | `src/dur_safety/config.py`, `screening.py`(Frozen), 노트북 15, 감사 manifest 2개, `read_errors.csv` 에 `/content/drive/MyDrive/medical-ai-project` | 낮음. 개인 식별 정보 없음. 개발 환경을 보여 줌 | Frozen Core는 수정 금지. 그대로 둠 |
| 이메일 패턴 | 추적 파일에서 0건(`test_ui_adapter.diff` 의 `@pytest…` 는 오탐). 이전 transfer 보고서의 의심 2건(`medguard.css` 는 `@import`/`@media`, `test_ui_adapter.py` 는 테스트 문자열)도 오탐 | — | — |
| **커밋 메타데이터** | 작성자 이메일이 개인 메일 주소(gmail 도메인). 값은 기록하지 않음 | **중간(공개 시)**. 공개 저장소에서는 누구나 `git log` 로 볼 수 있음 | 공개 전환 전에 사용자가 결정: (a) 그대로 공개, (b) GitHub noreply 주소로 기록 재작성. 재작성은 force push가 필요하므로 **사용자가 직접 판단·실행**. 이후 커밋에는 noreply 설정 권장 |
| 실수로 커밋된 파일 | `er.email`(파일 목록) | 낮음 | §4 REVIEW |
| 미추적 STEP 9-3 산출물 | 사용자 경로·이름·이메일 패턴 0건 | 낮음 | 커밋 전 사용자가 한 번 훑어볼 것 |
| 화면 캡처 5장 | 이번에 이미지 내용을 다시 열어 보지는 않음 | NOT_VERIFIED | STEP 10-4에서 확인 |

**Git 기록 판단**: 커밋이 하나뿐이고 위 검사에서 비밀정보가 없으므로, 현재 기록을 재작성할 필요는 없다. 개인 이메일 메타데이터만 공개 여부와 함께 결정할 사항이다. 이 단계에서는 기록을 재작성하지 않았다.

---

## 6. 데이터·모델 관리 현황

| 항목 | 현황 | 근거 |
|---|---|---|
| 런타임 데이터 | `data/processed/**` 29개 파일(manifest 35개 중 29개). Screening 4개, evidence, rag, retrieval(+dense 임베딩), generation 설정·결과 | 코드·manifest |
| 무결성 | `data_manifest.json` SHA256 + 앱 시작 시 `generation_config.json` 기록값 비교(불일치 시 실행 중단, fail-closed) | 코드(`DATA_STRATEGY.md`, `app.py`) |
| 데이터 배포 도구 | `tools/fetch_runtime_data.py --verify / --fetch`. `--fetch` 는 `MEDGUARD_DATA_BASE_URL` 이 필요하며 URL은 아직 없음(템플릿) | 코드 |
| 배포 방식 | `DATA_STRATEGY.md`: **NOT_DECIDED** | 기존 |
| 임베딩 모델 | `BAAI/bge-m3` revision `5617a9f6…` 고정. 최초 실행 시 HF Hub에서 약 2.3 GB 다운로드. 코퍼스 임베딩은 미리 계산된 `.npy` 사용 | 코드·`production_baseline.json` |
| LLM | OpenAI `gpt-5.4-mini`, `store=False`, 키 없으면 설명만 비활성 | `production_baseline.json`, preflight |
| 전처리 재현성 | 원본 공공데이터 → `data/processed` 생성 과정은 Colab 노트북(01·03 등)과 Drive에 있었고, 저장소에는 **생성 파이프라인이 없음**. 저장소의 노트북은 15번 하나. 02/04/05는 개인정보로 제외 | 실측(`git ls-files notebooks`) |
| 외부 사용자 재현 범위 | §7 참고 | — |
| 데이터 출처·이용 조건 | README §9와 STEP 9-3: 식약처 DUR·의약품 허가정보. **의약품 제품 허가정보(data.go.kr 15095677) 이용 조건 NOT_VERIFIED**. LICENSE 파일 없음 | 기존 |

**공개 저장소로 바꿀 때 추가로 제외·확인할 것**

1. `data/` — 지금처럼 계속 제외(용량 + 이용 조건).
2. `reports/` 안의 데이터 발췌: `ingredient_coverage_audit` CSV, STEP 7 평가 산출물(`step7_validation/` 등)에는 허가정보 문장 일부가 인용되어 있을 수 있음(**추정**, 이번에 내용 검토 안 함). 이용 조건 확인 결과에 따라 판단 필요.
3. 실제 LLM 출력 원문(`step7final_validation/`, `step8_validation/`): OpenAI 출력의 공개 자체는 일반적으로 문제되지 않는 것으로 알려져 있으나 이번에 약관을 확인하지 않음(NOT_VERIFIED).
4. 커밋 메타데이터의 개인 이메일(§5).

데이터와 모델을 GitHub에 올리도록 바꾸지 않았다. 권장 방향은 **현행 유지**(Git 제외 + manifest 해시 + 데이터 출처·생성 절차 문서화)다.

---

## 7. 실행 재현 가능성 평가

### 7-1. 저장소만으로 실행 가능한가 — 실측

`git archive HEAD` 로 커밋 내용만 프로젝트 밖 임시 폴더에 풀고, 기존 `.venv` Python으로 `tools/deploy_preflight.py --quick` 을 실행했다(앱·모델 로드 없음).

| 점검 | 결과 |
|---|---|
| `app.py` REQUIRED_FILES | **FAIL 3/16** — `data/processed/**` 13개 누락 |
| data manifest 존재 | WARN 6/35 (있는 6개는 `reports/` 감사 결과) |
| 모델 캐시 | OK — 단, 이 PC의 공용 HF 캐시를 썼기 때문. 외부 사용자는 **없음**(추정) |
| 종합 | **FAIL 1 / WARN 2 / OK 7** |

**결론: 현재 GitHub 저장소만으로는 앱을 실행할 수 없다.** 이것은 의도된 설계(데이터 Git 제외)의 결과다.

### 7-2. 데이터·모델이 없는 환경에서 예상되는 실패 (코드 기반 추정)

| 상황 | 예상 동작 | 근거 |
|---|---|---|
| `data/processed` 없음 | 앱이 REQUIRED_FILES 검사에서 중단(fail-closed) | 코드(`app.py` REQUIRED_FILES, preflight) |
| 데이터 해시 불일치 | 실행 중단 | `DATA_STRATEGY.md`, generation_config 비교 |
| 모델 캐시 없음 + 인터넷 있음 | 최초 실행 시 bge-m3 약 2.3 GB 다운로드 후 동작 | preflight 메시지 |
| 모델 캐시 없음 + `HF_HUB_OFFLINE=1` | 앱 시작 실패 | preflight 메시지 |
| API 키 없음 | Screening·근거 검색은 동작, LLM 설명만 비활성 | preflight, README §12, STEP 8 nokey 화면 |
| 메모리 8 GB 미만 | 실패 가능성 높음(RSS 약 5 GiB) | 기존(STEP 9-3) |
| pytest | 데이터가 없으면 `conftest.py` 가 데이터 의존 테스트를 skip. 데이터는 있고 노트북 02/04/05가 없으면 `test_source_parity` 가 파일 없음 오류로 실패할 것 | 코드(`tests/conftest.py`, `tools/nbsource.py`). 실행하지 않음 |

### 7-3. 외부 사용자가 할 수 있는 것

| 범위 | 가능 여부 |
|---|---|
| 코드·구조·Frozen Core 해시 검증(`sha256sum -c`) | 가능 |
| 보고서·평가 지표·화면 캡처 열람 | 가능 |
| 데이터 없이 일부 단위 테스트 | 부분 가능(대부분 skip, NOT_VERIFIED) |
| 앱 실행·Screening·RAG | **불가** — 데이터 배포 방식 미정 |
| 데이터 재생성 | **불가** — 전처리 파이프라인이 저장소에 없음 |

포트폴리오 목적에서는 "실행 화면 + 검증 보고서 + 실행 절차"로 이를 보완하는 것이 현실적이다. 데모 데이터 축소본 제작은 의료 판단 결과를 바꿀 수 있으므로 **권장하지 않는다**(기능 축소 금지 원칙).

---

## 8. 의료 AI 포트폴리오 관점의 강점과 약점 (기술 면접관 관점)

| 질문 | 평가 | 설명 |
|---|---|---|
| 시스템 구조를 쉽게 이해할 수 있는가? | **부분적** | README §4에 ASCII 구조도가 있으나 실행 경로(runpy, adapter) 중심이다. "Structured Screening → 근거 검색 → LLM 설명 → Guardrail → UI" 데이터 흐름과 "LLM은 판정하지 않는다"는 핵심 설계가 한눈에 보이지 않는다 |
| 기술 선택 이유가 설명되어 있는가? | **약함** | BM25+bge-m3 하이브리드, RRF(k=60), 한국어 char bigram, Frozen Core + SHA256, fail-closed Guardrail, `store=False` 등을 왜 골랐는지 README에 없다. 근거는 `production_baseline.json` 과 보고서에 흩어져 있다 |
| 의료 AI로서 검증 과정이 충분히 제시되어 있는가? | **강함(보고서) / 약함(README)** | 사전 등록 기준(`STEP7_CRITERIA_PREREGISTERED.md`), 저장 출력 30건 재평가, 실제 호출 ledger, 합성 위험 응답 778건, UI↔Core 30/30 일치, Linux clean clone 등 검증은 매우 충실하다. 그러나 README에서 이 내용으로 가는 길이 없다 |
| 평가 결과와 임상적 유효성이 구분되어 있는가? | **양호** | README 첫머리에 `CLINICAL_VALIDATION_STATUS = NOT_VALIDATED`. 보고서는 LLM judge·AI 대조와 사람·전문가 검토를 구분한다. README에 수치를 옮길 때도 "소프트웨어 평가 ≠ 임상 유효성"을 표로 유지해야 한다 |
| 한계가 투명하게 공개되어 있는가? | **보고서는 우수, README는 일반론** | STEP 7 BLOCKED(표현 변형 통과), CE001 근거 모순 3회 재현, 실제 출력 과잉 차단 3/9, CPU 검색 회귀 1건 등이 보고서에만 있다. 면접관에게는 이 "알고 있는 실패"가 오히려 강점인데 README에 드러나지 않는다 |
| 실행 화면과 사용 방법이 충분한가? | **약함** | 캡처 5장이 `reports/step8_validation/screens/` 에 있으나 README에 넣지 않았다. README §13은 Streamlit Cloud 배포 안내로, 새 방향(배포 보류)과 맞지 않는다. 데이터를 받는 방법이 없어서 "설치 방법"을 그대로 따라 하면 실패한다 |

**강점 요약**
1. 규칙 기반 판정과 LLM 설명의 역할 분리 — LLM이 DUR 판정을 만들지 않음.
2. Frozen Core + SHA256 + manifest + fail-closed: 재현성과 변경 통제가 코드로 강제됨.
3. 사전 등록 기준과 실패 공개(BLOCKED/INCOMPLETE를 숨기지 않음).
4. 실제 LLM 호출을 예산 ledger로 통제한 검증.
5. 간호학 배경과 연결되는 도메인 설계(노인주의, 효능군 중복, "발견되지 않음 ≠ 안전").

**약점 요약**
1. README가 STEP 7~9의 성과·한계를 담지 않음(가장 큰 격차).
2. 저장소만으로 실행 불가, 데이터 생성 과정 미포함.
3. 데이터 이용 조건·LICENSE 미정.
4. 단계 번호(STEP 4~9) 위주 보고서 구조 — 처음 보는 사람이 읽기 어렵다.
5. README의 오래된 정보: streamlit `VERSION_UNSPECIFIED`(현재 1.66.0 고정), RAG "배포 환경 NOT_VERIFIED"(STEP 9-3에서 Linux 로컬 실행 확인됨), Streamlit Cloud 안내.

---

## 9. README 개선 방향 (STEP 10-2 입력)

### 9-1. 권장 구성

1. 한 줄 소개 + 의료 안전 고지(현행 유지) + 상태 배지 성격의 표(`NOT_VALIDATED`, 공개 배포 없음)
2. **대표 화면 2~3장**(`reports/step8_validation/screens/` 재사용)
3. 핵심 설계 원칙 3가지: 규칙이 판정, LLM은 설명만 / 근거 인용 강제 + fail-closed Guardrail / Frozen Core
4. 아키텍처 다이어그램(데이터 흐름 기준, Mermaid)
5. 기술 선택 이유 표(선택 / 대안 / 이유)
6. **검증 요약 표** — 지표, 값, 표본, 평가 방법(LLM judge/규칙/사람), 한계. 출처 보고서 링크 포함
7. **알려진 한계와 실패 사례**(STEP 7 BLOCKED, CE001, 과잉 차단, CPU 회귀)
8. 실행 방법: 요구 사양(8 GB RAM), 데이터 준비 방식, preflight, `streamlit run app.py`, 키 없을 때의 동작
9. 저장소 구조와 보고서 읽는 순서(STEP 안내)
10. 데이터 출처·이용 조건(확인 후), 라이선스

### 9-2. README에 넣을 자료 목록

| 자료 | 위치 | 상태 |
|---|---|---|
| 화면 캡처 5장 | `reports/step8_validation/screens/*.png` | 있음(내용 재확인 필요) |
| Groundedness / Hallucination / Usefulness / Screening consistency | `STEP7_GENERATION_GUARDRAIL_VALIDATION.md` §0, `step7_metrics.json` | 있음 |
| 실제 LLM 10건 결과, 과잉 차단, CE001 | `STEP7_FINAL_REAL_LLM_VALIDATION.md` §0 | 있음 |
| UI↔Core 30/30, CE001 3회 재현 | `STEP8_STREAMLIT_INTEGRATION_VALIDATION.md` | 있음 |
| Linux 자원 측정(RSS, 콜드 스타트, 2 vCPU) | `STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, `step9_3_validation/profile_*.json` | 있음(**미커밋**) |
| 검색 설정(BM25 파라미터, RRF, depth, top-k), 모델 revision | `production_baseline.json` | 있음 |
| Source parity 240/240, negative control | `production_baseline.json` `regression_evidence` | 있음 |
| Coverage 지표 | `reports/ui_coverage_audit/…/03_coverage_metrics.csv`, `ingredient_coverage_audit/…/12_ingredient_coverage_report.md` | 있음 |
| Screening 규칙 수·데이터 규모 | `data/processed/screening/*.parquet` (로컬) | 집계 필요(읽기 전용) |
| 검색 정확도(Recall@k 등) | 저장소에 독립 지표 없음(smoke test 결과는 `data/` 안) | **NOT_VERIFIED / 확인 필요** |
| 데이터 출처 URL·이용 조건 | 없음 | **사용자 확인 필요** |
| 전처리 노트북(01·03 등) 요약 | Drive 원본 | 저장소에 없음 |

---

## 10. 후속 작업 우선순위

원칙: 새 기능 개발보다 **이미 한 일을 보여 주는 작업**을 먼저 한다. 의료 판단 로직·Frozen Core·평가 결과는 바꾸지 않는다.

### STEP 10-2 — README 및 기술 문서 개선 (P0)
1. README 재작성(§9-1 구성). 오래된 정보 정정(§8 약점 5). Streamlit Cloud 안내는 "배포 보류, 향후 계획"으로 이동하고 `DEPLOYMENT.md` 로 연결.
2. `docs/ARCHITECTURE.md`: 데이터 흐름, 모듈 책임, Frozen Core 정책, 설계 결정 기록(ADR 형식 짧게).
3. `reports/README.md`(보고서 색인): 각 STEP이 무엇을 검증했고 판정이 무엇인지 한 표로.
4. 데이터 준비 절차 문서화: 필요한 파일 목록(manifest), 출처, "현재 외부 사용자는 데이터 없이 실행 불가"를 명시.
5. (사용자 승인 후) `er.email` 제거, STEP 9-3 산출물 커밋.

### STEP 10-3 — 평가 결과 및 의료 AI 한계 정리 (P0)
1. `docs/EVALUATION.md`: 지표별 값·표본 크기·평가 주체(규칙/LLM judge/AI 대조/사람)·데이터 출처(REAL_STORED/SYNTHETIC/REAL_NEW)를 한 표로. 기존 보고서의 수치만 사용하고 새로 계산하지 않음.
2. `docs/LIMITATIONS.md`: 임상 검증 없음, 공식 성분 동일성 NO-GO, STEP 7 BLOCKED 원인, CE001, 과잉 차단, CPU 검색 회귀, 데이터 시점.
3. "소프트웨어 평가 ≠ 임상 유효성" 구분 표.
4. 데이터 출처·이용 조건 정리(사용자 확인 결과 반영). LICENSE 결정.

### STEP 10-4 — Streamlit 시연 자료 제작 (P1)
1. 기존 캡처 5장의 개인정보 확인 후 `docs/images/` 로 정리(원본은 보존).
2. 필요하면 로컬에서 앱을 실행해 대표 시나리오 캡처 추가(키 없이 가능한 Screening·근거 화면 우선. LLM 화면은 기존 실제 호출 캡처 재사용 → 추가 API 비용 없음).
3. 짧은 GIF 또는 시연 영상(선택). 화면에 "연구용, 임상 사용 금지" 고지가 보이도록.

### STEP 10-5 — GitHub 포트폴리오 최종 검증 (P1)
1. 새 폴더에 clean clone 후 문서 링크·이미지 경로 확인.
2. 비밀정보·개인정보 재스캔(이번 §5 방법 재사용), 미추적 파일 정리 확인.
3. Frozen Core 9/9, manifest 35/35 재확인.
4. 공개 전환 여부 결정 체크리스트: 데이터 이용 조건, LICENSE, 커밋 이메일, `reports/` 내 데이터 발췌.
5. 저장소 About, topics, 고정(pin) 설정 — 사용자가 GitHub에서 직접.

---

## 11. 최종 판정

```
STEP10_1_STATUS          = CONDITIONAL_READY
STEP10_2_READINESS       = YES
PUBLIC_REPOSITORY_READY  = NO   (데이터 이용 조건 NOT_VERIFIED, LICENSE 없음, 커밋 이메일 결정 필요)
CORE_LOGIC_CHANGED       = NO   (Frozen Core 9/9, 추적 파일 변경 0)
SECRETS_IN_GIT           = NONE FOUND (가짜 시험 키 문자열만 존재)
REPO_ALONE_RUNNABLE      = NO   (data/ 미포함 — 의도된 설계)
```

### 확인하지 못한 사항 (NOT_VERIFIED)
- GitHub 저장소 visibility 값 직접 조회(`gh` 없음). 익명 접근 거부로 비공개로 추정.
- 앱 실행, 메모리·시작 시간 재측정(이번 세션에서 실행하지 않음, STEP 9-3 수치 인용).
- pytest 실행 결과(실행하지 않음).
- 화면 캡처 5장의 개인정보 여부.
- 데이터 이용 조건·재배포 가능 여부, OpenAI 출력 공개 관련 약관.
- `reports/` 내 평가 산출물에 포함된 허가정보 원문 인용 범위.

### 사용자가 직접 해야 하는 작업
1. `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, `reports/step9_3_validation/`, 이 보고서를 검토하고 커밋·push 할지 결정.
2. `er.email` 삭제 여부 결정(권장: `git rm er.email`).
3. 의약품 제품 허가정보(data.go.kr 15095677) 등 데이터 이용 조건 확인, LICENSE 선택.
4. 공개 전환을 고려한다면 커밋 작성자 이메일 처리 방식 결정(기록 재작성은 force push 필요).
5. GitHub 웹에서 저장소가 Private인지 한 번 확인.

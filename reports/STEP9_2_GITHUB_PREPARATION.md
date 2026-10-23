# STEP 9-2 — GitHub 비공개 저장소 업로드 준비 보고서

- 작성일: 2026-10-23 / 대상: MEDGUARD AI (연구·교육용 프로토타입, **임상 검증 아님**)
- 선행: `reports/STEP9_1_DEPLOYMENT_READINESS.md` (CONDITIONAL_PASS)
- 산출물: `reports/step9_2_validation/`
- 이번 단계에서 실행하지 않은 것: `git commit`, `git remote add`, `git push`, 공개 범위 변경, 외부 배포, 유료 API 호출, 의료 판단 로직 수정
- 개인정보 보호: 이 보고서와 산출물에는 사용자 이름·Google 계정 ID·이메일을 쓰지 않았다(`<USER>`로 표기).

## 0. 결론

```
STEP9_2_STATUS = CONDITIONAL_PASS
```

| 질문 | 답 |
|---|---|
| 1. 상태 | **CONDITIONAL_PASS** — 업로드 대상 정리·검증 완료. 조건: 사용자가 commit·remote·push를 직접 실행하고, push 전에 원격 저장소가 Private인지 확인 |
| 2. Git 초기화 | 기존 저장소 **없음**(remote·커밋 이력 없음). `git init -b main` 실행, 186개 파일 **staging만** 함(커밋 없음) |
| 3. 업로드/제외 | 업로드 186개 3.97 MB(코드·설정 예시·requirements·문서·검증 기록). 제외: `.venv`, `.idea`, `data/`, 비밀값 파일, 캐시, 로그, 백업, 개인정보 포함 파일 — §2 |
| 4. API 키·개인정보 | staging 대상에서 실제 키 0, 토큰 0, 사용자 이름 0, Google userId 0, 이메일 0 (§3). 업로드 전에 개인정보 18개 파일을 처리함 |
| 5. 대용량 | 포함 안 됨. 최대 파일 0.27 MB. 데이터(638 MB)·모델(2.3 GB)·`.npy`·`.parquet`·`.bin` 0개 |
| 6. 의료 판단 로직 | **보존**. Frozen Core SHA256 9/9(작업 트리·업로드 사본 모두), manifest 35/35, 코드 변경 0 |
| 7. 업로드 가능 | **가능**(비공개 저장소). 공개 저장소는 STEP 9-1 판정대로 아직 불가 |
| 8. 사용자 명령 | §8 |

## 1. Git 상태 확인 (작업 1)

| 항목 | 결과 (작업 전) |
|---|---|
| 저장소 초기화 | **아니오** — `git rev-parse` 실패, 상위 폴더에도 `.git` 없음 |
| 브랜치 / remote | 없음 / 없음 |
| 추적 파일 | 없음 |
| 기존 커밋 이력의 민감정보 | **해당 없음**(이력 없음) |
| 전역 커밋 작성자 | `user.name` 설정됨, `user.email` 설정됨(gmail) — 커밋에 그대로 기록됨(§8) |
| 줄바꿈 설정 | 시스템 설정 `core.autocrlf=true` (Git for Windows 기본값) — §4.2 위험 |
| Git 버전 | 2.55.0.windows.5 |

조치: `git init -b main` 후 `git add -A` (staging). 기존 Git 설정·remote를 지우거나 바꾼 것은 없다(원래 없었음). 전역 설정도 바꾸지 않았다.

## 2. 업로드 대상 점검 (작업 2)

### 2.1 업로드 대상 (186개, 3.97 MB, 전체 목록: `step9_2_validation/staged_files.txt`)

| 영역 | 파일 수 | 내용 |
|---|---|---|
| 실행 코드 | `app.py` 1, `app/` 25, `src/dur_safety/` 10, `ui_integration/` 2 | 진입점, UI, Frozen Core 9개 + `FROZEN_SHA256SUMS.txt`, 성분 후보 어댑터 |
| 런타임 비코드 | `notebooks/15_*.ipynb` 1, `production_baseline.json`, `data_manifest.json`, `.streamlit/config.toml`, 감사 결과 5개(`reports/ingredient_coverage_audit`, `reports/ui_coverage_audit`) | 앱이 실행 중 읽는 파일 |
| 설정 예시·의존성 | `.env.example`, `.streamlit/secrets.toml.example`, `requirements.txt`, `requirements-server-cpu.txt`, `requirements-dev.txt`, `.gitignore`, `.gitattributes`, `.gitattributes.lfs.example` | 값 없음 |
| 도구·테스트 | `tools/` 3, `tests/` 12 | 사전 점검, 데이터 검증, 회귀 테스트 |
| 문서 | `README.md`, `DEPLOYMENT.md`, `DATA_STRATEGY.md`, `MERGE_NOTE.txt` | |
| 검증 기록 | `reports/` 117개 (STEP 4–9 보고서, 검증 스크립트·CSV·JSON·스크린샷, 실제 LLM 출력) | 개인정보·키 없음 확인 |

### 2.2 제외 대상과 `.gitignore` 실제 작동 확인 (`git check-ignore -v`)

| 대상 | 규칙 | 확인 |
|---|---|---|
| `.venv/` | `.venv/` | ✓ ignored |
| `.idea/` | `.idea/` | ✓ |
| `__pycache__/`, `*.pyc` | `__pycache__/` | ✓ |
| `.env`, `.streamlit/secrets.toml` | 해당 규칙 | ✓ (현재 파일 자체가 없음) |
| 원본·가공 데이터, 임베딩 | `data/` | ✓ (`approval_chunks.parquet` 예시) |
| 백업 | `_backup_*/`, `_incoming_*/` | ✓ |
| 실행 로그 | `*.log` | ✓ |
| Playwright 산출물 | `reports/*/playwright_artifacts/` | ✓ |
| **개인정보 포함 개발 파일 (신규)** | `notebooks/02,04,05_*.ipynb`, `reports/**/*.xml`, `reports/step5_6_validation/rag_probe_result.json`, `reports/**/*runtime_trace*.json` | ✓ |
| 모델 파일 | 저장소 밖(HF 캐시) | 해당 없음 |

유지해야 할 파일(`.env.example`, `secrets.toml.example`, `config.toml`, requirements 2종, 노트북 15, 감사 결과)은 모두 staging됨을 `git ls-files --error-unmatch`로 확인했다.

## 3. API 키·개인정보 노출 위험

staging된 blob 기준(`git grep --cached`) 최종 결과:

| 항목 | 결과 |
|---|---|
| OpenAI 키 형식(`sk-…`) | 실제 키 **0**. 의도적 가짜 키 `sk-step8-fake-not-a-real-key`(STEP 8 오류 처리 시험용)가 2개 문서에 있음 — 실제 키 아님 |
| AWS·GitHub·HF·Google API 키·개인키 | 0 |
| 사용자 이름(Windows 계정명) | **0** |
| Google 계정 userId | **0** |
| 커밋 작성자 이메일 문자열 | 0 (단, 커밋 메타데이터에는 기록됨 — §8) |
| 환자 정보 | 없음(입력은 공개 itemSeq·나이만, 실제 환자 데이터 없음) |

### 3.1 업로드 전 처리한 개인정보 (18개 파일)

| 파일 | 내용 | 처리 | 근거 |
|---|---|---|---|
| `notebooks/02,04,05_*.ipynb` | Colab 셀 메타데이터의 개발자 Google 표시 이름·userId | **Git 제외**(파일 무수정) | 서비스 실행에 불필요. `production_baseline.json`에 SHA256이 고정돼 있어 수정하면 source parity 기준이 깨짐 |
| `notebooks/15_*.ipynb` | 같은 메타데이터 9곳 | **`executionInfo.user` 블록만 삭제**(작업 트리 수정, 백업 있음) | 런타임 필수 파일이라 제외 불가. §5.2에서 동작 동일성 검증 |
| `reports/STEP4–8_*.md` 5개 | `C:\Users\<이름>\…` 경로 7곳 | 경로의 사용자 이름만 `<USER>`로 치환(백업 있음) | 내용·판정 무변경 |
| pytest JUnit XML 6개, `rag_probe_result.json`, `runtime_trace*.json` 3개 | 로컬 절대경로 | **Git 제외**(파일 무수정) | 결과 요약은 STEP 보고서에 있음 |

## 4. 코드 의존성 확인 (작업 3)

### 4.1 기존 구조와의 일치

- 업로드 사본(`git checkout-index`로 staging 내용을 빈 폴더에 내보냄, clone과 같은 줄바꿈 규칙 적용)은 **작업 트리와 183/183 바이트 동일**(이후 추가된 검증 기록 제외)
- `.py` 75개 모두 `py_compile` 통과
- 점검 대상 파일 상태:

| 파일 | 상태 |
|---|---|
| `app.py` | STEP 8·9-1과 동일. `REQUIRED_FILES` 16개 확인 후 `ui_integration/app_v2.py` 실행 |
| `src/` | Frozen Core 9/9 SHA 일치(작업 트리·업로드 사본) |
| `requirements.txt` | STEP 9-1 고정본(streamlit 1.66.0 등). `pip check` 정상 |
| `requirements-server-cpu.txt` | STEP 9-1 신규(Linux CPU torch) |
| `.streamlit/config.toml` | STEP 8 설정(`fileWatcherType="none"`) |
| `DEPLOYMENT.md`, `README.md` | STEP 9-1 문서. README §13이 DEPLOYMENT.md 안내 |

### 4.2 줄바꿈 변환 위험과 조치

- Frozen Core 파일과 `FROZEN_SHA256SUMS.txt`는 **LF** 기준이다(`git ls-files --eol` 확인).
- 이 PC의 Git 기본값 `core.autocrlf=true`로 **Windows에 clone하면 LF가 CRLF로 바뀌어** SHA256 검증(`test_core_contract`, `test_ui_adapter`)이 실패한다.
- 조치: `.gitattributes`에 `* -text`(줄바꿈 변환 금지). 업로드 사본에서 Frozen Core **9/9 OK** 확인.
- 정정: 작업 중 한때 "파일이 CRLF"라고 판단했으나 Git Bash `grep $'\r'` 오탐이었고, `git ls-files --eol`로 LF임을 확인했다. 조치(`-text`)의 필요성은 같다.

### 4.3 데이터·모델 없이 실행 가능한 범위 (업로드 사본으로 실제 실행)

| 상태 | 결과 | 근거 |
|---|---|---|
| clone 직후 (데이터·키 없음) | 앱이 **시작하지 않고** "필수 데이터 파일을 찾을 수 없어 앱을 시작하지 않았습니다. 검사 결과가 없는 상태이며, 이는 위험이 없다는 의미가 아닙니다"와 누락 파일 13개 목록 표시. 예외 0 | AppTest 3.5 s |
| 사전 점검 | `tools/deploy_preflight.py` → FAIL 1(데이터 누락), WARN 2(manifest 6/35, 키 없음) | 실행 |
| clone + 데이터 13개 배치 + 모델 캐시 | **전체 기능 동작**: 예외 0, runtime ready, ViewModel COMPLETED, 성분 엔진 OK, import 모듈이 원본 실행과 동일, preflight FAIL 0 / OK 10, manifest 35/35 | 데이터는 디렉터리 junction으로 연결해 실행 후 링크만 제거(원본 데이터 269개 파일 유지) |

| 기능 | 데이터·모델 없이 | 필요한 추가 파일 |
|---|---|---|
| 앱 화면 | 안내 화면만(검사 불가) | `data/processed/` 13개 |
| 약물 검색 | 불가 | 같은 데이터 |
| 병용금기·노인주의·효능군 Screening | 불가 | `screening/*.parquet` 4개 + 해시 검증용 config |
| 성분 중복 후보 | 불가 | `evidence/drug_approval_items.parquet` (+ 노트북 15, 포함됨) |
| RAG 근거 검색 | 불가 | `rag/approval_chunks.parquet`, `retrieval/*` 4개, `.npy`, bge-m3 모델(2.3 GB) |
| LLM 설명 | 불가(검색 선행) | 위 전부 + `OPENAI_API_KEY` |
| 단위 테스트 일부 | 실데이터 필요 테스트는 skip/fail | `data/`, 노트북 02/04/05(로컬 보관) |

## 5. 무결성 확인 (작업 4)

### 5.1 결과

| 검증 | 결과 |
|---|---|
| Frozen Core SHA256 (작업 트리) | **9/9 OK** |
| Frozen Core SHA256 (업로드 사본) | **9/9 OK** |
| data manifest SHA256 (`fetch_runtime_data.py --verify`) | **35/35 OK** |
| 읽기 전용 테스트 `test_core_contract` + `test_ui_adapter` + `test_medguard_dashboard` | **169 passed / 1 skipped** (STEP 8·9-1과 동일, SKIP은 기존 문서 부재) |
| Screening·RAG·Generation·Guardrail 코드 변경 | **0** (`src/`, `app/`, `ui_integration/` 무변경) |
| 유료 API 호출 | 0 |

### 5.2 노트북 15 수정의 동작 동일성

노트북 15는 성분 후보 엔진이 코드 셀을 읽어 실행하는 파일이다. 이번 수정은 Colab `executionInfo`의 `user` 블록 9개만 삭제했다.

| 검사 | 결과 |
|---|---|
| 코드 셀 소스·셀 종류·출력 | 동일(스크립트 assertion) |
| 다른 셀 메타데이터·노트북 메타데이터 | 동일(assertion) |
| 엔진이 계산하는 셀 해시(`NB15_CELL_SHA`)·상수 | 동일 |
| 성분 엔진 결과 5개 입력(CE001, TD005, TD002, EC008, 3개 약물) — 원본 vs 수정본, 별도 프로세스 | **5/5 동일**(요청 ID·실행 시간 메타 제외) |
| 파일 SHA256 고정 여부 | 고정된 곳 없음(앱·테스트·manifest·baseline 모두 이 파일의 해시를 검사하지 않음) |

자료: `step9_2_validation/strip_nb_user.py`, `nb15_equivalence.py`, `nb15_equiv_original.json`, `nb15_equiv_stripped.json`

## 6. 변경 파일

백업: `_backup_step9_2_20261023/` (Git 제외 폴더 — 원본에 개인정보가 있으므로 업로드하지 않음)

| 파일 | 변경 | 이유 |
|---|---|---|
| `.gitignore` | 개인정보 포함 개발 파일 제외 규칙 추가(노트북 02/04/05, `reports/**/*.xml`, `rag_probe_result.json`, `reports/**/*runtime_trace*.json`) | 개인정보 업로드 방지 |
| `.gitattributes` (신규) | `* -text` | Windows clone 시 Frozen Core SHA 불일치 방지 |
| `notebooks/15_ingredient_duplicate_candidates_prototype.ipynb` | Colab `executionInfo.user` 9곳 삭제 | 런타임 필수 파일의 개인정보 제거(§5.2) |
| `reports/STEP4,5,6,7,8_*.md` | 경로의 Windows 사용자 이름 → `<USER>` (7곳) | 개인정보 제거, 내용 무변경 |
| `reports/STEP9_2_GITHUB_PREPARATION.md`, `reports/step9_2_validation/*` (신규) | 본 보고서와 검증 스크립트·결과 | 기록 |
| `.git/` (신규) | `git init -b main` + staging | 업로드 준비 |

변경하지 않음: `src/`(Frozen Core), `app/`, `ui_integration/`, `app.py`, `tests/`, `data/`, `data_manifest.json`, `production_baseline.json`, 노트북 02/04/05(로컬에 원본 그대로 존재), requirements, 설정.

## 7. 남은 조건과 위험

| 등급 | 항목 | 내용 |
|---|---|---|
| 조건 | 원격 저장소 공개 범위 | 사용자가 만든 저장소가 **Private**인지 push 전에 확인 필요(이번에 확인 불가 — 원격 정보를 받지 않음) |
| 조건 | 커밋 작성자 정보 | 전역 `user.name`·`user.email`이 커밋에 기록됨. 노출을 원치 않으면 GitHub noreply 이메일로 이 저장소만 설정(§8) |
| MEDIUM | 데이터 이용허락 | 사용자가 DUR·e약은요 이용허락범위를 확인했다고 알려 왔으나, 이 단계에서 조건 내용을 받지 않아 **기록·검증하지 않음**. 데이터는 크기(100 MB 초과 2개)와 관계없이 계속 Git 제외. 저장소에 데이터를 넣으려면 조건을 문서화한 뒤 Git LFS 결정 필요 |
| MEDIUM | 공개 저장소 전환 | STEP 9-1 판정 유지(PUBLIC_REPOSITORY_READY = NO): 허가정보 데이터 조건 미확인, STEP 8 F1(근거 모순 설명) 미결 |
| LOW | Windows 긴 경로 | clone 위치가 깊으면 `reports/ingredient_coverage_audit/…` 경로가 260자를 넘어 체크아웃 실패 가능(이번 시험에서 재현, `core.longpaths=true`로 해결) |
| LOW | 로컬 전용 자료 | 노트북 02/04/05, JUnit XML, 실행 추적 JSON, 백업은 로컬에만 있음. 다른 PC에서 source parity 테스트를 돌리려면 별도로 옮겨야 함 |
| 참고 | `reports/step7*_validation/` | 실제 LLM 응답·평가 기록 포함(키·개인정보 없음). 비공개 저장소 기준 문제 없음 |

## 8. 사용자가 직접 실행할 명령어

PowerShell 또는 Git Bash에서 프로젝트 폴더로 이동한 뒤 실행합니다. `<GitHub사용자명>/<저장소명>`은 직접 바꾸세요.

```bash
cd "C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer"

# 1) 업로드 대상 마지막 확인 (186개 'A' 표시, data/.venv/.idea 가 없어야 함)
git status
git status --short | find /c "A"          # Git Bash 에서는: git status --short | wc -l

# 2) (선택) 커밋에 개인 이메일 대신 GitHub noreply 주소를 쓰려면 이 저장소에만 설정
git config user.email "<ID>+<GitHub사용자명>@users.noreply.github.com"

# 3) 첫 커밋
git commit -m "Initial commit: MEDGUARD AI (code, configs, docs; data/model excluded)"

# 4) 원격 연결 — GitHub 에서 저장소가 Private 인지 먼저 확인
git remote add origin https://github.com/<GitHub사용자명>/<저장소명>.git
git remote -v

# 5) push (승인 후)
git push -u origin main
```

push 후 확인:
- GitHub 저장소 Settings에서 **Visibility = Private**인지 확인합니다.
- 파일 목록에 `data/`, `.venv/`, `.idea/`가 없어야 합니다.
- Code 화면의 저장소 크기가 수 MB여야 합니다.
- (선택) 다른 폴더에 clone한 뒤 `sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt`로 9/9를 확인합니다. Windows에서 깊은 경로에 clone할 때는 `git clone -c core.longpaths=true …`를 사용합니다.

되돌리기(필요 시):
- 커밋 전 staging만 취소하려면 `git reset`을 실행합니다.
- 저장소 초기화 전체를 취소하려면 `.git` 폴더를 삭제합니다. 작업 파일은 영향을 받지 않습니다.
- 노트북과 보고서 원본은 `_backup_step9_2_20261023/`에 있습니다.

## 9. 재현 명령

```bash
git ls-files --eol src/dur_safety/                       # i/lf w/lf attr/-text
git -c core.longpaths=true checkout-index -a --prefix=<빈폴더>/   # 업로드 사본 생성
(cd <빈폴더> && sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt)
python -X utf8 tools/fetch_runtime_data.py --verify
python -X utf8 reports/step9_2_validation/nb15_equivalence.py . <노트북경로> <out.json>   # 원본/수정본 각각
env -u OPENAI_API_KEY MEDICAL_AI_PROJECT_ROOT=$PWD DUR_UI_ADAPTER_REAL_DATA=1 python -X utf8 -m pytest tests/test_core_contract.py tests/test_ui_adapter.py tests/test_medguard_dashboard.py -q -p no:cacheprovider
git grep --cached -l -F "<개인정보 문자열>"                 # 0 이어야 함
```

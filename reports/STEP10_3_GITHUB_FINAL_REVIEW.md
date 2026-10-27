# STEP 10-3 — GitHub 최종 반영 준비 및 포트폴리오 마무리 검토

- 작성일: 2026-10-27 / 대상: MEDGUARD AI (연구·포트폴리오용 프로토타입, **임상 검증 아님**)
- 선행: STEP 10-2 `CONDITIONAL_PASS` (`reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md`)
- 표기: **실측**(이번 세션에서 실행·확인) / **코드**(소스를 읽어 확인) / **기존**(이전 보고서 기록) / **사용자 보고** / **NOT_VERIFIED**
- 하지 않은 것: 의료 판단·검색·생성·Guardrail·UI 코드 수정, 데이터·모델 변경, LLM·API 호출, Streamlit 서버 실행, **pytest 실행(이번 단계에서 테스트를 돌리지 않음)**, commit/push, 공개 전환, Git 기록 재작성

> 이 보고서의 판정은 **GitHub 문서·보안·무결성 정리**에 대한 것입니다. 의료 AI 안전성 판정이 아닙니다. 기존 STEP 7 `BLOCKED`, STEP 7-R `INCOMPLETE` 같은 의료 AI 평가 판정은 그대로 유효합니다.

---

## 1. 수행 목적

기존 Screening → RAG → LLM → Guardrail 구조와 검증 결과를 바꾸지 않습니다. 그 상태에서 GitHub 비공개 저장소에 올릴 문서·파일의 정확성, 보안, 무결성을 최종 점검합니다. 반영 명령어는 사용자가 직접 실행하도록 준비만 합니다.

## 2. 현재 GitHub 상태 (실측)

| 항목 | 결과 |
|---|---|
| 프로젝트 루트 | `C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer` |
| 브랜치 | `main` (upstream `origin/main`) |
| 원격 | `origin` → `github.com/bomi-data/medguard-ai`. URL에 토큰 없음 |
| 마지막 commit | `23c5376 Initial MEDGUARD AI deployment preparation` (저장소의 유일한 commit) |
| 원격 동기화 | `git ls-remote`: 원격 `main` = `23c5376` = 로컬 HEAD |
| 비공개 여부 | 익명 접근 거부(STEP 10-1) → 비공개로 추정. visibility 값 직접 조회는 **NOT_VERIFIED** |
| Working tree | `M README.md`, `M DEPLOYMENT.md`, `D er.email`(staged), 미추적: `docs/`, `reports/STEP9_3_*`, `reports/step9_3_validation/`, `reports/STEP10_1_*`, `reports/STEP10_2_*`, (이 보고서) |
| `.gitignore` 적용 | `.venv/`, `.idea/`, `data/`, `_backup_*/`, `_incoming_*/`, `__pycache__/`, 노트북 02·04·05, `*.log`, `reports/**/*.xml`, `playwright_artifacts/` 모두 무시됨(`git status --ignored`로 확인) |
| `git diff --check` | 문제 없음 |

## 3. README 최종 평가

README를 처음부터 끝까지 읽고 코드·보고서와 대조했습니다.

| 점검 항목 | 결과 | 비고 |
|---|---|---|
| A. 목적·주제·프로토타입·임상 미검증 고지 | PASS | 첫 화면 고지 상자, §7 머리말, §9, 맨 끝 고지 |
| B. 아키텍처가 코드 실행 순서와 일치 | PASS | 코드 순서: UI → `adapters` → `pipeline.run_safety_check` → `screen_patient` → `findings` → finding별 `retrieve_hybrid` → 근거 검증(없으면 LLM 미호출) → `call_llm` → `validate_output` → `ui_policy.decide_display_mode` → UI. 요청서 도식과 같고, 차이는 두 가지입니다. (1) Guardrail이 Core 출력 검증과 UI 표시 정책 두 단계로 나뉨 (2) 성분 중복 후보는 별도 경로. README에 둘 다 표시되어 있음 |
| C. 기능별 구현 범위·제한 | PASS | 7개 기능 모두 구현 위치와 검증 상태를 따로 적음. 성분 후보와 공식 성분 동일성(NO-GO) 구분 |
| D. 평가 결과의 근거 | PASS | 모든 수치가 기존 보고서와 일치(§4 대조). 영역별로 따로 제시하며 합산 지표 없음 |
| E. 알려진 문제 누락 여부 | **보완 후 PASS** | CE001, 과잉 차단, CPU 회귀 FAIL, 임상 미검증은 이미 기재됨. **STEP 7 `BLOCKED` 판정이 출처로만 언급되고 판정 자체는 적혀 있지 않았고**, "실제 환자 대상 검증 부재"가 명시되지 않아 두 곳을 보완함(§3-1) |
| F. 실행 방법 | PASS (정적 검토) | `app.py`, `requirements*.txt`, `tools/fetch_runtime_data.py`, `tools/deploy_preflight.py`, `.env.example`, `.streamlit/secrets.toml.example` 모두 존재. 서버는 실행하지 않음. pytest 예시는 bash 문법(PowerShell에서는 환경변수 지정 방식이 다름) |
| G. 이미지·다이어그램 | 경로 PASS / **렌더링 NOT_VERIFIED** | 이미지 2장과 링크한 파일은 모두 Git 추적 중. 상대 링크·앵커 깨짐 0. Mermaid는 정적 검사(따옴표·괄호 짝, `flowchart TD`, `-.->\|...\|` 문법)만 통과했고, GitHub에서 실제로 그려지는지는 확인하지 못함 |

### 3-1. 이번에 고친 내용

| 파일 | 수정 | 이유 |
|---|---|---|
| `README.md` §7 | 평가 표 아래에 **단계별 판정 한 줄** 추가: STEP 5 INCOMPLETE · STEP 6 PASS · **STEP 7 BLOCKED** · 7-R INCOMPLETE · 7-FINAL / 8 CONDITIONAL_PASS · 9-3 CONDITIONAL_READY. "STEP 10에서 바꾸지 않음" 명시 | STEP 7 BLOCKED가 README에 드러나지 않았음 |
| `README.md` §9 | "임상 검증 없음" 행에 "실제 환자 대상 검증 없음, 임상적 정확성과 환자 안전성 미검증" 명시 | 요청 항목 E |
| `docs/DATA_SOURCES.md` §3-1 | 데이터셋 3개 × 5개 항목(이용 가능, 재배포, 출처 표시, 가공 데이터 공개, API 조건) 확인 상태 표 신설. 사용자 보고와 NOT_VERIFIED 구분. 공식 데이터셋 이름·ID 기록 여부, 현재 재배포 안 함 명시 | 요청 §4 |
| `DEPLOYMENT.md` §3 | "13개 파일 배치 → `--verify` 모두 OK"의 모순 수정. manifest의 data 파일은 29개이고 `--verify`는 전부 검사함. 앱 필수는 13개(코드 기준)라고 명시하고, 13개만으로 실행해 보지는 않았다고 적음 | 문서 내부 모순(STEP 9-1부터 있던 문제) |

## 4. 기술 문서 정합성

| 항목 | README | EVALUATION | DATA_SOURCES | DEPLOYMENT | 판정 |
|---|---|---|---|---|---|
| 목적 | 연구·포트폴리오, 임상 미검증 | 같음 | — | 같음 | 일치 |
| 데이터 출처 | DUR, 허가정보 15095677, e약은요 | — | 같음 + 행 수·시점 | 데이터 Git 제외 | 일치 |
| 이용 조건 | DUR·e약은요 사용자 보고, 허가정보 미확인 | — | 같음 + 5개 항목 세분 | "재배포 조건 NOT_VERIFIED" | 일치 |
| 시스템 구조 | Mermaid + 모듈 표 | Guardrail 단계 표 | — | 진입점·파일 | 일치 |
| 모델·라이브러리 | bge-m3(revision 고정), gpt-5.4-mini, 버전 | gpt-5.4 judge | bge-m3 `5617a9f6…` | 같은 revision | 일치 |
| 평가 방법·결과 | 요약 표 | 상세 표 | — | — | 수치 일치(아래) |
| 한계 | 10개 항목 | §7 "주장할 수 없는 것" | 재현 범위 | — | 일치 |
| 배포 여부 | "공개 배포 안 함", Linux는 로컬 WSL2 실행 | "클라우드 미검증" | — | "배포 보류, 참고용" 안내 | 일치. "배포 완료/배포했" 표현 0건 |
| 임상 활용 | 불가 | 불가 | — | 임상 도구 아님 | 일치 |

**수치 대조 (실측: 문서 간 문자열 비교 + 원 보고서 대조)**: 265/274, 2/274, 58/778(README는 69.2%→7.5%로 표기), 5/111, 0/450, 7/7, 3/9, 74.9초, 4.98 GiB, nDCG@5 0.734, 77.46%, 179/1/1, 32/32, 30/30 모두 문서 간 차이가 없습니다. 출처 보고서(STEP 6, 7, 7-R, 7-FINAL, 8, 9-3, coverage CSV)의 값과도 같습니다.

**같아 보이지만 다른 수치 (오류 아님)**: 노인주의 1,982(규칙 **행** 수, DATA_SOURCES)와 1,980(규칙에 등장하는 **제품** 수, EVALUATION). 효능군 7,064(행)와 7,056(제품)도 같은 관계입니다. 각 문서에 단위를 적어 두었습니다.

## 5. 데이터 출처 및 이용 조건

| 데이터 | 이용 가능 | 재배포 | 출처 표시 | 가공 데이터 공개 | API 조건 | 이 저장소의 재배포 |
|---|---|---|---|---|---|---|
| DUR 규칙 | 사용자 보고: 제한 없음 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | 하지 않음 |
| e약은요 | 사용자 보고: 제한 없음 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | 하지 않음 |
| 허가정보 15095677 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | 하지 않음 |

- 외부 사이트에는 접근하지 않았습니다. 공공데이터포털 URL은 추측해서 쓰지 않았습니다.
- DUR·e약은요의 공식 데이터셋 이름과 ID는 처리 파일에 기록되어 있지 않습니다. 사용자 확인이 필요합니다.
- 원본·가공 데이터는 계속 Git에서 제외합니다. 다만 `reports/`의 일부 평가 산출물에는 허가정보 문장 일부와 LLM 출력 원문이 평가 증거로 들어 있습니다(기존 commit에 이미 포함). 비공개 저장소에서는 문제로 보지 않고, 공개 전환 전에 검토할 항목입니다.

## 6. 보안 및 개인정보 점검 (실측)

| 범위 | 방법 | 결과 |
|---|---|---|
| 반영 후보 16개 파일(§7 A) | 키 패턴(OpenAI `sk-`, GitHub `ghp_`/`github_pat_`/`gho_`, AWS `AKIA`, HF `hf_`, Google `AIza`, 개인키, 공공데이터 `serviceKey=`) | **실제 키 0건**. 일치 1건은 STEP 10-2 보고서가 검사 패턴 이름(`github_pat_`)을 적은 문장(오탐) |
| 같은 16개 파일 | 이메일, 사용자 이름, Windows 사용자 경로, WSL `/home/<user>`, Colab 경로, 호스트 이름, 사설 IP | 개인정보 0건. 경로는 모두 `<USER>`로 가려져 있음. Colab 경로(`/content/drive/MyDrive/medical-ai-project`)는 개인 식별 정보가 없는 일반 경로이며 STEP 10-1 보고서 설명문에만 있음. 사설 IP 0건 |
| **Git 전체 기록** | `git rev-list --all`(commit 1개, ref 2개: `main`, `origin/main`, stash 0) 전체 blob에 키 패턴 검사 | 3건 일치 → 모두 STEP 8 오류 처리 시험용 **가짜 키 문자열**(`sk-step…`, 실제 키 아님, STEP 9-1·9-2·10-1에서 같은 결론). 실제 키 0건 |
| Git 기록의 민감 경로 | 모든 commit의 파일명에서 `.env`, `secrets.toml`, `.pem`, `credential`, `.venv/`, `__pycache__`, `.idea/`, `data/` 검색 | 0건 |
| `.env`, `.streamlit/secrets.toml` | 존재 여부 | 둘 다 로컬에 없음. `.gitignore` 규칙 있음 |
| Git 작성자 정보 | `git log --format` | 작성자·커미터 이메일이 개인 메일 주소(gmail 도메인). 값은 기록하지 않음. **비공개 저장소에서는 위험이 낮고, 공개 전환 시 노출됨** |
| 불필요 파일 | `git status --ignored` | `.venv/`, `.idea/`, `data/`, 모델 캐시(프로젝트 밖 HF 캐시), `_backup_*`, 로그, `playwright_artifacts/` 모두 무시됨. `git add -n`으로 후보에 들어가지 않음을 확인 |
| `er.email` | STEP 10-2 | 파일 목록 텍스트, 비밀정보 없음. 삭제 staged. 기존 commit에는 남음(무해) |

**검사의 한계**: 원격에는 commit이 1개뿐이고 로컬 기록과 같아서 전체 기록을 검사할 수 있었습니다. 다만 정규식 검사이므로 형식이 알려지지 않은 비밀값은 놓칠 수 있습니다. 이미지 파일은 STEP 10-2에서 화면 캡처 5장만 눈으로 확인했습니다. 노출된 실제 비밀정보는 없으므로 기록 재작성이나 키 폐기는 필요 없다고 판단합니다.

## 7. GitHub 반영 대상 파일

| 분류 | 파일 | 이유 |
|---|---|---|
| **A. 반영 권장** | `README.md`, `DEPLOYMENT.md`, `docs/EVALUATION.md`, `docs/DATA_SOURCES.md` | 포트폴리오 핵심 문서. 보안 검사 통과 |
| A | `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`, `reports/step9_3_validation/`(json·out·py·txt 9개) | README·DEPLOYMENT의 Linux 수치 근거. 개인정보 0건. `playwright_artifacts/`는 자동 제외 |
| A | `reports/STEP10_1_GITHUB_PORTFOLIO_AUDIT.md`, `reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md`, `reports/STEP10_3_GITHUB_FINAL_REVIEW.md` | 정리 과정 기록. 개인 이메일 값과 실명은 없음(gmail 도메인만 언급) |
| A | `er.email` 삭제 (이미 staged) | 실수로 커밋된 파일 |
| **B. 반영 보류** | 없음 | — |
| **C. 반영 금지** | `data/`, `.venv/`, `.idea/`, `_backup_*/`, `_incoming_drive_originals/`, 노트북 02·04·05, `*.log`, JUnit XML, `*runtime_trace*.json`, `playwright_artifacts/`, `.env`, `.streamlit/secrets.toml` | 대용량, 이용 조건 미확인, 개인정보·로컬 경로, 비밀정보. 모두 `.gitignore`로 이미 제외됨 |
| **D. 추가 확인 필요** | 없음(이번 반영 대상 기준) | 공개 전환 시에는 `reports/`의 허가정보 인용과 커밋 이메일 검토 필요(§9) |

기존에 추적 중인 파일은 `er.email` 말고는 삭제하거나 바꾸지 않았습니다.

## 8. 기존 시스템 무결성 (실측)

| 검사 | 결과 |
|---|---|
| Frozen Core `sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt` | **9/9 OK** |
| 코드·노트북·설정 파일 56개 해시(`src/`, `app/`, `ui_integration/`, `app.py`, `tests/`, `tools/`, `notebooks/`, `data_manifest.json`, `production_baseline.json`) | STEP 10-2 시작 전 기록과 **56/56 동일** |
| `git diff HEAD --name-only` (코드·설정·`.gitignore`·`.streamlit`) | 0개 |
| data manifest (`tools/fetch_runtime_data.py --verify`) | **35/35 OK** |
| `git diff --check` | 문제 없음 |
| 테스트 | **실행하지 않음.** 코드 변경이 없어 회귀 테스트가 필요 없다고 판단. 마지막 기록은 STEP 8의 179 PASS / 1 FAIL / 1 SKIP(기존) |

## 9. 남아 있는 위험

| # | 위험 | 비공개 반영에 영향 | 공개 전환에 영향 |
|---|---|---|---|
| R1 | 데이터 재배포·출처 표시·가공 데이터 공개·API 조건 NOT_VERIFIED. 허가정보는 이용 가능 여부도 미확인 | 없음 | **차단** |
| R2 | LICENSE 없음 | 없음 | 차단 |
| R3 | 커밋 작성자 개인 이메일 | 낮음 | 노출(사용자 결정) |
| R4 | `reports/` 내 허가정보 문장·LLM 출력 인용 | 없음 | 이용 조건에 따라 검토 |
| R5 | Mermaid 렌더링 NOT_VERIFIED | 표시 문제만 | 같음 |
| R6 | 코드 docstring이 저장소에 없는 문서 3개를 참조(`docs/STREAMLIT_VIEW_MAPPING.md`, `docs/CORE_INTERFACE_CONTRACT.md`, `docs/PRODUCTION_BASELINE.md`) | 없음 | 독자 혼란 |
| R7 | 의료 AI 기술 문제: CE001 근거 모순, 의미 수준 Guardrail 없음, 과잉 차단, CPU 회귀 FAIL, 임상 미검증 | 문서에 공개됨 | 문서에 공개됨 |

## 10. 포트폴리오 완성도 평가

| # | 기준 | 판정 | 근거 |
|---|---|---|---|
| 1 | 프로젝트 목적의 명확성 | PASS | 부제, 소개, 개발 배경 표 |
| 2 | 의료 AI 시스템 설계 | PASS | 규칙 판정과 LLM 설명의 분리, fail-closed, Frozen Core가 코드로 강제됨 |
| 3 | 데이터 처리 및 근거 관리 | CONDITIONAL_PASS | SHA256 manifest와 근거 ID 검증은 갖춤. 수집·전처리 파이프라인이 저장소에 없고 이용 조건 일부 미확인 |
| 4 | Screening-RAG-LLM-Guardrail 통합 | CONDITIONAL_PASS | 통합 동작 확인(UI↔Core 30/30). 의미 수준 모순(CE001)은 막지 못함 |
| 5 | 평가 방법의 타당성 | CONDITIONAL_PASS | 사전 등록 기준, held-out, 합성·실제 구분은 좋음. 표본이 작고(30건) 사람 전문가 평가 0건 |
| 6 | 실패 사례와 한계 공개 | PASS | BLOCKED/INCOMPLETE 판정, CE001 A/B 분리, 과잉 차단, CPU FAIL, 임상 미검증 모두 README에 있음 |
| 7 | GitHub 문서 가독성 | CONDITIONAL_PASS | 목차, 표, 화면, 문서 안내 갖춤. GitHub 렌더링(Mermaid·이미지)은 NOT_VERIFIED |
| 8 | 재현 가능성 | CONDITIONAL_PASS | clone만으로 실행 불가(데이터 미포함)를 명시하고 절차와 해시를 제공함. 외부인은 데이터가 없어 재현할 수 없음 |
| 9 | 개인정보 및 보안 | PASS (비공개 기준) | 실제 키 0건(전체 기록 포함), 개인정보 0건. 공개 시에는 커밋 이메일 결정 필요 |
| 10 | 포트폴리오로서의 설명력 | PASS | 기술 선택 이유, 검증 수준, 한계를 근거와 함께 설명 |

**Q1. GitHub 기술 포트폴리오로 마무리할 수 있는 수준인가?** 예. 비공개 포트폴리오로는 마무리할 수 있습니다. 설계 의도, 실제 구현, 평가와 실패가 근거와 함께 정리되어 있습니다.

**Q2. 추가 개발 없이 종료해도 되는가?** 예. 남은 작업은 확인과 결정(이용 조건, LICENSE, 렌더링 확인)뿐입니다. 의료 AI 기술 문제(CE001 등)는 "향후 개선"으로 공개했으므로, 포트폴리오를 끝내기 위해 코드를 더 개발할 필요는 없습니다.

**Q3. README에 과장되거나 검증되지 않은 표현이 있는가?** 확인한 범위에서는 없습니다. 모든 수치에 출처가 있고, 판정자(LLM judge·Claude, 사람 0건), 표본 크기, 임상 미검증이 함께 적혀 있습니다. 다만 Mermaid·이미지 렌더링은 NOT_VERIFIED입니다.

**Q4. 평가 실패 사례가 정확하게 공개되어 있는가?** 예. CE001(3회 재현, 화면 표시, A/B 분리), 과잉 차단 3/9, Guardrail 미탐(규칙 밖 7/7, 의미 수준 58/778), STEP 7 BLOCKED(이번에 명시), CPU 회귀 FAIL이 원 보고서 값 그대로 실려 있습니다.

**Q5. 비공개 저장소에 변경 문서를 반영해도 안전한가?** 예. 비밀정보와 개인정보가 없고, 코드·데이터 변경도 없습니다.

**Q6. 공개 저장소로 전환하려면?** (1) 데이터 3종의 재배포·출처 표시·가공 데이터 공개·API 조건 확인, 허가정보는 이용 가능 여부까지 (2) LICENSE 결정 (3) 커밋 작성자 이메일 처리 결정(기록 재작성은 force push 필요) (4) `reports/` 내 허가정보 인용과 LLM 출력의 공개 가능 여부 (5) 없는 문서 3개 참조 정리 (6) 공개 후 시크릿 스캐닝 경고(가짜 키 문자열) 확인.

## 11. 사용자 직접 확인 사항

1. `git diff README.md DEPLOYMENT.md`, `docs/` 두 문서 검토. 특히 README §7 CE001 A/B 설명과 단계별 판정 줄이 맞는지 확인
2. push 후 GitHub 웹에서 확인: Mermaid 다이어그램, 이미지 2장, 저장소 Private 여부
3. (공개를 고려할 때만) 공공데이터포털에서 데이터 3종의 이용 조건 확인 → 결과를 알려 주면 `docs/DATA_SOURCES.md` §3-1 갱신

## 12. 최종 판정

```
STEP10_3_STATUS = CONDITIONAL_PASS
```

- 문서·보안·무결성 검토는 모두 마쳤고, **비공개 GitHub 반영을 막는 문제는 없습니다.**
- PASS가 아닌 이유:
  - GitHub 렌더링(Mermaid·이미지)과 저장소 visibility를 이 환경에서 확인하지 못했습니다(push 후 사용자 확인 필요).
  - 데이터 이용 조건 일부가 사용자 보고 또는 미확인 상태입니다(공개 전환에만 영향).
- 이 판정은 GitHub 문서 정리 판정입니다. **MEDGUARD AI가 의료 AI로서 안전성 검증을 통과했다는 뜻이 아닙니다.**

## 13. 다음 작업

### 13-1. GitHub 반영 (사용자 승인 후 직접 실행)

```bash
git add README.md DEPLOYMENT.md docs/ \
        reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md reports/step9_3_validation/ \
        reports/STEP10_1_GITHUB_PORTFOLIO_AUDIT.md \
        reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md \
        reports/STEP10_3_GITHUB_FINAL_REVIEW.md
git status                 # 확인: 위 파일 + "deleted: er.email" 만 staged, data/·.venv/·playwright_artifacts 없음
git diff --cached --stat
git commit -m "Docs: finalize GitHub portfolio README, evaluation and data source docs (STEP 10)"
git push origin main       # force push 금지, 기존 commit 수정 없음
```

PowerShell에서도 위 명령은 그대로 쓸 수 있습니다. 줄 끝의 `\` 대신 한 줄로 이어 쓰세요.

### 13-2. 이후 (선택)
- 앞으로 커밋할 때 개인 이메일을 쓰지 않으려면: `git config user.email "<ID>+<사용자명>@users.noreply.github.com"` (이 저장소에만 적용, 기존 commit은 그대로)
- 공개 전환은 §10 Q6 항목을 모두 해결한 뒤에 하세요.
- 프로젝트는 이 단계에서 종료할 수 있습니다. 이어서 개발한다면 README §10의 1번(설명과 근거의 의미 일치 검사)이 가장 우선입니다.

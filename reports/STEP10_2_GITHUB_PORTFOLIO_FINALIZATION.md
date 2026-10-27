# STEP 10-2 — GitHub 포트폴리오 README 및 기술 문서 최종 정리

- 작성일: 2026-10-27 / 대상: MEDGUARD AI (연구·포트폴리오용 프로토타입, **임상 검증 아님**)
- 선행: STEP 10-1 `CONDITIONAL_READY` (`reports/STEP10_1_GITHUB_PORTFOLIO_AUDIT.md`)
- 표기: **실측**(이번 세션에서 실행·확인) / **코드**(소스를 읽어 확인) / **기존**(이전 보고서 기록 인용) / **NOT_VERIFIED**
- 하지 않은 것: 의료 판단·검색·생성·Guardrail·UI 코드 수정, 데이터·모델 변경, LLM·유료 API 호출, 모델 로딩, 앱 실행, pytest 실행, commit/push, 저장소 공개 전환, Git 기록 재작성

---

## 1. 최종 판정

```
STEP10_2_STATUS = CONDITIONAL_PASS
```

**PASS가 아닌 이유**
1. 데이터 이용 조건 중 **의약품 제품 허가정보(15095677)는 확인되지 않았습니다.** DUR·e약은요는 사용자 확인 보고이며 Claude가 독립적으로 확인하지 않았습니다. 그래서 README에는 "확인 필요"로 적었습니다. LICENSE도 없습니다.
2. Mermaid 다이어그램은 문법을 손으로 검토했지만, **GitHub에서 실제 렌더링되는지는 확인하지 못했습니다**(NOT_VERIFIED).
3. README·`DEPLOYMENT.md`가 링크하거나 언급하는 `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`가 아직 **미커밋** 상태입니다. 함께 커밋하지 않으면 GitHub에서 근거 보고서가 빠집니다.
4. 코드 docstring이 언급하는 문서 3개(`docs/STREAMLIT_VIEW_MAPPING.md`, `docs/CORE_INTERFACE_CONTRACT.md`, `docs/PRODUCTION_BASELINE.md`)가 저장소에 없습니다(§9).

**INCOMPLETE·BLOCKED가 아닌 이유**
- README 전면 개선과 기술 문서 2개 작성을 마쳤습니다. 수치는 모두 기존 보고서에서 출처를 확인해 옮겼습니다.
- 기존 실패·한계(STEP 7 BLOCKED, CE001, 과잉 차단, CPU 회귀 FAIL)를 삭제하거나 PASS로 바꾸지 않았습니다.
- 무결성: Frozen Core 9/9, 코드·노트북·설정 파일 56개의 해시가 작업 전후 같음, data manifest 35/35(실측).
- 새 문서와 변경 문서에서 비밀정보·개인정보 0건(실측).

---

## 2. README 개선 내용

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 첫인상 | 고지 문구 + 짧은 소개 | 부제, 3~5문장 소개, 고지, **실제 화면 캡처 2장** |
| 개발 배경 | 1문장 | 질문 4개(문제, 규칙 기반 이유, RAG 이유, LLM 단독 판단을 쓰지 않은 이유) 표 |
| 설계 원칙 | 없음 | 5개: 판정은 규칙/설명은 LLM, 근거 범위 제한, fail-closed, "발견되지 않음 ≠ 안전", Frozen Core (모두 코드 위치 표기) |
| 기능 | 목록 | 표: 기능·설명·구현 위치·**검증 상태**. 성분 중복 후보와 공식 성분 동일성(NO-GO)을 분리 |
| 아키텍처 | ASCII (실행 경로 중심) | **Mermaid** 데이터 흐름(근거 없음 시 LLM 미호출 분기, Core 검증과 UI 표시 정책 분리, 성분 후보 별도 경로) + 모듈 책임 표 |
| 기술 스택 | 한 줄 | 표. "사용하지 않은 것"(FAISS, LangChain, 벡터 DB, 파인튜닝) 명시 |
| 데이터 출처 | "NOT_VERIFIED" 한 줄 | 제공기관·데이터·용도·기록 시점 표. 이용 조건 확인 상태를 데이터별로 구분 |
| 평가 결과 | "검증하지 않은 수치는 기재하지 않음" (수치 없음) | 6개 영역(Screening, Retrieval, Generation, 실제 LLM, Guardrail, Streamlit, Linux) 표 + **CE001 실패 사례 A/B 분리** |
| 실행 방법 | `pip install` + `streamlit run` (데이터 없으면 실패) | **"clone만으로는 실행되지 않음"** 명시, 데이터 없이 할 수 있는 것과 전체 실행 구분, 환경변수 표, 테스트와 기록된 결과 |
| 배포 | Streamlit Cloud 배포 절차 4단계 | 삭제. "현재 공개 배포 안 함" + `DEPLOYMENT.md` 링크(보존) |
| 한계 | 일반론 3줄 | 10개 항목 표, 항목마다 근거 수치와 출처 |
| 향후 개선 | 한 줄 | 확인된 한계 기반 5개 |
| 오래된 정보 | `streamlit # VERSION_UNSPECIFIED`, RAG "배포 환경 NOT_VERIFIED" | 1.66.0 고정 반영, Linux(WSL2) 실행 결과 반영 |

**부제 제안**: 요청서 예시("다약제 복용 안전성 검토 및 근거 기반 설명 시스템") 대신 "한국 DUR 규칙 기반 다제약물(Polypharmacy) 안전성 Screening과 허가정보 근거 기반 설명 생성 — 연구용 프로토타입"을 썼습니다. "안전성 검토 시스템"은 임상 판단을 하는 것처럼 읽힐 수 있습니다. 실제 기능은 규칙 조회(Screening)와 근거 설명입니다.

---

## 3. 기술 문서 구성

| 파일 | 상태 | 내용 |
|---|---|---|
| `README.md` | 전면 개선 | §2 |
| `docs/EVALUATION.md` | **신규** | 영역별 목적·표본·방법·결과·발견된 문제·해석상 한계, 출처. Guardrail 검사 항목(코드 기준), CE001 A/B 분리, "주장할 수 있는 것과 없는 것" 표 |
| `docs/DATA_SOURCES.md` | **신규** | 데이터셋별 출처 기록, 용도, 처리 파일·행 수, 기록된 시점, 이용 조건 확인 상태, 저장소 제외 이유, 보고서 내 데이터 인용 |
| `DEPLOYMENT.md` | 최소 수정(+4줄) | 맨 위에 "공개 배포 보류, 참고용 보존" 안내와 Linux 실측값 위치 추가. 기존 절차는 그대로 |
| `.gitignore` | 변경 없음 | `er.email`을 Git 추적에서 제거했으므로 무시 규칙은 필요 없다고 판단 |
| `reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md` | 신규 | 이 보고서 |

`docs/ARCHITECTURE.md`와 `docs/LIMITATIONS.md`는 만들지 않았습니다. 아키텍처와 한계는 README 안에서 충분히 다룰 수 있어, 문서를 늘리지 않는 쪽을 택했습니다.

---

## 4. 평가 결과 반영 현황

모든 수치는 아래 출처에서 그대로 옮겼습니다. 새로 계산한 값은 없습니다.

| 반영 수치 | 출처 |
|---|---|
| Screening 회귀 32/32, finding 동등성 33/33, 소스 동등성 240/240, 음성 대조 PASS | `production_baseline.json` `regression_evidence` |
| CPU 엄격 검색 회귀 FAIL(3/33 strict, 순위 33/33 동일), dense 점수 차 ≤0.0007, 30건 중 12건 근접 | `production_baseline.json`, STEP 5 §0, STEP 6 §7 |
| 커버리지 16,441 / 12,736 (77.46%) / 3,705, 누락 의심 196·588·3,648, 효능군 9개 | `reports/ui_coverage_audit/run_20261011_152938/03_coverage_metrics.csv` |
| 성분 기반 확장 OPTION C, 공식 D↔M 연결표 없음 | `reports/ingredient_coverage_audit/run_20261012_184823/11_feasibility_decision.json`, `12_ingredient_coverage_report.md` |
| BM25 / Dense / Hybrid hit@k·P@5·MRR@5·nDCG@5, Top-5 30/30, nDCG 역전 15건 | STEP 6 §6 |
| 인덱스 36,988×1024 | STEP 6 §0 |
| Groundedness 265/274, Hallucination 2/274, Screening Consistency 30/30, 표시 30/30, Usefulness 11.83/12 | STEP 7 §0 |
| 합성 위험 응답 통과 538/778 → 58/778, 세부 U3~U9, FPR 5/111, held-out 450/450 → 0/450, 사후 점검 7/7 | STEP 7-R §0·§1.3·§3·§7 |
| 실제 호출 10/10, 지시·안심·부정·허위 ID 0/10, CE001 모순, 과잉 차단 3/9(EC008·EC010·TD005), Citation Accuracy 29/30 | STEP 7-FINAL §0·§5·§8 |
| 실제 호출 5/5, UI↔Core 30/30, pytest 181개 중 179/1/1, CE001 3회 재현, `fileWatcherType` 수정 | STEP 8 §1·§9 |
| 콜드 스타트 74.9초, RSS 4.98 GiB, 검사 2.6초, 2 vCPU, RAM 한도 7.6GB | STEP 9-3 §0 |

**이번에 코드에서 직접 확인한 사실(코드)**
- LLM은 판정하지 않습니다. 시스템 프롬프트가 재판정을 금지하고, `validate_output`이 `finding_id`·`risk_type` 불일치를 무효로 처리합니다(`src/dur_safety/generation.py`).
- 근거가 0건이거나 무결성 오류가 있으면 LLM을 호출하지 않고 고정 문구를 냅니다(`generate_explanation`).
- 검색은 finding의 `ITEM_SEQ` 허가정보 chunk로 먼저 걸러 냅니다(`retrieval.get_candidates`). RRF 가중치는 bm25 1.0 / dense 1.0 / prior 0.5, depth 100, top-k 5입니다.
- 벡터 DB는 없습니다. 사전 계산 임베딩에 NumPy 내적을 씁니다(`rank_dense`).
- e약은요 데이터는 제품명 조회에만 씁니다. RAG 코퍼스의 출처 기록은 전부 허가정보(15095677)입니다(데이터에서 실측).
- UI Guardrail(`ui_policy.unsafe_text_reasons`)은 문장 단위 정규식입니다. 문장과 근거의 의미 일치는 검사하지 않습니다.

**포함하지 않은 수치**: 06-C(Screening 평가) 원 결과는 저장소에 없어 인용하지 않았습니다. 독립적인 검색 정확도 지표는 06-A/06-B 기록값만 썼습니다.

---

## 5. 의료 AI 안전성 표현 검토

| 점검 | 결과 |
|---|---|
| 임상 검증 미완료 고지 | README 첫 화면(고지 상자), §7 머리말, §9, 맨 끝 고지. `docs/EVALUATION.md` 해석 원칙 |
| 기술 PASS ≠ 임상 정확성 | §3 "검증 상태" 열 설명, §7 "읽는 법", EVALUATION §7 "주장할 수 있는 것과 없는 것" |
| 소표본 확대 해석 경고 | §7 머리말, EVALUATION 해석 원칙 3 |
| 판정자 명시 | LLM judge(gpt-5.4)·Claude 대조, 사람 검토 0건을 명시 |
| 실패 사례 보존 | STEP 7 BLOCKED, 7-R INCOMPLETE, CE001(3회 재현, 화면 표시), 과잉 차단 3/9, CPU 회귀 FAIL 모두 기재 |
| CE001 A/B 분리 | README §7과 EVALUATION §3-2. "A를 허용해도 B는 해결되지 않음"을 명시. A의 근거는 사용자 설명이라고 밝힘 |
| 과장 표현 점검 | "안전합니다", "정확도", "보장", "완벽", "검증된", "임상적으로"를 검색했습니다. 남은 사용은 고지·부정 문맥뿐입니다. 애매한 표현 3곳은 고쳤습니다("검증된 셀" → "실행 확인한 코드 셀", "Screening 판정은 정확했습니다" → "DUR 규칙대로 나왔습니다", "검증된 값" → "평가 당시 고정한 모델·revision") |
| 존재하지 않는 기능 | 기능 표의 항목은 모두 코드 위치와 대조했습니다. 화면 이름은 `app/utils/ui_helpers.NAV_ITEMS`와 일치합니다 |

---

## 6. 개인정보 및 보안 점검

| 범위 | 방법 | 결과 |
|---|---|---|
| 신규·변경 문서 4개 (README, DEPLOYMENT, docs 2개) | 키 패턴(`sk-`, `ghp_`, `github_pat_`, `hf_`), 이메일 도메인, 사용자 이름, Windows/Colab 개인 경로, password | **0건** (실측) |
| 추적 파일 전체 + Git 기록 | STEP 10-1에서 같은 방법으로 검사, 이번에 추적 코드 파일 변경 없음 | 실제 키 0건, 가짜 시험 키 문자열만 존재(기존) |
| 화면 캡처 5장 (`reports/step8_validation/screens/`) | 이번에 이미지를 직접 열어 확인 | 개인정보 없음. 약품명·품목코드·실행 시각·폴더 이름(`medguard-pycharm-transfer`)만 표시 (실측) |
| `er.email` | 내용 확인 | 추적 파일 목록(186줄). 비밀정보·이메일 주소 없음. 어느 코드도 참조하지 않음 → 실행에 불필요 |
| 보고서 내 허가정보 원문 | 범위 확인 | `reports/step7_validation/` claim CSV, `reports/step7final_validation/case_*.json` 등에 허가정보 문장 일부와 LLM 출력 원문이 있음. 개인 식별 정보는 아님. 공개 전환 시 이용 조건에 따라 검토 필요(`docs/DATA_SOURCES.md` §5) |
| 커밋 메타데이터 | — | 기존 커밋 `23c5376`의 작성자 이메일은 개인 메일 주소입니다(STEP 10-1). 기록 재작성은 하지 않았습니다 |

**`er.email` 처리**
- `_backup_step10_2_20261027/er.email`에 백업했습니다(이 폴더는 `.gitignore`의 `_backup_*/` 규칙으로 Git에서 제외됨).
- `git rm er.email`로 추적에서 제거하고 삭제를 staged 상태로 두었습니다. **커밋은 하지 않았습니다.**
- 이미 `23c5376`에 커밋되어 있으므로, 다음 커밋 후에도 **Git 기록에는 남습니다.** 내용이 파일 목록뿐이라 기록 재작성은 권장하지 않습니다.
- 다시 생길 이유가 없는 일회성 파일이라 `.gitignore`에 추가하지 않았습니다.

---

## 7. 코드 및 데이터 무결성 (실측)

| 검사 | 작업 전 | 작업 후 |
|---|---|---|
| Frozen Core `sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt` | 9/9 OK | **9/9 OK** |
| 추적 코드·노트북·설정 해시(`src/`, `app/`, `ui_integration/`, `app.py`, `tests/`, `tools/`, `notebooks/`, `data_manifest.json`, `production_baseline.json`, 56개) | 기록 | **56/56 동일** |
| data manifest (`tools/fetch_runtime_data.py --verify`) | 35/35 (STEP 10-1) | **35/35 OK** |
| 핵심 소스 변경 | — | 없음 (`git diff`에 코드 파일 없음) |

---

## 8. Git 변경 사항 (커밋 전, 실측)

```
git status --short
 M DEPLOYMENT.md
 M README.md
D  er.email                                   (staged)
?? docs/                                      (EVALUATION.md, DATA_SOURCES.md)
?? reports/STEP10_1_GITHUB_PORTFOLIO_AUDIT.md
?? reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md
?? reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md
?? reports/step9_3_validation/

git diff --stat           DEPLOYMENT.md +4 / README.md +249 −57 (작성 도중 기준)
git diff --cached --stat  er.email −186
git diff --check          문제 없음
```

- 줄바꿈: 저장소 원본은 LF입니다. 편집 도중 Windows에서 CRLF로 바뀐 것을 발견해 LF로 되돌렸습니다. `.gitattributes`가 `* -text`이므로 줄바꿈이 바뀌면 diff 전체가 바뀝니다.
- 복구: `git checkout -- README.md DEPLOYMENT.md`, `git restore --staged er.email && git checkout -- er.email`, 또는 `_backup_step10_2_20261027/`.

---

## 9. 남은 문제

| # | 문제 | 영향 | 권장 |
|---|---|---|---|
| R1 | 허가정보(15095677) 이용 조건 NOT_VERIFIED. DUR·e약은요는 사용자 보고만 있음 | 공개 전환 차단 | 사용자가 공공데이터포털에서 확인한 뒤 README §6과 `docs/DATA_SOURCES.md` §3 갱신 |
| R2 | LICENSE 없음 | 공개 시 이용 범위 불명확 | 데이터 조건 확인 후 결정 |
| R3 | Mermaid 렌더링 NOT_VERIFIED | 다이어그램이 깨져 보일 수 있음 | push 후 GitHub에서 확인 |
| R4 | `STEP9_3` 보고서와 산출물 미커밋 | README·DEPLOYMENT의 Linux 수치 근거가 GitHub에 없음 | 이번 변경과 함께 커밋 |
| R5 | 코드 docstring과 `production_baseline.json`이 저장소에 없는 문서를 참조함: `docs/STREAMLIT_VIEW_MAPPING.md`, `docs/CORE_INTERFACE_CONTRACT.md`(`app/ui_policy.py`), `docs/PRODUCTION_BASELINE.md`(`change_policy`) | 독자가 찾을 수 없음. 동작 영향 없음 | 코드는 수정하지 않았습니다. Drive 원본에서 찾아 추가할지 사용자가 결정 |
| R6 | CE001 근거 모순, 의미 수준 Guardrail 부재, 과잉 차단, CPU 회귀 FAIL | 기존 미해결 기술 문제(문서에 공개함) | 향후 개선 §10의 1·2번 |
| R7 | 커밋 작성자 개인 이메일 | 공개 시 노출 | 공개 전 사용자 결정 |
| R8 | GitHub visibility 직접 확인 안 됨 | — | GitHub 웹에서 Private 확인 |
| R9 | 노트북 02·04·05가 저장소에 없어 `test_source_parity`는 clone 환경에서 실행 불가 | README §8-4에 명시함 | 유지 |

---

## 10. 사용자가 직접 해야 할 작업

1. **변경 검토**: `git diff README.md DEPLOYMENT.md`, 그리고 `docs/EVALUATION.md`·`docs/DATA_SOURCES.md` 읽기. 특히 CE001 A/B 설명(README §7)이 의도한 평가 기준과 맞는지 확인하세요.
2. **데이터 이용 조건 확인**: 의약품 제품 허가정보(15095677)의 이용허락범위를 확인하세요. 결과를 알려 주시면 문서를 갱신하겠습니다.
3. **커밋(승인 시)**: 아래는 예시이며 이번 단계에서 실행하지 않았습니다.
   ```bash
   git add README.md DEPLOYMENT.md docs/ reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md reports/step9_3_validation/ reports/STEP10_1_GITHUB_PORTFOLIO_AUDIT.md reports/STEP10_2_GITHUB_PORTFOLIO_FINALIZATION.md
   git status            # er.email 삭제가 staged 상태인지, playwright_artifacts 가 빠졌는지 확인
   git commit -m "Docs: portfolio README, evaluation and data source docs (STEP 10-2)"
   git push origin main
   ```
4. **push 후 확인**: GitHub에서 README의 Mermaid 다이어그램과 이미지가 보이는지, 저장소가 Private인지 확인하세요.
5. **선택**: 앞으로 커밋할 때 개인 이메일 대신 GitHub noreply 주소를 쓰려면 이 저장소에서만 `git config user.email "<ID>+<사용자명>@users.noreply.github.com"`으로 설정하세요(기존 커밋에는 영향 없음).

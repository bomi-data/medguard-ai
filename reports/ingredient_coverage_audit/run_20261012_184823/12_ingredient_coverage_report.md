# STEP 8-1.6 Ingredient-based DUR Coverage Expansion Feasibility Audit

- 실행 시각(KST): 20261012_184823 · 기준선: `reports/ui_coverage_audit/run_20261011_152938` · 결과 폴더: `reports/ingredient_coverage_audit/run_20261012_184823`
- 성격: 읽기 전용 분석. 운영 데이터·Screening 엔진·UI·평가 결과 변경 없음(분석 전/후 sha256 비교: 불변).
- 표기: **FACT**(실제 데이터로 계산) / **ESTIMATE**(전제·추정 포함) / **UNKNOWN**(현재 데이터로 판단 불가) / **JUDGMENT**(데이터로 계산되지 않는 판단).

## 1. Executive Summary
- **판정: OPTION C — 현재 데이터로는 신뢰할 만한 성분 기반 DUR 연결 불가.** 근거: 게이트 FAIL 또는 검증된 추가 연결 제품 0개 — 현재 데이터로 신뢰할 만한 성분 기반 연결 불가.
- 기준선 규칙 연결 12,736/16,441개(77.46%). 검증 등급(INFERRED) 기준으로 **추가 0개**(→ 77.46%, **ESTIMATE**), 후보 상한 768개(**검사 가능 수 아님**).
- 공식 D↔M 연결표: 없음. INFERRED 241쌍은 DUR 레코드 내부 일관성 기준이며 식약처 원천 대조 전입니다. leave-one-out 정확도 100.0%.
- 게이트: GATE1 WARN / GATE2 WARN / GATE3 WARN. **운영 Screening Engine 변경 금지**(사용자 승인 전).
- STEP 8-2: 조건부 진행 — 성분 기반 확장은 운영에 넣지 않고, UI는 상태 문구 분리·범위 고지(8-1.5 P0)를 설계하는 조건. 확장 구현은 별도 승인 후

## 2. Current DUR Coverage Problem (기준선 재검증)
- U = 16,441, 규칙 테이블 등장 12,736, UI '미포함' 3,705 (= S4 768 + S5 2,937 + S7 0, 서로소 확인).
- 복합제 누락 의심 3,191는 다른 집합(S4 일부 + S2 일부)이며 3,705와 **합산하지 않습니다**. 겹침: 미포함과 725, 미포함 밖 2,466.
| 기준선 집합 | 제품 수 | 신규 분석 T1 | T2(조건부) | T3(후보) | 겹침 없음(NONE) | 설명 |
|---|---|---|---|---|---|---|
| S4 규칙 미등재·누락 의심 (UI '미포함') | 768 | 0 | 405 | 363 | 0 | 8-1.5: 같은 성분 규칙이 있으나 테이블 미등장 |
| S5 정상 조회·규칙 매칭 없음 (UI '미포함') | 2937 | 0 | 0 | 0 | 2937 | 8-1.5: 성분이 3유형 규칙 성분과 겹치지 않음 |
| UI '미포함' 전체 (S4 ∪ S5 ∪ S7) | 3705 | 0 | 405 | 363 | 2937 | S4·S5·S7은 서로소여야 함 (실제 8-1.5: S7=0) |
| S7 판정 불가 (UI '미포함') | 0 | 0 | 0 | 0 | 0 | 성분 정보 없음 |
| S2 부분 검사 가능 (표시 없음) | 3048 | 7 | 800 | 2240 | 1 | 규칙 테이블에는 있으나 다른 유형 누락 의심 |
| 복합제 매핑 누락 의심 (8-1.5 원인 C) | 3191 | 0 | 1161 | 2030 | 0 | = 복합제 ∧ (S4 ∨ 유형별 누락 의심) — 3,705와 다른 집합 |

| 관계 | 제품 수 |
|---|---|
| S4 ∩ S5 | 0 |
| S4 ∪ S5 ∪ S7 | 3705 |
| UI 미포함 전체 | 3705 |
| 복합제 누락 의심 ∩ UI 미포함 | 725 |
| 복합제 누락 의심 − UI 미포함 (S2 쪽) | 2466 |
| 복합제 누락 의심 ∪ UI 미포함 | 6171 |
| 복합제 누락 의심 + UI 미포함 (단순 합 — 중복 포함, 사용 금지) | 6896 |

## 3. Dataset Inventory
| Dataset | Rows | Columns | Product Identifier | Ingredient Identifier | Ingredient Name | Missing Rate | Duplicate Rate | Mapping Potential | Notes |
|---|---|---|---|---|---|---|---|---|---|
| drug_approval_items | 42977 | 77 | ITEM_SEQ | MAIN_ITEM_INGR | INGR_NAME, ITEM_INGR_NAME, MAIN_INGR_ENG, MATERIAL_NAME | ITEM_SEQ=0.0%; MAIN_ITEM_INGR=0.13% | 0.0% (키: ITEM_SEQ) | MEDIUM — 제품 + 주성분 M코드(문자열 파싱 필요), DUR 성분코드(D) 없음 | 런타임 미사용 · 분석 기준 경로 |
| easy_drug_canonical | 4757 | 17 | item_seq, itemSeq | 없음 | 없음 | item_seq=0.0%; itemSeq=0.0% | 0.0% (키: item_seq) | LOW — 제품 식별자만 있음(성분 정보 없음) | 운영(Core) 로딩 대상; 성분 식별자·성분명 없음 |
| screening_itemseq_mapping | 17244 | 13 | item_seq_norm, ITEM_SEQ, source_identifier | 없음 | 없음 | item_seq_norm=0.0%; ITEM_SEQ=0.0%; source_identifier=0.0% | N/A | LOW — 제품 식별자만 있음(성분 정보 없음) | 런타임 미사용 · 분석 기준 경로; 성분 식별자·성분명 없음 |
| contraindication_pairs | 322816 | 3 | drug_1_item_seq, drug_2_item_seq | 없음 | 없음 | drug_1_item_seq=0.0%; drug_2_item_seq=0.0% | 0.0% (키: canonical_pair_id) | LOW — 제품 식별자만 있음(성분 정보 없음) | 운영(Core) 로딩 대상; 성분 식별자·성분명 없음 |
| contraindication_evidence | 796668 | 59 | item_seq, mixture_item_seq | ingr_code, mixture_ingr_code, MAIN_INGR, MIXTURE_MAIN_INGR | ingredient_name_kor, mixture_ingredient_name_kor | item_seq=0.0%; mixture_item_seq=0.0%; ingr_code=0.0%; mixture_ingr_code=0.0%; MAIN_INGR=0.0%; MIXTURE_MAIN_INGR=0.0% | 17.85% (키: canonical_pair_id, ingr_code, mixture_ingr_code) | HIGH — 제품(item_seq) + DUR 성분코드(D)가 같은 행에 있음 + 주성분(M) 문자열 | 운영(Core) 로딩 대상 |
| elderly_caution_rules | 1982 | 29 | item_seq | ingr_code, MAIN_INGR | ingredient_name_kor | item_seq=0.0%; ingr_code=0.0%; MAIN_INGR=0.05% | 0.1% (키: item_seq) | HIGH — 제품(item_seq) + DUR 성분코드(D)가 같은 행에 있음 + 주성분(M) 문자열 | 운영(Core) 로딩 대상 |
| therapeutic_group_mapping | 7064 | 38 | item_seq | ingr_code, MAIN_INGR | ingredient_name_kor | item_seq=0.0%; ingr_code=0.0%; MAIN_INGR=0.0% | 0.11% (키: item_seq, effect_name) | HIGH — 제품(item_seq) + DUR 성분코드(D)가 같은 행에 있음 + 주성분(M) 문자열 | 운영(Core) 로딩 대상 |
| therapeutic_group_summary | 9 | 4 | 없음 | 없음 | 없음 | - | 0.0% (키: effect_name) | NONE — 제품 식별자 없음 | 런타임 미사용 · 분석 기준 경로; 성분 식별자·성분명 없음 |

## 4. Identifier Compatibility Findings
| Source Dataset | Source Identifier | Target Dataset | Target Identifier | Join Method | Matched Records | Match Rate | Verification Status | Risk | Notes |
|---|---|---|---|---|---|---|---|---|---|
| drug_approval_items | ITEM_SEQ | DUR 규칙표 / 엔진 U | item_seq | 동일 식별자(정규화 후 문자열 일치) | 16441 | 100.0 | EXACT | 낮음 | 같은 item_seq 체계 (제품 단위 연결) |
| drug_approval_items | MAIN_ITEM_INGR [M…] | DUR 규칙표 | MAIN_INGR [M…] | 동일 M 코드 체계(문자열 일치) | 720 | 100.0 | EXACT | 낮음 | 같은 주성분 코드 체계 — 제품↔DUR 제품 행의 성분 비교에 사용 가능 |
| DUR 규칙표 | ingr_code [D…] | drug_approval_items | MAIN_ITEM_INGR [M…] | 공식 D↔M 연결표 | 0 |  | UNMAPPED | 중간 | 프로젝트 데이터에서 D↔M 직접 연결표를 찾지 못함 |
| DUR 규칙표(병용금기) | ingr_code [D…] | drug_approval_items | [M…] via DUR 단일성분 행 동시 출현 | DUR 레코드 내부 동시 출현 + 1:1·2제품·성분명 일치 | 112 | 51.14 | INFERRED | 중간 — 식약처 원천 대조 전 운영 적용 금지 | 규칙 D 219개 중 INFERRED 112 / CANDIDATE만 95 / 연결 근거 없음 12 |
| DUR 규칙표(노인주의) | ingr_code [D…] | drug_approval_items | [M…] via DUR 단일성분 행 동시 출현 | DUR 레코드 내부 동시 출현 + 1:1·2제품·성분명 일치 | 44 | 55.0 | INFERRED | 중간 — 식약처 원천 대조 전 운영 적용 금지 | 규칙 D 80개 중 INFERRED 44 / CANDIDATE만 36 / 연결 근거 없음 0 |
| DUR 규칙표(효능군) | ingr_code [D…] | drug_approval_items | [M…] via DUR 단일성분 행 동시 출현 | DUR 레코드 내부 동시 출현 + 1:1·2제품·성분명 일치 | 160 | 62.5 | INFERRED | 중간 — 식약처 원천 대조 전 운영 적용 금지 | 규칙 D 256개 중 INFERRED 160 / CANDIDATE만 94 / 연결 근거 없음 2 |
| DUR 규칙표 | ingr_code [D…] | drug_approval_items | [M…] via 성분명 정규화 | 성분명 일치(유일 후보) | 133 | 76.88 | CANDIDATE | 높음 — 동의어·염 형태 차이 | 정보용. 개선 수치에 포함하지 않음 |
| DUR 규칙표 | ingr_code [D…] | drug_approval_items | [M…] via 숫자부 일치 | 코드 숫자 일치 | 0 |  | UNMAPPED | 높음 — 우연 일치 | 숫자부 일치 쌍 중 공식 레코드로 확인된 쌍 0개. 사용하지 않음 (B-5) |
| DUR 규칙표 | (D,M) 쌍 — leave-one-out 예측 | 등재된 단일성분 제품 | 실제 ingr_code | 등재 제품 자기 행 제외 후 예측 | 9920 | 100.0 | INFERRED | 낮음 | 예측 가능 9,920건 중 오답 0건, 모호(여러 D) 72건, 예측 불가 121건 |

- INFERRED 241쌍 / CANDIDATE 309쌍. 후보 사유: {'D_MULTI_M': 177, 'SINGLE_PRODUCT_SUPPORT': 65, 'D_MULTI_M|SINGLE_PRODUCT_SUPPORT': 50, 'D_MULTI_M|M_MULTI_D': 3, 'D_MULTI_M|SINGLE_PRODUCT_SUPPORT|NAME_MISMATCH_OR_MISSING': 3, 'D_MULTI_M|NAME_MISMATCH_OR_MISSING': 2, 'M_MULTI_D|SINGLE_PRODUCT_SUPPORT': 2, 'NAME_MISMATCH_OR_MISSING': 2, 'SINGLE_PRODUCT_SUPPORT|NAME_MISMATCH_OR_MISSING': 2, 'D_MULTI_M|M_MULTI_D|NAME_MISMATCH_OR_MISSING': 2, 'M_MULTI_D': 1}.
- 공식 연결표 탐색(data/ 113개 파일): 후보 0개. 식별자 체계: DUR 성분코드 D / 주성분코드 M — 문자열 교집합 0개.

## 5. Ingredient Mapping Feasibility
| metric_id | metric | type | numerator | denominator | value_% | note |
|---|---|---|---|---|---|---|
| C1 | 전체 제품 수 (U) | EXACT | 16441 |  |  | 기준선과 동일 집합 |
| C2 | 성분 정보 존재 제품 수 | EXACT | 16441 | 16441.0 | 100.0 |  |
| C3 | 성분 식별자(M코드) 존재 제품 수 | EXACT | 16441 | 16441.0 | 100.0 | 이 데이터에서 성분 식별자 = 주성분 M코드 |
| C3b | 그중 DUR 성분 코드(D)에 INFERRED 연결이 하나라도 있는 제품 | EXACT | 6748 | 16441.0 | 41.04 |  |
| C4 | 단일성분제 수 | EXACT | 10909 | 16441.0 | 66.35 |  |
| C5 | 복합제 수 | EXACT | 5005 | 16441.0 | 30.44 |  |
| C5b | 구분이 모호한 제품 수 (M코드 1개인데 성분 수 ≥ 2) | EXACT | 527 | 16441.0 | 3.21 |  |
| C6 | 전체 성분 매핑 완료 제품 수 (INFERRED) | EXACT | 5163 | 16441.0 | 31.4 |  |
| C7 | 일부 성분만 매핑된 제품 수 | EXACT | 1585 | 16441.0 | 9.64 | 정보 불완전한 제품 포함 — 완전 매핑으로 처리하지 않음 |
| C7b | 후보 연결만 있는 제품 수 | CANDIDATE | 6665 | 16441.0 | 40.54 | 개선 수치에 미포함 |
| C8 | 성분 매핑 불가능 제품 수 (UNMAPPED + NO_INFO) | EXACT | 3028 | 16441.0 | 18.42 | '안전'이 아니라 '판정 근거 없음' |
| C9 | 성분 매핑 완료 비율 | EXACT | 5163 | 16441.0 | 31.4 |  |
| C10 | 복합제 완전 매핑 비율 | EXACT | 36 | 5005.0 | 0.72 |  |
| C10b | 복합제 중 부분 매핑 | EXACT | 1353 | 5005.0 | 27.03 |  |
| C11 | UNMAPPED 성분 중 'DUR 표에는 있으나 연결 못 만든' 성분을 가진 제품 | EXACT | 2907 | 16441.0 | 17.68 | 매핑 실패 가능성이 있는 부분 |
| C12 | UNMAPPED 성분 중 'DUR에 성분 자체가 없는' 성분을 가진 제품 | EXACT | 3277 | 16441.0 | 19.93 | 규칙이 없는 성분일 가능성 — 매핑 실패와 구분 불가 |

## 6. Combination Drug Analysis
| class | n_m_bucket | CANDIDATE_ONLY | COMPLETE_INFERRED | PARTIAL_INFERRED | UNMAPPED | 제품 수 |
|---|---|---|---|---|---|---|
| COMBO | 2 | 1660 | 36 | 791 | 368 | 2855 |
| COMBO | 3 | 115 | 0 | 167 | 292 | 574 |
| COMBO | 4+ | 92 | 0 | 395 | 1089 | 1576 |
| INCONSISTENT | 1 | 211 | 0 | 232 | 84 | 527 |
| SINGLE | 1 | 4587 | 5127 | 0 | 1195 | 10909 |

사용자 확인 제품(실제 상태):

| item_seq | item_name | class | state | m_codes | d_verified | tier_CI | tier_E | tier_T |
|---|---|---|---|---|---|---|---|---|
| 202106954 | 타이레놀콜드-에스정 | COMBO | PARTIAL_INFERRED | M223211\|M202983\|M203364\|M040353 | D000448\|D000893 | NONE | T2_CONDITIONAL | T2_CONDITIONAL |
| 202200658 | 우먼스타이레놀정 | COMBO | CANDIDATE_ONLY | M040353\|M082487 |  | NONE | NONE | T3_CANDIDATE |
| 202200525 | 어린이타이레놀현탁액(아세트아미노펜) | SINGLE | UNMAPPED | M281939 |  | NONE | NONE | NONE |
| 202200407 | 타이레놀8시간이알서방정(아세트아미노펜) | INCONSISTENT | CANDIDATE_ONLY | M040353 |  | NONE | NONE | BASELINE_LISTED |
| 202106092 | 타이레놀정500밀리그람(아세트아미노펜) | SINGLE | CANDIDATE_ONLY | M040353 |  | NONE | NONE | BASELINE_LISTED |
| 202005623 | 어린이타이레놀산160밀리그램(아세트아미노펜) | SINGLE | UNMAPPED | M279100 |  | NONE | NONE | NONE |
| 202201300 | 타이레놀산500밀리그램(아세트아미노펜) | SINGLE | CANDIDATE_ONLY | M262287 |  | NONE | NONE | BASELINE_LISTED |

## 7. Contraindication Coverage Potential
| DUR Type | Current Product Coverage | Ingredient Mapping Available | Rule Linkage Candidates | Inferred Linkages | Unverified Linkages | Additional Coverage Potential | Major Limitations |
|---|---|---|---|---|---|---|---|
| 병용금기 | 8,208/16,441 (49.92%) | 6,748/16,441 제품에 INFERRED 성분 연결 | 196 (미등재 중 규칙 성분과 겹침) | 4 | 192 | T1 4 / 조건부(T1+T2) 78 / 후보 상한(T1~T3) 196 | 제품쌍 규칙 — 제품 단위 연결은 필요조건일 뿐(상대 약물 필요). 제형·경로·용량 조건 UNKNOWN |

제품쌍 단위 상한(ESTIMATE, 조합 비생성): {"baseline_listed_pairs": 322816, "ingredient_pairs": 356, "new_verified_upper": 344, "new_conditional_upper": 1100, "new_candidate_upper": 3009, "all_upper": 348764, "ingredient_pair_listed_sum": 327214}

## 8. Elderly Caution Coverage Potential
| DUR Type | Current Product Coverage | Ingredient Mapping Available | Rule Linkage Candidates | Inferred Linkages | Unverified Linkages | Additional Coverage Potential | Major Limitations |
|---|---|---|---|---|---|---|---|
| 노인주의 | 1,980/16,441 (12.04%) | 6,748/16,441 제품에 INFERRED 성분 연결 | 588 (미등재 중 규칙 성분과 겹침) | 0 | 588 | T1 0 / 조건부(T1+T2) 307 / 후보 상한(T1~T3) 588 | 연령(65세) 입력 필요. 제형은 이름 기반 추정, 함량·용량 UNKNOWN |

연령 조건: 엔진 상수 65세, 미입력은 매핑 실패가 아님.

## 9. Therapeutic Duplication Coverage Potential
| DUR Type | Current Product Coverage | Ingredient Mapping Available | Rule Linkage Candidates | Inferred Linkages | Unverified Linkages | Additional Coverage Potential | Major Limitations |
|---|---|---|---|---|---|---|---|
| 효능군 중복 | 7,056/16,441 (42.92%) | 6,748/16,441 제품에 INFERRED 성분 연결 | 3,647 (미등재 중 규칙 성분과 겹침) | 3 | 3644 | T1 3 / 조건부(T1+T2) 1,081 / 후보 상한(T1~T3) 3,647 | 프로젝트 지원 9개 효능군에 한정. 같은 군 ≠ 부적절한 중복. 제형 이름 기반 추정 |

| 효능군 | 기존 등재 제품 | T1 추가 제품 | 기존 군 내 제품쌍(C(n,2)) | T1 반영 시 제품쌍 상한 |
|---|---|---|---|---|
| 당뇨병용제 | 733 | 0 | 268278 | 268278 |
| 마약류 아편유사제 | 140 | 0 | 9730 | 9730 |
| 소화성궤양용제 | 886 | 0 | 392055 | 392055 |
| 정신신경용제 | 1123 | 3 | 630003 | 633375 |
| 지질저하제 | 773 | 0 | 298378 | 298378 |
| 최면진정제 | 9 | 0 | 36 | 36 |
| 해열진통소염제 | 1227 | 0 | 752151 | 752151 |
| 혈압강하작용의약품 | 1017 | 0 | 516636 | 516636 |
| 호흡기관용약 | 1148 | 0 | 658378 | 658378 |

## 10. Baseline vs Inferred Expansion
| Metric | Baseline | Inferred Expansion | Candidate Potential | Difference (Inferred − Baseline) | Interpretation | Basis |
|---|---|---|---|---|---|---|
| 1. 전체 평가 대상 제품 수 (U) | 16441 | 16441 | 16441 | 0.0 | 기준선과 동일 집합 | FACT |
| 2. 규칙 연결 제품 수 (3유형 중 하나라도) | 12736 | 12736 | 13504 | 0.0 | 중복 제거 후 고유 제품 수 (유형이 여럿이어도 1회) | FACT / ESTIMATE |
| 3. 규칙 연결 비율 (%) | 77.46 | 77.46 | 82.14 | 0.0 | 분모 U | FACT / ESTIMATE |
| 4. 내부 추론 기반 추가 연결 제품 수 | 0 | 0 | 768 | 0.0 | 기존 미등재 제품 중 T1 / T1~T3 | ESTIMATE |
| 5. 개선 후 규칙 연결 제품 수 | 12736 | 12736 | 13504 | 0.0 | = 2행과 동일 값 (검산용) | ESTIMATE |
| 7. Coverage 증가 (%p) | 0.0 | 0.0 | 4.68 | 0.0 | 후보 값은 상한이며 실제 개선이 아님 | ESTIMATE |
| 8. 미연결 제품 수 | 3705 | 3705 | 2937 | 0.0 | '미연결' ≠ 안전 | ESTIMATE |
| 9. 미연결 제품 비율 (%) | 22.54 | 22.54 | 17.86 | 0.0 |  | ESTIMATE |
| 10. 후보 연결만 가능한 제품 수 (T1 없음, T2/T3만) | 0 | 0 | 768 | 0.0 | 검증되지 않아 운영 사용 불가 | CANDIDATE |
| 11. 병용금기 추가 연결 제품 수 (해당 유형으로 새로 등재되는 제품) | 0 | 4 | 196 | 4.0 | 이미 다른 유형으로 등재된 제품도 포함(유형별 수는 합산 금지) | ESTIMATE |
| 12. 노인주의 추가 연결 제품 수 (해당 유형으로 새로 등재되는 제품) | 0 | 0 | 588 | 0.0 | 이미 다른 유형으로 등재된 제품도 포함(유형별 수는 합산 금지) | ESTIMATE |
| 13. 효능군 중복 추가 연결 제품 수 (해당 유형으로 새로 등재되는 제품) | 0 | 3 | 3647 | 3.0 | 이미 다른 유형으로 등재된 제품도 포함(유형별 수는 합산 금지) | ESTIMATE |
| [참고] 이미 규칙 테이블에 있으나 다른 유형이 추가되는 제품 | 0 | 7 | 3047 | 7.0 | 유형 단위 추가 (제품 수 증가 아님) | ESTIMATE |
| [병용금기 제품쌍] 기존 등재 제품쌍 | 322816 | 323160 | 325825 | 344.0 | 성분쌍 기준 상한(조합 비생성). 임상적으로 의미 있는 처방쌍 수가 아님 | ESTIMATE |
| [병용금기 제품쌍] 추가 제품쌍 상한 | 0 | 344 | 3009 | 344.0 | 같은 제품쌍이 여러 성분쌍에 중복 집계될 수 있음 | ESTIMATE |
| [병용금기] 규칙 성분 적격 제품 중 등재 비율 (%) | 98.78 | 98.83 | 60.68 | 0.04999999999999716 | 분모 = 규칙 성분과 INFERRED로 겹치거나 이미 등재된 제품 8,309개 (후보 열은 후보 겹침 포함) | ESTIMATE |
| [노인주의] 규칙 성분 적격 제품 중 등재 비율 (%) | 81.18 | 81.18 | 68.85 | 0.0 | 분모 = 규칙 성분과 INFERRED로 겹치거나 이미 등재된 제품 2,439개 (후보 열은 후보 겹침 포함) | ESTIMATE |
| [효능군] 규칙 성분 적격 제품 중 등재 비율 (%) | 84.38 | 84.42 | 78.62 | 0.04000000000000625 | 분모 = 규칙 성분과 INFERRED로 겹치거나 이미 등재된 제품 8,362개 (후보 열은 후보 겹침 포함) | ESTIMATE |
| [노인주의] 연령 미입력으로 평가 안 함 | N/A | N/A | N/A |  | 실행 시점 입력 조건 — 제품 수로 계산하지 않음 (매핑 실패와 무관) | UNKNOWN |

## 11. Candidate Expansion Potential
후보 전용 제품 768개, 후보 상한(T1~T3) 미등재 제품 768개. **운영에 사용할 수 없으며 `candidate_quarantine/`에만 저장됩니다.**

## 12. Medical Safety Risks
| Test Case | Product | Actual Result | PASS/WARN/FAIL |
|---|---|---|---|
| F-1 서로 다른 성분이 잘못 연결되지 않았는가 | (전체) | 오답 0건 / 예측 9,920건 (정확도 100.0%), 모호 72건 | PASS |
| F-2 서로 다른 염 형태를 무조건 동일 처리하지 않았는가 | (전체) | 0건 (INFERRED 쌍 중 염/수화물 표기를 제거해야 이름이 같아지는 쌍 11개) | PASS |
| F-3 복합제의 일부 성분만 확인했는데 전체를 확인한 것으로 처리하지 않았는가 | (전체) | 위반 0건 · 복합제 T2 1412건은 조건부로 분리됨 | PASS |
| F-4 제형 차이를 무시하지 않았는가 | (전체) | T1 7건 중 제형 PASS 7건 · MISMATCH→T3 400건 · UNKNOWN→T2 558건 | PASS |
| F-4b 제형 판단의 근거 수준 | (전체) | 제형군은 제품명 접미사/제형명 기반 추정 — T1도 원천 대조 필요 | WARN |
| F-5 투여 경로 차이를 무시하지 않았는가 | (전체) | 허가정보에 투여경로 컬럼 없음 → UNKNOWN (외용/점안 등은 제형군으로만 간접 구분) | WARN |
| F-6 함량·용량 조건을 무시하지 않았는가 | (전체) | 구조화 컬럼 없음 → UNKNOWN (prohbt_content 텍스트만 존재) | WARN |
| F-7 제품 규칙과 성분 규칙이 충돌하지 않는가 | (전체) | 0건 (등재된 단일성분 제품의 INFERRED D가 등재 D와 불일치) | PASS |
| F-8 노인주의 연령 조건을 유지하는가 | (전체) | {None: 'not_evaluated_age_missing', 64: 'not_applicable_age_below_threshold', 65: 'evaluated'} | PASS |
| F-9 효능군 중복을 실제 금기와 혼동하지 않는가 | (전체) | rule_type 단일값 · 유형별 지표 행 분리 | PASS |
| F-10 근거 없는 규칙을 LLM이 생성하지 않는가 | (전체) | 새로 로딩된 LLM 관련 모듈: 없음 | PASS |
| F-11 기존 Screening 결과가 분석 때문에 변경되지 않았는가 | (전체) | 변경된 파일 없음 · 회귀 동일 (25건) | PASS |
| F-12 성분 매핑 실패를 안전한 약물로 잘못 해석하지 않는가 | (전체) | 허용 어휘 외 값 없음 · '안전' 포함 라벨 0건 | PASS |
| F-13 공식 근거와 프로젝트 내부 추정 규칙을 구분하는가 | (전체) | 기존 17,244 / 확장 4,431 | PASS |
| F-14 동일 규칙이 제품 기반과 성분 기반으로 중복 탐지되지 않는가 | (전체) | 중복 0건 | PASS |
| F-15 내부 추론·후보 연결이 실제 Screening 결과/코드에 반영되지 않는가 | (전체) | 누출 없음  | PASS |
| 정확하게 연결된 단일성분제 | 페니라민주사(클로르페니라민말레산염) (196000010) | leave-one-out MATCH | PASS |
| 정확하게 연결된 복합제 | 페리나정 (197600345) | {'CI': 'NONE', 'E': 'T2_CONDITIONAL', 'T': 'T2_CONDITIONAL'} | PASS |
| 일부 성분만 연결된 복합제 | 하트만용액 (196400020) | state=PARTIAL_INFERRED, tiers={'CI': 'BASELINE_LISTED', 'E': 'NONE', 'T': 'NONE'} | PASS |
| 식별자 연결이 불가능한 제품 | 활명수 (195700020) | {'CI': 'NONE', 'E': 'NONE', 'T': 'NONE'} | PASS |
| 성분명은 같지만 적용 조건이 다른 제품(제형) | 판콜에이내복액 (196800036) | tier=T3_CANDIDATE, reasons=COMBO_OR_PARTIAL_OR_INCOMPLETE\|FORM_MISMATCH | PASS |
| 기존 제품 규칙과 성분 규칙이 중복되는 사례 | 페니라민주사(클로르페니라민말레산염) (196000010) | {'CI': 'NONE', 'E': 'BASELINE_LISTED', 'T': 'BASELINE_LISTED'} | PASS |
| [사용자 확인 제품] 실제 상태 | 타이레놀콜드-에스정 (202106954) | tiers={'CI': 'NONE', 'E': 'T2_CONDITIONAL', 'T': 'T2_CONDITIONAL'} | WARN |
| [사용자 확인 제품] 실제 상태 | 우먼스타이레놀정 (202200658) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'T3_CANDIDATE'} | WARN |
| [사용자 확인 제품] 실제 상태 | 어린이타이레놀현탁액(아세트아미노펜) (202200525) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'NONE'} | PASS |
| [사용자 확인 제품] 실제 상태 | 타이레놀8시간이알서방정(아세트아미노펜) (202200407) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'BASELINE_LISTED'} | PASS |
| [사용자 확인 제품] 실제 상태 | 타이레놀정500밀리그람(아세트아미노펜) (202106092) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'BASELINE_LISTED'} | PASS |
| [사용자 확인 제품] 실제 상태 | 어린이타이레놀산160밀리그램(아세트아미노펜) (202005623) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'NONE'} | PASS |
| [사용자 확인 제품] 실제 상태 | 타이레놀산500밀리그램(아세트아미노펜) (202201300) | tiers={'CI': 'NONE', 'E': 'NONE', 'T': 'BASELINE_LISTED'} | PASS |

## 13. Root Cause Analysis
| 원인 | 확인된 제품 수 | 미포함 대비 % | 확정/추정 | 우선순위 | 중복 관계(상위 3) |
|---|---|---|---|---|---|
| G1 제품은 검색 가능하지만 현재 프로젝트의 DUR 규칙(item_seq)에 연결되지 않음 | 3705 | 100.0 | 확정 | P3 | G3 3,133; G5 2,459; G8 1,919 |
| G2 제품의 성분 정보가 누락됨 | 0 | 0.0 | 확정 | P1 | - |
| G3 제품 성분 식별자(M)와 DUR 성분 식별자(D)가 서로 다른 체계라 INFERRED 연결이 없음 | 3133 | 84.56 | 체계 차이는 확정 · 미포함에 대한 기여는 추정 | P0 | G1 3,133; G5 1,935; G8 1,919 |
| G4 공식 연결표 부재로 일부 성분을 CANDIDATE/UNMAPPED_IN_DUR로만 남김 | 1603 | 43.27 | 추정 | P0 | G1 1,603; G5 1,510; G3 1,214 |
| G5 복합제 성분 일부가 누락/미연결 또는 성분 수 불일치 | 2459 | 66.37 | 정보 불완전은 확정 · 규칙 누락 여부는 추정 | P0 | G1 2,459; G3 1,935; G4 1,510 |
| G6 제형(또는 투여경로) 차이로 규칙 적용 여부를 확인할 수 없음 | 245 | 6.61 | 추정(제형은 이름 기반) | P1 | G1 245; G5 200; G4 149 |
| G7 성분은 INFERRED 연결되지만 수집된 3유형 어디에도 그 성분 규칙이 없음 | 0 | 0.0 | 확정(수집 범위 내) | P2 | - |
| G8 수집된 DUR 데이터에 성분 자체가 없음 | 1919 | 51.79 | 확정(수집 범위 내) | P2 | G1 1,919; G3 1,919; G5 814 |
| G10 기타: 허가 상태 '정상' 아님 / 성분 수 불일치(INCONSISTENT) | 87 | 2.35 | 확정 | P3 | G1 87; G5 87; G3 84 |
| G9 검색 데이터와 규칙 조회 데이터 범위가 다름 (허가정보 '정상' 제품 중 UI 검색 불가) | 18832 |  | 확정 | P1 | 미포함 집합과 다른 분모 — 합산 금지 |

상호 배타적 1차 분류:

| 1차 분류 | 제품 수 | 미포함 대비 % |
|---|---|---|
| 3) 규칙 성분 겹침 — T2(조건 미확인) | 405 | 10.93 |
| 4) 규칙 성분 겹침 — T3(후보/제형 불일치) | 363 | 9.8 |
| 6) 수집된 DUR 데이터에 성분 자체가 없음 | 1919 | 51.79 |
| 7) 기타(부분 매핑·후보 연결 등으로 판단 불가) | 1018 | 27.48 |

## 14. Required Additional Data
- **공식 D↔M 성분코드 대응(또는 품목-성분 상세)**: 식약처 계열 공공데이터. 공공데이터포털에 식약처 DUR 관련 OpenAPI 페이지가 검색에는 노출되지만(예: data.go.kr/data/15059486, 15056780) **이 세션에서 내용·필드를 확인하지 못했으므로 존재·제공 필드는 UNKNOWN**입니다. 필요한 컬럼: 품목일련번호, 성분코드(D와 M 중 어느 쪽인지), 성분명, 함량, 제형, 투여경로. 연결 식별자: item_seq. 한계: 미확인.
- **제형·투여경로·함량 구조화 데이터**: 현재 허가정보에는 성상(`CHART`)과 문자열만 있음 → F-4~F-6 UNKNOWN 해소용.
- **약사/임상 검토 프로세스**: T1을 운영에 올리기 전 필수(데이터로 대체 불가).

## 15. Recommended Architecture
- Core 엔진은 그대로 두고 **별도 보조 조회 계층**을 둡니다: `item_seq → {추가 규칙 후보, 근거 등급, 요구 조건}`. 결과는 UI에 "후보/검증 필요"로만 표시하고 Screening 판정에는 합치지 않습니다.
- 모든 확장 행은 `evidence_basis=PROJECT_INFERENCE`, `requires_source_check=True`. T2/T3는 격리 폴더에서만 관리.
- UI는 8-1.5 P0에 따라 상태를 분리 표시(검사 가능 / 일부 / 규칙 데이터에 없음 — 위험 없음 아님 / 판정 불가).

## 16. Implementation Difficulty
| 평가 항목 | 근거 종류 | 근거 | 평가 | 비고 |
|---|---|---|---|---|
| 1 공식 성분 식별자 연결 | FACT | 없음 (D↔M 직접 연결표 미발견) | 제한적 | INFERRED (D,M) 241쌍은 DUR 레코드 내부 일관성 기준 |
| 2 성분 매핑 정확도 | FACT | leave-one-out 100.0% (오답 0, 예측 9,920건) | 양호 | 등재 제품에 대한 검증이며 미등재 제품 정확도는 UNKNOWN |
| 3 복합제 처리 | FACT | 완전 매핑 36/5,005 (0.72%) | 제한적 | 복합제는 T1이 될 수 없음(조건부) |
| 4 병용금기 적용 | ESTIMATE | T1 4개 · 제품쌍 추가 상한 344 | 제한적 | 제품쌍 규칙, 제형·경로·용량 UNKNOWN |
| 5 노인주의 적용 | ESTIMATE | T1 0개 | 제한적 | 연령 65 입력 필요, 함량 UNKNOWN |
| 6 효능군 중복 적용 | ESTIMATE | T1 3개 | 제한적 | 9개 지원 군에 한정, 같은 군 ≠ 부적절 |
| 7 의료 안전성 | FACT | GATE 3 = WARN | 조건부 | WARN 항목(F-2/4b/5/6)은 보고서에 유지 |
| 8 기존 엔진 호환성 | FACT | 엔진은 item_seq 딕셔너리 조회 — 별도 보조 조회 계층(item_seq→추가 규칙 후보)으로 엔진 수정 없이 결합 가능 | 양호 | 분석 전/후 엔진·데이터 해시 불변: 확인 |
| 9 구현 난이도 | JUDGMENT | 보조 계층 자체는 중간, 원천 대조·약사 검토 프로세스가 병목 | 중간~높음 | 데이터로 계산되는 값이 아님 |
| 10 포트폴리오 가치 | JUDGMENT | 식별자 체계 불일치를 감사하고 검증 등급으로 안전하게 격리한 설계 근거를 보여 줌 | 높음(주관) | 사용자 판단 영역 |

## 17. Portfolio Value Assessment (JUDGMENT)
식별자 체계 불일치를 감사하고, 검증 등급·격리·회귀 해시로 의료 안전성을 지키며 확장 가능성을 정량화한 점이 핵심 근거입니다. 이 항목은 데이터로 계산되지 않는 판단입니다.

## 18. Final Decision
**OPTION C — 현재 데이터로는 신뢰할 만한 성분 기반 DUR 연결 불가**

게이트 FAIL 또는 검증된 추가 연결 제품 0개 — 현재 데이터로 신뢰할 만한 성분 기반 연결 불가

## 19. Next Step Recommendation
1. 위 Required Additional Data 확보 가능성 확인(특히 공식 D↔M 대응).
2. T1 표본(`internal_inferred/08b_*`)을 약사가 검토해 오연결·조건 위반을 라벨링 → 정답 라벨로 정밀도 측정.
3. STEP 8-2: 조건부 진행 — 성분 기반 확장은 운영에 넣지 않고, UI는 상태 문구 분리·범위 고지(8-1.5 P0)를 설계하는 조건. 확장 구현은 별도 승인 후

---
## 부록. 단계별 상태 / PASS가 아닌 검사
| Step | Status |
|---|---|
| 0 | PASS |
| A | PASS |
| B1 | WARN |
| B2 | WARN |
| C1 | WARN |
| C2 | WARN |
| GATE2 | WARN |
| D1 | WARN |
| D2 | WARN |
| D3 | WARN |
| D4 | PASS |
| E | WARN |
| GATE3 | WARN |
| G | PASS |
| H | PASS |

| step | check | result | detail |
|---|---|---|---|
| B1 | GATE1-0 공식 연결표 스캔 중 읽기 실패 파일 없음 | WARN | 1개: data/processed/evaluation/_cache_06D/smoke_preview/generation_eval_case_results.parquet |
| B1 | GATE1-12 투여경로·함량 구조화 컬럼 존재 | WARN | 없으면 해당 조건은 UNKNOWN으로만 보고 |
| B2 | 공식 D↔M 연결표(EXACT) 존재 | WARN | 없음 — INFERRED는 'DUR 레코드 내부 일관성' 기준이며 식약처 원천 대조 필요 |
| C1 | 제형·함량·투여경로 구조화 컬럼 | WARN | 함량·투여경로 UNKNOWN, 제형은 성상(CHART)+이름 기반 추정 |
| C2 | 복합제 완전 매핑 비율 ≥ 50% | WARN | 0.72% (36/5,005) |
| GATE2 | GATE2-8 공식 D↔M 연결표(EXACT) 존재 | WARN | 없음 — INFERRED는 DUR 레코드 내부 일관성 기준(식약처 대조 전) |
| GATE2 | GATE2-9 제형·투여경로·함량 조건 확인 가능 | WARN | 투여경로·함량 UNKNOWN — 적용 조건 미확인 |
| D1 | 병용금기 적용 조건(제형·경로·용량) 구조화 데이터 | WARN | UNKNOWN — prohbt_content 텍스트만 있음 |
| D2 | 함량·용량 조건 구조화 데이터 | WARN | UNKNOWN — prohbt_content 텍스트만 있음 |
| D2 | T1 후보가 존재 | WARN | 0개 |
| D3 | 원천(식약처) 전체 효능군 범위 확인 | WARN | UNKNOWN — 프로젝트 데이터로는 확인 불가 |
| E | 개선 수치가 ESTIMATE 라벨을 가짐 (원천 대조 전) | WARN | Inferred Expansion은 DUR 레코드 내부 일관성 + 이름 기반 제형 추정에 의존 |
| GATE3 | F-4b 제형 판단의 근거 수준 | WARN | 제형군은 제품명 접미사/제형명 기반 추정 — T1도 원천 대조 필요 |
| GATE3 | F-5 투여 경로 차이를 무시하지 않았는가 | WARN | 허가정보에 투여경로 컬럼 없음 → UNKNOWN (외용/점안 등은 제형군으로만 간접 구분) |
| GATE3 | F-6 함량·용량 조건을 무시하지 않았는가 | WARN | 구조화 컬럼 없음 → UNKNOWN (prohbt_content 텍스트만 존재) |

*수치는 위 실행 시각의 데이터 파일로 계산했습니다. ESTIMATE는 전제(DUR 레코드 내부 일관성, 이름 기반 제형 추정)에 의존하며 식약처 원천 및 약사 검토 전에는 확정할 수 없습니다.*

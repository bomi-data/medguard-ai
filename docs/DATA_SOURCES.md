# MEDGUARD AI — 데이터 출처와 이용 조건

> 이 저장소에는 원본 데이터, 처리된 데이터, 임베딩 모델 가중치가 **포함되어 있지 않습니다.**
> 처리된 데이터 파일 35개(`data/processed/` 29개 + `reports/` 감사 결과 6개)의 경로와 SHA256은 [`data_manifest.json`](../data_manifest.json)에 있습니다.

## 1. 데이터셋

| 제공기관 | 데이터 | 데이터 안의 출처 기록 | 프로젝트 내 용도 | 처리 파일 (`data/processed/`) | 기록된 시점 |
|---|---|---|---|---|---|
| 식품의약품안전처 | 의약품안전사용서비스(DUR) 규칙: 병용금기, 노인주의, 효능군중복 | 데이터셋 ID·API 이름이 처리 파일에 기록되어 있지 않음 (`NOT_RECORDED`) | Structured Screening의 판정 기준 | `screening/contraindication_pairs.parquet`(322,816쌍), `contraindication_evidence.parquet`(796,668행), `elderly_caution_rules.parquet`(1,982행), `therapeutic_group_mapping.parquet`(7,064행) | 고시일자(`NOTIFICATION_DATE`) 범위: 병용금기 2007-04-11 ~ 2024-06-25, 노인주의 2014-07-28 ~ 2025-05-30. 수집일 기록 없음 |
| 식품의약품안전처 | 의약품 제품 허가정보 | `data.go.kr 15095677 식품의약품안전처_의약품 제품 허가정보`, API `DrugPrdtPrmsnInfoService08` | RAG 근거 문서(사용상 주의사항·효능효과·용법용량 등), 성분 중복 후보 | `evidence/drug_approval_items.parquet`(42,977개 제품), `rag/approval_chunks.parquet`(323,676 chunk, 12,736개 제품) | 상세 정보 수집 2026-09-26 (`detail_prov_retrieved_at`) |
| 식품의약품안전처 | e약은요 (의약품개요정보) | 데이터셋 ID가 처리 파일에 기록되어 있지 않음 (`NOT_RECORDED`). 열 구조(`efcyQesitm` 등)로 식별 | 품목코드→제품명 표시 보조. RAG 근거로는 쓰지 않음 | `evidence/easy_drug_canonical.parquet`(4,757개 제품) | `updateDe` 최대 2026-09-21 |
| BAAI (Hugging Face) | 임베딩 모델 `BAAI/bge-m3` | revision `5617a9f61b028005a4858fdac845db406aefb181` | 밀집 검색(질의 인코딩). 코퍼스 임베딩은 미리 계산해 둠 | `retrieval/dense/BAAI__bge-m3/` (임베딩 행렬만, 모델 가중치는 HF 캐시) | — |

이 표의 출처 기록, 행 수, 시점은 로컬 데이터 파일에서 읽기 전용으로 확인했습니다(STEP 10-2). 공공데이터포털 페이지의 정확한 URL은 이 문서에 적지 않았습니다. 확인한 값만 기록하기 위해서입니다.

## 2. 처리 과정 (요약)

- 원본 API 응답을 Google Colab 노트북에서 수집하고 정리해 Parquet로 저장했습니다. 수집·전처리 노트북은 **이 저장소에 포함되어 있지 않습니다.**
- 허가정보 문서는 조항 단위 chunk로 나누었습니다. 문서 유형(`precautions`, `efficacy`, `dosage`, `professional`)과 고령자·상호작용·금기 조항 표시를 붙였습니다.
- 앱은 시작할 때 데이터 SHA256을 평가 당시 기록값과 비교합니다. 다르면 검색·분석을 비활성화합니다(`src/dur_safety/resources.py`).

## 3. 이용 조건 확인 상태

| 데이터 | 상태 | 비고 |
|---|---|---|
| DUR 규칙 데이터 | **사용자 확인 보고**: 이용허락범위 제한 없음 | 이 문서 작성 과정에서 독립적으로 확인하지 않았습니다 |
| e약은요 | **사용자 확인 보고**: 이용허락범위 제한 없음 | 위와 같음 |
| 의약품 제품 허가정보 (15095677) | **NOT_VERIFIED** | 이용 조건을 확인한 기록이 없습니다 |
| `BAAI/bge-m3` | NOT_VERIFIED (이 문서에서 확인 안 함) | 모델 카드의 라이선스를 직접 확인하세요 |
| OpenAI 생성 출력 (보고서에 일부 수록) | NOT_VERIFIED | 서비스 약관을 확인하지 않았습니다 |

이용 조건이 "제한 없음"이어도 출처 표시 의무나 재배포 방식에 관한 조건이 있을 수 있습니다. 데이터를 공개 위치에 올리거나 저장소를 공개로 바꾸기 전에 공공데이터포털의 각 데이터셋 페이지에서 이용허락범위를 다시 확인하세요.

### 3-1. 항목별 확인 상태 (STEP 10-3)

"이용할 수 있다"는 것과 "다시 배포해도 된다"는 것은 서로 다른 조건입니다. 아래 표에서 **사용자 보고**는 사용자가 직접 확인했다고 알려 준 내용이고, Claude가 원문을 보고 확인한 것이 아닙니다. 이 작업 환경에서는 외부 사이트를 열람하지 않았습니다.

| 항목 | DUR 규칙 데이터 | e약은요 | 의약품 제품 허가정보 (15095677) |
|---|---|---|---|
| 1. 데이터 이용 가능 여부 | 사용자 보고: 제한 없음 | 사용자 보고: 제한 없음 | NOT_VERIFIED |
| 2. 원본 데이터 재배포 가능 여부 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED |
| 3. 출처 표시 의무 | NOT_VERIFIED (이 문서는 출처를 표시함) | NOT_VERIFIED (이 문서는 출처를 표시함) | NOT_VERIFIED (이 문서는 출처를 표시함) |
| 4. 가공 데이터 공개 가능 여부 | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED |
| 5. API 이용 조건(인증키·호출 제한 등) | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED |
| 정확한 공식 데이터셋 이름·ID | 처리 파일에 기록 없음 — 확인 필요 | 처리 파일에 기록 없음 — 확인 필요 | `식품의약품안전처_의약품 제품 허가정보` (15095677), 데이터 내 기록 |
| 현재 이 저장소의 재배포 | **하지 않음** (원본·가공 데이터 모두 Git 제외) | **하지 않음** | **하지 않음** |

공개 전환 전에 사용자가 확인할 것: 2~5번 항목, DUR·e약은요의 공식 데이터셋 이름과 ID. 확인 결과가 정해지면 이 표와 README §6을 함께 갱신하세요.

## 4. 저장소에서 데이터를 제외하는 이유

1. 100MB를 넘는 파일이 2개 있어(`drug_approval_items.parquet` 392.5MB, `approval_chunks.parquet` 129.6MB) 일반 Git push가 불가능합니다.
2. 허가정보의 재배포 조건을 확인하지 않았습니다.
3. 실행에 필요한 것은 처리된 데이터와 manifest입니다. 데이터를 받은 사람은 `python tools/fetch_runtime_data.py --verify`로 SHA256 일치를 확인할 수 있습니다.

데이터 배포 방식(외부 비공개 저장소, Git LFS, 데이터 패키지 등)은 아직 정하지 않았습니다. 선택지는 [`DATA_STRATEGY.md`](../DATA_STRATEGY.md)에 있습니다.

## 5. 보고서에 포함된 데이터 인용

`reports/` 안의 일부 평가 산출물(예: `reports/step7_validation/`의 claim 검토 CSV, `reports/step7final_validation/case_*.json`)에는 허가정보 문장 일부와 LLM 출력 원문이 평가 증거로 들어 있습니다. 저장소를 공개로 바꾸기 전에 위 이용 조건 확인 결과에 따라 포함 여부를 검토하세요.

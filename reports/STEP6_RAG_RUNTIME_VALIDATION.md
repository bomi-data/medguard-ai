# STEP 6 — 실제 RAG 검색 환경 정상화 보고서

- 작성일: 2026-10-23
- 대상: MEDGUARD AI — 연구·포트폴리오용 프로토타입, **임상 검증 아님** (`CLINICAL_VALIDATION_STATUS = NOT_VALIDATED`)
- PROJECT_ROOT: `C:\Users\<USER>\Downloads\medguard-pycharm-transfer\medguard-pycharm-transfer`

> **구분**: 이 보고서의 "PASS"는 (1) 검색 함수가 실제 모델·인덱스로 실행되고 (2) 평가 당시 시스템과 동일한 근거를 반환함을 뜻한다. 반환된 근거가 **의학적으로 적합한지에 대한 새로운 검증은 아니다.** 품질 수치는 기존 06-A 사람 라벨 30건에 한정된다.

## 0. 판정 요약

| 항목 | 상태 | 근거 |
|---|---|---|
| bge-m3 다운로드 | PASS | 공식 `BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`, Hub 기록 크기·LFS sha256 일치 |
| 실제 모델 로딩 (`require_dense=True`) | PASS | `model_loaded=True, index_loaded=True, error=None`, 인덱스 36,988×1024 |
| BM25 / Dense / Hybrid 실행 | PASS | 3 질의 × 3 방법 모두 status OK, 5건 반환 |
| Evidence ID·원본 연결 | PASS | 운영 경로에서 E1~E5 부여, 근거 행 검증 오류 0, corpus 메타 일치 |
| 검색 실패 처리 | PASS | 빈 질의·미등록 품목·후보 없음 → NO_EVIDENCE, 잘못된 risk_type → ValueError |
| 06-A 대비 검색 결과 재현 | PASS | Top-5 30/30 일치 (3개 방법 모두), 지표 = 06-B 기록값 |
| 엄격 retrieval 회귀 테스트 | FAIL (예상된 장치 차이) | dense_score 값만 최대 0.0007 차이, 순위 33/33 동일 (STEP 5 §5.2) |
| **STEP6_STATUS** | **PASS** | 위 런타임 검증 항목 전부 실제 실행으로 확인 |

## 1. 작업 목적

STEP 4에서 bge-m3 미설치로 실행 불가였던 평가 구성(BM25 + Dense + prior, RRF hybrid)을 Windows CPU 환경에서 실제로 실행하고, 결과·근거 연결·실패 처리·자원 사용량을 측정한다. 검색 구조는 변경하지 않는다.

## 2. 기존 RAG 구조 (코드 확인: `src/dur_safety/retrieval.py`, Frozen Core)

| 요소 | 구현 |
|---|---|
| 후보 제한 | `get_candidates`: 입력 ITEM_SEQ의 허가정보 chunk로 hard filter + risk_type별 soft prior |
| BM25 | sklearn `CountVectorizer(char_wb, 2-gram)`, k1=1.2, b=0.75, unique text 단위 |
| Dense | `SentenceTransformer("BAAI/bge-m3", revision=resolved_revision)`, max_seq_length 1024, 정규화 cosine, 사전 계산 임베딩 `unique_text_embeddings.npy` (fp16, mmap) |
| revision 고정 | `retrieval_config.json` `resolved_revision` = `config.EXPECTED_DENSE_REVISION` = `generation_config` → `resources.verify_runtime()`이 3중 검사 |
| Hybrid | RRF(k=60), 가중치 bm25 1.0 / dense 1.0 / prior 0.5, depth 100, 다품목 시 품목별 round-robin |
| Evidence ID | `generation.prepare_evidence_context`: 검증(`validate_evidence_rows`: chunk_id·document_id·ITEM_SEQ·text_hash·sha1) 통과 행에 `E1..E5` 부여 |
| 실패 처리 | `NO_EVIDENCE`(EMPTY_QUERY / ITEM_SEQ_NOT_IN_CORPUS / NO_CANDIDATES …), dense 불가 시 `DEGRADED`(hybrid_bm25_only) — 운영 기본값(`require_dense=True`)은 DEGRADED를 허용하지 않고 실패(fail-closed) |
| 캐싱 | `resources.load_resources()`가 프로세스당 1회 로딩, 모델은 HF 기본 캐시 사용 |
| 장치 | CUDA면 `half()`(평가 구성), CPU면 fp32 — 코드가 CPU 사용 시 경고 출력 |

## 3. 모델·인덱스 호환성 및 자원 점검 (다운로드 전)

| 항목 | 확인 결과 |
|---|---|
| 공식 저장소 | `huggingface.co/BAAI/bge-m3` (author BAAI), 지정 revision 존재 확인 |
| 인덱스 호환 | `embedding_meta.json`: model `BAAI/bge-m3`, `resolved_revision` 동일, dim 1024, n_texts 36,988, hash_order_sha256 일치 |
| 기존 다운로드 | 없음 (`~/.cache/huggingface/hub`에 e5-small, Llama-3.2-1B만 존재) |
| 디스크 | C: 여유 약 147GB |
| RAM | 총 15.7GB, 확인 시 여유 1.9~3.9GB(다른 프로세스 사용 중), 커밋 여유 14.3GB → OOM 아닌 페이징 위험으로 판단하고 진행 |
| 캐시 위치 | `C:\Users\<USER>\.cache\huggingface\hub\models--BAAI--bge-m3` (HF_HOME 미설정, 기본값) |

## 4. 다운로드

```python
snapshot_download("BAAI/bge-m3", revision="5617a9f61b028005a4858fdac845db406aefb181",
    allow_patterns=[modules.json, config_sentence_transformers.json, sentence_bert_config.json, config.json,
                    1_Pooling/config.json, pytorch_model.bin, tokenizer.json, tokenizer_config.json,
                    special_tokens_map.json, sentencepiece.bpe.model])
```

- 저장소 전체 4.59GB 중 SentenceTransformer 로딩에 쓰이지 않는 `onnx/`(2.27GB), `imgs/`, `colbert_linear.pt`, `sparse_linear.pt` 제외 → 실제 약 2.29GB, 83초.
- 검증: 10개 파일 크기 = Hub 메타데이터, LFS 3개(`pytorch_model.bin`, `tokenizer.json`, `sentencepiece.bpe.model`) sha256 = Hub LFS sha256.
- Windows에서 symlink 미지원 경고(개발자 모드 아님) → 캐시가 복사 방식으로 저장됨. 기능 영향 없음.
- 다른 모델 사용: **없음**.

## 5. 실제 실행 검증

명령 (`reports/step5_6_validation/rag_probe.py`, 읽기 전용, 결과: `rag_probe_result.json`):

```bash
PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 (OPENAI_API_KEY 제거) \
  .venv/Scripts/python.exe -X utf8 reports/step5_6_validation/rag_probe.py <root> rag_probe_result.json
```

### 5.1 로딩

| 항목 | 값 |
|---|---|
| `load_resources(require_dense=True, verify_hashes=True)` | 성공 (해시·런타임 parity 검사 포함) |
| 소요 시간 | 48.0초 (첫 실행 62.3초) |
| DENSE_STATE | model_loaded=True, index_loaded=True, device=cpu, error=None, revision=5617a9f… |
| 모델 dtype | torch.float32 (CPU) |

### 5.2 검색 (04 smoke 기준 질의 3건, 결과 5건, 지연시간 = warm-up 후 3회 중앙값)

| 질의 | 방법 | status | 결과 수 | 후보 text | 입력 품목만 반환 | corpus 메타 일치 | 지연 |
|---|---|---|---|---|---|---|---|
| Q1 노인주의 | BM25 | OK | 5 | 16 | ✓ | ✓ | 5.5 ms |
| | Dense | OK | 5 | 16 | ✓ | ✓ | 138.8 ms |
| | Hybrid | OK (method=hybrid) | 5 | 16 | ✓ | ✓ | 120.9 ms |
| Q2 병용금기 | BM25 | OK | 5 | 28 | ✓ | ✓ | 8.6 ms |
| | Dense | OK | 5 | 28 | ✓ | ✓ | 130.7 ms |
| | Hybrid | OK (method=hybrid) | 5 | 28 | ✓ | ✓ | 137.5 ms |
| Q3 효능군 중복 | BM25 | OK | 5 | 29 | ✓ | ✓ | 7.4 ms |
| | Dense | OK | 5 | 29 | ✓ | ✓ | 127.2 ms |
| | Hybrid | OK (method=hybrid) | 5 | 29 | ✓ | ✓ | 128.2 ms |

STEP 4의 `DEGRADED / hybrid_bm25_only`가 이번에는 **`OK / hybrid`** (평가 구성)로 실행됨. 06-A 30건 × 3방법 전체 실행 9.6초.

### 5.3 Evidence ID 연결 (운영 경로: `screen_patient` → `findings_from_screening_result` → `retrieve_evidence` → `prepare_evidence_context`)

| 질의 | retrieval | evidence_id | chunk_id (예) | 검증 오류 |
|---|---|---|---|---|
| Q1 | OK / hybrid | E1–E5 | 197000079_NB_01_009_01 … | 0 |
| Q2 | OK / hybrid | E1–E5 | 195700013_NB_01_006_01, 196900031_NB_01_006_01 … (두 품목 균형) | 0 |
| Q3 | OK / hybrid | E1–E5 | 197000068_NB_01_005_01, 197700114_NB_01_005_01 … | 0 |

`validate_evidence_rows`가 각 근거의 chunk_id·document_id·ITEM_SEQ·text_hash(sha1 재계산)를 corpus 원본과 대조 → 오류 0.

### 5.4 검색 실패 처리

| 입력 | 결과 |
|---|---|
| 빈 질의 (hybrid) | `NO_EVIDENCE / EMPTY_QUERY` |
| 미등록 ITEM_SEQ 999999999 (hybrid) | `NO_EVIDENCE / ITEM_SEQ_NOT_IN_CORPUS` |
| 후보 없음 (dense) | `NO_EVIDENCE / NO_CANDIDATES` |
| 잘못된 risk_type | `ValueError` (허용 목록 안내) |
| dense 불가 + `require_dense=True` | `ResourceVerificationError` (STEP 4에서 확인, fail-closed) |

### 5.5 메모리 (Windows `K32GetProcessMemoryInfo`, 단일 프로세스)

| 시점 | 작업 집합 | 커밋(private) |
|---|---|---|
| 시작 | 0.02 GB | 0.01 GB |
| 로딩 직후 | 2.80 GB (최대 2.85) | 5.93 GB (최대 5.97) |
| 검색·평가 후 | 3.97 GB (최대 3.97) | 5.95 GB (최대 **5.97**) |

- 필요 메모리(커밋)는 **약 6.0GB**. 측정 당시 물리 여유 RAM이 약 3.9GB여서 일부가 페이징됨 → 작업 집합이 커밋보다 작게 측정됨.
- STEP 4의 BM25-only 약 3.4GB 대비 모델(fp32 약 2.3GB) 추가분과 대체로 일치.

## 6. 검색 품질 (기존 평가셋 사용)

- 평가셋: 06-A 사람 라벨(`evaluation_annotation_completed` + `evaluation_pool_master`), 30 질의 중 관련 근거가 있는 29건(EC008 제외, 06-B와 동일 집계).
- 지표 구현 검증: 저장된 06-A 결과(`evaluation_retrieval_raw`)로 계산한 값이 06-B `retrieval_evaluation_report.json` 기록값과 **3개 방법 모두 소수 6자리까지 일치** → 같은 정의로 계산하고 있음을 확인.

| 방법 | 06-A 대비 Top-5 일치 | hit@1 | hit@3 | hit@5 | P@5 | MRR@5 | nDCG@5 |
|---|---|---|---|---|---|---|---|
| BM25 (이번 CPU) | 30/30 | 0.4828 | 0.8276 | 0.9310 | 0.4897 | 0.6580 | 0.5373 |
| Dense (이번 CPU) | 30/30 | 0.6552 | 0.9655 | 0.9655 | 0.5655 | 0.7931 | 0.6723 |
| **Hybrid (이번 CPU)** | **30/30** | 0.8966 | 0.9655 | 1.0000 | 0.5655 | 0.9322 | 0.7340 |
| Hybrid (06-B 기록, GPU) | — | 0.8966 | 0.9655 | 1.0000 | 0.5655 | 0.9322 | 0.7340 |

해석:
- Windows CPU 실행이 평가 당시 GPU 실행과 **같은 근거를 같은 순서로** 반환하므로, 06-B에 기록된 품질이 이 환경에서도 재현된다.
- 이는 **30건의 라벨 범위 안에서의 재현**이다. 새 입력에 대한 일반화, 근거의 임상적 적합성, 사람 라벨 자체의 정확성은 검증 대상이 아니다.
- 06-B 기록상 hybrid가 단일 방법보다 nDCG@5가 낮은 질의도 15건 있음(`query_level_summary`) — 기존 평가 결과로서 그대로 둔다.

## 7. 알려진 차이 및 위험

1. **CPU fp32 vs GPU fp16**: dense_score가 0.0001–0.0007 차이. 이번 33건에서는 순위 영향 0. 동결 기준 문서에 따르면 06-A 30건 중 12건은 인접 dense 점수 차가 0.0007 이하 → **새 입력에서는 근거 순위가 바뀔 수 있음**(평가 구성은 GPU fp16).
2. 엄격 retrieval 회귀 테스트는 CPU에서 FAIL(STEP 5 §5.2). 허용 오차 변경은 하지 않았다.
3. 메모리 약 6GB — Streamlit Community Cloud 무료 한도를 넘을 가능성이 높음(클라우드는 이번에 검증하지 않음).
4. 모델 로딩 48–62초 — 앱 콜드 스타트 시간에 직접 반영.

## 8. 변경 파일 목록

| 파일 | 종류 |
|---|---|
| `C:\Users\<USER>\.cache\huggingface\hub\models--BAAI--bge-m3\` (약 2.2GB) | 모델 캐시 (프로젝트 외부, 신규) |
| `reports/STEP6_RAG_RUNTIME_VALIDATION.md` | 본 보고서 (신규) |
| `reports/step5_6_validation/rag_probe.py`, `rag_probe_result.json`, `rag_probe.log` | 읽기 전용 검증 스크립트·결과 (신규) |

코드·설정·데이터·테스트·기준 파일 변경: **없음**. 실제 OpenAI API 호출: **0회**.

## 9. Core SHA256 / 데이터 무결성

- Frozen Core: 작업 종료 후 `sha256sum -c` **9/9 OK**.
- `data_manifest.json`: **35/35** 일치. `load_resources(verify_hashes=True)` 런타임 해시·parity PASS.
- 복원 평가 자료 243개: 테스트·검증 후 **243/243** 동일.

## 10. 미해결 문제

1. GPU 환경 부재로 평가 구성(fp16) 그대로의 실행·엄격 회귀 PASS는 확인 불가.
2. 메모리(약 6GB)·로딩 시간 — 배포 환경 적합성 미검증(STEP 9).
3. Streamlit UI 경로(`rt.ready` → 검색·검사 버튼 활성)는 이번에 실행하지 않음 → STEP 8에서 확인 필요.
4. 실제 LLM 생성·Guardrail 통합은 STEP 7 범위(API 키 없음).
5. 검색 품질은 30건 라벨 범위의 재현일 뿐, 임상적 근거 적합성은 미검증.

## 11. 다음 단계 진행 가능 여부

- 로컬 Windows(CPU)에서 평가 구성의 Hybrid RAG가 실제 모델로 실행되고 평가 당시 결과를 재현 → **STEP 7(실제 LLM 검증) 진행 가능**.
- Streamlit 통합은 아직 실행 검증하지 않았으므로 READY로 표기하지 않는다.

```
STEP5_STATUS                = INCOMPLETE
STEP6_STATUS                = PASS
CORE_INTEGRITY              = PASS
DATA_INTEGRITY              = PASS
RAG_RUNTIME_READY           = YES   (로컬 Windows CPU 기준; 배포 환경 미검증)
STREAMLIT_INTEGRATION_READY = NO    (UI 경로 미실행, LLM 키 없음 — STEP 8 대상)
```

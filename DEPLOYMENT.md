# MEDGUARD AI — 배포 준비 가이드 (STEP 9-1)

> **현재 운영 방향 (STEP 10-2, 2026-10-27): 공개 배포를 보류합니다.** 프로젝트는 GitHub 비공개 저장소와 로컬 Streamlit 데모로 유지합니다.
> 이 문서는 향후 배포에 대비해 보존한 참고 절차이며, 지금 실행할 작업이 아닙니다. 로컬 실행 방법은 [README §8](README.md#8-실행-방법)을 따르세요.
> Linux(WSL2) 실측값(콜드 스타트 74.9초, 서버 RSS 약 4.98 GiB, 권장 RAM 8GB)은 `reports/STEP9_3_DEPLOYMENT_ARCHITECTURE.md`에 있습니다. 아래 §1·§6의 메모리·시작 시간은 STEP 8 Windows 측정값입니다.

연구·포트폴리오용 데모이며 임상 의사결정 도구가 아닙니다(`CLINICAL_VALIDATION_STATUS = NOT_VALIDATED`).
근거와 측정값은 `reports/STEP9_1_DEPLOYMENT_READINESS.md` 를 참고하세요. 이 문서의 클라우드 관련 내용은 **실제 클라우드에서 검증되지 않았습니다.**

## 1. 실행에 필요한 것 (실제 실행 추적으로 확인)

| 구분 | 내용 |
|---|---|
| 진입점 | `streamlit run app.py` (→ `ui_integration/app_v2.py`) |
| 코드 | `app.py`, `app/` (styles 포함), `src/dur_safety/` (Frozen Core 9개), `ui_integration/` |
| 런타임에 읽는 비코드 파일 | `notebooks/15_ingredient_duplicate_candidates_prototype.ipynb`(코드 셀을 실행), `production_baseline.json`, `.streamlit/config.toml`, `reports/ingredient_coverage_audit/run_20261012_184823/`, `reports/ui_coverage_audit/run_20261011_152938/` |
| 데이터 | `data/processed/` 아래 13개, 약 670MB (`app.py` 의 `REQUIRED_FILES`, 해시는 `data_manifest.json`) — **Git 에서 제외됨** |
| 모델 | `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`, 약 2.3GB (Hugging Face 캐시) — **Git 에 넣지 않음** |
| 비밀값 | `OPENAI_API_KEY` (없으면 LLM 설명만 비활성) |
| 메모리 | 로컬 측정 커밋 약 6.6GB / 작업 집합 약 4.6GB (STEP 8, Windows CPU) |

## 2. 설치

```bash
python -m venv .venv
# Windows (개발·검증 환경)
.venv\Scripts\activate && pip install -r requirements.txt
# Linux CPU 서버 (torch CUDA 패키지 제외)
source .venv/bin/activate && pip install -r requirements-server-cpu.txt
```
Python 3.12 권장(로컬 검증 3.12.10). 3.13 은 Linux wheel 해석만 확인했습니다.

## 3. 데이터 준비 (저장소에 포함하지 않음)

1. 사용자가 보관 중인 원본 사본에서 `data_manifest.json` 에 적힌 `data/processed/...` 파일 29개(앱 필수 13개 포함)를 경로 그대로 배치합니다(원본을 가공하지 않음). 코드상 앱 실행에 쓰이는 것은 `app.py` `REQUIRED_FILES` 의 13개이며, 13개만 두면 아래 `--verify` 는 나머지 16개를 MISSING 으로 표시합니다(13개만으로 앱을 실행해 보지는 않았습니다).
2. 확인: `python tools/fetch_runtime_data.py --verify` → 모두 `OK` 여야 합니다(앱도 시작 시 SHA256 을 검사해 불일치하면 실행을 멈춥니다).
3. 외부 저장소를 쓰는 경우에만: `MEDGUARD_DATA_BASE_URL=<비공개 주소> python tools/fetch_runtime_data.py --fetch` (해시 불일치 파일은 버림).
   **공공데이터 재배포 조건이 NOT_VERIFIED 이므로, 공개 위치에 데이터를 올리지 마세요.**

## 4. 모델 준비 (최초 1회, 서버의 영구 디스크에)

```bash
export HF_HOME=/영구/디스크/hf-cache        # 컨테이너 재시작 시 재다운로드를 막으려면 영구 경로 지정
python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-m3', revision='5617a9f61b028005a4858fdac845db406aefb181', allow_patterns=['modules.json','config_sentence_transformers.json','sentence_bert_config.json','config.json','1_Pooling/config.json','pytorch_model.bin','tokenizer.json','tokenizer_config.json','special_tokens_map.json','sentencepiece.bpe.model'])"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # 받은 뒤에는 오프라인으로 고정
```
- 다른 모델·revision 을 쓰지 마세요. `RETRIEVAL_DENSE_MODEL` / `RETRIEVAL_DENSE_REVISION` 은 설정하지 않습니다(불일치 시 앱 시작 중단).
- 모델이 없고 오프라인 모드면 앱은 BM25 로 축소하지 않고 시작을 거부합니다(fail-closed, STEP 9-1 확인).

## 5. 비밀값

- 로컬: `.streamlit/secrets.toml` (`.streamlit/secrets.toml.example` 형식) 또는 환경변수 `OPENAI_API_KEY`. `.env` 는 자동으로 읽히지 않습니다.
- Streamlit Cloud: 앱 설정 > Secrets. `app.py` 가 Secrets 를 환경변수로 옮기고 값을 출력하지 않습니다.
- 공개 데모에서는 LLM 호출 비용이 발생합니다(finding 1개당 1회). 호출 한도·사용량 알림을 OpenAI 계정에서 설정하세요.

## 6. 실행 전 점검과 실행

```bash
python tools/deploy_preflight.py      # FAIL 0 이어야 함 (읽기 전용, 키 값 미출력)
streamlit run app.py --server.port 8501
```
첫 접속 시 데이터·모델 로딩에 로컬 기준 약 90–100초 걸립니다(이후 세션은 수 초).

## 7. 하지 말 것

- 검색 모델 교체, Hybrid → BM25-only 축소, `src/dur_safety/` 수정 (Frozen Core, `FROZEN_SHA256SUMS.txt`)
- `data/` 나 모델 파일을 공개 저장소·공개 URL 에 업로드
- `.streamlit/secrets.toml`, 실제 키가 담긴 파일 커밋

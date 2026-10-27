# STEP 9-3 — 배포 환경 및 데이터·모델 운영 방식 검토

- 작성일: 2026-10-24 / 대상: MEDGUARD AI (연구·교육용 프로토타입, **임상 검증 아님**)
- 선행: STEP 8 (CONDITIONAL_PASS), STEP 9-1 (CONDITIONAL_PASS), STEP 9-2 (CONDITIONAL_PASS, 커밋 `23c5376`, remote `medguard-ai` 확인)
- 산출물: `reports/step9_3_validation/`
- 표기
  - **실측**: 이번 단계에서 직접 실행해 측정함
  - **기존**: 이전 보고서 수치(출처 표기)
  - **코드**: 소스에서 확인한 사실
  - **추정**: 근거를 밝힌 판단
  - **미확인**: 확인하지 못한 외부 사양·가격
- 이번 단계에서 하지 않은 것: 코드·설정·데이터·모델·검색 방식 변경, 유료 서비스 사용, LLM 호출, GitHub push, 공개 배포

## 0. 판정

```
STEP9_3_STATUS = CONDITIONAL_READY
```

**근거**
- GitHub에 올린 커밋을 **Linux(Ubuntu 24.04, WSL2, RAM 7.6 GB 한도)에 그대로 clone**했다. `requirements-server-cpu.txt`만으로 설치했고 코드·데이터·모델은 변경 없이 썼다. 이 상태로 Streamlit 서버가 실행되었다(실측).
  - Frozen Core SHA 9/9
  - manifest 35/35
  - preflight FAIL 0
  - 콜드 스타트 74.9 s
  - 검사 2.6 s
  - 서버 RSS 4.98 GiB
- 2코어로 제한해도 요청 처리가 정상이었다(실측).
- 따라서 **기존 Screening·Hybrid RAG·LLM·Guardrail 구조를 바꾸지 않고 배포할 수 있다.**

**조건(미충족)**
1. RAM 8 GB 이상 호스트 확보
2. 데이터(638 MB)를 둘 비공개 위치 결정
3. 의약품 제품 허가정보(data.go.kr 15095677)의 이용 조건 확인
4. 모델 사전 다운로드·캐시 경로 설정
5. API 키·접근 제어 설정
6. 공개 시 STEP 8 F1 정책 결정

## 1. 현재 시스템 구조 (코드 기준)

| # | 항목 | 실제 구현 (근거 파일) |
|---|---|---|
| 1 | Streamlit 진입점 | `streamlit run app.py` → 필수 파일 16개 확인, Secrets→환경변수 → `runpy` `ui_integration/app_v2.py` |
| 2 | Screening 초기화 | `@st.cache_resource get_runtime()` → `ui_runtime.load_runtime()` → `resources.load_resources(verify_hashes=True)` → `screening.init_screening`(DUR parquet 4개 로드) |
| 3 | RAG 인덱스·데이터 | `retrieval.init_retrieval`: `approval_chunks` 메타 컬럼, `unique_text_index`, `text_hash_mapping`, DUR lookup 4개 로드 → **BM25 행렬을 시작할 때마다 `CountVectorizer.fit_transform`으로 새로 생성**(36,988 텍스트) → `unique_text_embeddings.npy`는 `mmap_mode="r"` |
| 4 | 임베딩 모델 | `SentenceTransformer("BAAI/bge-m3", revision=5617a9f6…, device=cpu)`, CPU면 fp32. 시작 시 1회, 프로세스 공유 |
| 5 | LLM 호출 | finding마다 `generation.call_llm` → OpenAI Responses API(`gpt-5.4-mini`, `store=False`, timeout 120 s, 재시도 2). 키 없으면 네트워크 없이 `LLM_UNAVAILABLE` |
| 6 | Guardrail | Core `generation.validate_output`(스키마·인용·지시어 패턴) → `app/ui_policy.decide_display_mode`(+ STEP 7-R `unsafe_text_reasons`). 순수 Python 규칙, 추가 자원 거의 없음 |
| 7 | 시작 시 메모리 적재 | 위 2–4 + **성분 후보 엔진**(`@st.cache_resource get_integration()` → `IA.load_engine`): `screening.py`를 다시 `exec`해 **DUR 테이블 사본을 한 번 더 로드**하고, 노트북 15 코드로 `drug_approval_items.parquet`(392.5 MB) 로드 |
| 8 | 요청 시 추가 메모리 | 질의 임베딩 1회(bge-m3 forward) + BM25·dense 점수 계산. 첫 요청에서 모델 가중치 mmap 페이지가 올라옴(file-backed 약 1.15 GiB, §2) |
| 9 | 초기 실행 시간 | 첫 브라우저 접속 시 위 로딩 수행(`st.cache_resource`) — §2 |
| 10 | 외부 의존 | 데이터 13개(Git 제외), HF 모델(캐시), `OPENAI_API_KEY`(선택). 그 외 외부 API·DB 없음 |

## 2. 실제 자원 사용량

측정 스크립트: `step9_3_validation/resource_profile.py`
- 앱과 같은 공개 함수를 같은 순서로 호출한다(`app.py`의 환경변수 설정 재현).
- 키를 제거해 LLM은 호출하지 않는다.
- 메모리 측정 방법: Windows는 `GetProcessMemoryInfo`, Linux는 `/proc/self/status`. 단위는 GiB.

### 2.1 단계별 메모리·시간 (실측)

| 단계 | Windows 11 (16코어) | Linux WSL2 (16코어) | Linux, **2코어 제한** |
|---|---|---|---|
| import | 6.1 s / RSS 0.17 | 4.3 s / 0.20 | 6.1 s / 0.20 |
| `load_resources` (해시 검증 + Screening + BM25 + bge-m3) | 40.8 s* / RSS 2.83, 커밋 5.96 | 48.6 s / RSS 2.94 (익명 2.78) | 44.2 s / 2.83 |
| 성분 엔진 (DUR 사본 + 허가정보) | 14.9 s / RSS 3.71, 커밋 6.84 | 22.3 s / RSS 3.79 (익명 3.63) | 17.3 s / 3.65 |
| 첫 요청 후 | RSS 4.86, 커밋 6.88 | RSS 4.95 (익명 3.64 + 파일 1.31) | 4.80 |
| 요청 6개 + 동시 4·8개 후 **최대** | RSS 4.89, **커밋 6.92** | **RSS 4.99** (익명 3.67 + 파일 1.32) | 4.85 |

\* 디스크 캐시가 따뜻한 상태. 같은 PC에서 디스크 캐시가 차가운 첫 실행은 105.6 s였다(실측, 이번 단계 첫 시도).

**모델만 단독 로딩 (실측)**

| 측정 | Windows | Linux |
|---|---|---|
| `import sentence_transformers` | 29.6 s | 10.4 s |
| bge-m3 로딩 | 5.9 s, 커밋 3.77 GiB | 4.0 s, RSS 0.81 GiB(익명 0.66) |
| 첫 질의 인코딩 후 | — | RSS 1.95 GiB(파일 1.29) |

**해석**
- Linux에서 실제 상주 메모리는 **약 5.0 GiB**이고, 그중 1.3 GiB는 파일 매핑(모델 가중치·임베딩)이다.
- Windows의 "커밋 6.9 GB"는 Windows의 메모리 예약 회계 방식 때문에 크게 잡힌 값이다. Linux 사양 산정에는 RSS를 쓴다.
- 성분 엔진이 **약 0.85 GiB**를 추가한다. DUR 테이블 중복 로드 + 허가정보 392.5 MB.

### 2.2 Streamlit 서버 실측 (Linux, 실제 clone)

| 항목 | 값 |
|---|---|
| 설치 | `pip install -r requirements-server-cpu.txt` **250 s**, venv **1.7 GB**, `torch 2.11.0+cpu`, CUDA 패키지 **0**, `pip check` 정상 |
| 무결성 | clone 상태에서 Frozen Core 9/9, `deploy_preflight.py` FAIL 0 (manifest 35/35, 모델 캐시 확인) |
| HTTP 기동 | 6 s 안에 `/_stcore/health` 200 (Windows 브라우저에서 접속 확인) |
| **콜드 스타트** (첫 접속 → 사용 가능) | **74.9 s** (Windows 기존 측정 88.7–102.0 s) |
| 검사 1회 (CE001, 키 없음) | **2.6 s**, 병용금기 1건 표시 |
| 서버 프로세스 메모리 | **RSS 4.98 GiB** (VmHWM 동일, 익명 3.67 + 파일 1.31) |
| 서버 로그 | 오류 0 (STEP 8의 `fileWatcherType="none"` 효과 유지) |

### 2.3 요청 처리 시간 (LLM 제외, 실측)

| 조건 | Windows 16코어 | Linux 16코어 | Linux 2코어 |
|---|---|---|---|
| 순차 1건 (Core 경로) | 0.11–0.69 s | 0.20–1.13 s | 0.18–0.43 s |
| 동시 4건 전체 | 0.9 s | 2.4 s | **1.4 s** |
| 동시 8건 전체 | 2.2 s | 5.2 s | **2.8 s** |
| 동시 요청 시 메모리 증가 | +0.02 GiB | +0.03 GiB | +0.03 GiB |

- 2코어가 16코어보다 동시 처리에서 빠르다. 스레드 과다 경쟁(torch 8스레드 × 요청 8개)이 줄었기 때문이다.
- LLM 응답 시간은 기존 측정값(STEP 8 ledger)으로 finding 1개당 **3.8–9.6 s**다. **사용자 체감 시간은 LLM이 결정한다.**
- finding이 여러 개면 순차로 호출하므로 시간이 비례해 늘어난다(코드).

### 2.4 데이터·모델 크기 (실측, STEP 9-1 확인값과 동일)

| 대상 | 크기 |
|---|---|
| 런타임 데이터 13개 | 638.1 MB (최대 `drug_approval_items` 392.5 MB, `approval_chunks` 129.6 MB, `.npy` 75.8 MB) |
| `data/` 전체(개발용 포함) | 642 MB |
| bge-m3 (필요 파일만) | 2.27 GB (`pytorch_model.bin` 2,271 MB) |
| Linux venv | 1.7 GB |
| 디스크 합계(코드 제외) | 약 4.6 GB |

### 2.5 Windows와 Linux 차이

| 항목 | 결과 |
|---|---|
| 동작 | 같음. 같은 커밋을 Linux에서 clone·설치해 실행했고 화면 결과(병용금기 1건)가 같다 |
| 메모리 지표 | Windows 커밋 6.9 GB / Linux RSS 5.0 GiB. 서버 사양은 Linux RSS 기준 |
| 로딩 속도 | Linux import·모델 로딩이 더 빠름(import 10.4 s vs 29.6 s) |
| 콜드 스타트 | Linux 74.9 s, Windows 88.7–102 s |
| 줄바꿈·해시 | `.gitattributes -text` 덕분에 Linux clone에서도 Frozen Core 9/9 |
| 설치 | Linux는 `requirements-server-cpu.txt` 필수(PyPI 기본 torch는 CUDA 13 패키지 7종 동반) |
| 미측정 | 실제 클라우드 VM의 디스크 속도·네트워크·CPU 세대 차이. 모델 다운로드 시간(이번에는 Windows 캐시를 복사, 28 s) |

## 3. 배포 병목 분석

| 순위 | 병목 | 근거 | 영향 |
|---|---|---|---|
| 1 | **RAM 약 5 GiB 상주** | 실측 §2 | 무료/소형 호스트(1–4 GB) 불가. 8 GB 권장(OS·Streamlit·여유 포함, 추정) |
| 2 | **콜드 스타트 75–105 s** | 실측 | 재시작·휴면 후 첫 사용자가 오래 기다림. 상시 실행 호스트가 유리 |
| 3 | **모델 2.27 GB 확보** | 실측 크기 | 임시 디스크 호스트는 재시작마다 다운로드(시간·실패 가능성). 영구 디스크·사전 다운로드 필요 |
| 4 | LLM 지연·비용 | 기존 3.8–9.6 s/finding | 체감 지연의 대부분. 공개 시 비용·남용 제어 필요 |
| 5 | 동시성 | 실측: 8건 동시 2.8–5.2 s(LLM 제외), 메모리 증가 미미 | 데모 규모(수 명)는 문제없음(추정). 수십 명 동시 + LLM이면 OpenAI 호출 대기·비용이 먼저 한계 |
| 6 | 데이터 배치 | 638 MB, GitHub 100 MB 초과 2개 | 저장소로 전달 불가 → 별도 배치 필요 |
| 7 | 시작 시 BM25 재생성·DUR 중복 로드 | 코드 | 각각 시작 시간·약 0.85 GiB 원인. **이번에는 변경하지 않음**(개선 후보, §9) |

## 4. 데이터 저장 방식 비교

이용 조건 사실관계:

| 데이터 | 상태 |
|---|---|
| 식약처 DUR, e약은요 | **사용자가 이용허락범위를 확인했다고 알려 옴**. 조건 내용(출처 표시·변경 허용·재배포 범위)은 받지 못해 이 보고서에서 확인·인용하지 않음 |
| 의약품 제품 허가정보 (data.go.kr 15095677) + 첨부문서 기반 chunk | **미확인**. 가장 큰 파일 2개(`drug_approval_items`, `approval_chunks`)가 여기에 해당 |
| 공통 | 서비스 화면에 원문을 표시하므로 '서비스 내 활용'과 '출처 표시' 조건이 필요. 비공개 저장소·비공개 서버 보관은 공개 재배포가 아님(추정). 다만 공개 저장소나 공개 URL은 조건 확인 전 금지 |

| 기준 | A. 서버 내부 저장 | B. 외부 Object Storage (비공개 버킷) | C. Git LFS | D. 앱 시작 시 외부에서 다운로드 |
|---|---|---|---|---|
| 구현 난이도 | **낮음**: 1회 업로드(scp 등) 후 `fetch_runtime_data.py --verify` | 중간: 버킷·권한 설정 | 중간: LFS 설치·추적 설정, 서버에서 `git lfs pull` | 중간: `fetch_runtime_data.py --fetch`가 이미 있으나 **인증 헤더 미지원**(공개 URL 또는 서명 URL 필요) |
| 운영 비용 | VM 디스크에 포함 | 저장·전송 요금(미확인) | GitHub LFS 저장·대역폭 한도(미확인) | B와 같음 + 매 시작 전송 |
| 무결성 | SHA256 manifest 검증 + 앱 시작 시 재검증 | 같음(다운로드 후 해시 불일치 폐기) | Git 객체 해시 + 앱 검증 | 같음 |
| 보안 | 서버 접근 통제만 관리 | 버킷 권한·서명 URL 관리 | 저장소 접근 권한과 같음 | 다운로드 URL 노출 위험 |
| 초기 로딩 | 추가 없음 | 최초 1회 다운로드 | clone 시 1회 | **매 시작마다 638 MB 전송** |
| GitHub 호환 | 영향 없음(`data/` 제외 유지) | 영향 없음 | `.gitignore`의 `data/` 해제 + `.gitattributes` LFS 규칙 필요 | 영향 없음 |
| 코드 변경 | **없음** | 없음(서명 URL 사용 시) | 없음 | 없음(공개 URL) / 인증이 필요하면 도구 수정 |
| 이용 조건 위험 | 낮음(비공개 보관) | 낮음(비공개) | 중간(제3자 서비스에 사본) | 버킷이 공개면 높음 |
| **평가** | **권장(VM과 함께)** | 대안(여러 서버·재구축 시) | 보류(한도 미확인) | 비권장(임시 디스크 호스트에서만 B와 함께) |

## 5. 임베딩 모델 운영 방식 비교

기준: 평가된 RAG는 bge-m3 @ `5617a9f6`와 사전 계산 임베딩(`.npy`, 36,988×1024)의 조합이다. 모델이 바뀌면 질의 임베딩과 문서 임베딩 공간이 어긋난다.

| 기준 | A. 서버에서 직접 로딩 (영구 캐시) | B. 서버 시작 시 다운로드 | C. 별도 임베딩 서비스 | D. 경량 모델 전환 |
|---|---|---|---|---|
| 메모리 | 모델 몫 약 0.66 GiB 익명 + 1.3 GiB 파일 매핑(실측) | A와 같음 | 앱 서버에서 그만큼 감소, 서비스 측 별도 필요 | 감소(크기 미측정) |
| 속도 | 로딩 4.0 s(Linux), 질의 인코딩 수백 ms 이하(실측 범위) | + 2.27 GB 다운로드(미측정, 네트워크 의존) | 질의마다 네트워크 왕복 추가 | 빨라질 수 있음(미측정) |
| 비용 | 디스크 약 2.3 GB | 전송량(미확인) | 서비스 요금(미확인) | 재평가 작업 비용 |
| 코드 변경 | **없음** | 없음(`HF_HUB_OFFLINE` 미설정) | **필요**(`retrieval.py`는 Frozen Core, 로컬 `SentenceTransformer` 호출) | **필요**(모델·revision 3중 검증, 임베딩 재계산) |
| RAG 성능 유지 | **유지**(STEP 6: 06-A Top-5 30/30) | 유지(같은 revision) | 정밀도·런타임이 다르면 점수 차이(GPU fp16 vs CPU fp32 차이가 이미 0.0007 수준으로 기록됨) → 재검증 필요 | **유지 보장 없음** — 36,988개 재임베딩 + 06-A/06-B 재평가 필요 |
| 승인 필요 | 아니오 | 아니오 | **예** | **예**(자동 변경 금지) |
| **평가** | **권장** | A의 최초 준비 단계로만 사용 | 비권장 | 비권장(현 단계) |

## 6. 호스팅 플랫폼 비교

**중요**: 이번 단계에서 플랫폼의 **최신 리소스 한도·가격을 공식 문서로 확인하지 못했다**(외부 문서 조회가 조직 정책으로 거부됨, STEP 9-1). 아래 "사전 지식" 칸은 Claude가 과거에 알고 있던 정보이며 **공식 사양이 아니다. 변경되었을 수 있다.** 확정 판단 전에 각 공식 문서에서 확인해야 한다.

필요 사양(실측 기반 산정)
- RAM: 8 GB 이상(상주 5.0 GiB + OS·여유)
- vCPU: 2 이상(2코어 실측 정상)
- 디스크: 10 GB 이상(데이터 0.64 + 모델 2.3 + venv 1.7 + 여유)
- 상시 실행 권장(콜드 스타트 75–105 s)

| 기준 | 1. Streamlit Community Cloud | 2. Hugging Face Spaces (Streamlit/Docker) | 3. 클라우드 VM (Linux) | 4. 기타: 컨테이너 PaaS (Render·Railway·Fly.io 등) |
|---|---|---|---|---|
| 필요 RAM 충족 | 사전 지식: 앱당 메모리가 1 GB 안팎으로 알려졌음(**미확인**) → 5 GiB 상주와 맞지 않을 가능성 높음 | 사전 지식: 무료 CPU 하드웨어가 2 vCPU·16 GB RAM으로 알려졌음(**미확인**) → 확인되면 충족 | 사양 선택 가능 → **충족**(8 GB 선택) | 요금제별(미확인). 8 GB급은 유료일 가능성(추정) |
| CPU | 미확인 | 사전 지식 2 vCPU(미확인) | 선택(2 vCPU 충분, 실측) | 요금제별 |
| 저장 공간 | 저장소 크기 기반, 영구 디스크 없음(사전 지식, 미확인) | 기본 디스크는 재시작 시 초기화, 영구 스토리지는 유료 옵션(사전 지식, 미확인) | **영구 디스크** 선택 | 영구 볼륨 옵션(미확인) |
| 모델 다운로드 | 가능하나 재부팅마다 반복(추정) | HF Hub 같은 인프라라 빠를 가능성(추정), 재시작마다 반복 | 1회 다운로드 후 캐시 영구 | 볼륨 사용 시 1회 |
| 비공개 GitHub 연동 | 지원으로 알려짐(미확인) | Space는 자체 Git 저장소. GitHub 연동은 Actions 동기화 방식(미확인) | 서버에서 deploy key·토큰으로 clone(직접 설정) | 대부분 GitHub 연동 지원(미확인) |
| API 키 관리 | Secrets → `app.py` 브리지 지원(코드 확인) | Space Secrets → 환경변수(코드는 환경변수 지원) | 환경변수·systemd EnvironmentFile | 환경변수 |
| 데이터 배치 | 저장소 불가(100 MB 초과) → 매 시작 다운로드(D) | Space 저장소(LFS) 업로드 또는 다운로드 — **허가정보 이용 조건 확인 필요** | **서버 내부 저장(A)** | 볼륨 또는 다운로드 |
| 월 예상 비용 | 무료(조건 미확인) | 무료 CPU면 0(미확인), 영구 스토리지·업그레이드는 유료 | **미확인** — 8 GB/2 vCPU 인스턴스 시간당 요금 × 730 h + 디스크 | 미확인 |
| 설정 난이도 | 낮음 | 낮음–중간 | 중간(OS, 프로세스 관리, HTTPS 역방향 프록시) | 중간 |
| 안정성 | 메모리 초과로 중단될 위험(추정) | 비활성 시 휴면 → 콜드 스타트 75 s+ (사전 지식, 미확인) | 상시 실행, 직접 관리 | 요금제별 |
| 포트폴리오 시연 | 링크 공유 쉬움, 실행 실패 위험 | 링크 공유 쉬움, 비공개 Space 가능(미확인) | 안정적, 접근 제한 직접 설정 | 보통 |
| 기존 기능 보존 | 메모리 부족 시 축소 유혹 → **금지 사항 위반 위험** | 보존 가능(사양 확인 시) | **보존(실측된 Linux 구성과 같음)** | 보존 가능(사양 확보 시) |
| **평가** | **비권장** | **대안**(사양·이용 조건 확인 후) | **권장** | 보류 |

비용에는 OpenAI 사용료가 별도로 붙는다. 기존 측정(STEP 8)으로 finding 1개당 입력 약 2.4–5.1k / 출력 약 0.2–0.9k 토큰이고, 단가는 미확인이다. 공개 데모라면 사용량 한도 설정이 필수다.

## 7. 최종 추천 아키텍처

**권장: 단일 Linux VM(8 GB RAM / 2 vCPU 이상 / 영구 디스크 20 GB 이상) + 서버 내부 데이터 저장(A) + 모델 영구 캐시(A)**

```
[GitHub 비공개 저장소 medguard-ai]
     │ git clone (deploy key, 읽기 전용)          ← 코드·설정·문서만 (data/ 제외)
     ▼
[Linux VM]  python 3.12 venv ← pip install -r requirements-server-cpu.txt   (torch +cpu, 실측 250 s)
     │
     ├─ data/processed/ 13개 (638 MB) ← 사용자가 비공개 경로로 1회 업로드 → fetch_runtime_data.py --verify (SHA256 35/35)
     ├─ HF_HOME=/srv/hf-cache ← bge-m3 @5617a9f6 1회 다운로드 → HF_HUB_OFFLINE=1
     ├─ OPENAI_API_KEY ← 환경변수 파일(권한 600) 또는 .streamlit/secrets.toml (Git 제외)
     ├─ tools/deploy_preflight.py → FAIL 0 확인
     ▼
[streamlit run app.py]  (systemd 서비스, 상시 실행, 127.0.0.1:8501)
     │  시작 시 1회: 해시 검증 → Screening 테이블 → BM25 → bge-m3 → 성분 엔진  (약 75 s, RSS 약 5.0 GiB)
     ▼
[요청]  입력 검증 → Structured Screening(판정 기준) → finding별 Hybrid RAG(BM25+dense+prior, top 5)
        → LLM 설명(gpt-5.4-mini) → validate_output + ui_policy Guardrail → 표시/보류
     ▼
[역방향 프록시(HTTPS) + 접근 제한(인증 또는 IP 허용)] → 사용자 브라우저
```

- 선택 이유
  - 이번에 **실제로 실행해 검증한 구성**(Linux, 같은 커밋, 같은 데이터·모델)과 같다.
  - 의료 판단·검색 구조를 하나도 바꾸지 않는다.
  - 데이터를 공개 위치에 두지 않는다.
  - 콜드 스타트를 1회로 줄인다(상시 실행).
- 비용·공급자는 미확인이다. 사용자가 공급자 가격표에서 8 GB 인스턴스 요금을 확인해야 한다.
- 대안: **Hugging Face Spaces (비공개 Space)**. 무료 CPU 하드웨어가 RAM 8 GB 이상임을 공식 문서로 확인한 경우에만 시도한다. 데이터를 Space에 올려야 하므로 **허가정보 이용 조건 확인이 먼저**다. 재시작마다 모델 다운로드·콜드 스타트가 반복된다(추정).

## 8. 예상 비용 및 운영상 위험

| 구분 | 내용 | 수준 |
|---|---|---|
| 서버 비용 | 8 GB/2 vCPU VM 월 비용 **미확인** | 확인 필요 |
| LLM 비용 | finding당 1회 호출. 단가 미확인. 공개 시 반복 사용·남용 위험 | 중간 — OpenAI 사용량 한도 설정, 접근 제한 |
| 메모리 여유 | 상주 5.0 GiB / 8 GB → 여유 약 3 GB(추정). 다른 프로세스와 같이 쓰지 말 것 | 낮음–중간 |
| 재시작 | 75–105 s 사용 불가(실측) | 낮음(상시 실행) |
| 데이터 이용 조건 | 허가정보 미확인, DUR·e약은요는 사용자 확인(내용 미제공) | **높음(공개 시)** |
| 의료 정보 정확성 | STEP 8 F1(근거 모순 설명 표시) 미결 | **높음(공개 시)** |
| 보안 | 키 노출, 무단 접근, 데이터 유출 | 중간 — 키 파일 권한, HTTPS, 인증 |
| 업데이트 | 코드 변경 시 Frozen Core·manifest 재검증 필요 | 낮음(`deploy_preflight.py`) |
| 모니터링 | 현재 없음 | 낮음 — systemd 재시작 정책, 로그 확인 |

## 9. 기존 기능 변경 필요 여부

**배포를 위해 꼭 변경해야 하는 기능: 없음.** 권장 구조는 현재 코드·데이터·모델·검색·Guardrail을 그대로 쓴다(Linux에서 실측 확인).

선택적 개선 후보(**이번에 적용하지 않음, 적용하려면 사용자 승인과 재검증 필요**)

| 후보 | 기대 효과 | 위험 |
|---|---|---|
| 성분 엔진이 DUR 테이블을 중복 로드하지 않도록 정리(`ui_integration/`) | 메모리 일부 절감(성분 엔진 몫 약 0.85 GiB 중 일부) | 통합 엔진 동작 재검증 필요 |
| BM25 행렬 캐시 파일화 | 시작 시간 단축 | Frozen Core 변경 → 승인 필수 |
| 경량 모델·외부 임베딩 | 메모리 절감 | RAG 품질 재평가 필수, 기본 비권장 |

## 10. 사용자가 직접 진행해야 할 작업

1. **호스팅 결정**: 클라우드 VM 공급자에서 8 GB RAM / 2 vCPU / 20 GB 디스크 Linux 인스턴스 가격 확인 후 선택. HF Spaces를 고려하면 공식 문서에서 무료 CPU 사양·휴면 정책·비공개 Space 지원 확인.
2. **데이터 이용 조건**
   - 의약품 제품 허가정보(data.go.kr 15095677)의 이용허락범위를 확인한다.
   - DUR·e약은요 확인 내용(출처 표시 문구, 변경·재배포 조건)을 `DATA_STRATEGY.md` 또는 별도 문서에 기록한다.
3. **데이터 사본 보관 위치**: 현재 PC의 `data/` 원본을 백업하고, 서버 업로드 방법(scp 등)을 정한다.
4. **비밀값**
   - OpenAI 사용량 한도를 설정한다.
   - 서버용 API 키는 가능하면 별도 키로 발급한다.
5. **공개 범위 결정**: 비공개(인증·IP 제한) 데모로 시작할지, STEP 8 F1 정책(공개 시 LLM 설명 끄기 등) 결정.
6. (선택) WSL 측정 환경 정리. `wsl -e rm -rf ~/medguard_step9_3`로 삭제하며, venv 1.7 GB, 모델 2.2 GB, 데이터 복사본 642 MB가 정리된다. STEP 9-4 리허설에 다시 쓰려면 유지한다.

## 11. 다음 단계 실행 계획 (STEP 9-4 제안)

| 순서 | 작업 | 검증 |
|---|---|---|
| 1 | VM 생성(사용자), SSH 접속 정보 준비 | — |
| 2 | 서버 기본 설정: Python 3.12, 사용자 계정, 방화벽(SSH·HTTPS만) | — |
| 3 | `git clone`(deploy key 읽기 전용) → `pip install -r requirements-server-cpu.txt` | `pip check` |
| 4 | 데이터 13개 업로드 → `python tools/fetch_runtime_data.py --verify` | 35/35 |
| 5 | `HF_HOME` 지정 후 bge-m3 @5617a9f6 1회 다운로드 → `HF_HUB_OFFLINE=1` | preflight 모델 캐시 OK |
| 6 | `OPENAI_API_KEY` 설정(권한 600) | preflight 키 OK(값 미출력) |
| 7 | `sha256sum -c src/dur_safety/FROZEN_SHA256SUMS.txt`, `tools/deploy_preflight.py` | 9/9, FAIL 0 |
| 8 | systemd 서비스로 `streamlit run app.py` 상시 실행, 127.0.0.1 바인딩 | 재부팅 후 자동 시작 |
| 9 | 역방향 프록시 + HTTPS + 접근 제한 | 외부에서 인증 후 접속 |
| 10 | 스모크 테스트: STEP 8 수동 항목 M1–M4(유료 호출 1–3회, 사전 승인) | 화면·판정 확인 |
| 11 | 메모리·로그 모니터링 1주 | RSS·재시작 기록 |

## 부록 A. 실행 명령과 산출물

```bash
# Windows 프로파일 (키 없음)
env -u OPENAI_API_KEY HF_HUB_OFFLINE=1 python -X utf8 reports/step9_3_validation/resource_profile.py . reports/step9_3_validation/profile_windows_full.json
python -X utf8 reports/step9_3_validation/resource_profile.py . reports/step9_3_validation/profile_windows_model.json --model-only
# Linux (WSL2 Ubuntu 24.04, ~/medguard_step9_3): 커밋 clone → venv(--without-pip + get-pip) → requirements-server-cpu.txt
git clone <로컬 저장소> repo && venv/bin/python -m pip install -r repo/requirements-server-cpu.txt
cp -r <data> repo/data && cp -r <HF 캐시의 models--BAAI--bge-m3> $HF_HOME/hub/
HF_HOME=... HF_HUB_OFFLINE=1 venv/bin/python repo/tools/deploy_preflight.py
venv/bin/python -X utf8 resource_profile.py repo /tmp/profile_linux_full.json            # 16코어
taskset -c 0,1 env OMP_NUM_THREADS=2 venv/bin/python -X utf8 resource_profile.py repo /tmp/profile_linux_2cpu.json   # 2코어
venv/bin/streamlit run app.py --server.port 8510   # + Windows Playwright 로 콜드 스타트·검사, /proc/<pid>/status 로 RSS
```

| 파일 | 내용 |
|---|---|
| `resource_profile.py` | 단계별 메모리·시간 측정(읽기 전용, 키 필요 없음) |
| `profile_windows_full.json` / `_model.json` | Windows 실측 |
| `profile_linux_full.json` / `_model.json` / `_2cpu.json` | Linux 실측 |
| `streamlit_linux_server.txt` | Linux 서버 로그(URL 줄 제외) |
| `profile_windows_*.out` | 실행 출력 |
| `playwright_artifacts/` | 브라우저 스냅샷(Git 제외) |

## 부록 B. 무결성 (이번 단계 종료 시점)

- Frozen Core SHA256: Windows 작업 트리 9/9, Linux clone 9/9
- data manifest: 35/35 (Windows), 35/35 (Linux 복사본)
- 작업 트리 변경: `reports/step9_3_validation/` 추가와 본 보고서뿐(코드·설정·데이터 무변경, `git status` 확인)
- LLM 호출 0회, GitHub push 0회

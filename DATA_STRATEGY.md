# 데이터 배포 전략 (사용자 결정 필요)

원본 데이터를 축소하거나 가공하지 않았습니다. 필수 데이터는 원본과 바이트 단위로 같은 사본이며, 앱은 시작할 때 SHA256 을 `generation_config.json` 의 기록값과 비교합니다(불일치 시 실행 중단).

## 큰 파일
- `data/processed/evidence/drug_approval_items.parquet`
- `data/processed/rag/approval_chunks.parquet`

## 선택지

- **1 GitHub 저장소에 포함** — 장점: 가장 단순 / 제약: 파일당 100MB 초과 파일 2개(drug_approval_items.parquet, approval_chunks.parquet) 는 일반 push 불가(알려진 제한, 재확인 안 함) / 평가: 부적합(큰 파일)
- **2 Git LFS** — 장점: Git 흐름 유지 / 제약: 무료 저장/전송 한도 수치 NOT_VERIFIED. Streamlit Cloud 가 LFS 파일을 가져오는지도 이번에 검증 안 함 / 평가: CONDITIONAL
- **3 별도 외부 저장소** — 장점: 저장소 가벼움·해시 검증 가능 / 제약: 호스팅 선택·접근 권한 필요, 이번 단계에서 업로드 금지 / 평가: 추천 후보
- **4 배포 시 다운로드** — 장점: 저장소에 데이터 불필요 / 제약: 시작 시간 증가·네트워크 의존·실패 시 fail-closed 처리 필요(앱은 해시 불일치/누락 시 실행 중단) / 평가: 추천 후보(3과 함께)
- **5 배포용 데이터 패키지** — 장점: 버전·해시 고정 / 제약: 패키지 형식/호스팅 필요. 앱의 SHA256 검증(generation_config)과 잘 맞음 / 평가: 추천 후보

## 현재 상태
- 선택된 방식: **NOT_DECIDED** (이 노트북은 업로드하지 않음)
- `data_manifest.json` 에 경로/SHA256 이 기록되어 있어 어떤 방식을 선택해도 검증에 사용할 수 있습니다.
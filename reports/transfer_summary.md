# 이전 요약
## 이전 상태: COMPLETE
- 원본 프로젝트: 파일 880개, 1512.0MB (상위 폴더: data 277, .git 187, reports 173, medguard-deployment 98, app 31, notebooks 30, tests 26, src 19)
- 중복 파일 그룹(동일 SHA256, .git 제외): 105
- 이전 대상 97개 중 정상 복사 97개, 읽기 실패 0개
  - 코드/설정/테스트 62개, 데이터 35개(658.8MB)
- 제외 1개 (원본 보존), 미해결 9건
- 읽기 실패 3건 {'GOOGLE_NATIVE_OR_SHORTCUT_OBJECT': 3}, 재시도로 복구 0건 (상세: read_errors.csv)
- 예상 Python: 3.8+ (코드 문법 기준 추정, 권장 3.11)
- 민감정보 의심: 2건(값 미기록)
  - app/styles/medguard.css : EMAIL ×1
  - tests/test_ui_adapter.py : ASSIGNED_SECRET ×1
- 무결성: PASS
- 실행 검증: 하지 않음(PYCHARM_EXECUTION_VERIFIED=NO). 데이터 공개/재배포 가능 여부: NOT_VERIFIED — 공개 저장소에 올리지 말 것.
- 19B_VALIDATION_STATUS=BLOCKED(테스트 13건 실패/오류, 3건 스킵, 독립 실행 미완료)는 이번 이전으로 해결되지 않았다.

## 합치는 방법
압축 파일을 같은 상위 폴더에 풀면 `medguard-pycharm-transfer/` 하나로 합쳐진다. PyCharm에서는 `medguard-pycharm-transfer/` 폴더를 연다.
- code.zip: app/ src/ ui_integration/ tools/ tests/ .streamlit/ requirements*.txt reports/
- data.zip: data/processed/... 와 매니페스트가 가리키는 reports/..., data_manifest.json
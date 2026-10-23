# 의존성 보고서
- 분석 대상 .py: 49개 (배포 폴더 `medguard-deployment` 기준)
- 진입점(이름 기준): app/streamlit_app.py, app/streamlit_main.py, app.py, tools/fetch_runtime_data.py, ui_integration/app_v2.py
- 실행 import 폐포: 35개 / 테스트 폐포: 30개

## import 관계(프로젝트 내부)
- `app/__init__.py` → `app/ui_policy.py`
- `app/adapters.py` → `app.py`, `app/__init__.py`, `app/ui_policy.py`, `app/view_models.py`, `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/findings.py`, `src/dur_safety/pipeline.py`, `src/dur_safety/resources.py`
- `app/components/coverage_page.py` → `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/drug_search.py` → `app.py`, `app/adapters.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/drug_table.py` → `app.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/evidence_panel.py` → `app.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/findings.py` → `app.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/gate_timeline.py` → `app.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`
- `app/components/header.py` → `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`
- `app/components/pages.py` → `app.py`, `app/components/__init__.py`, `app/components/drug_search.py`, `app/components/drug_table.py`, `app/components/evidence_panel.py`, `app/components/findings.py`, `app/components/safety_matrix.py`, `app/ui_policy.py`, `app/ui_render.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/safety_matrix.py` → `app.py`, `app/ui_policy.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/sidebar.py` → `app.py`, `app/ui_policy.py`, `app/utils/__init__.py`, `app/utils/ui_helpers.py`
- `app/components/summary_cards.py` → `app.py`, `app/ui_policy.py`, `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`
- `app/medguard_dashboard.py` → `app.py`, `app/adapters.py`, `app/components/__init__.py`, `app/components/coverage_page.py`, `app/components/drug_search.py`, `app/components/drug_table.py`, `app/components/evidence_panel.py`, `app/components/findings.py`, `app/components/gate_timeline.py`, `app/components/header.py`, `app/components/pages.py`, `app/components/safety_matrix.py`, `app/components/sidebar.py`, `app/components/summary_cards.py`, `app/ui_runtime.py`, `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`
- `app/streamlit_main.py` → `app.py`, `app/adapters.py`, `app/ui_render.py`, `app/ui_runtime.py`
- `app/ui_render.py` → `app.py`, `app/ui_policy.py`
- `app/ui_runtime.py` → `app.py`, `app/adapters.py`, `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/resources.py`
- `app/utils/ui_helpers.py` → `app.py`, `app/ui_policy.py`
- `src/dur_safety/drug_lookup.py` → `src/dur_safety/__init__.py`, `src/dur_safety/resources.py`, `src/dur_safety/retrieval.py`, `src/dur_safety/screening.py`
- `src/dur_safety/findings.py` → `src/dur_safety/retrieval.py`
- `src/dur_safety/generation.py` → `src/dur_safety/config.py`, `src/dur_safety/findings.py`, `src/dur_safety/retrieval.py`
- `src/dur_safety/pipeline.py` → `src/dur_safety/__init__.py`, `src/dur_safety/findings.py`, `src/dur_safety/generation.py`, `src/dur_safety/resources.py`, `src/dur_safety/retrieval.py`, `src/dur_safety/screening.py`
- `src/dur_safety/resources.py` → `src/dur_safety/__init__.py`, `src/dur_safety/config.py`, `src/dur_safety/findings.py`, `src/dur_safety/generation.py`, `src/dur_safety/retrieval.py`, `src/dur_safety/screening.py`
- `tests/conftest.py` → `src/dur_safety/__init__.py`, `src/dur_safety/resources.py`
- `tests/regression_checks.py` → `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/findings.py`, `src/dur_safety/generation.py`, `src/dur_safety/pipeline.py`, `src/dur_safety/resources.py`, `src/dur_safety/retrieval.py`, `src/dur_safety/screening.py`, `tools/nbsource.py`
- `tests/test_core_contract.py` → `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/findings.py`, `src/dur_safety/generation.py`, `src/dur_safety/pipeline.py`, `src/dur_safety/screening.py`
- `tests/test_finding_regression.py` → `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_generation_regression.py` → `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_medguard_dashboard.py` → `app.py`, `app/adapters.py`, `app/ui_policy.py`, `app/ui_runtime.py`, `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`, `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/pipeline.py`, `tests/test_ui_adapter.py`
- `tests/test_pipeline_regression.py` → `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_retrieval_regression.py` → `src/dur_safety/__init__.py`, `src/dur_safety/retrieval.py`, `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_screening_regression.py` → `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_source_parity.py` → `tests/conftest.py`, `tests/regression_checks.py`
- `tests/test_ui_adapter.py` → `app.py`, `app/adapters.py`, `app/ui_policy.py`, `src/dur_safety/__init__.py`, `src/dur_safety/drug_lookup.py`, `src/dur_safety/findings.py`, `src/dur_safety/generation.py`, `src/dur_safety/pipeline.py`, `src/dur_safety/resources.py`, `src/dur_safety/retrieval.py`, `src/dur_safety/screening.py`
- `ui_integration/app_v2.py` → `app.py`, `app/adapters.py`, `app/components/__init__.py`, `app/components/coverage_page.py`, `app/components/drug_search.py`, `app/components/drug_table.py`, `app/components/evidence_panel.py`, `app/components/findings.py`, `app/components/gate_timeline.py`, `app/components/header.py`, `app/components/pages.py`, `app/components/safety_matrix.py`, `app/components/sidebar.py`, `app/components/summary_cards.py`, `app/ui_policy.py`, `app/ui_runtime.py`, `app/utils/__init__.py`, `app/utils/audit_reader.py`, `app/utils/ui_helpers.py`, `ui_integration/ingredient_dur_ui_adapter.py`

## 외부 패키지 import
- streamlit (11회)
- pandas (10회)
- pytest (7회)
- numpy (6회)
- pyarrow (3회)
- openai (2회)
- sklearn (2회)
- sentence_transformers (2회)
- google (1회)
- scipy (1회)
- torch (1회)
- baselines (1회)
- jsonschema (1회)

## requirements에 없는 외부 패키지 후보(이름 매칭 한계 있음)
- baselines
- google

## 런타임 파일 참조(문자열 리터럴 기준)
- `data/processed/evidence/drug_approval_items.parquet` ← app.py, ui_integration/ingredient_dur_ui_adapter.py
- `data/processed/evidence/easy_drug_canonical.parquet` ← app.py
- `data/processed/generation/generation_config.json` ← app.py
- `data/processed/rag/approval_chunks.parquet` ← app.py
- `data/processed/retrieval/dense/BAAI__bge-m3/embedding_meta.json` ← app.py
- `data/processed/retrieval/dense/BAAI__bge-m3/unique_text_embeddings.npy` ← app.py
- `data/processed/retrieval/retrieval_config.json` ← app.py
- `data/processed/retrieval/text_hash_mapping.parquet` ← app.py
- `data/processed/retrieval/unique_text_index.parquet` ← app.py
- `data/processed/screening/contraindication_evidence.parquet` ← app.py
- `data/processed/screening/contraindication_pairs.parquet` ← app.py
- `data/processed/screening/elderly_caution_rules.parquet` ← app.py
- `data/processed/screening/therapeutic_group_mapping.parquet` ← app.py
- `data_manifest.json` ← tools/fetch_runtime_data.py
- `notebooks/15_ingredient_duplicate_candidates_prototype.ipynb` ← app.py
- `production_baseline.json` ← app.py, app/ui_runtime.py, tests/test_ui_adapter.py
- `src/dur_safety/FROZEN_SHA256SUMS.txt` ← tests/test_ui_adapter.py

## 동적 import / 분석 불가(읽기·파싱 실패 포함)
- 없음

## sys.path 조작 파일
- app.py
- app/medguard_dashboard.py
- app/streamlit_main.py
- tests/regression_checks.py
- tests/test_ui_adapter.py
- ui_integration/app_v2.py

## 누락 가능성
- 프로젝트 루트에만 있는 참조 파일 없음

분석은 정적(AST) 기준이며 런타임에 조립되는 경로는 놓칠 수 있다. 읽지 못한 .py는 분석에서 빠졌으므로 위 결과가 불완전할 수 있다. 실행 검증은 PyCharm에서 별도로 해야 한다.
"""Streamlit runtime provider — loads the Frozen Core once and exposes the 3 things the UI needs.

    rt = load_runtime()
    rt.ready          -> bool (False: DUR data / model could not be loaded; UI disables search and run)
    rt.search(q)      -> drug_lookup.search_drugs(q, limit=...)   (candidates only, never auto-selects)
    rt.core_fn        -> None (production default: pipeline.run_safety_check with real retrieval + call_llm)
    rt.runtime_info   -> {"device", "deployment"} for ViewModel metadata

Nothing here interprets results. Tests replace `load_runtime` (monkeypatch) with a fake Runtime so the
real app script can be exercised with mock Core / mock LLM.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

SEARCH_LIMIT = 20


@dataclass
class Runtime:
    ready: bool
    search: Optional[Callable] = None
    core_fn: Optional[Callable] = None          # None -> adapters.execute uses pipeline.run_safety_check
    resources_module: object = None             # None -> dur_safety.resources (tests may inject)
    runtime_info: dict = field(default_factory=dict)
    error_user: Optional[str] = None
    error_dev: Optional[str] = None
    load_report: Optional[dict] = None


LOAD_FAILED_TEXT = ("DUR 데이터를 불러오지 못했습니다. 약물 검색과 안전성 검사를 실행할 수 없습니다. "
                    "검사 결과가 없는 상태이며, 이는 위험이 없다는 의미가 아닙니다.")


def project_root():
    root = os.environ.get("MEDICAL_AI_PROJECT_ROOT")
    return Path(root) if root else Path(__file__).resolve().parents[1]


def load_runtime():
    """Load resources (once per process; resources.load_resources caches internally)."""
    try:
        from dur_safety import drug_lookup, resources
        from app import adapters
        report = resources.load_resources(project_root())
        deployment = adapters.read_deployment_info(project_root() / "production_baseline.json")
        info = adapters.runtime_info_from_load_report(report, deployment=deployment)
        return Runtime(ready=True, search=lambda q: drug_lookup.search_drugs(q, limit=SEARCH_LIMIT),
                       core_fn=None, runtime_info=info, load_report=report)
    except Exception as e:  # noqa: BLE001 — any load failure disables the UI (fail closed)
        return Runtime(ready=False, error_user=LOAD_FAILED_TEXT,
                       error_dev=f"{type(e).__name__}: {str(e)[:500]}")

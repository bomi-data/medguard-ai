"""pytest fixtures. Requires MEDICAL_AI_PROJECT_ROOT (the Drive project folder with data/ and notebooks/).

Dense-dependent tests skip unless the bge-m3 model/index loads (set DUR_ALLOW_NO_DENSE=1 to allow BM25-only runs).
No test calls the OpenAI API (regression_checks.api_guard blocks client construction).
"""
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE.parent / "tools"), str(HERE)]


@pytest.fixture(scope="session")
def project_root():
    root = os.environ.get("MEDICAL_AI_PROJECT_ROOT")
    if not root or not (Path(root) / "data" / "processed").exists():
        pytest.skip("MEDICAL_AI_PROJECT_ROOT not set to the medical-ai-project folder")
    return Path(root)


@pytest.fixture(scope="session")
def notebook_dir(project_root):
    return project_root / "notebooks"


@pytest.fixture(scope="session")
def loaded(project_root):
    from dur_safety import resources
    os.environ.pop("OPENAI_API_KEY", None)
    return resources.load_resources(project_root, require_dense=os.environ.get("DUR_ALLOW_NO_DENSE") != "1",
                                    verify_hashes=os.environ.get("DUR_SKIP_HASHES") != "1")


@pytest.fixture(scope="session")
def bl(project_root, loaded):
    from baselines import Baselines
    return Baselines(project_root)


def assert_pass(r):
    if r["status"] == "SKIPPED":
        pytest.skip(r.get("reason"))
    assert r["status"] == "PASS", f"{r['name']}: {r['status']} — failures: {r['failures'][:5]}"

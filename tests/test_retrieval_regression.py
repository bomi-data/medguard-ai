import pytest
import regression_checks as RC
from conftest import assert_pass
from dur_safety import retrieval


def test_retrieval_regression_vs_06A_and_04_smoke(bl):
    r = RC.check_retrieval_regression(bl)
    if r["status"] == "PARTIAL_BM25_ONLY":
        pytest.fail(f"dense not loaded — only BM25 compared: {r['failures'][:3]}")
    assert_pass(r)

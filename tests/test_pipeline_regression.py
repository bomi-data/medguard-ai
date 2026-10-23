import pytest
import regression_checks as RC
from conftest import assert_pass


@pytest.mark.parametrize("mode", ["replay", "live"])
def test_pipeline_integration_mock_llm(bl, mode):
    assert_pass(RC.check_pipeline_integration(bl, mode))


def test_drug_lookup_adapter(bl):
    assert_pass(RC.check_drug_lookup())

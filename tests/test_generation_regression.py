import pytest
import regression_checks as RC
from conftest import assert_pass


@pytest.mark.parametrize("mode", ["evaluated_finding+frozen_evidence", "production_finding+frozen_evidence",
                                  "production_live"])
def test_generation_input_parity(bl, mode):
    assert_pass(RC.check_generation_input_parity(bl, mode))


def test_output_validation_regression(bl, notebook_dir):
    assert_pass(RC.check_output_validation(bl, notebook_dir))

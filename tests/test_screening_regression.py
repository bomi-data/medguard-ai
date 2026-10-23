import regression_checks as RC
from conftest import assert_pass


def test_screening_regression_vs_06E(bl, notebook_dir):
    assert_pass(RC.check_screening_regression(bl, notebook_dir))

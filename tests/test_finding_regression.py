import regression_checks as RC
from conftest import assert_pass


def test_finding_parity_real_02_output_vs_evaluated_finding(bl):
    assert_pass(RC.check_finding_parity(bl))

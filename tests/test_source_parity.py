import regression_checks as RC
from conftest import assert_pass


def test_source_parity(notebook_dir):
    assert_pass(RC.check_source_parity(notebook_dir))

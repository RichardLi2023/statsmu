"""A deliberately failing test. Never runs in the normal test step.

The pipeline self-test copies this file into a module's tests/ folder and runs the normal
test command. That command must fail, which proves a failing test blocks a merge.
"""


def test_planted_failure():
    assert 1 + 1 == 3, "planted failure: the pipeline must report this"

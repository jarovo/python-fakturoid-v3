import pytest
from pytest_examples import find_examples, CodeExample, EvalExample
from unittest.mock import patch
from .mock import FakeResponse


@pytest.mark.parametrize('example', find_examples('README.md'), ids=str)
def test_docstrings_lint(example: CodeExample, eval_example: EvalExample):
    eval_example.lint(example)
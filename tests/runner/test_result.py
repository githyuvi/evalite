import pytest
from pydantic import ValidationError

from evalite.runner.result import Score


def test_score_value_out_of_range_raises():
    with pytest.raises(ValidationError):
        Score(passed=True, value=1.1)


def test_score_valid_value_constructs():
    score = Score(passed=True, value=1.0)
    assert score.passed is True
    assert score.value == 1.0
    assert score.reasoning == ""

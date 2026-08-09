import pytest
from pydantic import ValidationError

from evalite.runner.result import CaseResult, RunResult, Score


def test_score_value_out_of_range_raises():
    with pytest.raises(ValidationError):
        Score(passed=True, value=1.1)


def test_score_valid_value_constructs():
    score = Score(passed=True, value=1.0)
    assert score.passed is True
    assert score.value == 1.0
    assert score.reasoning == ""


def _make_case_result(case_id: str, passed: bool) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        iteration=0,
        input="what is 2+2?",
        actual="4",
        score=Score(passed=passed, value=1.0 if passed else 0.0),
        passed=passed,
        duration_ms=12.5,
    )


def test_run_result_pass_rate_stores_computed_value():
    case_results = [
        _make_case_result("case-1", True),
        _make_case_result("case-2", True),
        _make_case_result("case-3", False),
    ]
    run_result = RunResult(
        test_set_name="my-test-set",
        total=3,
        passed=2,
        failed=1,
        pass_rate=2 / 3,
        case_results=case_results,
        duration_ms=100.0,
    )
    assert run_result.pass_rate == pytest.approx(0.6666666666666666)
    assert run_result.total == 3
    assert run_result.passed == 2
    assert run_result.failed == 1
    assert len(run_result.case_results) == 3


def test_run_result_serializes_to_json():
    case_results = [
        _make_case_result("case-1", True),
        _make_case_result("case-2", True),
        _make_case_result("case-3", False),
    ]
    run_result = RunResult(
        test_set_name="my-test-set",
        total=3,
        passed=2,
        failed=1,
        pass_rate=2 / 3,
        case_results=case_results,
        duration_ms=100.0,
    )
    json_str = run_result.model_dump_json()
    assert isinstance(json_str, str)
    assert "my-test-set" in json_str


def test_case_result_passed_independent_of_score_passed():
    case_result = CaseResult(
        case_id="case-1",
        iteration=0,
        input="what is 2+2?",
        actual="5",
        score=Score(passed=False, value=0.0),
        passed=True,
        duration_ms=12.5,
    )
    assert case_result.passed is True
    assert case_result.score.passed is False

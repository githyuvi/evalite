import json

import pytest

from evalite.reporter.console import ConsoleReporter
from evalite.runner.result import CaseResult, RunResult, Score


def _make_case_result(
    case_id: str, iteration: int, passed: bool, score_value: float, duration_ms: float
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        iteration=iteration,
        input="test input",
        actual="test output",
        score=Score(passed=passed, value=score_value),
        passed=passed,
        duration_ms=duration_ms,
    )


def test_table_output_contains_case_ids(capsys):
    """Table output should contain all case IDs."""
    reporter = ConsoleReporter()
    case_results = [
        _make_case_result("case-1", 0, True, 1.0, 100.0),
        _make_case_result("case-2", 0, False, 0.0, 50.0),
        _make_case_result("case-3", 0, True, 0.8, 75.0),
    ]
    run_result = RunResult(
        test_set_name="test-set",
        total=3,
        passed=2,
        failed=1,
        pass_rate=2 / 3,
        case_results=case_results,
        duration_ms=225.0,
    )

    reporter.report(run_result, fmt="table")
    captured = capsys.readouterr()

    assert "case-1" in captured.out
    assert "case-2" in captured.out
    assert "case-3" in captured.out


def test_table_output_footer_contains_passed_total(capsys):
    """Table footer should contain correct passed/total counts."""
    reporter = ConsoleReporter()
    case_results = [
        _make_case_result("case-1", 0, True, 1.0, 100.0),
        _make_case_result("case-2", 0, False, 0.0, 50.0),
    ]
    run_result = RunResult(
        test_set_name="test-set",
        total=2,
        passed=1,
        failed=1,
        pass_rate=0.5,
        case_results=case_results,
        duration_ms=150.0,
    )

    reporter.report(run_result, fmt="table")
    captured = capsys.readouterr()

    assert "Passed: 1/2" in captured.out
    assert "50.0%" in captured.out


def test_json_output_is_valid_json(capsys):
    """JSON output should be valid JSON."""
    reporter = ConsoleReporter()
    case_results = [
        _make_case_result("case-1", 0, True, 1.0, 100.0),
    ]
    run_result = RunResult(
        test_set_name="test-set",
        total=1,
        passed=1,
        failed=0,
        pass_rate=1.0,
        case_results=case_results,
        duration_ms=100.0,
    )

    reporter.report(run_result, fmt="json")
    captured = capsys.readouterr()

    parsed = json.loads(captured.out)
    assert isinstance(parsed, dict)


def test_json_output_contains_test_set_name(capsys):
    """JSON output should contain test_set_name key."""
    reporter = ConsoleReporter()
    case_results = [
        _make_case_result("case-1", 0, True, 1.0, 100.0),
    ]
    run_result = RunResult(
        test_set_name="my-test-set",
        total=1,
        passed=1,
        failed=0,
        pass_rate=1.0,
        case_results=case_results,
        duration_ms=100.0,
    )

    reporter.report(run_result, fmt="json")
    captured = capsys.readouterr()

    parsed = json.loads(captured.out)
    assert "test_set_name" in parsed
    assert parsed["test_set_name"] == "my-test-set"


def test_table_empty_case_results_no_crash(capsys):
    """Reporter should not crash with empty case_results for table format."""
    reporter = ConsoleReporter()
    run_result = RunResult(
        test_set_name="test-set",
        total=0,
        passed=0,
        failed=0,
        pass_rate=0.0,
        case_results=[],
        duration_ms=0.0,
    )

    reporter.report(run_result, fmt="table")
    captured = capsys.readouterr()

    assert "Passed: 0/0" in captured.out
    assert "0.0%" in captured.out


def test_json_empty_case_results_no_crash(capsys):
    """Reporter should not crash with empty case_results for json format."""
    reporter = ConsoleReporter()
    run_result = RunResult(
        test_set_name="test-set",
        total=0,
        passed=0,
        failed=0,
        pass_rate=0.0,
        case_results=[],
        duration_ms=0.0,
    )

    reporter.report(run_result, fmt="json")
    captured = capsys.readouterr()

    parsed = json.loads(captured.out)
    assert parsed["total"] == 0
    assert parsed["passed"] == 0

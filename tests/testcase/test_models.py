import pytest
from pydantic import ValidationError

from evalite.testcase.models import ExpectedOutput, TestCase, TestSet


def test_valid_test_case_constructs_without_error():
    case = TestCase(
        id="happy_path_001",
        input="Book a meeting room for tomorrow at 3pm",
        expected=ExpectedOutput(task_completed=True, tool_called="book_room"),
        tags=["happy_path", "booking"],
        iterations=3,
    )

    assert case.id == "happy_path_001"
    assert case.input == "Book a meeting room for tomorrow at 3pm"
    assert case.tags == ["happy_path", "booking"]
    assert case.iterations == 3


def test_iterations_defaults_to_one():
    case = TestCase(
        id="case_1",
        input="some input",
        expected=ExpectedOutput(),
    )

    assert case.iterations == 1


def test_tags_defaults_to_empty_list():
    case = TestCase(
        id="case_1",
        input="some input",
        expected=ExpectedOutput(),
    )

    assert case.tags == []


def test_expected_output_accepts_arbitrary_extra_fields():
    expected = ExpectedOutput(task_completed=True, tool_called="book_room", custom_field=42)

    assert expected.task_completed is True
    assert expected.tool_called == "book_room"
    assert expected.custom_field == 42


def test_test_set_with_zero_cases_is_valid():
    test_set = TestSet(name="empty_set", cases=[])

    assert test_set.name == "empty_set"
    assert test_set.cases == []


def test_test_case_missing_id_raises_validation_error():
    with pytest.raises(ValidationError):
        TestCase(input="some input", expected=ExpectedOutput())


def test_test_case_missing_input_raises_validation_error():
    with pytest.raises(ValidationError):
        TestCase(id="case_1", expected=ExpectedOutput())

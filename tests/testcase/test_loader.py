import pytest

from evalite.testcase.loader import load_test_set


def test_load_valid_test_set():
    result = load_test_set("tests/testcase/fixtures/valid_test_set.yaml")
    assert len(result.cases) == 2
    assert result.name == "booking_agent_v1"


def test_load_invalid_missing_id():
    with pytest.raises(ValueError):
        load_test_set("tests/testcase/fixtures/invalid_missing_id.yaml")


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_test_set("tests/testcase/fixtures/nonexistent.yaml")


def test_load_yaml_with_wrong_shape_list(tmp_path):
    yaml_file = tmp_path / "list_fixture.yaml"
    yaml_file.write_text("- a\n- b\n")
    with pytest.raises(ValueError):
        load_test_set(yaml_file)

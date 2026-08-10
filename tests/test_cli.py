import json

from typer.testing import CliRunner

from evalite.cli import app

runner = CliRunner()

ECHO_AGENT = "tests/fixtures/echo_agent.py"


def _write_test_set(tmp_path, *, expected_contains: str):
    """Write a minimal test set YAML whose single case echoes `input` back.

    The echo agent returns the input verbatim, so `expected_contains`
    controls whether the case passes (substring of input) or fails
    (not present in input).
    """
    yaml_content = f"""
name: echo_test_set
cases:
  - id: case_1
    input: "the answer is 42"
    expected:
      contains: "{expected_contains}"
"""
    test_set_path = tmp_path / "test_set.yaml"
    test_set_path.write_text(yaml_content)
    return str(test_set_path)


def test_run_passing_case_exits_zero(tmp_path):
    test_set_path = _write_test_set(tmp_path, expected_contains="42")

    result = runner.invoke(app, ["run", test_set_path, "--agent", ECHO_AGENT])

    assert result.exit_code == 0, result.output


def test_run_failing_case_exits_one(tmp_path):
    test_set_path = _write_test_set(tmp_path, expected_contains="not present")

    result = runner.invoke(app, ["run", test_set_path, "--agent", ECHO_AGENT])

    assert result.exit_code == 1


def test_run_nonexistent_test_set_exits_one():
    result = runner.invoke(app, ["run", "does_not_exist.yaml", "--agent", ECHO_AGENT])

    assert result.exit_code == 1
    assert "Error" in result.output


def test_run_invalid_agent_path_exits_one(tmp_path):
    test_set_path = _write_test_set(tmp_path, expected_contains="42")

    result = runner.invoke(
        app, ["run", test_set_path, "--agent", "tests/fixtures/does_not_exist.py"]
    )

    assert result.exit_code == 1
    assert "Error" in result.output


def test_run_output_json_is_valid_json(tmp_path):
    test_set_path = _write_test_set(tmp_path, expected_contains="42")

    result = runner.invoke(
        app, ["run", test_set_path, "--agent", ECHO_AGENT, "--output", "json"]
    )

    parsed = json.loads(result.output)
    assert parsed["test_set_name"] == "echo_test_set"
    assert parsed["passed"] == 1


def test_run_with_enterprise_flags_does_not_error(tmp_path):
    test_set_path = _write_test_set(tmp_path, expected_contains="42")

    result = runner.invoke(
        app,
        [
            "run",
            test_set_path,
            "--agent",
            ECHO_AGENT,
            "--proxy",
            "http://proxy.corp.com:8080",
            "--ca-bundle",
            "/path/to/ca.pem",
        ],
    )

    assert result.exit_code == 0, result.output


def test_build_enterprise_config_cli_flags_win_over_env(monkeypatch):
    from evalite.cli import _build_enterprise_config

    monkeypatch.setenv("HTTP_PROXY", "http://env-proxy:1")
    monkeypatch.setenv("SSL_CA_BUNDLE", "/env/ca.pem")

    config = _build_enterprise_config(
        proxy="http://cli-proxy:2",
        ca_bundle="/cli/ca.pem",
        client_cert=None,
        client_key=None,
    )

    assert config.http_proxy == "http://cli-proxy:2"
    assert config.ssl_ca_bundle == "/cli/ca.pem"

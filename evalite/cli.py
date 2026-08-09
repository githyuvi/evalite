"""Command-line interface for evalite.

`evalite run` ties together the test set loader, the agent adapter (loaded
dynamically from a dotted import path or a standalone .py file), the
`Runner`, and the `ConsoleReporter` into a single end-to-end command
suitable for local use and CI.
"""

import asyncio
import importlib
import importlib.util

import typer

from evalite.agent.protocol import AgentAdapter
from evalite.reporter.console import ConsoleReporter
from evalite.runner.runner import Runner
from evalite.scorer.default import DefaultScorer
from evalite.testcase.loader import load_test_set

app = typer.Typer()


@app.callback()
def callback() -> None:
    """evalite: a lightweight, model-agnostic agent evaluation framework.

    An explicit (no-op) callback is required here so Typer keeps `run` as
    a named subcommand (`evalite run ...`) instead of collapsing into a
    single implicit command — Typer only builds subcommand dispatch when
    there's more than one registered command or a callback present.
    """


def load_adapter(agent: str) -> AgentAdapter:
    """Load and instantiate an `AgentAdapter` from a dotted path or .py file.

    If `agent` ends in `.py`, it is loaded as a standalone module (which
    must not import from evalite, per ADR-001) and a top-level class named
    `Agent` is instantiated from it. Otherwise `agent` is treated as a
    dotted import path (e.g. `mypackage.adapters.MyAgent`): everything
    before the last `.` is imported as a module, and the final segment is
    looked up as a class attribute on it.

    Either way the resulting instance is validated against the
    `AgentAdapter` Protocol.

    On any failure (missing file/module/class, import error, or an
    instance that doesn't satisfy `AgentAdapter`), an error is printed to
    stderr and the process exits with code 1.

    Args:
        agent: dotted import path to an `AgentAdapter` class, or path to a
            .py file containing a top-level class named `Agent`.

    Returns:
        An instantiated object satisfying `AgentAdapter`.
    """
    try:
        if agent.endswith(".py"):
            spec = importlib.util.spec_from_file_location("evalite_agent_module", agent)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load module spec from {agent}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            agent_cls = getattr(module, "Agent")
        else:
            module_path, _, class_name = agent.rpartition(".")
            if not module_path:
                raise ImportError(
                    f"Invalid agent path '{agent}': expected a dotted path "
                    "(e.g. mypackage.MyAgent) or a .py file path"
                )
            module = importlib.import_module(module_path)
            agent_cls = getattr(module, class_name)

        instance = agent_cls()
    except Exception as e:
        typer.echo(f"Error: failed to load agent '{agent}': {e}", err=True)
        raise typer.Exit(code=1)

    if not isinstance(instance, AgentAdapter):
        typer.echo(
            f"Error: agent '{agent}' does not implement the AgentAdapter "
            "protocol — missing async send(messages) method",
            err=True,
        )
        raise typer.Exit(code=1)

    return instance


@app.command()
def run(
    test_set: str = typer.Argument(..., help="Path to YAML test set file"),
    agent: str = typer.Option(
        ...,
        "--agent",
        help=(
            "Import path to AgentAdapter class (e.g. mypackage.MyAgent) "
            "OR path to a .py file with a top-level class named Agent"
        ),
    ),
    max_workers: int = typer.Option(10, "--max-workers", help="Max concurrent agent calls"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
) -> None:
    """Run a test set against an agent and report results."""
    try:
        test_set_obj = load_test_set(test_set)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    adapter = load_adapter(agent)

    scorer = DefaultScorer()
    runner = Runner(adapter=adapter, scorer=scorer, max_workers=max_workers)
    result = asyncio.run(runner.run(test_set_obj))
    ConsoleReporter().report(result, fmt=output)
    raise typer.Exit(code=0 if result.failed == 0 else 1)


if __name__ == "__main__":
    app()

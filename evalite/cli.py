"""Command-line interface for evalite.

`evalite run` ties together the test set loader, the agent adapter (loaded
dynamically from a dotted import path or a standalone .py file), the
`Runner`, and the `ConsoleReporter` into a single end-to-end command
suitable for local use and CI.

`evalite db migrate` and `evalite results` (Phase 2) add storage-backed
commands on top of `SqliteStorage`: preparing a database file's schema,
and listing/inspecting previously persisted runs.
"""

import asyncio
import importlib
import importlib.util
import json
import os
import webbrowser

import typer

from evalite.agent.protocol import AgentAdapter
from evalite.enterprise import EnterpriseConfig
from evalite.reporter.console import ConsoleReporter
from evalite.runner.result import RunResult
from evalite.runner.runner import Runner
from evalite.scorer.default import DefaultScorer
from evalite.testcase.loader import load_test_set

# NOTE: `evalite.storage.sqlite.SqliteStorage` is deliberately NOT imported
# at module level here. `evalite`'s core install (no `[storage]` extra)
# must not require `sqlalchemy`/`aiosqlite` — mirroring the same principle
# already followed in `evalite/__init__.py`. Each command below that
# actually touches storage (`run --db`, `db migrate`, `results`) imports
# `SqliteStorage` locally, so a plain `evalite --help` or a no-`--db`
# `evalite run` never triggers that import.

app = typer.Typer()
db_app = typer.Typer()
app.add_typer(db_app, name="db")


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


def _build_enterprise_config(
    proxy: str | None,
    ca_bundle: str | None,
    client_cert: str | None,
    client_key: str | None,
) -> EnterpriseConfig:
    """Merges `--proxy`/`--ca-bundle`/`--client-cert`/`--client-key` with env vars.

    Starts from `EnterpriseConfig.from_env()` (reading `HTTP_PROXY`,
    `HTTPS_PROXY`, `NO_PROXY`, `SSL_CA_BUNDLE`, `SSL_CLIENT_CERT`,
    `SSL_CLIENT_KEY`), then lets each CLI flag override its corresponding
    field when given. There is no `--https-proxy` flag, so `https_proxy`
    is env-var-only; `--proxy` only overrides `http_proxy` and is not
    also applied to `https_proxy`, keeping the mapping one-flag-to-one-field
    rather than having `--proxy` implicitly affect two fields at once.

    Extracted as a standalone helper (rather than inlined in each command)
    so the merge logic can be unit-tested directly without mocking Typer
    command internals.
    """
    env_config = EnterpriseConfig.from_env()
    return EnterpriseConfig(
        http_proxy=proxy or env_config.http_proxy,
        https_proxy=env_config.https_proxy,
        no_proxy=env_config.no_proxy,
        ssl_ca_bundle=ca_bundle or env_config.ssl_ca_bundle,
        ssl_client_cert=client_cert or env_config.ssl_client_cert,
        ssl_client_key=client_key or env_config.ssl_client_key,
    )


def _parse_db_url(db: str) -> str:
    """Extract a filesystem path from a `sqlite:///` connection string.

    Only SQLite URLs are supported by the CLI's `--db` option in this
    phase (per the Phase 2 plan's `--db sqlite:///evalite.db` example) —
    arbitrary SQLAlchemy URLs (e.g. postgres://...) are out of scope
    here, even though `StorageBackend` itself is backend-agnostic.

    On an unsupported scheme, an error is printed to stderr and the
    process exits with code 1.

    Args:
        db: a connection string of the form `sqlite:///<path>`.

    Returns:
        The raw filesystem path to the SQLite database file.
    """
    prefix = "sqlite:///"
    if not db.startswith(prefix):
        typer.echo(
            f"Error: unsupported --db value '{db}' — only sqlite:/// URLs are supported",
            err=True,
        )
        raise typer.Exit(code=1)
    return db[len(prefix) :]


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
    db: str | None = typer.Option(
        None,
        "--db",
        help=(
            "SQLite connection string, e.g. sqlite:///evalite.db. "
            "If provided, persists the run."
        ),
    ),
    proxy: str | None = typer.Option(None, "--proxy", help="HTTP/HTTPS proxy URL"),
    ca_bundle: str | None = typer.Option(None, "--ca-bundle", help="Path to custom CA bundle"),
    client_cert: str | None = typer.Option(None, "--client-cert", help="Path to client certificate"),
    client_key: str | None = typer.Option(None, "--client-key", help="Path to client key"),
) -> None:
    """Run a test set against an agent and report results.

    --proxy/--ca-bundle/--client-cert/--client-key configure an EnterpriseConfig for future use by HTTP-calling components (LLM judge providers, etc.) — currently these components must still be constructed and configured directly in user code; this CLI flow does not yet auto-wire them.
    """
    try:
        test_set_obj = load_test_set(test_set)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    enterprise_config = _build_enterprise_config(proxy, ca_bundle, client_cert, client_key)

    adapter = load_adapter(agent)

    scorer = DefaultScorer()

    storage: "SqliteStorage | None" = None
    if db is not None:
        db_path = _parse_db_url(db)

        from evalite.storage.sqlite import SqliteStorage

        storage = SqliteStorage(db_path=db_path)

    runner = Runner(adapter=adapter, scorer=scorer, max_workers=max_workers, storage=storage)

    async def _run_with_storage() -> RunResult:
        """Initialize storage (if configured) and run the test set.

        Wrapped in a single coroutine so the CLI makes exactly one
        `asyncio.run()` call, rather than one for `storage.init()` and a
        separate one for `runner.run()`.
        """
        if storage is not None:
            await storage.init()
        return await runner.run(test_set_obj)

    result = asyncio.run(_run_with_storage())
    ConsoleReporter().report(result, fmt=output)
    raise typer.Exit(code=0 if result.failed == 0 else 1)


@app.command()
def serve(
    db: str = typer.Option(
        "sqlite:///evalite.db",
        "--db",
        help=(
            "Connection string for the storage backend: sqlite:///path.db, "
            "or postgresql+asyncpg://user:pass@host/dbname for PostgreSQL."
        ),
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind the server to"),
    port: int = typer.Option(8000, "--port", help="Port to bind the server to"),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable uvicorn auto-reload (development only; not supported here, see NOTE below)",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        help="Open the server URL in your default browser after it starts",
    ),
    proxy: str | None = typer.Option(None, "--proxy", help="HTTP/HTTPS proxy URL"),
    ca_bundle: str | None = typer.Option(None, "--ca-bundle", help="Path to custom CA bundle"),
    client_cert: str | None = typer.Option(None, "--client-cert", help="Path to client certificate"),
    client_key: str | None = typer.Option(None, "--client-key", help="Path to client key"),
) -> None:
    """Start the evalite API server (evalite\[server] extra required).

    Requires the `EVALITE_API_KEY` environment variable to be set — the
    server refuses to start otherwise (rule 15's "fail loud" requirement;
    the per-request 401 check in `evalite.server.auth.require_api_key`
    is a separate, request-time enforcement of the same rule).

    NOTE on --reload: uvicorn's auto-reload mechanism re-imports a fixed
    "module:app" string in a subprocess, which requires a module-level
    `app` object built without CLI arguments. This command instead
    builds the app dynamically from `--db` via `create_app(storage)`, so
    there is no such fixed import target — passing --reload prints a
    warning and is otherwise ignored rather than silently doing nothing
    unexplained.

    --proxy/--ca-bundle/--client-cert/--client-key configure an EnterpriseConfig for future use by HTTP-calling components (LLM judge providers, etc.) — currently these components must still be constructed and configured directly in user code; this CLI flow does not yet auto-wire them.
    """
    if not os.environ.get("EVALITE_API_KEY"):
        typer.echo(
            "Error: EVALITE_API_KEY environment variable must be set to start the server",
            err=True,
        )
        raise typer.Exit(code=1)

    enterprise_config = _build_enterprise_config(proxy, ca_bundle, client_cert, client_key)

    try:
        import uvicorn

        from evalite.server.app import create_app
    except ImportError:
        typer.echo(
            "Error: the API server requires the [server] extra — "
            "install with: pip install evalite[server]",
            err=True,
        )
        raise typer.Exit(code=1)

    if db.startswith("postgresql"):
        from evalite.storage.postgres import PostgresStorage

        storage = PostgresStorage(url=db)
    else:
        from evalite.storage.sqlite import SqliteStorage

        db_path = _parse_db_url(db)
        storage = SqliteStorage(db_path=db_path)

    asyncio.run(storage.init())

    if reload:
        typer.echo(
            "Warning: --reload is not supported when serving a dynamically "
            "constructed app (see `evalite serve --help`) — starting without it",
            err=True,
        )

    fastapi_app = create_app(storage)

    if open_browser:
        url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
        webbrowser.open(url)

    uvicorn.run(fastapi_app, host=host, port=port)


@db_app.command("migrate")
def db_migrate(
    db: str = typer.Option(
        "sqlite:///evalite.db",
        "--db",
        help="SQLite connection string to prepare, e.g. sqlite:///evalite.db",
    ),
) -> None:
    """Prepare a database file's schema for use by evalite storage.

    NOTE: this does not (yet) run real Alembic migrations. `alembic.ini`'s
    `script_location = evalite/storage/migrations` is a path relative to
    the evalite project root, and neither `alembic.ini` nor a real
    `alembic` subprocess invocation is packaged/guaranteed to work from
    an arbitrary user's CWD after `pip install evalite` — only from
    inside a checkout of this repo. There are also no real version
    scripts under `evalite/storage/migrations/versions/` yet (just
    `.gitkeep`), so `alembic upgrade head` would currently be a no-op
    even if invoked correctly. Closing this gap for real (bundling
    migrations as package data, or driving them via
    `alembic.command.upgrade` with a `Config` pointed at the installed
    package's migrations directory) is left to a later phase.

    For now, this command instead calls `SqliteStorage.init()`
    (`Base.metadata.create_all`), which satisfies Phase 2's actual
    done-criterion — creating tables on a fresh SQLite file — just as
    well as a real migration would at this stage.
    """
    db_path = _parse_db_url(db)

    from evalite.storage.sqlite import SqliteStorage

    storage = SqliteStorage(db_path=db_path)

    try:
        asyncio.run(storage.init())
    except Exception as e:
        typer.echo(f"Error: migration failed: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Database ready at {db_path}")


@app.command()
def results(
    db: str = typer.Option(
        "sqlite:///evalite.db",
        "--db",
        help="SQLite connection string to read from, e.g. sqlite:///evalite.db",
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Show the full case-level breakdown for a specific run"
    ),
    limit: int = typer.Option(20, "--limit", help="Max number of recent runs to list"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
) -> None:
    """List recently persisted runs, or show full detail for one run."""
    db_path = _parse_db_url(db)

    from evalite.storage.sqlite import SqliteStorage

    storage = SqliteStorage(db_path=db_path)

    if run_id is not None:
        run_result = asyncio.run(storage.get_run(run_id))
        if run_result is None:
            typer.echo(f"Error: run '{run_id}' not found", err=True)
            raise typer.Exit(code=1)
        ConsoleReporter().report(run_result, fmt=output)
        return

    runs = asyncio.run(storage.list_runs(limit=limit))

    if output == "json":
        print(json.dumps(runs, indent=2))
        return

    if not runs:
        typer.echo("No runs found")
        return

    header = f"{'run_id':<38} {'test_set_name':<20} {'passed':<7} {'failed':<7} {'timestamp':<26}"
    print(header)
    print("-" * len(header))
    for run_entry in runs:
        row = (
            f"{run_entry['run_id']:<38} {run_entry['test_set_name']:<20} "
            f"{run_entry['passed']:<7} {run_entry['failed']:<7} {run_entry['timestamp']:<26}"
        )
        print(row)


if __name__ == "__main__":
    app()

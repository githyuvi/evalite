"""Storage backend contract.

Defines the structural interface any persistence backend must satisfy to
be plugged into evalite. Like `AgentAdapter` (ADR-001) and `Scorer`, this
is a `Protocol` rather than an ABC: an implementation never needs to
import from this library to satisfy the contract.

Per ADR-003, storage is opt-in — the runner accepts an optional
`StorageBackend` and works fine with none configured. This Protocol is
not `runtime_checkable`, consistent with `Scorer` (see
`evalite/scorer/base.py`): storage backends are library-internal or
user-configured objects passed directly into the runner/CLI config, not
something the runner does an `isinstance` startup check against. Unlike
`AgentAdapter` (which the runner validates eagerly because a malformed
adapter is a common, easy-to-hit user error), a misconfigured storage
backend will fail loudly the first time `save_run`/`get_run` is awaited
and doesn't provide the method — an `isinstance` check here would just
be extra ceremony with no corresponding benefit. If this reasoning turns
out to be wrong once the CLI wires up storage, it's a small, local change
to make it `runtime_checkable` and add the check.
"""

from typing import Protocol

from evalite.runner.result import RunResult


class StorageBackend(Protocol):
    """Structural contract for anything evalite can use to persist runs.

    Implementations must be async (ADR-002/ADR-003): all I/O (database
    reads/writes) runs on the event loop via an async driver
    (`aiosqlite`, `asyncpg`), never a blocking call.
    """

    async def save_run(self, run: RunResult) -> str:
        """Persist a completed run.

        Args:
            run: the aggregated result of a test set run.

        Returns:
            The run_id (UUID string) the run was stored under.
        """
        ...

    async def get_run(self, run_id: str) -> RunResult | None:
        """Fetch a previously persisted run by id.

        Args:
            run_id: the UUID string returned by `save_run`.

        Returns:
            The reconstructed `RunResult`, or `None` if no run with that
            id exists.
        """
        ...

    async def list_runs(self, limit: int = 50) -> list[dict]:
        """List recent runs without loading full per-case detail.

        Args:
            limit: maximum number of runs to return, most recent first.

        Returns:
            Lightweight dicts, one per run, each with keys: `run_id`,
            `test_set_name`, `passed`, `failed`, `timestamp`.
        """
        ...

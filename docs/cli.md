# CLI reference

## `evalite run`

```bash
evalite run test-set.yaml --agent agent.py
```

Runs a YAML test set against an agent and reports pass/fail. Exit code is
`0` if every case passed, `1` otherwise.

| Flag | Default | Meaning |
|---|---|---|
| `--agent` | required | Import path to an `AgentAdapter` class, or a path to a `.py` file with a top-level `Agent` class |
| `--max-workers` | `10` | Max concurrent agent calls |
| `--output` | `table` | `table` or `json` |
| `--db` | none | SQLite connection string (e.g. `sqlite:///evalite.db`); persists the run if set |
| `--proxy`, `--ca-bundle`, `--client-cert`, `--client-key` | none | Network configuration for enterprise/regulated environments |

## `evalite serve`

```bash
EVALITE_API_KEY=... evalite serve --db sqlite:///evalite.db
```

Starts the REST + WebSocket API server (`evalite[server]` extra
required). Requires `EVALITE_API_KEY` to be set; refuses to start
otherwise.

| Flag | Default | Meaning |
|---|---|---|
| `--db` | `sqlite:///evalite.db` | SQLite or PostgreSQL (`postgresql+asyncpg://...`) connection string |
| `--host` | `0.0.0.0` | Bind host |
| `--port` | `8000` | Bind port |
| `--open` | off | Open the dashboard in your default browser after starting |
| `--proxy`, `--ca-bundle`, `--client-cert`, `--client-key` | none | Network configuration for enterprise/regulated environments |

## `evalite db migrate`

```bash
evalite db migrate --db sqlite:///evalite.db
```

Prepares a database file's schema for use by evalite storage.

## `evalite results`

```bash
evalite results --db sqlite:///evalite.db
evalite results --db sqlite:///evalite.db --run-id <id>
```

Lists recently persisted runs, or shows the full case-level breakdown for
one run with `--run-id`.

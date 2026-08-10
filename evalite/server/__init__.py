"""evalite API server: FastAPI app exposing the runner over REST + WebSocket.

This is an optional extra (`evalite[server]`) — see `pyproject.toml`.
Nothing in `evalite/__init__.py` imports this package, so a bare
`import evalite` never pulls in FastAPI.
"""

from evalite.server.app import create_app

__all__ = ["create_app"]

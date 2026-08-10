from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


def mount_ui(app: FastAPI) -> None:
    """Mounts the built React app onto the FastAPI app if dist/ exists."""
    dist = Path(__file__).parent / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")

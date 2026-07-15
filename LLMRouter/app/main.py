"""FastAPI application factory + uvicorn entry point.
main.py is intentionally tiny: its only job is to build the FastAPI
app and attach the routers defined elsewhere. All business logic lives
under app/api/, app/services/, and app/core/.
"""

from fastapi import FastAPI

from app.api.routes import api_router
from app.core.config import get_config

app = FastAPI(title="LLM router & Execution Platform")
app.include_router(api_router)

def run() -> None:
    """Programmatic uvicorn launcher.
    Used by the root-level main.py so the project can be started with
    `uv run python main.py` without remembering uvicorn flags.
    """
    import uvicorn
    from app.core.logging import configure_logging

    configure_logging()
    cfg = get_config()
    uvicorn.run("app.main:app", host=cfg.api.host, port=cfg.api.port)
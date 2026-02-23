"""
FastAPI Application: Einstiegspunkt des Web-Layers.
Warum FastAPI: Automatische OpenAPI-Dokumentation, native async-Unterstützung,
Pydantic-Integration für typsichere Request/Response-Validierung.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from config.settings import PipelineConfig, setup_logging

# Logging einrichten
_config = PipelineConfig()
setup_logging(_config)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Churn Early Warning + Playbook Generator",
    description=(
        "Automatisiertes Churn-Frühwarnsystem: Customer Events → Risk Score + Playbook. "
        "Laden Sie eine CSV-Datei hoch und erhalten Sie sofort eine priorisierte "
        "Liste der gefährdeten Accounts mit konkreten Handlungsempfehlungen."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS: In Produktion auf spezifische Domains einschränken
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# API-Routen registrieren
app.include_router(router, prefix="/api")

# Statische Dateien (Frontend)
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Liefert das Single-Page-Frontend."""
    index_path = _static_dir / "index.html"
    if not index_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend nicht gefunden.")
    return FileResponse(str(index_path))


logger.info("FastAPI App initialisiert. Docs: http://localhost:8000/docs")

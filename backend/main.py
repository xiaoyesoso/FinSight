"""FastAPI application factory for the IIRAS backend.

Wires CORS, the `/health` endpoint and the research/upload/stream routes.
The config singleton is imported for its side effect of validating env vars
at import time, so a misconfigured deployment exits before serving traffic.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importing config validates environment variables eagerly (fail fast).
from backend.config import settings
from backend.api.upload import router as upload_router
from backend.api.research import router as research_router
from backend.api.sse import router as sse_router


def create_app() -> FastAPI:
    """Build the FastAPI application with CORS and routes registered."""
    app = FastAPI(
        title="IIRAS Backend",
        description="Intelligent Investment Research Agent System - multi-agent orchestration API",
        version="1.0.0",
    )

    # Allow the frontend origin(s) to call the API and consume SSE streams.
    # In development the Vite dev server may run on any localhost port, so we
    # allow all http://localhost:* origins via regex. Production should set a
    # specific FRONTEND_ORIGIN (which takes precedence over the regex).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Liveness probe used by task 7.1 validation.
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "model": settings.anthropic_model}

    # Register API routers.
    app.include_router(upload_router, prefix="/api")
    app.include_router(research_router, prefix="/api")
    app.include_router(sse_router, prefix="/api")

    return app


# ASGI entrypoint used by `uvicorn backend.main:app`.
app = create_app()

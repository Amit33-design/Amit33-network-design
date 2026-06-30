"""AlphaHunter AI — FastAPI application entrypoint.

Run locally:
    uvicorn backend.main:app --reload --port 8000
Then open http://localhost:8000/docs for the interactive API.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scheduler is opt-in (off in dev/test to avoid surprise network calls).
    if settings.alphahunter_env == "production":
        try:
            from backend.scheduler.jobs import start_scheduler, shutdown_scheduler
            start_scheduler()
            yield
            shutdown_scheduler()
            return
        except Exception:  # pragma: no cover
            logging.getLogger("alphahunter").warning("scheduler unavailable")
    yield


app = FastAPI(
    title="AlphaHunter AI",
    version="0.1.0",
    description="AI-powered stock discovery, scoring, options & portfolio intelligence.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "AlphaHunter AI",
        "version": "0.1.0",
        "docs": "/docs",
        "score_weights": settings.score_weights,
    }


@app.get("/health")
def health():
    return {"status": "ok"}

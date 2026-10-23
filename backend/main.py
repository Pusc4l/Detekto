"""DETEKTO :: backend/main.py
Run: uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from api import graph, health, interrogate, swarm, verdict, ws
from core.config import get_settings
from core.log_bus import bus
from services.health_probe import build_health_report
from services.log_bridge import redis_log_bridge
from services.ml_runtime import get_runtime
from services.sqlite_store import init_sqlite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("detekto")

_STATE_LEVEL = {"primary": "OK", "fallback": "WARN", "down": "ERROR"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    try:
        await asyncio.to_thread(init_sqlite, settings.sqlite_file)
    except Exception as exc:  # SQLite gagal tidak boleh menjatuhkan server
        log.warning("sqlite init gagal: %s", type(exc).__name__)

    await bus.emit("SYS", "BOOT", f"{settings.app_name} EDGE ENGINE v{settings.app_version} ONLINE")
    try:
        report = await build_health_report(settings)
        for svc in report.services:
            tag = "PRIMARY" if svc.state == "primary" else ("FALLBACK ENGAGED" if svc.state == "fallback" else "DOWN")
            await bus.emit(_STATE_LEVEL[svc.state], svc.key, f"{tag} → {svc.mode.upper()} // {svc.detail}")  # type: ignore[arg-type]
        await bus.emit("SYS", "BOOT", f"INFRA SCAN DONE: {report.primary_count} PRIMARY / {report.fallback_count} FALLBACK / {report.down_count} DOWN")
    except Exception as exc:
        log.warning("boot scan gagal: %s", type(exc).__name__)
    try:
        rt = await get_runtime()
        await bus.emit("SYS", "LEARNER", f"MODEL SGD SIAP // v{rt.learner.version} // SUMBER {rt.learner.source.upper()} // {rt.learner.n_samples} SAMPEL FEEDBACK // PENYIMPANAN {rt.store.storage_name.upper()}")
    except Exception as exc:
        log.warning("ml runtime gagal: %s", type(exc).__name__)
    bridge = asyncio.create_task(redis_log_bridge(settings))  # log Celery worker -> Live Terminal
    yield
    bridge.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await bridge
    await bus.emit("SYS", "BOOT", "ENGINE SHUTDOWN")


settings = get_settings()
app = FastAPI(title="DETEKTO Edge Engine", version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    """Tolak payload raksasa SEBELUM diparse (anti Memory-Exhaustion DoS)."""
    if request.method in ("POST", "PUT", "PATCH"):
        length = request.headers.get("content-length")
        if length is None:
            if "chunked" in request.headers.get("transfer-encoding", "").lower():
                return JSONResponse(status_code=411, content={"detail": {"code": "LENGTH_REQUIRED", "message": "CONTENT-LENGTH WAJIB ADA"}})
        elif not length.isdigit() or int(length) > settings.max_upload_bytes:
            return JSONResponse(status_code=413, content={"detail": {"code": "PAYLOAD_TOO_LARGE", "message": f"PAYLOAD MELEBIHI {settings.max_upload_bytes // 1_000_000} MB"}})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(health.router)
app.include_router(interrogate.router)
app.include_router(swarm.router)
app.include_router(verdict.router)
app.include_router(graph.router)
app.include_router(ws.router)

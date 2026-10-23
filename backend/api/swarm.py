"""DETEKTO :: api/swarm.py — Fase 4: kerahkan swarm, pantau dossier, ambil graph batch (Memgraph-ready)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path

from core.config import get_settings
from core.log_bus import bus
from models.interrogation import SESSION_ID_PATTERN
from models.swarm import GraphResponse, SwarmMeta, SwarmRequest, SwarmStatus
from workers.swarm_manager import (
    _load_phase3,
    build_jobs,
    choose_executor,
    dispatch_jobs,
    is_swarm_running,
    load_graph_response,
    load_meta,
    load_swarm_status,
    save_meta,
)
from datetime import datetime, timezone

router = APIRouter(prefix="/api", tags=["swarm"])
SessionPath = Annotated[str, Path(pattern=SESSION_ID_PATTERN)]


def _http(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@router.post("/interrogate/{session_id}/swarm", status_code=202)
async def launch_swarm(session_id: SessionPath, req: SwarmRequest, background: BackgroundTasks) -> dict[str, str | int]:
    phase3 = await _load_phase3(session_id)
    if phase3 is None:
        raise _http(404, "SESSION_NOT_FOUND", "SESI / HASIL FASE 3 TIDAK DITEMUKAN ATAU KEDALUWARSA — JALANKAN ULANG INTEROGASI")
    if phase3[1].status != "done" or not phase3[1].targets:
        raise _http(409, "NOT_READY", "ANALISIS FASE 3 BELUM SELESAI ATAU TIDAK MENEMUKAN TARGET")
    current = await load_swarm_status(session_id) if await load_meta(session_id) is not None else None
    if is_swarm_running(session_id) or (current is not None and current.status in ("queued", "running")):
        raise _http(409, "ALREADY_RUNNING", "SWARM UNTUK SESI INI SEDANG BERJALAN")

    jobs, skipped = build_jobs(session_id, phase3, req)
    if not jobs:
        raise _http(422, "NO_VALID_TARGET", "TIDAK ADA USERNAME TARGET YANG VALID UNTUK DISCRAPE")
    if skipped:
        await bus.emit("WARN", "SWARM", f"USERNAME TIDAK VALID DILEWATI: {', '.join(skipped)}")

    executor = await choose_executor()
    await save_meta(SwarmMeta(session_id=session_id, executor=executor, targets=[j.username for j in jobs], started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
    await dispatch_jobs(executor, jobs, background)
    return {"status": "queued", "executor": executor, "targets": len(jobs), "ttl_seconds": get_settings().result_ttl_seconds}


@router.get("/interrogate/{session_id}/swarm", response_model=SwarmStatus)
async def swarm_status(session_id: SessionPath) -> SwarmStatus:
    status = await load_swarm_status(session_id)
    if status is None:
        raise _http(404, "SWARM_NOT_FOUND", "SWARM BELUM DIJALANKAN ATAU SUDAH KEDALUWARSA")
    return status


@router.get("/interrogate/{session_id}/graph", response_model=GraphResponse)
async def swarm_graph(session_id: SessionPath) -> GraphResponse:
    resp = await load_graph_response(session_id)
    if resp is None:
        raise _http(409, "GRAPH_NOT_READY", "GRAPH BELUM SIAP — SWARM MASIH BERJALAN ATAU BELUM DIJALANKAN")
    return resp

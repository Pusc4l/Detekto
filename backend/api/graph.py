"""DETEKTO :: api/graph.py — Fase 6: GraphMap (+Patient Zero), uji beban graf, Hive-Mind sync, Takedown Dossier (PDF/HTML)."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response

from core.config import get_settings
from core.log_bus import bus
from models.graph import GraphMap, HiveSyncRequest, HiveSyncResult
from models.interrogation import SESSION_ID_PATTERN, AnalysisResult
from models.swarm import SwarmStatus
from models.verdict import VerdictSet
from services import dossier as dossier_svc
from services.ephemeral_vault import get_vault, k_swarm
from services.graph_mapper import build_graph_map, stress_batch, sync_to_memgraph, verdict_lookup
from services.hivemind_sync import sync_verdicts
from services.verdict_pipeline import load_session_verdicts
from workers.swarm_manager import _load_phase3, ensure_graph, load_swarm_status

router = APIRouter(prefix="/api", tags=["graph"])
SessionPath = Annotated[str, Path(pattern=SESSION_ID_PATTERN)]
_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"


def _http(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def _graph_map(sid: str) -> tuple[GraphMap, VerdictSet | None, SwarmStatus]:
    swarm = await load_swarm_status(sid)
    if swarm is None or swarm.status != "done":
        raise _http(409, "SWARM_NOT_DONE", "SWARM BELUM SELESAI / TIDAK DITEMUKAN — GRAPH BELUM BISA DIBANGUN")
    built = await ensure_graph(sid)
    if built is None:
        raise _http(409, "GRAPH_NOT_READY", "GRAPH BATCH BELUM SIAP")
    batch, mode = built
    vs = await load_session_verdicts(sid)
    gm = build_graph_map(batch, verdict_lookup(vs), mode)
    vault = get_vault()
    flag_key = k_swarm(sid, "enriched")
    flag = await vault.get(flag_key)
    if vs is not None and flag is None:
        # Pertama kali setelah verdict: tulis properti vonis + sentralitas + AMPLIFIES ke Memgraph (fallback otomatis ke NetworkX)
        new_mode = await sync_to_memgraph(batch, gm)
        await vault.put(flag_key, new_mode)
        gm.mode = new_mode  # type: ignore[assignment]
        await bus.emit("OK" if new_mode == "memgraph" else "WARN", "GRAPH", f"GRAPH DIPERKAYA VERDICT // MODE {new_mode.upper()}" + ("" if new_mode == "memgraph" else " (MEMGRAPH TIDAK TERJANGKAU → NETWORKX IN-MEMORY)"))
        if gm.patient_zero:
            await bus.emit("WARN", "GRAPH", f"PATIENT ZERO (KANDIDAT): {gm.patient_zero.name} // {gm.patient_zero.connected_buzzers} BUZZER TERHUBUNG")
    elif flag in ("memgraph", "networkx"):
        gm.mode = flag  # type: ignore[assignment]
    return gm, vs, swarm


@router.get("/interrogate/{session_id}/graphmap", response_model=GraphMap)
async def graph_map(session_id: SessionPath) -> GraphMap:
    return (await _graph_map(session_id))[0]


@router.get("/graph/stress", response_model=GraphMap)
async def graph_stress(nodes: int = Query(default=200, ge=20, le=1000), seed: int = Query(default=1, ge=0, le=10_000)) -> GraphMap:
    """Jaringan sintetis untuk uji beban render (Phantom A). Tidak menyentuh sesi atau Memgraph."""
    batch, lookup = await asyncio.to_thread(stress_batch, nodes, seed)
    return await asyncio.to_thread(build_graph_map, batch, lookup, "networkx")


@router.post("/interrogate/{session_id}/hive-sync", response_model=HiveSyncResult)
async def hive_sync(session_id: SessionPath, req: HiveSyncRequest) -> HiveSyncResult:
    """Kirim hash username + skor ke Hive-Mind. WAJIB persetujuan eksplisit (confirm=true)."""
    if not req.confirm:
        raise _http(422, "CONSENT_REQUIRED", "PERSETUJUAN EKSPLISIT DIPERLUKAN (confirm=true) SEBELUM MENGIRIM DATA KE HIVE-MIND")
    vs = await load_session_verdicts(session_id)
    if vs is None:
        raise _http(409, "VERDICT_NOT_READY", "VERDICT BELUM DIHITUNG")
    gm: GraphMap | None
    try:
        gm = (await _graph_map(session_id))[0]
    except HTTPException:
        gm = None
    result = await sync_verdicts(get_settings(), vs, gm)
    await bus.emit("OK", "HIVE", f"HIVE-MIND // {result.synced} BARIS VIA {result.mode.upper()} // PAYLOAD MAKS {result.max_payload_bytes} B (< 5 KB)")
    return result


async def _dossier_data(sid: str) -> tuple[dossier_svc.DossierData, GraphMap]:
    gm, vs, swarm = await _graph_map(sid)
    if vs is None:
        raise _http(409, "VERDICT_NOT_READY", "VERDICT BELUM DIHITUNG — JATUHKAN VERDICT SEBELUM MENGEKSPOR DOSSIER")
    phase3 = await _load_phase3(sid)
    if phase3 is None:
        raise _http(404, "SESSION_NOT_FOUND", "DATA FASE 3 KEDALUWARSA")
    result: AnalysisResult = phase3[1]
    data = await asyncio.to_thread(dossier_svc.assemble, sid, result, swarm, vs, gm, phase3[0].context_text)
    return data, gm


@router.get("/interrogate/{session_id}/dossier.pdf")
async def dossier_pdf(session_id: SessionPath) -> Response:
    data, gm = await _dossier_data(session_id)
    pdf = await asyncio.to_thread(dossier_svc.render_pdf, data, gm)
    await bus.emit("OK", "DOSSIER", f"TAKEDOWN DOSSIER PDF DIBUAT LOKAL // {len(pdf) // 1024} KB // SHA {data.integrity[:12].upper()} // MODE GRAF {gm.mode.upper()}")
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="detekto-dossier-{session_id[:8]}.pdf"', "Cache-Control": "no-store"})


@router.get("/interrogate/{session_id}/dossier.html")
async def dossier_html(session_id: SessionPath) -> Response:
    data, gm = await _dossier_data(session_id)
    body = await asyncio.to_thread(dossier_svc.render_html, data, gm)
    await bus.emit("OK", "DOSSIER", f"TAKEDOWN DOSSIER HTML DIBUAT LOKAL // SHA {data.integrity[:12].upper()}")
    return Response(
        content=body, media_type="text/html; charset=utf-8",
        headers={"Content-Security-Policy": _CSP, "Content-Disposition": f'attachment; filename="detekto-dossier-{session_id[:8]}.html"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )

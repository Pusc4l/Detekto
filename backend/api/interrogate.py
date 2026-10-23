"""DETEKTO :: api/interrogate.py — Task 3.1 Ephemeral Upload + pemicu & hasil analisis."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path

from core.config import get_settings
from core.log_bus import bus
from core.security import EvidenceRejected, decode_and_verify_image
from models.interrogation import (
    SESSION_ID_PATTERN,
    AnalysisResult,
    OcrStatus,
    SessionMeta,
    UploadEvidenceRequest,
    UploadEvidenceResponse,
)
from services.analysis_pipeline import is_running, run_analysis
from services.ephemeral_vault import VaultFullError, get_vault
from services.ocr_engine import engine_status

router = APIRouter(prefix="/api", tags=["interrogation"])

SessionPath = Annotated[str, Path(pattern=SESSION_ID_PATTERN)]
MAX_TOTAL_DECODED_BYTES = 40_000_000


def _http(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@router.post("/upload-evidence", response_model=UploadEvidenceResponse, status_code=201)
async def upload_evidence(req: UploadEvidenceRequest) -> UploadEvidenceResponse:
    """Terima Base64 -> validasi zero-trust -> simpan HANYA di vault RAM (Redis TTL 300s) -> kembalikan session_id."""
    settings = get_settings()
    vault = get_vault()

    media: dict[str, list[str]] = {"context": [], "evidence": []}
    hashes: dict[str, list[str]] = {"context": [], "evidence": []}
    total = 0
    try:
        for bucket, images in (("context", req.context_images), ("evidence", req.evidence_images)):
            for i, img in enumerate(images):
                label = f"{'KONTEKS' if bucket == 'context' else 'BUKTI'} #{i + 1}"
                data = await asyncio.to_thread(decode_and_verify_image, img.base64, img.sha256, label)
                total += len(data)
                del data
                if total > MAX_TOTAL_DECODED_BYTES:
                    raise EvidenceRejected("TOTAL", "TOTAL UKURAN BUKTI MELEBIHI 40 MB")
                media[bucket].append(img.base64)
                hashes[bucket].append(img.sha256.lower())
    except EvidenceRejected as exc:
        await bus.emit("ERROR", "SHIELD", f"UPLOAD DITOLAK [{exc.code}] {exc.message}")
        raise _http(422, exc.code, exc.message) from exc

    session_id = uuid.uuid4().hex
    meta = SessionMeta(
        session_id=session_id,
        platform=req.platform,
        post_url=req.post_url,
        context_text=req.context_text,
        context_hashes=hashes["context"],
        evidence_hashes=hashes["evidence"],
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    try:
        backend = await vault.create_session(meta, media)
    except VaultFullError as exc:
        await bus.emit("ERROR", "VAULT", "VAULT RAM PENUH — UPLOAD DITOLAK")
        raise _http(503, "VAULT_FULL", "VAULT RAM PENUH. TUNGGU TTL 5 MENIT ATAU NYALAKAN REDIS.") from exc
    finally:
        media.clear()

    await bus.emit(
        "OK", "VAULT",
        f"SESI {session_id[:8].upper()} DISIMPAN DI {backend.upper()} // {len(hashes['context'])} KONTEKS + {len(hashes['evidence'])} BUKTI // TTL {settings.redis_ttl_seconds}s // AUTO-PURGE",
    )
    return UploadEvidenceResponse(
        session_id=session_id,
        ttl_seconds=settings.redis_ttl_seconds,
        vault_backend=backend,
        accepted_context=len(hashes["context"]),
        accepted_evidence=len(hashes["evidence"]),
        total_bytes=total,
    )


@router.post("/interrogate/{session_id}/analyze", status_code=202)
async def analyze(session_id: SessionPath, background: BackgroundTasks) -> dict[str, str]:
    vault = get_vault()
    if is_running(session_id):
        raise _http(409, "ALREADY_RUNNING", "ANALISIS UNTUK SESI INI SEDANG BERJALAN")
    if await vault.load_meta(session_id) is None:
        raise _http(404, "SESSION_NOT_FOUND", "SESI TIDAK DITEMUKAN ATAU TTL 5 MENIT HABIS — UNGGAH ULANG BUKTI")
    queued = AnalysisResult(
        session_id=session_id, status="queued", started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    await vault.save_result(session_id, queued.model_dump_json())
    background.add_task(run_analysis, session_id)  # fallback tanpa Celery: BackgroundTasks + asyncio.gather
    return {"status": "queued", "session_id": session_id}


@router.get("/interrogate/{session_id}/result", response_model=AnalysisResult)
async def result(session_id: SessionPath) -> AnalysisResult:
    raw = await get_vault().load_result(session_id)
    if raw is None:
        raise _http(404, "RESULT_NOT_FOUND", "HASIL TIDAK ADA / SUDAH KEDALUWARSA")
    return AnalysisResult.model_validate_json(raw)


@router.delete("/interrogate/{session_id}")
async def purge(session_id: SessionPath) -> dict[str, int]:
    removed = await get_vault().purge_session(session_id)
    await bus.emit("SYS", "VAULT", f"SESI {session_id[:8].upper()} DIHAPUS MANUAL ({removed} KUNCI)")
    return {"removed": removed}


@router.get("/ocr/status", response_model=OcrStatus)
async def ocr_status() -> OcrStatus:
    return await asyncio.to_thread(engine_status)

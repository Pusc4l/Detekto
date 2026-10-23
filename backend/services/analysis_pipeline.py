"""DETEKTO :: services/analysis_pipeline.py — Orkestrator Fase 3 (OCR paralel + Ground Truth paralel + Auto-Purge)."""
from __future__ import annotations

import asyncio
import contextlib
import base64
import gc
from datetime import datetime, timezone

from core.log_bus import bus
from models.interrogation import AnalysisResult, OcrPage, SessionMeta, TargetEntity
from services.context_parser import INJECTION_NOTICE, build_ground_truth
from services.ephemeral_vault import EphemeralVault, get_vault
from services.ocr_engine import OcrUnavailableError, ocr_image, split_targets
from core.security import scan_injection

_running: set[str] = set()


def is_running(session_id: str) -> bool:
    return session_id in _running


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _log(level: str, source: str, message: str) -> None:
    await bus.emit(level, source, message)  # type: ignore[arg-type]


async def _publish(vault: EphemeralVault, result: AnalysisResult) -> None:
    await vault.save_result(result.session_id, result.model_dump_json())


async def _ocr_one(vault: EphemeralVault, b64: str | None, sha: str, label: str, warnings: list[str]) -> OcrPage | None:
    """OCR satu gambar dengan Smart Hashing: hasil teks di-cache per SHA-256 (gambar sama tidak diproses ulang)."""
    cached = await vault.cache_get(sha)
    if cached:
        await _log("INFO", "OCR", f"{label} // CACHE HIT (SHA {sha[:8].upper()}) — OCR DILEWATI")
        return OcrPage.model_validate_json(cached)
    if b64 is None:
        warnings.append(f"{label}: BUFFER KEDALUWARSA (TTL HABIS)")
        return None
    data = base64.b64decode(b64)
    try:
        page = await ocr_image(data)
    finally:
        del data
    await vault.cache_set(sha, page.model_dump_json())
    return page


async def _ocr_bucket(
    vault: EphemeralVault, meta: SessionMeta, bucket: str, warnings: list[str]
) -> list[OcrPage | None]:
    hashes = meta.context_hashes if bucket == "context" else meta.evidence_hashes
    if not hashes:
        return []
    media = await vault.load_media(meta.session_id, bucket, len(hashes))
    tag = "CTX" if bucket == "context" else "EVD"
    pages = await asyncio.gather(
        *(_ocr_one(vault, media[i], hashes[i], f"{tag} #{i + 1}", warnings) for i in range(len(hashes)))
    )
    media.clear()
    for i, page in enumerate(pages):
        label = f"{tag} #{i + 1}"
        if page is None:
            continue
        if not page.lines:
            warnings.append(f"{label}: TIDAK ADA TEKS TERBACA (GAMBAR BURAM/KOSONG)")
            await _log("WARN", "OCR", f"{label} // TIDAK ADA TEKS TERBACA — DILEWATI")
        else:
            if page.mean_conf < 45:
                warnings.append(f"{label}: KUALITAS OCR RENDAH ({page.mean_conf:.0f}%)")
            await _log("OK", "OCR", f"{label} // {page.engine.upper()} // {len(page.lines)} BARIS // CONF {page.mean_conf:.0f}%")
    return list(pages)


def _context_ocr_text(pages: list[OcrPage | None]) -> str:
    return "\n".join(line.text for p in pages if p for line in p.lines)


async def _log_targets(targets: list[TargetEntity]) -> None:
    if not targets:
        await _log("WARN", "SPLIT", "TIDAK ADA USERNAME KOMENTATOR TERDETEKSI DI SCREENSHOT")
        return
    await _log("OK", "SPLIT", f"{len(targets)} TARGET UNIK TERDETEKSI: " + ", ".join(f"@{t.username}" for t in targets[:8]))
    for t in targets[:5]:
        await _log("INFO", "TARGET", f"@{t.username} // {t.comment_count} KOMENTAR // {t.total_likes} LIKES // GAMBAR {','.join(str(i + 1) for i in t.image_indexes)}")
        for c in t.comments[:2]:
            body = f"⚠ {INJECTION_NOTICE}" if c.injection_flag else c.text[:110]
            await _log("WARN" if c.injection_flag else "INFO", "TARGET", f'  @{t.username} > "{body}" [{c.likes} LIKES]')


async def run_analysis(session_id: str) -> None:
    """Task latar belakang (FastAPI BackgroundTasks). TIDAK PERNAH melempar exception ke server."""
    if session_id in _running:
        return
    _running.add(session_id)
    vault = get_vault()
    result = AnalysisResult(session_id=session_id, status="running", started_at=_now())
    meta: SessionMeta | None = None
    try:
        meta = await vault.load_meta(session_id)
        if meta is None:
            result.status, result.error = "error", "SESI TIDAK DITEMUKAN / TTL 5 MENIT HABIS — UNGGAH ULANG BUKTI"
            result.finished_at = _now()
            await _publish(vault, result)
            await _log("ERROR", "PIPELINE", f"SESI {session_id[:8].upper()} KEDALUWARSA")
            return

        result.context_image_count, result.evidence_image_count = len(meta.context_hashes), len(meta.evidence_hashes)
        await _publish(vault, result)
        await _log("SYS", "PIPELINE", f"SESI {session_id[:8].upper()} // {meta.platform.upper()} // {result.context_image_count} KONTEKS + {result.evidence_image_count} BUKTI")

        # Tahap A: OCR konteks (dibutuhkan Ground Truth)
        ctx_pages: list[OcrPage | None] = []
        try:
            ctx_pages = await _ocr_bucket(vault, meta, "context", result.warnings)
        except OcrUnavailableError as exc:
            result.warnings.append("OCR KONTEKS DILEWATI: " + str(exc)[:120])
            await _log("ERROR", "OCR", str(exc)[:300])

        # Tahap B: OCR bukti komentar ‖ Ground Truth RAG (paralel)
        ev_task = _ocr_bucket(vault, meta, "evidence", result.warnings)
        gt_task = build_ground_truth(
            context_text=meta.context_text, context_ocr_text=_context_ocr_text(ctx_pages), platform=meta.platform, log=_log
        )
        ev_res, gt_res = await asyncio.gather(ev_task, gt_task, return_exceptions=True)

        if not isinstance(gt_res, BaseException):
            result.ground_truth = gt_res
        else:
            result.warnings.append(f"GROUND TRUTH GAGAL ({type(gt_res).__name__})")
            await _log("ERROR", "RAG", f"GROUND TRUTH GAGAL ({type(gt_res).__name__})")

        if isinstance(ev_res, OcrUnavailableError):
            result.status, result.error = "error", str(ev_res)[:400]
            await _log("ERROR", "OCR", str(ev_res)[:400])
        elif isinstance(ev_res, BaseException):
            result.status, result.error = "error", f"OCR GAGAL ({type(ev_res).__name__})"
            await _log("ERROR", "OCR", result.error)
        else:
            engines = {p.engine for p in [*ctx_pages, *ev_res] if p}
            result.ocr_engine = "+".join(sorted(engines)) or None
            result.targets = split_targets([p if p else OcrPage(engine="tesseract", lines=[], mean_conf=0.0) for p in ev_res])
            await _log_targets(result.targets)
            if any(t.injection_flag for t in result.targets):
                result.warnings.append("KOMENTAR BERISI PERINTAH INJEKSI TERDETEKSI (DITANDAI SEBAGAI SINYAL MENCURIGAKAN)")
                await _log("WARN", "SHIELD", "KOMENTAR BERPOLA PROMPT-INJECTION DITANDAI — TIDAK PERNAH DIKIRIM KE LLM")
            result.status = "done"
    except Exception as exc:  # jaring pengaman terakhir: server tidak boleh crash
        result.status, result.error = "error", f"KEGAGALAN INTERNAL ({type(exc).__name__})"
        await _log("ERROR", "PIPELINE", result.error)
    finally:
        if meta is not None:
            try:
                removed = await vault.purge_session_media(session_id)
                result.media_purged = True
                await _log("OK", "VAULT", f"ZERO-BLOAT: {removed} BUFFER GAMBAR DIHANCURKAN DARI RAM (DEL + gc.collect)")
            except Exception as exc:
                await _log("ERROR", "VAULT", f"PURGE GAGAL ({type(exc).__name__}) — TTL 300s TETAP MENGHAPUS OTOMATIS")
        result.finished_at = _now()
        with contextlib.suppress(Exception):  # gagal menyimpan hasil akhir tidak boleh menjatuhkan task
            await _publish(vault, result)
        _running.discard(session_id)
        gc.collect()
        await _log("SYS" if result.status == "done" else "ERROR", "PIPELINE", f"ANALISIS {result.status.upper()} // {len(result.targets)} TARGET")

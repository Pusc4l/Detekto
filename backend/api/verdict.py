"""DETEKTO :: api/verdict.py — Fase 5: Verdict, Feedback (online learning), sampel & status model."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path

from core.log_bus import bus
from models.interrogation import SESSION_ID_PATTERN
from models.verdict import (
    EvidenceIn,
    FeedbackRequest,
    FeedbackResponse,
    ModelStatus,
    SampleRequest,
    VerdictSet,
    WeightEntry,
)
from services import verdict as V
from services.ml_runtime import get_runtime
from services.verdict_pipeline import build_card, compute_session_verdicts, features_from_sample, load_session_verdicts

router = APIRouter(prefix="/api", tags=["verdict"])
SessionPath = Annotated[str, Path(pattern=SESSION_ID_PATTERN)]
_feedback_lock = asyncio.Lock()  # check-then-fit-then-save atomik: feedback ganda tidak bisa melatih model dua kali


def _http(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@router.post("/interrogate/{session_id}/verdict", response_model=VerdictSet)
async def compute_verdict(session_id: SessionPath) -> VerdictSet:
    try:
        return await compute_session_verdicts(session_id)
    except LookupError as exc:
        raise _http(404, "NOT_FOUND", str(exc)) from exc
    except RuntimeError as exc:
        raise _http(409, "NOT_READY", f"{exc} — JALANKAN SWARM DULU DAN TUNGGU STATUS DONE") from exc


@router.get("/interrogate/{session_id}/verdict", response_model=VerdictSet)
async def get_verdict(session_id: SessionPath) -> VerdictSet:
    vs = await load_session_verdicts(session_id)
    if vs is None:
        raise _http(404, "VERDICT_NOT_FOUND", "VERDICT BELUM DIHITUNG ATAU KEDALUWARSA")
    return vs


@router.post("/verdict/sample", response_model=VerdictSet)
async def verdict_sample(req: SampleRequest) -> VerdictSet:
    """Uji perhitungan verdict pada sampel fitur langsung (tanpa sesi/scraping). verdict_id yang dihasilkan valid untuk /feedback."""
    from datetime import datetime, timezone

    card = await build_card(
        username=req.username, platform=req.platform, features=features_from_sample(req.features), evidence=req.evidence, nlp=None,
        warnings=["Verdict dari SAMPEL manual, bukan hasil investigasi."],
    )
    rt = await get_runtime()
    return VerdictSet(
        session_id="0" * 32, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), threshold=round(V.threshold() * 100, 1),
        model_version=rt.learner.version, media_purged=True, cards=[card],
    )


@router.post("/interrogate/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest, background: BackgroundTasks) -> FeedbackResponse:
    """AKURAT / MELESET -> label koreksi -> SGDClassifier.partial_fit() seketika -> simpan bobot (SQLite + Supabase) -> prediksi baru."""
    rt = await get_runtime()
    if not rt.store.feedback_allowed():
        raise _http(429, "RATE_LIMITED", "TERLALU BANYAK FEEDBACK — TUNGGU SEBENTAR")
    async with _feedback_lock:
        row = await asyncio.to_thread(rt.store.load_verdict, req.verdict_id)
        if row is None:
            raise _http(404, "VERDICT_UNKNOWN", "VERDICT_ID TIDAK DIKENAL (TIDAK PERNAH DIHITUNG DI PERANGKAT INI)")
        if await asyncio.to_thread(rt.store.has_feedback, req.verdict_id):
            raise _http(409, "FEEDBACK_EXISTS", "FEEDBACK UNTUK VERDICT INI SUDAH PERNAH DIKIRIM")

        was_buzzer = row["verdict"] == "BUZZER"
        label = 1 if was_buzzer == (req.feedback == "accurate") else 0
        x = rt.learner.vector(row["features"])
        before, after, v_before, v_after, ms = await asyncio.to_thread(rt.learner.partial_fit, x, label)
        await asyncio.to_thread(rt.store.save_feedback, req.verdict_id, label, req.feedback, v_before, v_after)

    evidence = EvidenceIn.model_validate(row["evidence"])
    gate = V.evaluate_gate(row["features"], evidence)
    final_after, buzzer_after = V.apply_dictator(after, gate)
    version, n, payload = rt.learner.snapshot_for_sync
    background.add_task(rt.store.push_remote_state, version, n, payload)  # sinkronisasi Supabase best-effort
    await bus.emit(
        "OK", "LEARNER",
        f"FEEDBACK {req.feedback.upper()} @ {req.verdict_id[:8].upper()} → partial_fit({'BUZZER' if label else 'ORGANIC'}) // v{v_before}→v{v_after} // {ms:.1f} ms // P {before * 100:.1f}%→{after * 100:.1f}%",
    )
    return FeedbackResponse(
        verdict_id=req.verdict_id, applied_label="BUZZER" if label else "ORGANIC", model_version_before=v_before, model_version_after=v_after,
        # presisi 3 desimal: langkah SGD tetap terlihat saat skor jenuh mendekati 100%
        raw_score_before=round(before * 100, 3), raw_score_after=round(after * 100, 3),
        score_after=V.display_percent(final_after), verdict_after="BUZZER" if buzzer_after else "ORGANIC",
        update_ms=round(ms, 2), n_samples=n,
    )


@router.get("/model", response_model=ModelStatus)
async def model_status() -> ModelStatus:
    rt = await get_runtime()
    w, b = rt.learner.weights()
    from models.verdict import FEATURE_NAMES

    return ModelStatus(
        version=rt.learner.version, n_samples=rt.learner.n_samples, source=rt.learner.source,  # type: ignore[arg-type]
        storage=rt.store.storage_name,  # type: ignore[arg-type]
        weights=[WeightEntry(name=n, weight=round(x, 4)) for n, x in zip(FEATURE_NAMES, w)], intercept=round(b, 4),
        threshold=round(V.threshold() * 100, 1), updated_at=rt.learner.updated_at,
    )

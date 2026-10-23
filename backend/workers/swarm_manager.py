"""DETEKTO :: workers/swarm_manager.py — Parallel Swarm Queue (Task 4.1)

Eksekutor:
  1) Celery + Redis  -> worker Windows:  celery -A workers.swarm_manager.celery_app worker --pool=threads --concurrency=3 -l info
                                         (atau --pool=solo). Dipakai otomatis bila CELERY_ENABLED=true DAN ada worker yang merespons ping.
  2) FALLBACK        -> FastAPI BackgroundTasks + asyncio.gather (satu browser, banyak context) — nol konfigurasi.
Semua kerja Playwright berjalan di loop terisolasi (core/loop_runner) -> aman dengan uvicorn --reload di Windows.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Any, AsyncContextManager, Callable, Protocol

import redis as redis_sync
from fastapi import BackgroundTasks

from core.config import Settings, get_settings
from core.log_bus import bus, make_event
from core.loop_runner import MainLoopBridge, run_in_fresh_loop, run_in_thread_loop
from models.interrogation import AnalysisResult, SessionMeta
from models.swarm import (
    Executor,
    GraphBatch,
    GraphResponse,
    SwarmMeta,
    SwarmRequest,
    SwarmStatus,
    TargetDossier,
    TargetJob,
)
from services.ephemeral_vault import EphemeralVault, get_vault, k_swarm
from services.graph_export import build_graph, push_to_memgraph, to_cypher, to_force_graph
from services.log_bridge import LOG_CHANNEL
from services.osint_scraper import PageSource, ScraperUnavailable, SwarmBrowser, UnavailableSource, USERNAME_RE, investigate_target

_running: set[str] = set()
_graph_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================== Celery app (opsional) ==============================
def _make_celery(settings: Settings) -> Any | None:
    try:
        from celery import Celery
    except ImportError:
        return None
    app = Celery("detekto", broker=settings.redis_url, backend=None)
    app.conf.update(
        task_serializer="json", accept_content=["json"], task_ignore_result=True,
        broker_connection_retry_on_startup=True, worker_prefetch_multiplier=1,
        task_soft_time_limit=settings.swarm_job_timeout_seconds, task_time_limit=settings.swarm_job_timeout_seconds + 30,
    )
    return app


celery_app: Any | None = _make_celery(get_settings())


# ===================================== Sinks =====================================
class Sink(Protocol):
    async def log(self, level: str, source: str, message: str) -> None: ...
    async def save(self, session_id: str, dossier: TargetDossier) -> None: ...


class MainLoopSink:
    """Dipakai eksekutor in-process: menjembatani loop terisolasi -> vault async & LogBus di loop utama."""

    def __init__(self, bridge: MainLoopBridge, vault: EphemeralVault) -> None:
        self._bridge, self._vault = bridge, vault

    async def log(self, level: str, source: str, message: str) -> None:
        with contextlib.suppress(Exception):
            await self._bridge.call(bus.emit(level, source, message))  # type: ignore[arg-type]

    async def save(self, session_id: str, dossier: TargetDossier) -> None:
        await self._bridge.call(self._vault.put(k_swarm(session_id, f"t:{dossier.username}"), dossier.model_dump_json()))


class CelerySink:
    """Dipakai di proses worker Celery: Redis sinkron (publish log + simpan dossier)."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._r = redis_sync.Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=5)

    async def log(self, level: str, source: str, message: str) -> None:
        event = make_event(level, source, message)  # type: ignore[arg-type]
        with contextlib.suppress(Exception):
            await asyncio.to_thread(self._r.publish, LOG_CHANNEL, event.model_dump_json())

    async def save(self, session_id: str, dossier: TargetDossier) -> None:
        await asyncio.to_thread(self._r.set, k_swarm(session_id, f"t:{dossier.username}"), dossier.model_dump_json(), ex=self._s.result_ttl_seconds)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._r.close()


# ================================= inti eksekusi =================================
SourceFactory = Callable[[], AsyncContextManager[PageSource]]


def playwright_source_factory() -> AsyncContextManager[PageSource]:
    return SwarmBrowser()  # type: ignore[return-value]


async def run_jobs(jobs: list[TargetJob], sink: Sink, source_factory: SourceFactory, concurrency: int) -> None:
    """Jalankan semua job paralel di loop saat ini. Seluruh kegagalan menjadi dossier ber-state error (zero-crash).
    Bila browser tidak tersedia: mode degradasi (UnavailableSource) — intel non-browser tetap dikumpulkan."""
    cm = source_factory()
    entered = False
    try:
        source: PageSource = await cm.__aenter__()
        entered = True
    except ScraperUnavailable as exc:
        await sink.log("ERROR", "SWARM", f"{exc} — MODE DEGRADASI: HANYA INTEL NON-BROWSER (KOMENTAR + DORKING)")
        source = UnavailableSource(str(exc))
    except Exception as exc:
        await sink.log("ERROR", "SWARM", f"BROWSER GAGAL START ({type(exc).__name__}) — MODE DEGRADASI")
        source = UnavailableSource(f"BROWSER GAGAL START ({type(exc).__name__})")

    try:
        sem = asyncio.Semaphore(concurrency)

        async def one(job: TargetJob) -> None:
            async with sem:
                await sink.save(job.session_id, TargetDossier(username=job.username, platform=job.platform, state="running", started_at=_now()))
                dossier = await investigate_target(source, job, sink.log)
                await sink.save(job.session_id, dossier)
                await sink.log(
                    "OK" if dossier.state in ("done", "private", "login_wall") else "WARN", "SWARM",
                    f"@{job.username} // SELESAI: {dossier.state.upper()} // {len(dossier.syndicate_links)} TAUTAN SINDIKAT",
                )

        await asyncio.gather(*(one(j) for j in jobs))
    finally:
        if entered:
            with contextlib.suppress(Exception):
                await cm.__aexit__(None, None, None)


if celery_app is not None:

    @celery_app.task(name="detekto.investigate_target", acks_late=True)
    def investigate_target_task(payload: dict[str, Any]) -> None:
        """Task Celery per-target (dijalankan di thread/proses worker). Loop terisolasi dibuat per task."""
        settings = get_settings()
        job = TargetJob.model_validate(payload)
        sink = CelerySink(settings)
        try:
            run_in_fresh_loop(lambda: run_jobs([job], sink, playwright_source_factory, 1))
        finally:
            sink.close()


# ================================ dispatch & status ================================
async def choose_executor() -> Executor:
    s = get_settings()
    if celery_app is None or not s.celery_enabled:
        return "background-tasks"

    def ping() -> bool:
        return bool(celery_app.control.inspect(timeout=1.0).ping())  # type: ignore[union-attr]

    try:
        return "celery" if await asyncio.to_thread(ping) else "background-tasks"
    except Exception:
        return "background-tasks"


async def run_swarm_background(jobs: list[TargetJob]) -> None:
    """Fallback in-process (BackgroundTasks): satu browser + asyncio.gather; tidak pernah melempar exception."""
    s = get_settings()
    vault = get_vault()
    sid = jobs[0].session_id
    sink = MainLoopSink(MainLoopBridge(asyncio.get_running_loop()), vault)
    _running.add(sid)
    try:
        await bus.emit("SYS", "SWARM", f"{len(jobs)} TARGET DIKERAHKAN // EXECUTOR: BACKGROUND-TASKS + asyncio.gather // MAKS {s.swarm_max_browser_concurrency} BROWSER CONTEXT")
        await asyncio.wait_for(
            run_in_thread_loop(lambda: run_jobs(jobs, sink, playwright_source_factory, s.swarm_max_browser_concurrency)),
            timeout=s.swarm_job_timeout_seconds,
        )
    except asyncio.TimeoutError:
        await bus.emit("ERROR", "SWARM", f"SWARM MELEBIHI BATAS {s.swarm_job_timeout_seconds}s — HASIL PARSIAL DISIMPAN")
    except Exception as exc:
        await bus.emit("ERROR", "SWARM", f"SWARM GAGAL ({type(exc).__name__})")
    finally:
        _running.discard(sid)
        with contextlib.suppress(Exception):
            await ensure_graph(sid)


async def dispatch_jobs(executor: Executor, jobs: list[TargetJob], background: BackgroundTasks) -> None:
    if executor == "celery" and celery_app is not None:
        app = celery_app
        await bus.emit("SYS", "SWARM", f"{len(jobs)} TASK DIKIRIM KE CELERY WORKER (REDIS BROKER)")

        def publish() -> None:
            for job in jobs:
                app.send_task("detekto.investigate_target", args=[job.model_dump()])

        await asyncio.to_thread(publish)
    else:
        background.add_task(run_swarm_background, jobs)


def is_swarm_running(session_id: str) -> bool:
    return session_id in _running


async def save_meta(meta: SwarmMeta) -> None:
    await get_vault().put(k_swarm(meta.session_id, "meta"), meta.model_dump_json())


async def load_meta(sid: str) -> SwarmMeta | None:
    raw = await get_vault().get(k_swarm(sid, "meta"))
    return SwarmMeta.model_validate_json(raw) if raw else None


async def load_swarm_status(sid: str) -> SwarmStatus | None:
    s = get_settings()
    meta = await load_meta(sid)
    if meta is None:
        return None
    raws = await get_vault().get_many([k_swarm(sid, f"t:{u}") for u in meta.targets])
    dossiers = [TargetDossier.model_validate_json(r) for r in raws if r]
    finished = [d for d in dossiers if d.state not in ("queued", "running")]
    all_done = len(finished) == len(meta.targets)
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(meta.started_at)).total_seconds()
    error: str | None = None
    if all_done:
        status = "done"
    elif elapsed > s.swarm_job_timeout_seconds and not is_swarm_running(sid):
        status, error = "error", "WORKER TIDAK MERESPONS / TIMEOUT — PERIKSA CELERY WORKER ATAU JALANKAN ULANG"
    else:
        status = "running" if dossiers else "queued"
    graph_summary: dict[str, int | str] | None = None
    if status == "done":
        graph = await ensure_graph(sid)
        if graph is not None:
            graph_summary = {"nodes": len(graph[0].nodes), "edges": len(graph[0].edges), "mode": graph[1]}
    return SwarmStatus(
        session_id=sid, status=status, executor=meta.executor, targets=meta.targets, dossiers=dossiers,  # type: ignore[arg-type]
        started_at=meta.started_at, finished_at=max((d.finished_at for d in finished if d.finished_at), default=None) if all_done else None,
        error=error, graph_summary=graph_summary,
    )


async def _load_phase3(sid: str) -> tuple[SessionMeta, AnalysisResult] | None:
    vault = get_vault()
    meta = await vault.load_meta(sid)
    raw = await vault.load_result(sid)
    if meta is None or raw is None:
        return None
    return meta, AnalysisResult.model_validate_json(raw)


async def ensure_graph(sid: str) -> tuple[GraphBatch, str] | None:
    """Bangun GraphBatch sekali (idempoten), dorong ke Memgraph bila aktif, simpan di vault. Mode: memgraph | networkx."""
    vault = get_vault()
    async with _graph_lock:
        cached = await vault.get(k_swarm(sid, "graph"))
        if cached:
            import json

            data = json.loads(cached)
            return GraphBatch.model_validate(data["batch"]), str(data["mode"])
        meta = await load_meta(sid)
        phase3 = await _load_phase3(sid)
        if meta is None or phase3 is None:
            return None
        raws = await vault.get_many([k_swarm(sid, f"t:{u}") for u in meta.targets])
        dossiers = [TargetDossier.model_validate_json(r) for r in raws if r]
        if len(dossiers) < len(meta.targets) or any(d.state in ("queued", "running") for d in dossiers):
            return None
        batch = build_graph(sid, phase3[0].platform, dossiers, phase3[1].targets)
        mode = "memgraph" if await push_to_memgraph(batch, get_settings()) else "networkx"
        import json

        await vault.put(k_swarm(sid, "graph"), json.dumps({"batch": batch.model_dump(), "mode": mode}))
        await bus.emit("OK", "GRAPH", f"GRAPH BATCH SIAP: {len(batch.nodes)} NODE / {len(batch.edges)} EDGE // MODE {mode.upper()}")
        return batch, mode


async def load_graph_response(sid: str) -> GraphResponse | None:
    result = await ensure_graph(sid)
    if result is None:
        return None
    batch, mode = result
    return GraphResponse(batch=batch, cypher=to_cypher(batch), force_graph=to_force_graph(batch), graph_mode=mode)  # type: ignore[arg-type]


def build_jobs(session_id: str, phase3: tuple[SessionMeta, AnalysisResult], req: SwarmRequest) -> tuple[list[TargetJob], list[str]]:
    meta, result = phase3
    selected = result.targets[: req.max_targets]
    keywords = result.ground_truth.dorking_keywords[:3] if result.ground_truth else []
    jobs: list[TargetJob] = []
    skipped: list[str] = []
    for t in selected:
        if not USERNAME_RE.match(t.username):
            skipped.append(t.username)
            continue
        peers = {o.username: [c.text for c in o.comments][:10] for o in selected if o.username != t.username}
        jobs.append(
            TargetJob(
                session_id=session_id, platform=meta.platform, username=t.username,
                comments=[c.text for c in t.comments][:20], co_targets=[o.username for o in selected if o.username != t.username],
                peer_comments=dict(list(peers.items())[:4]), keywords=keywords, post_url=meta.post_url,
                force_reverse_image=req.force_reverse_image,
            )
        )
    return jobs, skipped

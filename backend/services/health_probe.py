"""DETEKTO :: services/health_probe.py
Probe seluruh service + Auto-Fallback resolver. Setiap probe DIJAMIN tidak melempar exception
(Zero-Crash Guarantee). Detail error hanya memuat nama kelas exception, tidak pernah URL/kredensial.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx
import redis.asyncio as aioredis

from core.config import Settings
from models.schemas import HealthReport, ServiceStatus
from services.ocr_engine import find_tesseract
from services.sqlite_store import check_sqlite

_searx_cache: tuple[float, ServiceStatus] | None = None
_SEARX_TTL_OK_S = 60.0
_SEARX_TTL_FAIL_S = 5.0


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------- Redis
async def probe_redis(s: Settings) -> ServiceStatus:
    start = time.perf_counter()
    client: aioredis.Redis | None = None
    try:
        client = aioredis.from_url(
            s.redis_url,
            socket_connect_timeout=s.probe_timeout_seconds,
            socket_timeout=s.probe_timeout_seconds,
        )
        await client.ping()
        return ServiceStatus(
            key="redis", label="REDIS // RAM VAULT", state="primary", mode="redis",
            detail=f"Ephemeral buffer aktif · TTL {s.redis_ttl_seconds}s · tanpa persistensi disk",
            latency_ms=_ms(start),
        )
    except Exception as exc:
        return ServiceStatus(
            key="redis", label="REDIS // RAM VAULT", state="fallback", mode="in-process-ttl",
            detail=f"Redis offline ({type(exc).__name__}) → vault TTL in-process aktif",
        )
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                await client.aclose()


# -------------------------------------------------------------- SearxNG
def _searx_fallback(reason: str) -> ServiceStatus:
    if _has_module("duckduckgo_search") or _has_module("ddgs"):
        return ServiceStatus(
            key="searxng", label="SEARXNG // FACT-FINDER", state="fallback", mode="duckduckgo-search",
            detail=f"SearxNG tidak siap ({reason}) → library duckduckgo-search",
        )
    return ServiceStatus(
        key="searxng", label="SEARXNG // FACT-FINDER", state="down", mode="none",
        detail=f"SearxNG tidak siap ({reason}) dan duckduckgo-search belum terpasang: pip install duckduckgo-search",
    )


async def probe_searxng(s: Settings) -> ServiceStatus:
    global _searx_cache
    now = time.monotonic()
    if _searx_cache is not None:
        age = now - _searx_cache[0]
        ttl = _SEARX_TTL_OK_S if _searx_cache[1].state == "primary" else _SEARX_TTL_FAIL_S
        if age < ttl:
            return _searx_cache[1]

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=max(s.probe_timeout_seconds, 4.0)) as client:
            resp = await client.get(
                f"{s.searxng_url.rstrip('/')}/search", params={"q": "detekto", "format": "json"}
            )
        if resp.status_code == 200 and "json" in resp.headers.get("content-type", ""):
            result = ServiceStatus(
                key="searxng", label="SEARXNG // FACT-FINDER", state="primary", mode="searxng",
                detail="Meta-search lokal aktif · format JSON diaktifkan",
                latency_ms=_ms(start),
            )
        else:
            result = _searx_fallback(f"HTTP {resp.status_code}")
    except Exception as exc:
        result = _searx_fallback(type(exc).__name__)
    _searx_cache = (now, result)
    return result


# ------------------------------------------------------------- Memgraph
async def probe_memgraph(s: Settings) -> ServiceStatus:
    start = time.perf_counter()
    writer: asyncio.StreamWriter | None = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(s.memgraph_host, s.memgraph_port), timeout=s.probe_timeout_seconds
        )
        return ServiceStatus(
            key="memgraph", label="MEMGRAPH // GRAPH DB", state="primary", mode="memgraph",
            detail=f"Bolt port {s.memgraph_port} terbuka · PageRank/Cypher siap",
            latency_ms=_ms(start),
        )
    except Exception as exc:
        if _has_module("networkx"):
            return ServiceStatus(
                key="memgraph", label="MEMGRAPH // GRAPH DB", state="fallback", mode="networkx",
                detail=f"Memgraph offline ({type(exc).__name__}) → NetworkX in-memory graph",
            )
        return ServiceStatus(
            key="memgraph", label="MEMGRAPH // GRAPH DB", state="down", mode="none",
            detail="Memgraph offline dan networkx belum terpasang: pip install networkx",
        )
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


# -------------------------------------------------------------- Hive-Mind
async def probe_hivemind(s: Settings) -> ServiceStatus:
    start = time.perf_counter()
    reason = ""
    if s.supabase_configured:
        try:
            async with httpx.AsyncClient(timeout=max(s.probe_timeout_seconds, 3.0)) as client:
                resp = await client.get(
                    f"{s.supabase_url.rstrip('/')}/auth/v1/health", headers={"apikey": s.supabase_key}
                )
            if resp.status_code == 200:
                return ServiceStatus(
                    key="hivemind", label="HIVE-MIND // PERSISTENCE", state="primary", mode="supabase",
                    detail="Supabase PostgreSQL terjangkau · payload < 5 KB",
                    latency_ms=_ms(start),
                )
            reason = f"HTTP {resp.status_code}"
        except Exception as exc:
            reason = type(exc).__name__

    ok, info = await asyncio.to_thread(check_sqlite, s.sqlite_file)
    prefix = f"Supabase gagal ({reason}) → " if reason else "Supabase belum dikonfigurasi → "
    if ok:
        return ServiceStatus(
            key="hivemind", label="HIVE-MIND // PERSISTENCE", state="fallback", mode="sqlite",
            detail=f"{prefix}SQLite lokal ({info})", latency_ms=_ms(start),
        )
    return ServiceStatus(
        key="hivemind", label="HIVE-MIND // PERSISTENCE", state="down", mode="none",
        detail=f"{prefix}SQLite gagal dibuka ({info})",
    )


# ------------------------------------------------------------------ LLM
async def probe_llm(s: Settings) -> ServiceStatus:
    if s.groq_api_key:
        return ServiceStatus(
            key="llm", label="LLM // RAG & DOM PARSER", state="primary", mode="groq",
            detail="API key Groq terdeteksi · llama-3.3-70b-versatile / llama-3.1-8b-instant",
        )
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=s.probe_timeout_seconds) as client:
            resp = await client.get(f"{s.ollama_url.rstrip('/')}/api/tags")
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            count = len(models) if isinstance(models, list) else 0
            return ServiceStatus(
                key="llm", label="LLM // RAG & DOM PARSER", state="fallback", mode="ollama",
                detail=f"Groq belum dikonfigurasi → Ollama lokal ({count} model terpasang)",
                latency_ms=_ms(start),
            )
        reason = f"HTTP {resp.status_code}"
    except Exception as exc:
        reason = type(exc).__name__
    return ServiceStatus(
        key="llm", label="LLM // RAG & DOM PARSER", state="fallback", mode="heuristic-regex",
        detail=f"Groq & Ollama tidak tersedia ({reason}) → heuristic regex parser darurat",
    )


# ------------------------------------------------------------------ OCR
async def probe_ocr(_: Settings) -> ServiceStatus:
    if find_tesseract():
        return ServiceStatus(
            key="ocr", label="OCR // TEXT EXTRACTOR", state="primary", mode="tesseract",
            detail="Binary Tesseract ditemukan · pytesseract aktif",
        )
    ready = _has_module("easyocr")
    return ServiceStatus(
        key="ocr", label="OCR // TEXT EXTRACTOR", state="fallback",
        mode="easyocr" if ready else "easyocr-pending",
        detail="Tesseract tidak ditemukan → EasyOCR" + ("" if ready else " (belum terpasang: pip install easyocr)"),
    )


# ----------------------------------------------------------- Task queue
def probe_task_queue(s: Settings, redis_ok: bool) -> ServiceStatus:
    if s.celery_enabled and redis_ok:
        return ServiceStatus(
            key="queue", label="TASK QUEUE // SWARM", state="primary", mode="celery",
            detail="Mode Celery · worker Windows wajib --pool=solo atau --pool=threads",
        )
    why = "Celery dimatikan" if not s.celery_enabled else "Redis offline"
    return ServiceStatus(
        key="queue", label="TASK QUEUE // SWARM", state="fallback", mode="background-tasks",
        detail=f"{why} → FastAPI BackgroundTasks + asyncio.gather",
    )


# ------------------------------------------------------------ Aggregator
async def _guard(
    key: str, label: str, fn: Callable[[Settings], Awaitable[ServiceStatus]], s: Settings
) -> ServiceStatus:
    try:
        return await fn(s)
    except Exception as exc:  # jaring pengaman terakhir
        return ServiceStatus(
            key=key, label=label, state="down", mode="none",
            detail=f"Probe error tak terduga ({type(exc).__name__})",
        )


async def build_health_report(s: Settings) -> HealthReport:
    redis_s, searx_s, mem_s, hive_s, llm_s, ocr_s = await asyncio.gather(
        _guard("redis", "REDIS // RAM VAULT", probe_redis, s),
        _guard("searxng", "SEARXNG // FACT-FINDER", probe_searxng, s),
        _guard("memgraph", "MEMGRAPH // GRAPH DB", probe_memgraph, s),
        _guard("hivemind", "HIVE-MIND // PERSISTENCE", probe_hivemind, s),
        _guard("llm", "LLM // RAG & DOM PARSER", probe_llm, s),
        _guard("ocr", "OCR // TEXT EXTRACTOR", probe_ocr, s),
    )
    queue_s = probe_task_queue(s, redis_s.state == "primary")
    services = [redis_s, searx_s, mem_s, hive_s, llm_s, ocr_s, queue_s]
    down = sum(1 for x in services if x.state == "down")
    return HealthReport(
        status="degraded" if down else "ok",
        app=s.app_name,
        version=s.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        primary_count=sum(1 for x in services if x.state == "primary"),
        fallback_count=sum(1 for x in services if x.state == "fallback"),
        down_count=down,
        services=services,
    )

"""DETEKTO :: services/log_bridge.py — Jembatan log Celery worker -> Live Terminal (WebSocket)

Worker Celery berjalan di proses terpisah dan tidak punya akses ke LogBus. Worker mem-publish LogEvent ke channel Redis;
FastAPI subscribe dan menyiarkannya ke semua klien WebSocket. Senyap bila Redis mati (retry dengan backoff).
"""
from __future__ import annotations

import asyncio
import contextlib

import redis.asyncio as aioredis
from pydantic import ValidationError

from core.config import Settings
from core.log_bus import bus
from models.schemas import LogEvent

LOG_CHANNEL = "detekto:logs"


async def redis_log_bridge(settings: Settings) -> None:
    delay = 5.0
    while True:
        client: aioredis.Redis | None = None
        try:
            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=settings.probe_timeout_seconds)
            pubsub = client.pubsub()
            await pubsub.subscribe(LOG_CHANNEL)
            delay = 5.0
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                raw = message.get("data")
                try:
                    event = LogEvent.model_validate_json(raw if isinstance(raw, (str, bytes)) else "")
                except ValidationError:
                    continue
                await bus.emit(event.level, event.source, event.message)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.aclose()

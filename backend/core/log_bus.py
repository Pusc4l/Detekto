"""DETEKTO :: core/log_bus.py
Pub/Sub log in-process -> semua klien WebSocket /ws/interrogation.
Pesan disanitasi (karakter kontrol dibuang, panjang dipotong) sebelum disiarkan.
"""
from __future__ import annotations

import asyncio
import re
from collections import deque
from datetime import datetime, timezone

from fastapi import WebSocket

from models.schemas import LogEvent, LogLevel

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SEND_TIMEOUT_S = 2.0


def _clean(text: str, limit: int) -> str:
    return _CONTROL_CHARS.sub("", text)[:limit]


def make_event(level: LogLevel, source: str, message: str) -> LogEvent:
    return LogEvent(
        ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        level=level,
        source=_clean(source, 24).upper(),
        message=_clean(message, 500),
    )


class LogBus:
    def __init__(self, history: int = 200) -> None:
        self._clients: set[WebSocket] = set()
        self._history: deque[LogEvent] = deque(maxlen=history)

    async def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)
        for event in list(self._history):
            await self._send(ws, event)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def emit(self, level: LogLevel, source: str, message: str) -> None:
        event = make_event(level, source, message)
        self._history.append(event)
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            if not await self._send(ws, event):
                dead.append(ws)
        for ws in dead:
            self.unregister(ws)

    @staticmethod
    async def _send(ws: WebSocket, event: LogEvent) -> bool:
        try:
            await asyncio.wait_for(ws.send_text(event.model_dump_json()), _SEND_TIMEOUT_S)
            return True
        except Exception:  # klien putus / lambat -> dibuang, tidak boleh menjatuhkan server
            return False


bus = LogBus()

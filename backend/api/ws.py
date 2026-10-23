"""DETEKTO :: api/ws.py — WebSocket /ws/interrogation (live terminal log streaming)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.config import get_settings
from core.log_bus import bus, make_event

router = APIRouter()
log = logging.getLogger("detekto.ws")

MAX_CLIENT_MESSAGE_CHARS = 1024
WS_POLICY_VIOLATION = 1008


@router.websocket("/ws/interrogation")
async def interrogation_ws(ws: WebSocket) -> None:
    # CORS tidak berlaku untuk WebSocket -> validasi Origin manual (anti Cross-Site WebSocket Hijacking).
    origin = ws.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origin_list:
        await ws.close(code=WS_POLICY_VIOLATION)
        return

    await ws.accept()
    await bus.register(ws)
    await bus.emit("SYS", "WS", f"TERMINAL LINK ESTABLISHED // CLIENTS: {bus.client_count}")
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_CLIENT_MESSAGE_CHARS:
                await ws.send_text(make_event("ERROR", "WS", "PAYLOAD TERLALU BESAR — DITOLAK").model_dump_json())
                continue
            if raw.strip().lower() == "ping":
                await ws.send_text(make_event("SYS", "WS", "PONG // LINK ALIVE").model_dump_json())
            else:
                await ws.send_text(make_event("WARN", "WS", "PERINTAH TIDAK DIKENAL (FASE 1)").model_dump_json())
    except WebSocketDisconnect:
        log.info("ws client disconnected")
    except Exception as exc:
        log.warning("ws error: %s", type(exc).__name__)
    finally:
        bus.unregister(ws)

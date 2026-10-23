"""DETEKTO :: models/schemas.py
Skema Pydantic v2 (batas panjang string & tipe ketat) untuk seluruh I/O Fase 1.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LogLevel = Literal["SYS", "INFO", "OK", "WARN", "ERROR"]
ServiceState = Literal["primary", "fallback", "down"]


class LogEvent(BaseModel):
    """Satu baris log untuk Live Terminal Ticker (WebSocket)."""

    model_config = ConfigDict(frozen=True)

    ts: str = Field(max_length=40)
    level: LogLevel
    source: str = Field(max_length=24)
    message: str = Field(max_length=500)


class ServiceStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str = Field(max_length=24)
    label: str = Field(max_length=48)
    state: ServiceState
    mode: str = Field(max_length=48)
    detail: str = Field(max_length=240)
    latency_ms: float | None = None


class HealthReport(BaseModel):
    status: Literal["ok", "degraded"]
    app: str = Field(max_length=48)
    version: str = Field(max_length=16)
    timestamp: str = Field(max_length=40)
    primary_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    down_count: int = Field(ge=0)
    services: list[ServiceStatus]

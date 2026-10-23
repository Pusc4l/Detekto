"""DETEKTO :: api/health.py — GET /api/health (selalu 200; kegagalan service = state, bukan crash)."""
from __future__ import annotations

from fastapi import APIRouter

from core.config import get_settings
from models.schemas import HealthReport
from services.health_probe import build_health_report

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthReport)
async def health() -> HealthReport:
    return await build_health_report(get_settings())

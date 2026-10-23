"""DETEKTO :: services/hivemind_sync.py — Global Hive-Mind Sync (Task 6.3 workflow)

Payload teks super ringan (< 5 KB/baris): username_hash, platform, verdict_score, buzzer_type, relationship_edges, ml_weights_version.
Supabase (PostgREST upsert) -> fallback otomatis SQLite lokal (tabel hive_verdicts). Hanya dijalankan atas persetujuan eksplisit pengguna.
Catatan privasi: username_hash = SHA-256 tanpa garam agar konsisten antar-pengguna; ini PSEUDONIM (username publik mudah ditebak), bukan anonim.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from typing import Any

import httpx

from core.config import Settings
from models.graph import GraphMap, HiveSyncResult
from models.verdict import VerdictSet
from services.verdict_pipeline import username_hash

MAX_PAYLOAD_BYTES = 5000
MAX_EDGES = 40


def _h8(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def build_rows(vs: VerdictSet, gm: GraphMap | None) -> tuple[list[dict[str, Any]], int, int]:
    """Bangun baris Hive per kartu verdict. Edge dipangkas sampai payload < 5 KB. Kembalikan (rows, skipped, max_bytes)."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    max_bytes = 0
    for card in vs.cards:
        node_id = f"{card.platform}:{card.username.lower()}"
        edges: list[list[str]] = []
        if gm is not None:
            for link in gm.links:
                if link.source == node_id:
                    edges.append([link.type, _h8(link.target)])
                elif link.target == node_id:
                    edges.append([f"{link.type}<", _h8(link.source)])
        edges = edges[:MAX_EDGES]
        row: dict[str, Any] = {
            "username_hash": username_hash(card.platform, card.username), "platform": card.platform, "verdict_score": card.score,
            "buzzer_type": card.buzzer_type, "relationship_edges": edges, "ml_weights_version": card.model_version,
        }
        while len(json.dumps(row, separators=(",", ":")).encode()) >= MAX_PAYLOAD_BYTES and row["relationship_edges"]:
            row["relationship_edges"] = row["relationship_edges"][:-5]
        size = len(json.dumps(row, separators=(",", ":")).encode())
        if size >= MAX_PAYLOAD_BYTES:
            skipped += 1
            continue
        max_bytes = max(max_bytes, size)
        rows.append(row)
    return rows, skipped, max_bytes


def _upsert_sqlite(settings: Settings, rows: list[dict[str, Any]]) -> None:
    with closing(sqlite3.connect(settings.sqlite_file, timeout=5.0)) as conn:
        conn.executemany(
            "INSERT INTO hive_verdicts (username_hash, platform, verdict_score, buzzer_type, relationship_edges, ml_weights_version) "
            "VALUES (:username_hash, :platform, :verdict_score, :buzzer_type, :edges, :ml_weights_version) "
            "ON CONFLICT(username_hash, platform) DO UPDATE SET verdict_score = excluded.verdict_score, buzzer_type = excluded.buzzer_type, "
            "relationship_edges = excluded.relationship_edges, ml_weights_version = excluded.ml_weights_version, "
            "created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
            [{**r, "edges": json.dumps(r["relationship_edges"], separators=(",", ":"))} for r in rows],
        )
        conn.commit()


async def _push_supabase(settings: Settings, rows: list[dict[str, Any]], transport: httpx.AsyncBaseTransport | None) -> bool:
    headers = {
        "apikey": settings.supabase_key, "Authorization": f"Bearer {settings.supabase_key}", "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, transport=transport) as client:
            resp = await client.post(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/hive_verdicts", params={"on_conflict": "username_hash,platform"},
                headers=headers, content=json.dumps(rows),
            )
        return resp.status_code in (200, 201, 204)
    except httpx.HTTPError:
        return False


async def sync_verdicts(settings: Settings, vs: VerdictSet, gm: GraphMap | None, transport: httpx.AsyncBaseTransport | None = None) -> HiveSyncResult:
    rows, skipped, max_bytes = build_rows(vs, gm)
    if not rows:
        return HiveSyncResult(mode="sqlite", synced=0, skipped=skipped, max_payload_bytes=max_bytes, note="Tidak ada baris yang layak dikirim.")
    if settings.supabase_configured and await _push_supabase(settings, rows, transport):
        return HiveSyncResult(mode="supabase", synced=len(rows), skipped=skipped, max_payload_bytes=max_bytes, note="Terkirim ke Supabase (upsert per username_hash+platform).")
    await asyncio.to_thread(_upsert_sqlite, settings, rows)
    reason = "Supabase gagal/tidak dikonfigurasi" if settings.supabase_configured else "Supabase belum dikonfigurasi"
    return HiveSyncResult(mode="sqlite", synced=len(rows), skipped=skipped, max_payload_bytes=max_bytes, note=f"{reason} → disimpan di SQLite lokal (detekto_hive.db).")

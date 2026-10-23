"""DETEKTO :: services/model_store.py — Persistensi bobot ML & jejak verdict/feedback

SQLite lokal = sumber kebenaran (selalu ada). Supabase (PostgREST) = sinkronisasi opsional, kunci per-instance (instance_id),
sehingga bobot satu pengguna tidak dapat menimpa bobot pengguna lain (anti model-poisoning lintas pengguna).
Bobot disimpan sebagai JSON tervalidasi — TIDAK PERNAH memuat pickle/joblib dari database (pickle = eksekusi kode).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from core.config import Settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ml_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ml_model_state (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    version    INTEGER NOT NULL,
    n_samples  INTEGER NOT NULL,
    payload    TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS ml_verdicts (
    verdict_id    TEXT PRIMARY KEY,
    username_hash TEXT NOT NULL,
    platform      TEXT NOT NULL,
    features      TEXT NOT NULL,
    evidence      TEXT NOT NULL,
    raw_score     REAL NOT NULL,
    final_score   REAL NOT NULL,
    verdict       TEXT NOT NULL CHECK (verdict IN ('BUZZER', 'ORGANIC')),
    buzzer_type   TEXT NOT NULL CHECK (buzzer_type IN ('A', 'B', 'C')),
    model_version INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ml_feedback (
    verdict_id           TEXT PRIMARY KEY REFERENCES ml_verdicts (verdict_id),
    label                INTEGER NOT NULL CHECK (label IN (0, 1)),
    feedback             TEXT NOT NULL,
    model_version_before INTEGER NOT NULL,
    model_version_after  INTEGER NOT NULL,
    created_at           TEXT NOT NULL
);
"""
_MAX_VERDICT_ROWS = 5000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ModelStore:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._path: Path = settings.sqlite_file
        self._remote_ok = settings.supabase_configured
        self._instance_id: str | None = None
        self._feedback_times: list[float] = []

    # ------------------------------------------------------------------ sqlite
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @property
    def storage_name(self) -> str:
        return "supabase+sqlite" if self._remote_ok else "sqlite"

    @property
    def instance_id(self) -> str:
        if self._instance_id is None:
            with closing(self._conn()) as conn:
                row = conn.execute("SELECT value FROM ml_meta WHERE key = 'instance_id'").fetchone()
                if row is None:
                    value = uuid.uuid4().hex
                    conn.execute("INSERT INTO ml_meta (key, value) VALUES ('instance_id', ?)", (value,))
                    conn.commit()
                    self._instance_id = value
                else:
                    self._instance_id = str(row["value"])
        return self._instance_id

    def load_state(self) -> dict[str, Any] | None:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT version, n_samples, payload, updated_at FROM ml_model_state WHERE id = 1").fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            return None
        return {"version": int(row["version"]), "n_samples": int(row["n_samples"]), "updated_at": row["updated_at"], "payload": payload}

    def save_state(self, version: int, n_samples: int, payload: dict[str, Any]) -> str:
        stamp = _now()
        with closing(self._conn()) as conn:
            conn.execute(
                "INSERT INTO ml_model_state (id, version, n_samples, payload, updated_at) VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET version = excluded.version, n_samples = excluded.n_samples, "
                "payload = excluded.payload, updated_at = excluded.updated_at",
                (version, n_samples, json.dumps(payload), stamp),
            )
            conn.commit()
        return stamp

    # ---------------------------------------------------------------- verdicts
    def save_verdict(self, row: dict[str, Any]) -> None:
        with closing(self._conn()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ml_verdicts (verdict_id, username_hash, platform, features, evidence, raw_score, final_score, "
                "verdict, buzzer_type, model_version, created_at) VALUES (:verdict_id, :username_hash, :platform, :features, :evidence, "
                ":raw_score, :final_score, :verdict, :buzzer_type, :model_version, :created_at)",
                row,
            )
            conn.execute(
                "DELETE FROM ml_verdicts WHERE verdict_id IN (SELECT verdict_id FROM ml_verdicts ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (_MAX_VERDICT_ROWS,),
            )
            conn.commit()

    def load_verdict(self, verdict_id: str) -> dict[str, Any] | None:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT * FROM ml_verdicts WHERE verdict_id = ?", (verdict_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["features"] = json.loads(data["features"])
        data["evidence"] = json.loads(data["evidence"])
        return data

    def has_feedback(self, verdict_id: str) -> bool:
        with closing(self._conn()) as conn:
            return conn.execute("SELECT 1 FROM ml_feedback WHERE verdict_id = ?", (verdict_id,)).fetchone() is not None

    def save_feedback(self, verdict_id: str, label: int, feedback: str, before: int, after: int) -> None:
        with closing(self._conn()) as conn:
            conn.execute(
                "INSERT INTO ml_feedback (verdict_id, label, feedback, model_version_before, model_version_after, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (verdict_id, label, feedback, before, after, _now()),
            )
            conn.commit()

    def feedback_allowed(self) -> bool:
        """Rate-limit global: cegah banjir feedback (model-poisoning / klik berlebih)."""
        now = time.monotonic()
        self._feedback_times = [t for t in self._feedback_times if now - t < 60.0]
        if len(self._feedback_times) >= self._s.feedback_max_per_minute:
            return False
        self._feedback_times.append(now)
        return True

    # ---------------------------------------------------------------- supabase
    def _headers(self) -> dict[str, str]:
        return {"apikey": self._s.supabase_key, "Authorization": f"Bearer {self._s.supabase_key}", "Content-Type": "application/json"}

    async def pull_remote_state(self, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any] | None:
        if not self._remote_ok:
            return None
        try:
            async with httpx.AsyncClient(timeout=6.0, transport=transport) as client:
                resp = await client.get(
                    f"{self._s.supabase_url.rstrip('/')}/rest/v1/ml_model_state",
                    params={"instance_id": f"eq.{self.instance_id}", "select": "version,n_samples,payload,updated_at"},
                    headers=self._headers(),
                )
            rows = resp.json() if resp.status_code == 200 else []
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                payload = rows[0].get("payload")
                payload = json.loads(payload) if isinstance(payload, str) else payload
                return {"version": int(rows[0]["version"]), "n_samples": int(rows[0]["n_samples"]), "updated_at": rows[0].get("updated_at"), "payload": payload}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None
        return None

    async def push_remote_state(self, version: int, n_samples: int, payload: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> bool:
        if not self._remote_ok:
            return False
        body = {"instance_id": self.instance_id, "version": version, "n_samples": n_samples, "payload": payload, "updated_at": _now()}
        try:
            async with httpx.AsyncClient(timeout=6.0, transport=transport) as client:
                resp = await client.post(
                    f"{self._s.supabase_url.rstrip('/')}/rest/v1/ml_model_state",
                    params={"on_conflict": "instance_id"},
                    headers={**self._headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                    content=json.dumps(body),
                )
            return resp.status_code in (200, 201, 204)
        except httpx.HTTPError:
            return False

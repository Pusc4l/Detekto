"""DETEKTO :: services/sqlite_store.py
Fallback Hive-Mind lokal (detekto_hive.db). HANYA menyimpan teks/angka ringan, tidak pernah gambar.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hive_verdicts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    username_hash      TEXT    NOT NULL,
    platform           TEXT    NOT NULL,
    verdict_score      REAL    NOT NULL CHECK (verdict_score >= 0 AND verdict_score <= 100),
    buzzer_type        TEXT    NOT NULL CHECK (buzzer_type IN ('A', 'B', 'C')),
    relationship_edges TEXT    NOT NULL DEFAULT '[]',
    ml_weights_version INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_hive_username_hash ON hive_verdicts (username_hash);
CREATE UNIQUE INDEX IF NOT EXISTS ux_hive_account ON hive_verdicts (username_hash, platform);
"""


def init_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=2.0)) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def check_sqlite(path: Path) -> tuple[bool, str]:
    try:
        with closing(sqlite3.connect(path, timeout=2.0)) as conn:
            conn.execute("SELECT 1 FROM hive_verdicts LIMIT 1")
        return True, path.name
    except sqlite3.Error as exc:
        return False, type(exc).__name__

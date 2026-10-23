"""DETEKTO :: services/ephemeral_vault.py — Ephemeral RAM Vault (Zero-Bloat Protocol)

Penyimpanan sementara bukti Base64. Backend utama: Redis (TTL 300 detik, tanpa persistensi disk).
Auto-Fallback: bila Redis mati -> vault TTL in-process (dict di RAM proses) dengan perilaku identik.
TIDAK ADA satu pun jalur yang menulis file gambar ke disk.
"""
from __future__ import annotations

import contextlib
import gc
import time
from typing import Literal

import redis.asyncio as aioredis

from core.config import Settings, get_settings
from models.interrogation import SessionMeta

BackendName = Literal["redis", "memory"]
_PREFIX = "detekto"
_REDIS_RETRY_AFTER_S = 10.0


class VaultFullError(Exception):
    """Vault in-process penuh (batas RAM tercapai)."""


def _k_meta(sid: str) -> str:
    return f"{_PREFIX}:session:{sid}:meta"


def _k_media(sid: str, bucket: str, idx: int) -> str:
    return f"{_PREFIX}:session:{sid}:media:{bucket}:{idx}"


def _k_result(sid: str) -> str:
    return f"{_PREFIX}:session:{sid}:result"


def k_swarm(sid: str, suffix: str) -> str:
    return f"{_PREFIX}:session:{sid}:swarm:{suffix}"


def _k_ocr(sha: str) -> str:
    return f"{_PREFIX}:ocr:{sha}"


class _MemoryBackend:
    """Fallback: dict ber-TTL. Murni RAM proses, dibersihkan malas (lazy sweep) pada tiap operasi."""

    name: BackendName = "memory"

    def __init__(self, max_bytes: int) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._bytes = 0
        self._max = max_bytes

    def _drop(self, key: str) -> bool:
        item = self._data.pop(key, None)
        if item is None:
            return False
        self._bytes -= len(item[1])
        return True

    def _sweep(self) -> None:
        now = time.monotonic()
        for key in [k for k, (exp, _) in self._data.items() if exp <= now]:
            self._drop(key)

    async def set_many(self, items: dict[str, str], ttl: int) -> None:
        self._sweep()
        incoming = sum(len(v) for v in items.values())
        outgoing = sum(len(self._data[k][1]) for k in items if k in self._data)
        if self._bytes - outgoing + incoming > self._max:
            raise VaultFullError("vault in-process penuh")
        exp = time.monotonic() + ttl
        for key, value in items.items():
            self._drop(key)
            self._data[key] = (exp, value)
            self._bytes += len(value)

    async def get_many(self, keys: list[str]) -> list[str | None]:
        self._sweep()
        return [self._data[k][1] if k in self._data else None for k in keys]

    async def delete(self, keys: list[str]) -> int:
        return sum(1 for k in keys if self._drop(k))


class _RedisBackend:
    name: BackendName = "redis"

    def __init__(self, client: aioredis.Redis) -> None:
        self._r = client

    async def set_many(self, items: dict[str, str], ttl: int) -> None:
        async with self._r.pipeline(transaction=True) as pipe:
            for key, value in items.items():
                pipe.set(key, value, ex=ttl)
            await pipe.execute()

    async def get_many(self, keys: list[str]) -> list[str | None]:
        if not keys:
            return []
        values = await self._r.mget(keys)
        return [v.decode("utf-8") if isinstance(v, bytes) else v for v in values]

    async def delete(self, keys: list[str]) -> int:
        return int(await self._r.delete(*keys)) if keys else 0


class EphemeralVault:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._memory = _MemoryBackend(settings.memory_vault_max_bytes)
        self._client: aioredis.Redis | None = None
        self._redis_down_until = 0.0
        self.last_backend: BackendName = "memory"

    # ------------------------------------------------------ pemilihan backend
    async def _redis(self) -> _RedisBackend | None:
        if time.monotonic() < self._redis_down_until:
            return None
        try:
            if self._client is None:
                self._client = aioredis.from_url(
                    self._s.redis_url,
                    socket_connect_timeout=self._s.probe_timeout_seconds,
                    socket_timeout=5.0,
                )
            await self._client.ping()
            return _RedisBackend(self._client)
        except Exception:
            self._redis_down_until = time.monotonic() + _REDIS_RETRY_AFTER_S
            if self._client is not None:
                with contextlib.suppress(Exception):
                    await self._client.aclose()
                self._client = None
            return None

    async def _write(self, items: dict[str, str], ttl: int) -> BackendName:
        backend = await self._redis()
        if backend is not None:
            try:
                await backend.set_many(items, ttl)
                self.last_backend = "redis"
                return "redis"
            except Exception:
                self._redis_down_until = time.monotonic() + _REDIS_RETRY_AFTER_S
        await self._memory.set_many(items, ttl)
        self.last_backend = "memory"
        return "memory"

    async def _read(self, keys: list[str]) -> list[str | None]:
        """Baca dari Redis lebih dulu; kunci yang tidak ada dicari di vault in-process (sesi bisa lahir di salah satunya)."""
        found: list[str | None] = [None] * len(keys)
        backend = await self._redis()
        if backend is not None:
            try:
                found = await backend.get_many(keys)
            except Exception:
                self._redis_down_until = time.monotonic() + _REDIS_RETRY_AFTER_S
        if any(v is None for v in found):
            mem = await self._memory.get_many(keys)
            found = [a if a is not None else b for a, b in zip(found, mem)]
        return found

    async def _delete(self, keys: list[str]) -> int:
        removed = await self._memory.delete(keys)
        backend = await self._redis()
        if backend is not None:
            try:
                removed += await backend.delete(keys)
            except Exception:
                self._redis_down_until = time.monotonic() + _REDIS_RETRY_AFTER_S
        return removed

    # --------------------------------------------------------------- sesi
    async def create_session(self, meta: SessionMeta, media: dict[str, list[str]]) -> BackendName:
        items: dict[str, str] = {_k_meta(meta.session_id): meta.model_dump_json()}
        for bucket, images in media.items():
            for idx, b64 in enumerate(images):
                items[_k_media(meta.session_id, bucket, idx)] = b64
        return await self._write(items, self._s.redis_ttl_seconds)

    async def load_meta(self, sid: str) -> SessionMeta | None:
        (raw,) = await self._read([_k_meta(sid)])
        return SessionMeta.model_validate_json(raw) if raw else None

    async def load_media(self, sid: str, bucket: str, count: int) -> list[str | None]:
        return await self._read([_k_media(sid, bucket, i) for i in range(count)])

    async def purge_session_media(self, sid: str) -> int:
        """redis.delete() semua buffer gambar sesi + gc.collect(). Meta (teks) ditandai media_purged."""
        meta = await self.load_meta(sid)
        if meta is None:
            gc.collect()
            return 0
        keys = [_k_media(sid, "context", i) for i in range(len(meta.context_hashes))]
        keys += [_k_media(sid, "evidence", i) for i in range(len(meta.evidence_hashes))]
        removed = await self._delete(keys)
        meta.media_purged = True
        await self._write({_k_meta(sid): meta.model_dump_json()}, self._s.result_ttl_seconds)
        gc.collect()
        return removed

    async def purge_session(self, sid: str) -> int:
        meta = await self.load_meta(sid)
        keys = [_k_meta(sid), _k_result(sid)]
        if meta is not None:
            keys += [_k_media(sid, "context", i) for i in range(len(meta.context_hashes))]
            keys += [_k_media(sid, "evidence", i) for i in range(len(meta.evidence_hashes))]
        removed = await self._delete(keys)
        gc.collect()
        return removed

    # ------------------------------------------------- blob teks generik (Fase 4)
    async def put(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._write({key: value}, ttl or self._s.result_ttl_seconds)

    async def get(self, key: str) -> str | None:
        (raw,) = await self._read([key])
        return raw

    async def get_many(self, keys: list[str]) -> list[str | None]:
        return await self._read(keys)

    # ------------------------------------------------------ hasil & cache OCR
    async def save_result(self, sid: str, result_json: str) -> None:
        await self._write({_k_result(sid): result_json}, self._s.result_ttl_seconds)

    async def load_result(self, sid: str) -> str | None:
        (raw,) = await self._read([_k_result(sid)])
        return raw

    async def cache_get(self, sha256: str) -> str | None:
        (raw,) = await self._read([_k_ocr(sha256)])
        return raw

    async def cache_set(self, sha256: str, value: str) -> None:
        try:
            await self._write({_k_ocr(sha256): value}, self._s.redis_ttl_seconds)
        except VaultFullError:
            pass  # cache bersifat opsional

    async def close(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.aclose()
            self._client = None


_vault: EphemeralVault | None = None


def get_vault() -> EphemeralVault:
    global _vault
    if _vault is None:
        _vault = EphemeralVault(get_settings())
    return _vault

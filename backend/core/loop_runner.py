"""DETEKTO :: core/loop_runner.py — Event loop terisolasi untuk Playwright.

Mengapa: Playwright (async) memerlukan subprocess; di Windows itu hanya didukung ProactorEventLoop, sedangkan
uvicorn --reload memaksa SelectorEventLoop. Solusi baku: jalankan seluruh pekerjaan Playwright di thread terpisah
dengan loop Proactor milik sendiri. Kode di dalam thread TIDAK BOLEH memakai objek yang terikat ke loop utama
(Redis async, WebSocket) — gunakan MainLoopBridge untuk menjembatani.
"""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import Future
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

T = TypeVar("T")


def new_isolated_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()  # type: ignore[attr-defined]
    return asyncio.new_event_loop()


def run_in_fresh_loop(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Sinkron: bangun loop baru, jalankan coroutine sampai selesai, tutup loop. Aman dipanggil dari thread mana pun."""
    loop = new_isolated_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(factory())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


async def run_in_thread_loop(factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Dipanggil dari loop utama: jalankan coroutine di thread + loop terisolasi dan tunggu hasilnya."""
    return await asyncio.to_thread(run_in_fresh_loop, factory)


class MainLoopBridge:
    """Jalankan coroutine milik loop utama (vault async, LogBus) dari thread/loop lain dan tunggu hasilnya."""

    def __init__(self, main_loop: asyncio.AbstractEventLoop) -> None:
        self._loop = main_loop

    async def call(self, coro: Awaitable[T]) -> T:
        fut: Future[T] = asyncio.run_coroutine_threadsafe(_wrap(coro), self._loop)
        return await asyncio.wrap_future(fut)


async def _wrap(coro: Awaitable[T]) -> T:
    return await coro

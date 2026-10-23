"""DETEKTO :: services/ml_runtime.py — singleton ModelStore + OnlineLearner (inisialisasi malas, aman dipanggil berulang)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.config import get_settings
from services.model_store import ModelStore
from services.online_learner import OnlineLearner


@dataclass
class MlRuntime:
    store: ModelStore
    learner: OnlineLearner


_runtime: MlRuntime | None = None
_lock = asyncio.Lock()


async def get_runtime() -> MlRuntime:
    global _runtime
    if _runtime is not None:
        return _runtime
    async with _lock:
        if _runtime is None:
            s = get_settings()
            store = ModelStore(s)
            await asyncio.to_thread(store.init)
            learner = OnlineLearner(store, s)
            remote = await store.pull_remote_state()
            await asyncio.to_thread(learner.load, remote)
            _runtime = MlRuntime(store=store, learner=learner)
    return _runtime


def reset_runtime_for_tests() -> None:
    global _runtime
    _runtime = None

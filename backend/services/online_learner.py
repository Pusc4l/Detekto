"""DETEKTO :: services/online_learner.py — Online Incremental Learning (Task 5.3)

SGDClassifier(loss="log_loss") dengan partial_fit per umpan balik. Cold-start: dibootstrap dari arketipe sintetis (Type A/B/C + organik
yang kebetulan menyalin) sehingga prior pakar tertanam; bobot kemudian dipelajari dari koreksi pengguna.
Persistensi: JSON tervalidasi di SQLite (+ Supabase), snapshot joblib lokal sebagai cadangan baca-manusia (TIDAK dimuat balik).
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import SGDClassifier

from core.config import Settings
from models.verdict import FEATURE_NAMES, FactorContribution
from services.model_store import ModelStore

N_FEATURES = len(FEATURE_NAMES)
IMPUTE_VALUE = 0.25          # fitur tak teramati diisi nilai prior "cenderung organik" (mayoritas pengguna organik)
_COEF_LIMIT = 6.0            # batas |bobot|: mencegah satu fitur mendominasi akibat feedback berlebihan / poisoning
_STATE_LIMIT = 50.0


def _bootstrap_dataset() -> tuple[np.ndarray, np.ndarray]:
    """Arketipe sintetis (seed tetap -> deterministik). Fitur: [umur, rename, engagement, copas, gt_dev, visual]."""
    rng = np.random.default_rng(20251018)

    def around(center: list[float], n: int, sd: float = 0.08) -> np.ndarray:
        return np.clip(rng.normal(center, sd, (n, N_FEATURES)), 0.0, 1.0)

    groups: list[tuple[np.ndarray, int]] = [
        (around([0.90, 0.60, 0.85, 0.95, 0.60, 0.80], 14), 1),   # Type A: bot, akun baru, salinan identik, visual anomali
        (around([0.75, 0.75, 0.70, 0.55, 0.80, 0.45], 14), 1),   # Type B: troll berbayar, sering ganti nama, mendistorsi fakta
        (around([0.20, 0.05, 0.15, 0.10, 0.15, 0.10], 18), 0),   # Type C: organik biasa
        (around([0.15, 0.00, 0.10, 0.90, 0.20, 0.10], 10), 0),   # organik yang menyalin meme/slogan (copas tinggi, sisanya organik)
        (around([0.30, 0.10, 0.20, 0.15, 0.85, 0.10], 8), 0),    # organik yang marah (agresif) tanpa anomali akun
        (around([0.65, 0.40, 0.55, 0.50, 0.45, 0.50], 6), 1),    # kasus tengah condong buzzer
    ]
    x = np.vstack([g for g, _ in groups])
    y = np.concatenate([np.full(len(g), lab) for g, lab in groups])
    return x, y


def _new_model() -> SGDClassifier:
    return SGDClassifier(loss="log_loss", penalty="l2", alpha=1e-4, learning_rate="constant", eta0=0.08, random_state=7)


def _valid_payload(payload: Any) -> bool:
    try:
        coef = payload["coef"]
        intercept = payload["intercept"]
        return (
            isinstance(coef, list) and len(coef) == N_FEATURES and all(isinstance(c, (int, float)) and math.isfinite(c) and abs(c) <= _STATE_LIMIT for c in coef)
            and isinstance(intercept, (int, float)) and math.isfinite(intercept) and abs(intercept) <= _STATE_LIMIT
            and payload.get("features") == list(FEATURE_NAMES)
        )
    except (KeyError, TypeError):
        return False


class OnlineLearner:
    def __init__(self, store: ModelStore, settings: Settings) -> None:
        self._store = store
        self._s = settings
        self._lock = threading.RLock()
        self._model: SGDClassifier = _new_model()
        self.version = 0
        self.n_samples = 0
        self.source: str = "bootstrap"
        self.updated_at: str | None = None

    # ----------------------------------------------------------- inisialisasi
    def _bootstrap(self) -> None:
        x, y = _bootstrap_dataset()
        model = _new_model()
        for _ in range(60):  # beberapa epoch agar prior pakar konvergen
            model.partial_fit(x, y, classes=np.array([0, 1]))
        self._model = model
        self.version, self.n_samples, self.source = 1, 0, "bootstrap"

    def _restore(self, payload: dict[str, Any], version: int, n_samples: int) -> None:
        model = _new_model()
        model.partial_fit(np.zeros((2, N_FEATURES)), np.array([0, 1]), classes=np.array([0, 1]), sample_weight=np.array([1e-12, 1e-12]))
        model.coef_ = np.array([payload["coef"]], dtype=float)
        model.intercept_ = np.array([payload["intercept"]], dtype=float)
        self._model = model
        self.version, self.n_samples = version, n_samples

    def load(self, remote: dict[str, Any] | None = None) -> str:
        """Urutan: Supabase (bila ada & valid) -> SQLite -> bootstrap. Mengembalikan sumber yang dipakai."""
        with self._lock:
            for source, state in (("supabase", remote), ("sqlite", self._store.load_state())):
                if state and _valid_payload(state.get("payload")):
                    self._restore(state["payload"], int(state["version"]), int(state["n_samples"]))
                    self.source, self.updated_at = source, state.get("updated_at")
                    return source
            self._bootstrap()
            self._persist()
            return "bootstrap"

    # ---------------------------------------------------------------- inferensi
    @staticmethod
    def vector(features: dict[str, float | None]) -> list[float]:
        return [float(features[n]) if features.get(n) is not None else IMPUTE_VALUE for n in FEATURE_NAMES]  # type: ignore[arg-type]

    def predict_proba(self, x: list[float]) -> float:
        with self._lock:
            return float(self._model.predict_proba(np.array([x], dtype=float))[0, 1])

    def weights(self) -> tuple[list[float], float]:
        with self._lock:
            return [float(w) for w in self._model.coef_[0]], float(self._model.intercept_[0])

    def contributions(self, x: list[float]) -> list[FactorContribution]:
        w, _ = self.weights()
        items = [FactorContribution(feature=n, value=round(v, 3), weight=round(wi, 3), contribution=round(wi * v, 3)) for n, v, wi in zip(FEATURE_NAMES, x, w)]
        return sorted(items, key=lambda c: -abs(c.contribution))[:6]

    # -------------------------------------------------------------- pembelajaran
    def partial_fit(self, x: list[float], label: int, weight: float | None = None) -> tuple[float, float, int, int, float]:
        """Satu langkah SGD. Kembalikan (p_sebelum, p_sesudah, versi_sebelum, versi_sesudah, durasi_ms)."""
        t0 = time.perf_counter()
        with self._lock:
            before = self.predict_proba(x)
            v_before = self.version
            self._model.partial_fit(
                np.array([x], dtype=float), np.array([label]), classes=np.array([0, 1]),
                sample_weight=np.array([weight if weight is not None else self._s.feedback_sample_weight]),
            )
            np.clip(self._model.coef_, -_COEF_LIMIT, _COEF_LIMIT, out=self._model.coef_)
            np.clip(self._model.intercept_, -_COEF_LIMIT, _COEF_LIMIT, out=self._model.intercept_)
            self.version += 1
            self.n_samples += 1
            after = self.predict_proba(x)
            v_after = self.version
            self._persist()
        return before, after, v_before, v_after, (time.perf_counter() - t0) * 1000.0

    def payload(self) -> dict[str, Any]:
        w, b = self.weights()
        return {"features": list(FEATURE_NAMES), "coef": w, "intercept": b, "loss": "log_loss", "eta0": 0.08, "alpha": 1e-4}

    def _persist(self) -> None:
        payload = self.payload()
        self.updated_at = self._store.save_state(self.version, self.n_samples, payload)
        try:
            joblib.dump(self._model, self._s.ml_snapshot_path if self._s.ml_snapshot_path.startswith(("/", "\\")) or ":" in self._s.ml_snapshot_path else str(self._s.sqlite_file.parent / self._s.ml_snapshot_path))
        except OSError:
            return  # snapshot joblib hanya cadangan; kegagalan tulis tidak boleh menghentikan pembelajaran

    @property
    def snapshot_for_sync(self) -> tuple[int, int, dict[str, Any]]:
        with self._lock:
            return self.version, self.n_samples, self.payload()

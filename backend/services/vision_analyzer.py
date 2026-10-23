"""DETEKTO :: services/vision_analyzer.py — Full-Feed Computer Vision & Deepfake Analyzer (Task 4.4)

Semua gambar hidup HANYA sebagai bytes di RAM (httpx stream -> numpy/Pillow) dan dihancurkan (del + gc.collect) di akhir.
- Foto profil: OpenCV FFT (spektrum frekuensi). HEURISTIK BELUM DIKALIBRASI -> dipakai sebagai SATU fitur; Fase 5 mempelajari bobotnya.
- Feed (<= 30 gambar): CLIP (opsional, bila sentence-transformers terpasang) -> fallback Perceptual Hash (dHash) pure Pillow.
"""
from __future__ import annotations

import asyncio
import gc
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

import core.security as security  # memastikan Image.MAX_IMAGE_PIXELS terpasang (anti decompression-bomb)
from core.config import get_settings
from models.swarm import FeedUniformity, FftResult, VisionReport

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

_FFT_SIZE = 256
_PHASH_CLUSTER_DISTANCE = 10  # bit berbeda dari 64 -> dianggap "poster seragam"
_MIN_FEED_FOR_VERDICT = 6
_FEED_FLAG_RATIO = 0.9  # PRD: akun yang ~90% isinya konten seragam
_FFT_SUSPICIOUS = 0.6
_clip_model: Any = None
_clip_failed = False


# ------------------------------------------------------------------ FFT
def _decode_gray(data: bytes) -> Any | None:
    if np is None or cv2 is None:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)


def _face_present(gray: Any) -> bool | None:
    if cv2 is None or not hasattr(cv2, "CascadeClassifier"):  # OpenCV 5 memindahkan cascade ke contrib -> pin <5 di requirements
        return None
    try:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if cascade.empty():
            return None
        small = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
        return len(cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))) > 0
    except cv2.error:
        return None


def fft_metrics(gray: Any) -> tuple[float, float]:
    """Kembalikan (hf_ratio, peak_z). Artefak upsampling GAN muncul sebagai puncak terisolasi di pita frekuensi tinggi."""
    g = cv2.resize(gray, (_FFT_SIZE, _FFT_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)
    g -= g.mean()
    window = np.outer(np.hanning(_FFT_SIZE), np.hanning(_FFT_SIZE)).astype(np.float32)  # redam kebocoran spektral tepi
    mag = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(g * window))))
    c = _FFT_SIZE // 2
    yy, xx = np.indices(mag.shape)
    r = np.hypot(xx - c, yy - c).astype(np.int32)
    profile = np.bincount(r.ravel(), mag.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    low = float(profile[4 : c // 2].mean())
    high = float(profile[c // 2 : c].mean())
    hf_ratio = high / low if low > 1e-6 else 0.0
    annulus = (r >= c // 2) & (r < c)
    resid = (mag - profile[r])[annulus]
    peak_z = float(resid.max() / (resid.std() + 1e-6))
    return hf_ratio, peak_z


def analyze_profile_photo(data: bytes) -> FftResult | None:
    gray = _decode_gray(data)
    if gray is None or gray.size < 64 * 64:
        return FftResult(score=0.0, hf_ratio=0.0, peak_z=0.0, face_detected=None, label="insufficient")
    hf, peak = fft_metrics(gray)
    face = _face_present(gray)
    spike = min(1.0, max(0.0, (peak - 8.0) / 8.0))
    flat = min(1.0, max(0.0, (0.55 - hf) / 0.25))
    score = 0.7 * spike + 0.3 * flat
    if face is False:
        score *= 0.5  # tanpa wajah, indikator FFT kurang relevan
    label = "suspicious" if score >= _FFT_SUSPICIOUS else "normal"
    return FftResult(score=round(score, 3), hf_ratio=round(hf, 3), peak_z=round(peak, 2), face_detected=face, label=label)


# ------------------------------------------------------------ keseragaman feed
def dhash(data: bytes) -> int | None:
    try:
        with Image.open(BytesIO(data)) as img:
            img.draft("L", (64, 64))
            small = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            px = list(small.tobytes())  # mode L: 1 byte/piksel (versi-proof, tanpa getdata() yang deprecated)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits


def cluster_ratio(hashes: list[int], max_distance: int = _PHASH_CLUSTER_DISTANCE) -> tuple[float, float]:
    """Klaster greedy berdasarkan jarak Hamming. Kembalikan (rasio_klaster_terbesar, rasio_unik)."""
    reps: list[int] = []
    sizes: list[int] = []
    for h in hashes:
        for i, rep in enumerate(reps):
            if (rep ^ h).bit_count() <= max_distance:
                sizes[i] += 1
                break
        else:
            reps.append(h)
            sizes.append(1)
    n = len(hashes)
    return max(sizes) / n, len(reps) / n


def _clip_uniformity(images: list[bytes]) -> float | None:
    """Rata-rata cosine similarity antar-embedding CLIP (0..1). None bila CLIP tidak tersedia."""
    global _clip_model, _clip_failed
    if _clip_failed or np is None:
        return None
    try:
        if _clip_model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

            _clip_model = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
        pil = []
        for raw in images:
            with Image.open(BytesIO(raw)) as im:
                pil.append(im.convert("RGB").copy())
        emb = _clip_model.encode(pil, convert_to_numpy=True, normalize_embeddings=True)
        sim = emb @ emb.T
        n = len(pil)
        return float((sim.sum() - n) / (n * (n - 1))) if n > 1 else None
    except Exception:
        _clip_failed = True
        return None


def analyze_feed(images: list[bytes]) -> FeedUniformity:
    n = len(images)
    if n < 2:
        return FeedUniformity(images_analyzed=n, method="none")
    clip_sim = _clip_uniformity(images) if n >= _MIN_FEED_FOR_VERDICT else None
    hashes = [h for h in (dhash(b) for b in images) if h is not None]
    if clip_sim is not None:
        ratio = max(0.0, min(1.0, clip_sim))
        uniq = cluster_ratio(hashes)[1] if hashes else None
        return FeedUniformity(
            images_analyzed=n, cluster_ratio=round(ratio, 3), unique_ratio=None if uniq is None else round(uniq, 3),
            method="clip", flagged=n >= _MIN_FEED_FOR_VERDICT and ratio >= _FEED_FLAG_RATIO,
        )
    if len(hashes) < 2:
        return FeedUniformity(images_analyzed=n, method="none")
    largest, uniq = cluster_ratio(hashes)
    return FeedUniformity(
        images_analyzed=len(hashes), cluster_ratio=round(largest, 3), unique_ratio=round(uniq, 3),
        method="phash", flagged=len(hashes) >= _MIN_FEED_FOR_VERDICT and largest >= _FEED_FLAG_RATIO,
    )


# ------------------------------------------------------------- orkestrasi
async def analyze_target_images(profile_image_url: str | None, feed_urls: list[str]) -> VisionReport:
    """Unduh (SSRF-safe) -> analisis -> hancurkan buffer. Tidak pernah raise."""
    s = get_settings()
    report = VisionReport()
    profile_bytes: bytes | None = None
    feed_bytes: list[bytes] = []
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            if profile_image_url:
                profile_bytes = await security.fetch_public_image(client, profile_image_url, s.max_image_fetch_bytes)
                report.images_fetched += 1 if profile_bytes else 0
                report.images_rejected += 0 if profile_bytes else 1
            sem = asyncio.Semaphore(6)

            async def one(url: str) -> bytes | None:
                async with sem:
                    return await security.fetch_public_image(client, url, s.max_image_fetch_bytes)

            urls = [u for u in dict.fromkeys(feed_urls) if u != profile_image_url][: s.max_feed_images]
            for url, data in zip(urls, await asyncio.gather(*(one(u) for u in urls))):
                if data:
                    feed_bytes.append(data)
                else:
                    report.images_rejected += 1
            report.images_fetched += len(feed_bytes)

        if profile_bytes:
            report.profile_photo = await asyncio.to_thread(analyze_profile_photo, profile_bytes)
        if feed_bytes:
            report.feed = await asyncio.to_thread(analyze_feed, feed_bytes)
    finally:
        profile_bytes = None
        feed_bytes.clear()
        gc.collect()  # Zero-Bloat: tidak ada piksel yang tersisa di RAM proses
        report.buffers_destroyed = True
    return report

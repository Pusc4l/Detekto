"""DETEKTO :: services/ocr_engine.py — Local OCR + Parallel Multi-Target Splitter

Urutan engine: Tesseract (pytesseract) -> EasyOCR (pure Python) -> OcrUnavailableError (pesan rapi, tanpa crash).
Semua proses dari bytes di RAM (io.BytesIO); tanpa penulisan file gambar apa pun.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from core.config import get_settings
from core.security import scan_injection
from models.interrogation import OcrLine, OcrPage, OcrStatus, TargetComment, TargetEntity

try:  # pytesseract opsional saat import; ketiadaan dilaporkan rapi saat dipakai
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - tergantung lingkungan
    pytesseract = None  # type: ignore[assignment]
    Output = None  # type: ignore[assignment]

WINDOWS_HELP = (
    "TESSERACT TIDAK DITEMUKAN. Instal dari https://github.com/UB-Mannheim/tesseract/wiki "
    "(centang bahasa tambahan bila perlu), lalu restart backend. Alternatif: set TESSERACT_CMD di backend/.env "
    "ke lokasi tesseract.exe, atau jalankan 'pip install easyocr' sebagai OCR cadangan."
)


class OcrUnavailableError(Exception):
    """Tidak ada engine OCR yang siap. Pesan sudah ramah-pengguna (aman dikirim ke frontend)."""


# ------------------------------------------------------------ deteksi engine
_WIN_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
_tess_cache: tuple[float, str | None] | None = None
_TESS_CACHE_TTL_S = 10.0


def find_tesseract() -> str | None:
    global _tess_cache
    now = time.monotonic()
    if _tess_cache is not None and now - _tess_cache[0] < _TESS_CACHE_TTL_S:
        return _tess_cache[1]
    s = get_settings()
    candidates: list[str] = []
    if s.tesseract_cmd:
        candidates.append(s.tesseract_cmd)
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates.extend(_WIN_PATHS)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Programs" / "Tesseract-OCR" / "tesseract.exe"))
    found = next((c for c in candidates if Path(c).is_file()), None)
    if found and pytesseract is not None:
        pytesseract.pytesseract.tesseract_cmd = found
    _tess_cache = (now, found)
    return found


def _easyocr_installed() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("easyocr") is not None
    except (ImportError, ValueError):
        return False


def engine_status() -> OcrStatus:
    if pytesseract is not None and find_tesseract():
        return OcrStatus(ready=True, engine="tesseract", message="Tesseract siap.")
    if _easyocr_installed():
        return OcrStatus(ready=True, engine="easyocr", message="Tesseract tidak ada; memakai EasyOCR (model diunduh saat pertama dipakai).")
    return OcrStatus(ready=False, engine="none", message=WINDOWS_HELP)


# ----------------------------------------------------------------- preprocess
def _preprocess(data: bytes) -> Image.Image:
    """Grayscale + autocontrast + upscale 2x bila kecil. Teks UI media sosial kecil -> Tesseract butuh >= ~30px tinggi huruf."""
    with Image.open(BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img).convert("L")
        img = ImageOps.autocontrast(img, cutoff=1)
        if img.width < 1100:
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
        return img.copy()


# ---------------------------------------------------------------- tesseract
def _tesseract_page(data: bytes) -> OcrPage:
    assert pytesseract is not None and Output is not None
    s = get_settings()
    img = _preprocess(data)
    config = "--oem 3 --psm 6"  # psm 6 = satu blok teks seragam: paling stabil untuk daftar komentar vertikal
    try:
        raw: dict[str, list[Any]] = pytesseract.image_to_data(
            img, lang=s.ocr_lang, config=config, output_type=Output.DICT, timeout=s.ocr_timeout_seconds
        )
    except pytesseract.TesseractError as exc:
        msg = str(exc)
        if s.ocr_lang != "eng" and ("language" in msg.lower() or "data file" in msg.lower()):
            raw = pytesseract.image_to_data(
                img, lang="eng", config=config, output_type=Output.DICT, timeout=s.ocr_timeout_seconds
            )
        else:
            raise

    grouped: dict[tuple[int, int, int], list[tuple[int, str, float]]] = {}
    for i, word in enumerate(raw["text"]):
        text = str(word).strip()
        try:
            conf = float(raw["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 0:
            continue
        key = (int(raw["block_num"][i]), int(raw["par_num"][i]), int(raw["line_num"][i]))
        grouped.setdefault(key, []).append((int(raw["left"][i]), text, conf))

    lines: list[OcrLine] = []
    for _, words in sorted(grouped.items()):
        words.sort(key=lambda w: w[0])
        text = " ".join(w[1] for w in words)[:400]
        conf = sum(w[2] for w in words) / len(words)
        lines.append(OcrLine(text=text, conf=max(0.0, min(100.0, conf))))
    mean = sum(l.conf for l in lines) / len(lines) if lines else 0.0
    return OcrPage(engine="tesseract", lines=lines, mean_conf=mean)


# ------------------------------------------------------------------ easyocr
_easy_reader: Any = None


def _easyocr_page(data: bytes) -> OcrPage:
    global _easy_reader
    import easyocr  # type: ignore[import-not-found]

    if _easy_reader is None:
        _easy_reader = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
    results = _easy_reader.readtext(data)  # menerima bytes langsung -> tanpa file sementara
    boxes: list[tuple[float, float, float, str, float]] = []  # (y_center, x_left, height, text, conf)
    for bbox, text, conf in results:
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        boxes.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), str(text).strip(), float(conf) * 100))
    boxes.sort(key=lambda b: (b[0], b[1]))

    rows: list[list[tuple[float, float, float, str, float]]] = []
    for box in boxes:
        if rows and abs(box[0] - rows[-1][0][0]) < 0.6 * max(box[2], rows[-1][0][2], 1.0):
            rows[-1].append(box)
        else:
            rows.append([box])
    lines: list[OcrLine] = []
    for row in rows:
        row.sort(key=lambda b: b[1])
        text = " ".join(b[3] for b in row if b[3])[:400]
        if text:
            conf = sum(b[4] for b in row) / len(row)
            lines.append(OcrLine(text=text, conf=max(0.0, min(100.0, conf))))
    mean = sum(l.conf for l in lines) / len(lines) if lines else 0.0
    return OcrPage(engine="easyocr", lines=lines, mean_conf=mean)


# --------------------------------------------------------------- API publik
def ocr_image_sync(data: bytes) -> OcrPage:
    """Tesseract -> EasyOCR. Raise OcrUnavailableError bila keduanya tak tersedia / gagal."""
    tess_error: str | None = None
    if pytesseract is not None and find_tesseract():
        try:
            return _tesseract_page(data)
        except pytesseract.TesseractNotFoundError:
            global _tess_cache
            _tess_cache = None
            tess_error = "Tesseract hilang saat dijalankan"
        except (pytesseract.TesseractError, RuntimeError) as exc:
            tess_error = f"Tesseract gagal ({type(exc).__name__})"

    if _easyocr_installed():
        try:
            return _easyocr_page(data)
        except Exception as exc:
            raise OcrUnavailableError(f"EasyOCR gagal dijalankan ({type(exc).__name__}). {WINDOWS_HELP}") from exc

    raise OcrUnavailableError(f"{tess_error + '. ' if tess_error else ''}{WINDOWS_HELP}")


_sem: asyncio.Semaphore | None = None


async def ocr_image(data: bytes) -> OcrPage:
    """Async wrapper: thread terpisah + semaphore (cegah 10 proses Tesseract membekukan PC pengguna)."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(get_settings().max_ocr_concurrency)
    async with _sem:
        return await asyncio.to_thread(ocr_image_sync, data)


# ===================== Parallel Multi-Target Splitter =====================
_TIME = (
    # [\dlIiOo]: Tesseract sering salah baca "1h" -> "lh"/"Ih" dan "0" -> "O". Aman karena header polos tetap digating (_handle_looks_special).
    r"(?:[\dlIiOo]{1,3}\s?(?:s|m|h|d|w|j|mo|y|detik|menit|mnt|jam|hari|hr|mgg|minggu|bln|bulan|thn|tahun)\b"
    r"|baru saja|just now|yesterday|kemarin)"
)
_SEP = r"(?:\s*[·•\-–|]\s*|\s+)"
_HANDLE = r"@?[A-Za-z0-9][A-Za-z0-9._]{1,29}"
_HEADER_RE = re.compile(rf"^(?P<handle>{_HANDLE}){_SEP}(?P<time>{_TIME})\s*(?P<rest>.*)$", re.I)
_AT_TIME_RE = re.compile(rf"^(?:.{{0,40}}?\s)?@(?P<handle>[A-Za-z0-9_.]{{2,30}}){_SEP}(?P<time>{_TIME})\s*(?P<rest>.*)$", re.I)
_ONLY_HANDLE_RE = re.compile(r"^@(?P<handle>[A-Za-z0-9_.]{2,30})$")
_NOISE_RE = re.compile(
    r"^(reply|balas|like|suka|translate|see translation|lihat terjemahan|hide replies|sembunyikan balasan|"
    r"view \d+ repl|lihat \d+ balasan|view all|lihat semua|\d+ repl(?:y|ies)|\d+ balasan)\b",
    re.I,
)
_LIKES_RE = re.compile(r"^[♡♥❤🤍]?\s*(?P<n>\d[\d.,]*\s?(?:k|m|rb|jt)?)\s*(?:likes?|suka|disukai)?$", re.I)
_LIKES_TRAIL_RE = re.compile(r"(?P<n>\d[\d.,]*\s?(?:k|m|rb|jt)?)\s*(?:likes?|suka|disukai)\s*$", re.I)
_NOISE_HANDLES = {"reply", "view", "like", "likes", "see", "more", "hide", "translate", "balas", "suka", "lihat"}


def parse_count(raw: str) -> int:
    s = raw.strip().lower().replace(" ", "")
    mult = 1
    for suffix, m in (("rb", 1_000), ("jt", 1_000_000), ("k", 1_000), ("m", 1_000_000)):
        if s.endswith(suffix):
            mult, s = m, s[: -len(suffix)]
            break
    if mult > 1:
        s = s.replace(",", ".")
        try:
            return int(float(s) * mult)
        except ValueError:
            return 0
    digits = re.sub(r"[.,]", "", s)
    return int(digits) if digits.isdigit() else 0


def _valid_handle(h: str) -> bool:
    h = h.lstrip("@").lower()
    return 2 <= len(h) <= 30 and h not in _NOISE_HANDLES and any(c.isalpha() for c in h)


def _handle_looks_special(raw: str) -> bool:
    return raw.startswith("@") or any(c in raw for c in "._0123456789")


def _detect_header(line: str) -> tuple[str, str] | None:
    """Kembalikan (username, sisa_teks) jika baris adalah header komentar, selain itu None."""
    m = _ONLY_HANDLE_RE.match(line)
    if m and _valid_handle(m["handle"]):
        return m["handle"].lower(), ""
    m = _AT_TIME_RE.match(line)
    if m and _valid_handle(m["handle"]):
        return m["handle"].lower(), m["rest"].strip()
    m = _HEADER_RE.match(line)
    if m and _valid_handle(m["handle"]):
        rest = m["rest"].strip()
        # handle tanpa ciri khusus ("mantap 2 jam") hanya dianggap header bila sisa baris kosong / UI noise
        if _handle_looks_special(m["handle"]) or rest == "" or _NOISE_RE.match(rest) or _LIKES_TRAIL_RE.search(rest):
            return m["handle"].lstrip("@").lower(), rest
    return None


class _Draft:
    __slots__ = ("username", "parts", "likes", "image_index")

    def __init__(self, username: str, image_index: int) -> None:
        self.username = username
        self.parts: list[str] = []
        self.likes = 0
        self.image_index = image_index


def _feed_text(draft: _Draft, text: str) -> None:
    text = text.strip()
    if not text or _NOISE_RE.match(text):
        return
    trail = _LIKES_TRAIL_RE.search(text)
    if trail:
        draft.likes = max(draft.likes, parse_count(trail["n"]))
        text = text[: trail.start()].strip(" ·•-–|")
    if text:
        draft.parts.append(text)


def split_targets(pages: list[OcrPage]) -> list[TargetEntity]:
    """Pisahkan hasil OCR banyak screenshot menjadi daftar target unik beserta komentar & likes masing-masing."""
    comments_by_user: dict[str, list[TargetComment]] = {}
    images_by_user: dict[str, set[int]] = {}

    def commit(d: _Draft | None) -> None:
        if d is None:
            return
        text = " ".join(d.parts).strip()[:500]
        if not text:
            return
        flag = bool(scan_injection(text))
        comments_by_user.setdefault(d.username, []).append(
            TargetComment(text=text, likes=d.likes, image_index=d.image_index, injection_flag=flag)
        )
        images_by_user.setdefault(d.username, set()).add(d.image_index)

    for idx, page in enumerate(pages):
        draft: _Draft | None = None
        for line in page.lines:
            text = line.text.strip()
            if not text:
                continue
            header = _detect_header(text)
            if header is not None:
                commit(draft)
                draft = _Draft(header[0], idx)
                _feed_text(draft, header[1])
                continue
            if draft is None:
                continue  # baris sebelum komentar pertama = caption/header postingan
            like_only = _LIKES_RE.match(text)
            if like_only and draft.parts and len(text) <= 12:
                draft.likes = max(draft.likes, parse_count(like_only["n"]))
                continue
            _feed_text(draft, text)
        commit(draft)

    targets: list[TargetEntity] = []
    for username, comments in comments_by_user.items():
        targets.append(
            TargetEntity(
                username=username,
                comment_count=len(comments),
                total_likes=sum(c.likes for c in comments),
                image_indexes=sorted(images_by_user[username]),
                injection_flag=any(c.injection_flag for c in comments),
                comments=comments[:20],
            )
        )
    targets.sort(key=lambda t: (-t.comment_count, -t.total_likes, t.username))
    return targets[:25]

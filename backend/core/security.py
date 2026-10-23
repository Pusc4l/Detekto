"""DETEKTO :: core/security.py
Zero-Trust gatekeeper: validasi gambar Base64 (signature malware / polyglot / bom dekompresi),
sanitasi teks, validasi URL, dan deteksi Prompt Injection untuk teks hasil OCR / DOM.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import unicodedata
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 80_000_000  # anti decompression-bomb

MAX_IMAGE_BYTES = 2_000_000  # < 2MB, identik dengan batas kompresor frontend
MAX_IMAGE_PIXELS = 80_000_000

PLATFORM_HOSTS: dict[str, tuple[str, ...]] = {
    "instagram": ("instagram.com",),
    "x": ("x.com", "twitter.com"),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com", "fb.com", "fb.watch"),
    "youtube": ("youtube.com", "youtu.be"),
}

_UNSAFE_CHARS = re.compile(r"[\u0000-\u0008\u000B-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]")


class EvidenceRejected(Exception):
    """Bukti ditolak oleh gatekeeper. code = kategori mesin, message = pesan rapi untuk UI."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ------------------------------------------------------------------ teks
def sanitize_text(raw: str, max_len: int) -> str:
    return _UNSAFE_CHARS.sub("", raw)[:max_len]


def neutralize_for_prompt(text: str) -> str:
    """Hancurkan karakter < > agar teks tidak bisa menutup/membuka tag delimiter <untrusted_*>."""
    return _UNSAFE_CHARS.sub("", text).replace("<", "‹").replace(">", "›")


def wrap_untrusted(tag: str, text: str) -> str:
    return f"<{tag}>\n{neutralize_for_prompt(text)}\n</{tag}>"


# --------------------------------------------------------- prompt injection
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("IGNORE_PREVIOUS", re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|system)\b.{0,30}\b(instruction|prompt|rule|direction)s?", re.I)),
    ("ABAIKAN_INSTRUKSI", re.compile(r"\b(abaikan|lupakan|kesampingkan|acuhkan)\b.{0,40}\b(instruksi|perintah|petunjuk|aturan)", re.I)),
    ("ROLE_HIJACK", re.compile(r"\b(you are now|act as|pretend to be|kamu sekarang|anda sekarang|bertindaklah sebagai|berperanlah sebagai)\b", re.I)),
    ("SYSTEM_PROMPT", re.compile(r"\b(system prompt|developer message|jailbreak|dan mode|prompt sistem)\b", re.I)),
    ("FORCE_OUTPUT", re.compile(r"\b(output|print|respond|reply|balas|keluarkan|tampilkan|jawab)\b.{0,30}\b(100\s?%|only|hanya|json|verdict|vonis)\b", re.I)),
    ("FORCE_VERDICT", re.compile(r"\b(100\s?%|seratus persen)\b.{0,25}\b(organic|organik|citizen|warga|human|manusia|buzzer|bot)\b", re.I)),
    ("NEW_INSTRUCTIONS", re.compile(r"\b(new instructions?|instruksi baru|perintah baru)\b", re.I)),
    ("TAG_BREAKOUT", re.compile(r"</?\s*untrusted|<\|?\s*(im_start|im_end|system)\b", re.I)),
)


def scan_injection(text: str) -> list[str]:
    """Kembalikan label pola injeksi yang terdeteksi (list kosong = bersih)."""
    normalized = unicodedata.normalize("NFKC", _UNSAFE_CHARS.sub("", text))
    return [label for label, pattern in _INJECTION_PATTERNS if pattern.search(normalized)]


# ------------------------------------------------------------------- URL
def validate_post_url(raw: str, platform: str) -> str:
    """Hanya https, tanpa kredensial, host wajib milik platform terpilih. Raise ValueError jika tidak valid."""
    value = raw.strip()
    if not value:
        raise ValueError("URL kosong")
    if len(value) > 300:
        raise ValueError("URL terlalu panjang")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
    except ValueError as exc:
        raise ValueError("Format URL tidak valid") from exc
    if parts.scheme != "https":
        raise ValueError("Hanya https yang diterima")
    if parts.username or parts.password:
        raise ValueError("URL berkredensial ditolak")
    allowed = PLATFORM_HOSTS.get(platform, ())
    if not any(host == h or host.endswith(f".{h}") for h in allowed):
        raise ValueError("Host bukan milik platform terpilih")
    return value


# ----------------------------------------------------------------- gambar
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "EXECUTABLE WINDOWS (PE/EXE/DLL)"),
    (b"\x7fELF", "EXECUTABLE LINUX (ELF)"),
    (b"%PDF", "DOKUMEN PDF"),
    (b"PK\x03\x04", "ARSIP ZIP/APK/JAR"),
    (b"Rar!", "ARSIP RAR"),
    (b"#!", "SKRIP SHELL"),
    (b"<?php", "SKRIP PHP"),
    (b"<script", "SKRIP HTML/JS"),
    (b"<html", "DOKUMEN HTML"),
    (b"<svg", "SVG (VEKTOR BERSKRIP)"),
    (b"<?xml", "XML/SVG"),
    (b"GIF8", "GIF"),
    (b"\x89PNG", "PNG (FRONTEND WAJIB MENGIRIM JPEG)"),
)

# Penanda payload tertanam (polyglot). Dibuat cukup panjang agar peluang salah-deteksi pada data JPEG acak ~ 0.
_EMBEDDED_MARKERS: tuple[tuple[bytes, str], ...] = (
    (b"<script", "TAG <script> TERTANAM"),
    (b"<?php", "KODE PHP TERTANAM"),
    (b"javascript:", "URI javascript: TERTANAM"),
    (b"This program cannot be run in DOS mode", "BINARY WINDOWS TERTANAM"),
    (b"\x7fELF\x02\x01\x01", "BINARY ELF TERTANAM"),
    (b"MZ\x90\x00\x03\x00\x00\x00", "HEADER PE TERTANAM"),
    (b"powershell -", "PERINTAH POWERSHELL TERTANAM"),
)


def decode_and_verify_image(b64: str, claimed_sha256: str, label: str) -> bytes:
    """Decode strict -> cek signature -> verifikasi hash -> validasi struktur JPEG via Pillow. Semua di RAM."""
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EvidenceRejected("BASE64", f"{label}: BASE64 TIDAK VALID") from exc

    if not data:
        raise EvidenceRejected("EMPTY", f"{label}: DATA KOSONG")
    if len(data) >= MAX_IMAGE_BYTES:
        raise EvidenceRejected("TOO_LARGE", f"{label}: MELEBIHI BATAS 2 MB")

    head = data[:16]
    if not head.startswith(b"\xff\xd8\xff"):
        lowered = head.lower()
        for sig, name in _SIGNATURES:
            if lowered.startswith(sig.lower()):
                raise EvidenceRejected("SIGNATURE", f"{label}: DITOLAK — TERDETEKSI {name}, BUKAN GAMBAR JPEG")
        raise EvidenceRejected("SIGNATURE", f"{label}: DITOLAK — BUKAN GAMBAR JPEG")

    lowered_all = data.lower()
    for marker, name in _EMBEDDED_MARKERS:
        if marker.lower() in lowered_all:
            raise EvidenceRejected("POLYGLOT", f"{label}: DITOLAK — {name}")

    actual = hashlib.sha256(data).hexdigest()
    if actual != claimed_sha256.lower():
        raise EvidenceRejected("HASH", f"{label}: HASH SHA-256 TIDAK COCOK (DATA DIMANIPULASI)")

    try:
        with Image.open(BytesIO(data)) as img:
            if img.format != "JPEG":
                raise EvidenceRejected("FORMAT", f"{label}: FORMAT BUKAN JPEG")
            width, height = img.size
            if width * height > MAX_IMAGE_PIXELS:
                raise EvidenceRejected("PIXELS", f"{label}: RESOLUSI TERLALU TINGGI")
            img.verify()
    except EvidenceRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError) as exc:
        raise EvidenceRejected("CORRUPT", f"{label}: STRUKTUR JPEG RUSAK / PALSU") from exc
    return data


# ===================== Fase 4: SSRF guard untuk URL hasil scraping =====================
import asyncio as _asyncio
import ipaddress as _ipaddress
import socket as _socket
from urllib.parse import urljoin as _urljoin

import httpx as _httpx

_MAX_REDIRECTS = 3


async def is_public_https_url(url: str) -> bool:
    """URL gambar dari halaman scraping = Untrusted. Tolak skema non-https dan host yang meresolusi ke IP privat/loopback/link-local."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    try:
        infos = await _asyncio.get_running_loop().getaddrinfo(host, parts.port or 443, type=_socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not _ipaddress.ip_address(info[4][0]).is_global:
                return False
        except ValueError:
            return False
    return True


async def fetch_public_image(client: _httpx.AsyncClient, url: str, max_bytes: int) -> bytes | None:
    """Unduh gambar publik ke RAM saja. Redirect diikuti manual (maks 3) dan SETIAP hop divalidasi ulang. Batas ukuran streaming."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        if not await is_public_https_url(current):
            return None
        try:
            async with client.stream("GET", current, follow_redirects=False) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        return None
                    current = _urljoin(current, location)
                    continue
                if resp.status_code != 200 or not resp.headers.get("content-type", "").lower().startswith("image/"):
                    return None
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    return None
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes(65_536):
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
        except (_httpx.HTTPError, OSError):
            return None
    return None

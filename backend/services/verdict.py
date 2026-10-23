"""DETEKTO :: services/verdict.py — Strict Threshold Dictator (Task 5.2)

Zero Grey-Area: probabilitas gabungan >= ambang (65%) => BUZZER (Type A/B); < ambang => ORGANIC (Type C). Tidak ada kelas "mungkin".

ANTI-TERTIPU (Evidence Gate): probabilitas SGD saja tidak cukup untuk menjatuhkan vonis BUZZER. Vonis sah hanya bila
  (1) >= 2 keluarga sinyal INDEPENDEN menyala, dan
  (2) minimal satu di antaranya BUKAN sinyal teks (akun / visual / jaringan).
Kemiripan teks tinggi + metadata organik => hanya 1 keluarga => skor dikunci di bawah ambang => ORGANIC. Organik sering menyalin slogan,
meme, atau mengutip headline; copy-paste murni bukan bukti koordinasi. Gate bekerja di atas model sehingga tetap aman walau bobot SGD
dimanipulasi lewat feedback berulang.
Rancangan sengaja mengutamakan presisi (menghindari tuduhan palsu) di atas recall, karena keluaran dapat dipakai untuk mass report.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from core.config import get_settings
from models.swarm import ProfileMetadata, VisionReport
from models.verdict import BuzzerType, EvidenceIn, Family, GateReport

ELEVATED: dict[str, float] = {"account": 0.55, "narrative_copy": 0.75, "content_hostility": 0.60, "visual": 0.60}
NON_TEXTUAL: frozenset[str] = frozenset({"account", "visual", "network"})
_FAMILY_MEMBERS: dict[str, tuple[str, ...]] = {
    "account": ("account_age_risk", "rename_frequency", "engagement_anomaly"),
    "narrative_copy": ("copypaste_similarity",),
    "content_hostility": ("gt_deviation",),
    "visual": ("visual_anomaly",),
}

_MONTHS = {
    "jan": 1, "january": 1, "januari": 1, "feb": 2, "february": 2, "februari": 2, "mar": 3, "march": 3, "maret": 3, "apr": 4, "april": 4,
    "may": 5, "mei": 5, "jun": 6, "june": 6, "juni": 6, "jul": 7, "july": 7, "juli": 7, "aug": 8, "agu": 8, "agt": 8, "august": 8, "agustus": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "okt": 10, "october": 10, "oktober": 10, "nov": 11, "november": 11, "nop": 11,
    "dec": 12, "des": 12, "december": 12, "desember": 12,
}


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))


# -------------------------------------------------------------- fitur akun
def parse_account_date(text: str | None) -> datetime | None:
    """Terima 'March 2023', 'Maret 2023', '2023-03-15', '15/03/2023'. None bila tak terbaca."""
    if not text:
        return None
    t = text.strip().lower()
    m = re.search(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", t)
    if m and 1 <= int(m[2]) <= 12:
        return datetime(int(m[1]), int(m[2]), int(m[3] or 1), tzinfo=timezone.utc)
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", t)
    if m and 1 <= int(m[2]) <= 12:
        return datetime(int(m[3]), int(m[2]), min(int(m[1]), 28), tzinfo=timezone.utc)
    m = re.search(r"([a-z]{3,9})\.?\s+(\d{4})", t)
    if m and m[1] in _MONTHS:
        return datetime(int(m[2]), _MONTHS[m[1]], 1, tzinfo=timezone.utc)
    m = re.search(r"\b(20\d{2}|19\d{2})\b", t)
    return datetime(int(m[1]), 7, 1, tzinfo=timezone.utc) if m else None


def account_age_risk(profile: ProfileMetadata | None, now: datetime) -> float | None:
    """Umur akun dinormalisasi: akun < 90 hari ~ 0.9+, akun >= 3 tahun = 0. Makin tinggi = makin mencurigakan."""
    born = parse_account_date(profile.account_creation_date) if profile else None
    if born is None or born > now:
        return None
    return round(1.0 - min((now - born).days / 1095.0, 1.0), 4)


def rename_frequency(profile: ProfileMetadata | None, now: datetime) -> float | None:
    """Frekuensi ganti username per tahun (>= 3x/tahun = 1.0). Tanpa umur: skala absolut (>= 4 ganti = 1.0)."""
    if profile is None or profile.username_change_count is None:
        return None
    born = parse_account_date(profile.account_creation_date)
    if born is not None and born <= now:
        years = max((now - born).days / 365.0, 0.25)
        return round(_clip(profile.username_change_count / years / 3.0), 4)
    return round(_clip(profile.username_change_count / 4.0), 4)


def engagement_anomaly(profile: ProfileMetadata | None) -> float | None:
    """Rasio followers/following ekstrem: mass-following (rasio < 0.3) atau follower 'dibeli' pada akun nyaris tanpa postingan."""
    if profile is None or profile.follower_following_ratio is None:
        return None
    r = profile.follower_following_ratio
    low = _clip((0.3 - r) / 0.3) if r < 0.3 else 0.0
    posts = profile.post_count
    high = _clip(math.log10(r / 50.0) / 1.5) if r > 50 and (posts is None or posts < 10) else 0.0
    return round(max(low, high), 4)


def visual_anomaly(vision: VisionReport | None) -> float | None:
    if vision is None:
        return None
    parts: list[tuple[float, float]] = []
    if vision.profile_photo is not None and vision.profile_photo.label != "insufficient":
        parts.append((vision.profile_photo.score, 0.6))
    if vision.feed is not None and vision.feed.cluster_ratio is not None and vision.feed.method != "none":
        parts.append((_clip((vision.feed.cluster_ratio - 0.5) / 0.5), 0.4))
    if not parts:
        return None
    total = sum(w for _, w in parts)
    return round(sum(v * w for v, w in parts) / total, 4)


def compute_features(
    profile: ProfileMetadata | None,
    vision: VisionReport | None,
    copy_similarity: float | None,
    gt_deviation: float | None,
    now: datetime | None = None,
) -> dict[str, float | None]:
    now = now or datetime.now(timezone.utc)
    return {
        "account_age_risk": account_age_risk(profile, now),
        "rename_frequency": rename_frequency(profile, now),
        "engagement_anomaly": engagement_anomaly(profile),
        "copypaste_similarity": None if copy_similarity is None else round(_clip(copy_similarity), 4),
        "gt_deviation": None if gt_deviation is None else round(_clip(gt_deviation), 4),
        "visual_anomaly": visual_anomaly(vision),
    }


def coverage(features: dict[str, float | None]) -> float:
    return round(sum(v is not None for v in features.values()) / len(features), 3)


# --------------------------------------------------------------- Evidence Gate
def elevated_families(features: dict[str, float | None], evidence: EvidenceIn) -> list[Family]:
    out: list[Family] = []
    acct = [features[k] for k in _FAMILY_MEMBERS["account"] if features.get(k) is not None]
    if acct and sum(acct) / len(acct) >= ELEVATED["account"]:  # type: ignore[arg-type]
        out.append("account")
    for fam, key in (("narrative_copy", "copypaste_similarity"), ("content_hostility", "gt_deviation"), ("visual", "visual_anomaly")):
        v = features.get(key)
        if v is not None and v >= ELEVATED[fam]:
            out.append(fam)  # type: ignore[arg-type]
    # Jaringan: independen dari teks (tautan grup yang sama dengan target lain / percobaan injeksi prompt)
    if evidence.shared_groups >= 1 or evidence.injection_attempt:
        out.append("network")
    return out


def evaluate_gate(features: dict[str, float | None], evidence: EvidenceIn) -> GateReport:
    fams = elevated_families(features, evidence)
    non_text = [f for f in fams if f in NON_TEXTUAL]
    if len(fams) >= 2 and non_text:
        return GateReport(passed=True, elevated=fams, reason=f"{len(fams)} keluarga sinyal independen menyala ({', '.join(fams)}).")
    if not fams:
        return GateReport(passed=False, elevated=fams, reason="Tidak ada keluarga sinyal yang menyala.")
    if len(fams) == 1:
        return GateReport(
            passed=False, elevated=fams,
            reason=f"DITAHAN: hanya 1 keluarga sinyal ({fams[0]}). Vonis BUZZER butuh >= 2 keluarga independen — satu sinyal saja bisa terjadi pada pengguna organik.",
        )
    return GateReport(
        passed=False, elevated=fams,
        reason=f"DITAHAN: sinyal hanya berbasis teks ({', '.join(fams)}). Wajib ada bukti non-teks (akun / visual / jaringan).",
    )


# ------------------------------------------------------------- ambang diktator
def threshold() -> float:
    return get_settings().verdict_threshold


def apply_dictator(raw_probability: float, gate: GateReport) -> tuple[float, bool]:
    """Kembalikan (probabilitas_final, is_buzzer). Gate gagal => dikunci tepat di bawah ambang. Perbandingan memakai nilai tak terbulat."""
    t = threshold()
    final = raw_probability if gate.passed else min(raw_probability, t - 1e-6)
    return final, final >= t


def classify_type(is_buzzer: bool, features: dict[str, float | None], evidence: EvidenceIn) -> BuzzerType:
    """Type A: bot (salinan >= 90% + profil kosong / visual anomali / akun sangat baru). Type B: buzzer manusia. Type C: organik."""
    if not is_buzzer:
        return "C"
    copy = features.get("copypaste_similarity") or 0.0
    visual = features.get("visual_anomaly") or 0.0
    age = features.get("account_age_risk") or 0.0
    if copy >= 0.90 and (evidence.profile_empty or visual >= 0.60 or age >= 0.70):
        return "A"
    return "B"


def display_percent(p: float) -> float:
    """Pemotongan (bukan pembulatan) ke 0,1% agar skor tampil selalu konsisten dengan vonis."""
    return math.floor(max(0.0, min(1.0, p)) * 1000.0) / 10.0

"""DETEKTO :: services/cross_post_matcher.py — Cross-Post Activity Matcher / Jaring Pukat (Task 4.3)

1) Automated OSINT Dorking: site:{platform}.com "{username}" "{keyword}" via SearxNG -> fallback duckduckgo-search.
2) Thread Sweep: komentar thread dari Playwright dicocokkan terhadap komentar target (copy-paste detection, Jaccard 3-gram).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from models.interrogation import OcrLine, OcrPage, TargetComment
from models.swarm import CopyPasteHit, CrossPostHit
from services.context_parser import LogFn, search_ground_truth
from services.ocr_engine import split_targets

PLATFORM_DOMAINS = {
    "instagram": "instagram.com",
    "x": "x.com",
    "tiktok": "tiktok.com",
    "facebook": "facebook.com",
    "youtube": "youtube.com",
}
MIN_WORDS_FOR_COPYPASTE = 5
COPYPASTE_THRESHOLD = 0.75


def build_dork_queries(platform: str, username: str, keywords: list[str]) -> list[str]:
    domain = PLATFORM_DOMAINS.get(platform, f"{platform}.com")
    kws = [k for k in keywords if k.strip()][:2]
    queries = [f'site:{domain} "{username}" "{k}"' for k in kws]
    queries.append(f'"{username}" {kws[0] if kws else ""}'.strip())  # jaring luas lintas situs
    return queries[:3]


async def dork_search(platform: str, username: str, keywords: list[str], log: LogFn) -> list[CrossPostHit]:
    sources, _engine = await search_ground_truth(build_dork_queries(platform, username, keywords), log)
    needle = username.lower()
    hits: list[CrossPostHit] = []
    for src in sources:
        blob = f"{src.title} {src.snippet} {src.url}".lower()
        hits.append(
            CrossPostHit(
                title=src.title, url=src.url, snippet=src.snippet, engine=src.engine, mentions_target=needle in blob
            )
        )
    hits.sort(key=lambda h: not h.mentions_target)
    return hits[:12]


# --------------------------------------------------------------- copy-paste
def _shingles(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < MIN_WORDS_FOR_COPYPASTE:
        return set()
    return {" ".join(words[i : i + 3]) for i in range(len(words) - 2)}


def similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_copy_paste(
    target: str,
    target_comments: list[str],
    others: dict[str, list[str]],
    basis: str,
) -> list[CopyPasteHit]:
    """Bandingkan komentar target dengan komentar akun lain; kembalikan pasangan paling mirip per akun (>= ambang)."""
    best: dict[str, CopyPasteHit] = {}
    for other, texts in others.items():
        if other == target:
            continue
        for mine in target_comments:
            for theirs in texts:
                sim = similarity(mine, theirs)
                if sim >= COPYPASTE_THRESHOLD and (other not in best or sim > best[other].similarity):
                    best[other] = CopyPasteHit(
                        other_username=other, similarity=round(sim, 3), sample=mine[:140], basis=basis  # type: ignore[arg-type]
                    )
    return sorted(best.values(), key=lambda h: -h.similarity)[:10]


def parse_thread_comments(text: str) -> dict[str, list[TargetComment]]:
    """Pecah teks DOM thread menjadi {username: [komentar]} memakai splitter yang sama dengan OCR Fase 3."""
    lines = [OcrLine(text=ln.strip()[:400], conf=100.0) for ln in text.splitlines() if ln.strip()]
    page = OcrPage(engine="dom", lines=lines, mean_conf=100.0)
    return {t.username: t.comments for t in split_targets([page])}


def host_matches(url: str, domain: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host == domain or host.endswith(f".{domain}")

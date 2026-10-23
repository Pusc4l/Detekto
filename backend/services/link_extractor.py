"""DETEKTO :: services/link_extractor.py — The Syndicate Crawler (Regex Radar)

Mendeteksi tautan grup/sosmed publik (Telegram, WhatsApp, Reddit, Threads, Instagram, TikTok, Twitter/X, Discord,
Facebook Groups) di bio, komentar, dan teks halaman. Tautan hanya DICATAT, TIDAK PERNAH dikunjungi (anti-SSRF / anti-malware).
Privasi: tautan nomor pribadi (wa.me/<nomor>) sengaja DIABAIKAN.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable
from urllib.parse import parse_qsl, unquote, urlsplit

from models.swarm import LinkKind, LinkSource, SocialPlatform, SyndicateLink

_ZERO_WIDTH = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060\u2066-\u2069\uFEFF]")
_HOSTS = r"(?:t\.me|telegram\.me|telegram\.dog|chat\.whatsapp\.com|whatsapp\.com|reddit\.com|threads\.net|threads\.com|instagram\.com|instagr\.am|tiktok\.com|twitter\.com|x\.com|discord\.gg|discord\.com|discordapp\.com|facebook\.com)"
_PRE = r"(?<![\w@.\-])(?:https?://)?(?:www\.|m\.|mobile\.|vm\.)?"

_IG_RESERVED = frozenset(
    "p reel reels tv explore stories accounts direct about developer legal privacy web challenge directory oauth emails "
    "static ar nametag session login signup api graphql topics locations tags".split()
)
_TW_RESERVED = frozenset(
    "i home search intent share hashtag explore messages settings compose notifications login signup tos privacy about "
    "download help jobs account lists".split()
)
_TG_RESERVED = frozenset("share addstickers addemoji proxy socks setlanguage login iv c boost contact".split())

# (nama, regex) — urutan tidak penting; hasil dideduplikasi lewat URL kanonik.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "telegram": re.compile(_PRE + r"(?:t\.me|telegram\.me|telegram\.dog)/(?:s/)?(?P<path>(?:\+|joinchat/)?[A-Za-z0-9_\-]{4,64})", re.I),
    "wa_group": re.compile(_PRE + r"chat\.whatsapp\.com/(?:invite/)?(?P<code>[A-Za-z0-9]{16,32})", re.I),
    "wa_channel": re.compile(_PRE + r"whatsapp\.com/channel/(?P<code>[A-Za-z0-9]{10,40})", re.I),
    "reddit": re.compile(_PRE + r"(?:old\.)?reddit\.com/(?P<k>r|user|u)/(?P<name>[A-Za-z0-9_\-]{3,21})", re.I),
    "threads": re.compile(_PRE + r"threads\.(?:net|com)/@(?P<name>[A-Za-z0-9._]{2,30})(?:/post/(?P<post>[A-Za-z0-9_\-]{5,40}))?", re.I),
    "ig_post": re.compile(_PRE + r"(?:instagram\.com|instagr\.am)/(?:p|reel|reels|tv)/(?P<code>[A-Za-z0-9_\-]{5,20})", re.I),
    "instagram": re.compile(_PRE + r"(?:instagram\.com|instagr\.am)/(?P<name>[A-Za-z0-9._]{2,30})(?![A-Za-z0-9._])", re.I),
    "tiktok": re.compile(_PRE + r"tiktok\.com/@(?P<name>[A-Za-z0-9._]{2,30})", re.I),
    "tiktok_short": re.compile(r"(?<![\w.\-])(?:https?://)?vm\.tiktok\.com/(?P<code>[A-Za-z0-9]{6,15})", re.I),
    "twitter": re.compile(_PRE + r"(?:twitter\.com|x\.com)/(?P<name>[A-Za-z0-9_]{1,15})(?:/status/(?P<sid>\d{5,25}))?", re.I),
    "discord": re.compile(r"(?<![\w.\-])(?:https?://)?(?:discord\.gg|(?:discord|discordapp)\.com/invite)/(?P<code>[A-Za-z0-9\-]{2,32})", re.I),
    "fb_group": re.compile(_PRE + r"facebook\.com/groups/(?P<name>[A-Za-z0-9._\-]{3,80})", re.I),
}

_REDIRECT_KEYS = ("u", "url", "q", "target", "dest")


def normalize_text(text: str) -> str:
    """Bongkar obfuskasi umum: t[.]me, hxxps, spasi di sekitar '.' atau '/', karakter zero-width / fullwidth."""
    t = unicodedata.normalize("NFKC", _ZERO_WIDTH.sub("", text))
    t = re.sub(r"\[\s*\.\s*\]|\(\s*\.\s*\)|\{\s*\.\s*\}", ".", t)
    t = re.sub(r"\bhxxp(s?)\b", lambda m: "http" + m.group(1), t, flags=re.I)
    t = re.sub(r"\b(t)\s*\.\s*(me)\b", r"\1.\2", t, flags=re.I)
    t = re.sub(rf"(?<![\w.\-])({_HOSTS})\s*/\s*", r"\1/", t, flags=re.I)
    return t


def decode_redirect(href: str) -> str:
    """Bongkar tautan pembungkus (l.instagram.com/?u=..., facebook.com/l.php?u=...) agar tautan asli terbaca."""
    current = href
    for _ in range(2):
        try:
            parts = urlsplit(current)
        except ValueError:
            return current
        inner = next((v for k, v in parse_qsl(parts.query) if k in _REDIRECT_KEYS and v.lower().startswith(("http", "%68")) ), None)
        if inner is None:
            return current
        current = unquote(inner)
    return current


def _snippet(text: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - 40) : end + 40]).strip()[:160]


def _link(platform: SocialPlatform, kind: LinkKind, url: str, ident: str, source: LinkSource, ev: str) -> SyndicateLink:
    return SyndicateLink(platform=platform, kind=kind, url=url[:300], identifier=ident[:100], source=source, evidence=ev)


def extract_from_text(text: str, source: LinkSource, exclude: Iterable[tuple[str, str]] = ()) -> list[SyndicateLink]:
    """Ekstrak semua tautan sindikat dari satu teks. exclude = {(platform, identifier_lowercase)} (mis. akun target sendiri)."""
    skip = {(p, i.lower()) for p, i in exclude}
    t = normalize_text(text)
    found: dict[str, SyndicateLink] = {}

    def add(link: SyndicateLink) -> None:
        if (link.platform, link.identifier.lower()) in skip:
            return
        found.setdefault(link.url.lower(), link)

    for m in _PATTERNS["telegram"].finditer(t):
        path = m["path"]
        head = path.lstrip("+").split("/")[0].lower()
        if head in _TG_RESERVED or path.lower() == "joinchat":
            continue
        invite = path.startswith("+") or path.lower().startswith("joinchat/")
        add(_link("telegram", "invite" if invite else "channel", f"https://t.me/{path}", path.lstrip("+"), source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["wa_group"].finditer(t):
        add(_link("whatsapp", "invite", f"https://chat.whatsapp.com/{m['code']}", m["code"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["wa_channel"].finditer(t):
        add(_link("whatsapp", "channel", f"https://whatsapp.com/channel/{m['code']}", m["code"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["reddit"].finditer(t):
        group = m["k"].lower() == "r"
        url = f"https://www.reddit.com/{'r' if group else 'user'}/{m['name']}"
        add(_link("reddit", "group" if group else "profile", url, m["name"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["threads"].finditer(t):
        if m["post"]:
            add(_link("threads", "post", f"https://www.threads.net/@{m['name']}/post/{m['post']}", f"{m['name']}/{m['post']}", source, _snippet(t, m.start(), m.end())))
        else:
            add(_link("threads", "profile", f"https://www.threads.net/@{m['name']}", m["name"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["ig_post"].finditer(t):
        add(_link("instagram", "post", f"https://www.instagram.com/p/{m['code']}/", m["code"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["instagram"].finditer(t):
        name = m["name"]
        if name.lower() in _IG_RESERVED or name.isdigit() or name.endswith("."):
            continue
        add(_link("instagram", "profile", f"https://www.instagram.com/{name}/", name, source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["tiktok"].finditer(t):
        add(_link("tiktok", "profile", f"https://www.tiktok.com/@{m['name']}", m["name"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["tiktok_short"].finditer(t):
        add(_link("tiktok", "post", f"https://vm.tiktok.com/{m['code']}", m["code"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["twitter"].finditer(t):
        name = m["name"]
        if name.lower() in _TW_RESERVED:
            continue
        if m["sid"]:
            add(_link("twitter", "post", f"https://x.com/{name}/status/{m['sid']}", f"{name}/{m['sid']}", source, _snippet(t, m.start(), m.end())))
        else:
            add(_link("twitter", "profile", f"https://x.com/{name}", name, source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["discord"].finditer(t):
        add(_link("discord", "invite", f"https://discord.gg/{m['code']}", m["code"], source, _snippet(t, m.start(), m.end())))
    for m in _PATTERNS["fb_group"].finditer(t):
        add(_link("facebook", "group", f"https://www.facebook.com/groups/{m['name']}", m["name"], source, _snippet(t, m.start(), m.end())))
    return list(found.values())


def extract_links(
    texts: Iterable[tuple[str, LinkSource]],
    hrefs: Iterable[str] = (),
    exclude: Iterable[tuple[str, str]] = (),
    limit: int = 40,
) -> list[SyndicateLink]:
    """Gabungkan hasil dari banyak teks + atribut href (setelah bongkar redirect). Dedupe lintas sumber; sumber pertama menang."""
    skip = list(exclude)
    merged: dict[str, SyndicateLink] = {}
    for text, source in texts:
        for link in extract_from_text(text, source, skip):
            merged.setdefault(link.url.lower(), link)
    for href in hrefs:
        for link in extract_from_text(decode_redirect(href), "page", skip):
            merged.setdefault(link.url.lower(), link)
    return list(merged.values())[:limit]

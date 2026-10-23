"""DETEKTO :: services/dossier.py — Takedown Dossier Generator (Task 6.3)

Laporan forensik 100% lokal (tanpa pihak ketiga): HTML siap cetak (CSP ketat, TANPA JavaScript) dan PDF native (ReportLab).
Isi: Ground Truth, daftar tersangka + stempel + skor + alasan Evidence Gate + 6 fitur, bukti jejak sindikat + reverse-image recon,
snapshot graf + Patient Zero, metodologi/keterbatasan, dan hash integritas.
ANTI-XSS: setiap string dinamis (bio, lokasi, komentar, judul sumber web, klaim LLM, nama akun) diperlakukan TIDAK TEPERCAYA:
dibersihkan (kontrol/bidi), dipotong, lalu di-escape (html.escape untuk HTML; xml.sax.saxutils.escape untuk markup mini ReportLab).
Screenshot sengaja TIDAK disertakan: Zero-Bloat — gambar sudah dihancurkan dari RAM; yang dilampirkan adalah kutipan teks OCR.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

import networkx as nx
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.security import sanitize_text
from models.graph import GraphMap
from models.interrogation import AnalysisResult
from models.swarm import SwarmStatus
from models.verdict import FEATURE_NAMES, VerdictSet

FEATURE_LABEL = {
    "account_age_risk": "Umur akun (risiko)", "rename_frequency": "Frekuensi ganti nama", "engagement_anomaly": "Anomali engagement",
    "copypaste_similarity": "Kemiripan copy-paste", "gt_deviation": "Deviasi ground truth", "visual_anomaly": "Anomali visual feed",
}
TYPE_NAME = {"A": "AUTOMATED BOT SCRIPT", "B": "PAID HUMAN TROLL", "C": "ORGANIC CITIZEN"}
DISCLAIMER = (
    "Laporan ini dihasilkan otomatis oleh DETEKTO dari data PUBLIK. Skor dan stempel adalah estimasi probabilistik, bukan putusan hukum atau "
    "bukti identitas. Hanya akun berstempel BUZZER yang layak dipertimbangkan untuk pelaporan; akun ORGANIC dilampirkan demi transparansi. "
    "Verifikasi manual wajib sebelum tindakan apa pun. Sentralitas graf (Patient Zero) hanya menunjukkan simpul paling terhubung."
)


def clean(value: Any, limit: int) -> str:
    """Bersihkan string tak tepercaya: buang karakter kontrol/bidi/zero-width, rapikan spasi, potong."""
    text = sanitize_text(str(value if value is not None else ""), limit * 2)
    return re.sub(r"[ \t]+", " ", text).replace("\r", "").strip()[:limit]


def _domain(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "")[:60]
    except ValueError:
        return ""


# ================================== data dossier ==================================
class DossierSuspect(BaseModel):
    username: str
    platform: str
    verdict: str
    buzzer_type: str
    type_name: str
    score: float
    raw_score: float
    threshold: float
    gate_passed: bool
    gate_reason: str
    elevated: list[str]
    features: dict[str, float | None]
    coverage: float
    nlp_line: str
    factors: list[str]
    warnings: list[str]
    comments: list[str]
    profile_line: str
    syndicate: list[str]
    recon: list[str]
    copy_paste: list[str]
    state: str


class DossierData(BaseModel):
    session_id: str
    generated_at: str
    platform: str
    context: str
    gt_claim: str
    gt_summary: str
    gt_baseline: str
    gt_confidence: str
    gt_grounded: bool
    gt_sources: list[str]
    suspects: list[DossierSuspect]
    patient_zero: dict[str, Any] | None
    graph: dict[str, Any]
    graph_mode: str
    model_version: int
    threshold: float
    integrity: str = Field(default="")


def assemble(session_id: str, result: AnalysisResult, swarm: SwarmStatus, vs: VerdictSet, gm: GraphMap, context: str = "") -> DossierData:
    gt = result.ground_truth
    by_user = {t.username.lower(): t for t in result.targets}
    dossiers = {d.username.lower(): d for d in swarm.dossiers}
    suspects: list[DossierSuspect] = []
    for c in vs.cards:
        d = dossiers.get(c.username.lower())
        t = by_user.get(c.username.lower())
        p = d.profile if d else None
        nlp = c.nlp
        nlp_line = ""
        if nlp:
            nlp_line = (
                f"Agresivitas {'-' if nlp.aggression is None else f'{nlp.aggression:.0%}'} · Distorsi {'-' if nlp.distortion is None else f'{nlp.distortion:.0%}'} · "
                f"Kemiripan tertinggi {nlp.top_similarity:.0%}" + (f" (dengan @{clean(nlp.partners[0].username, 30)})" if nlp.partners else "")
            )
        recon: list[str] = []
        if d and d.reverse_image:
            recon.append(f"Reverse-image: {d.reverse_image.status}" + (f" — {clean(d.reverse_image.reason, 120)}" if d.reverse_image.reason else ""))
            recon += [f"{m.platform}/{clean(m.handle, 60)} ({m.evidence}) {clean(m.url, 160)}" for m in d.reverse_image.matches[:8]]
        if d:
            recon += [f"{m.platform}/{clean(m.handle, 60)} ({m.evidence}) {clean(m.url, 160)}" for m in d.candidate_accounts[:8]]
        suspects.append(
            DossierSuspect(
                username=clean(c.username, 30), platform=c.platform, verdict=c.verdict, buzzer_type=c.buzzer_type, type_name=TYPE_NAME[c.buzzer_type],
                score=c.score, raw_score=c.raw_score, threshold=c.threshold, gate_passed=c.gate.passed, gate_reason=clean(c.gate.reason, 300),
                elevated=[clean(x, 30) for x in c.gate.elevated], features={k: c.features.get(k) for k in FEATURE_NAMES}, coverage=c.coverage,
                nlp_line=nlp_line, factors=[f"{FEATURE_LABEL.get(f.feature, f.feature)}: {f.contribution:+.2f}" for f in c.factors[:3]],
                warnings=[clean(w, 200) for w in c.warnings[:4]],
                comments=[("[DIREDAKSI: pola injeksi]" if cm.injection_flag else clean(cm.text, 200)) for cm in (t.comments[:3] if t else [])],
                profile_line=(
                    f"Followers {p.follower_count if p.follower_count is not None else '-'} · Following {p.following_count if p.following_count is not None else '-'} · "
                    f"Bergabung {clean(p.account_creation_date or '-', 40)} · Lokasi {clean(p.account_location or '-', 80)} · Bio: {clean(p.bio_text or '-', 300)}"
                ) if p else "Profil tidak tersedia.",
                syndicate=[f"{l.platform} {l.kind} [{l.source}] {clean(l.url, 200)}" for l in (d.syndicate_links[:12] if d else [])],
                recon=recon[:14],
                copy_paste=[f"@{clean(h.other_username, 30)} {h.similarity:.0%} ({h.basis})" for h in (d.copy_paste[:5] if d else [])],
                state=d.state if d else "unknown",
            )
        )
    pz = gm.patient_zero
    data = DossierData(
        session_id=session_id, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), platform=suspects[0].platform if suspects else "-",
        context=clean(context, 400),
        gt_claim=clean(gt.main_claim if gt else "", 400), gt_summary=clean(gt.objective_summary if gt else "Ground truth tidak tersedia.", 1200),
        gt_baseline=clean(gt.neutral_baseline if gt else "", 800), gt_confidence=gt.confidence if gt else "low", gt_grounded=bool(gt and gt.evidence_grounded),
        gt_sources=[f"{_domain(s.url)} — {clean(s.title, 140)}" for s in (gt.sources[:6] if gt else [])],
        suspects=suspects,
        patient_zero=(
            {"name": clean(pz.name, 80), "node_type": pz.node_type, "centrality": pz.centrality, "degree": pz.degree, "connected_buzzers": pz.connected_buzzers,
             "reason": clean(pz.reason, 400), "boss": clean(pz.boss_account_candidate or "", 80), "caveat": clean(pz.caveat, 300)} if pz else None
        ),
        graph=gm.model_dump(include={"stats", "paths"}) | {"nodes_n": len(gm.nodes)}, graph_mode=gm.mode, model_version=vs.model_version, threshold=vs.threshold,
    )
    canonical = json.dumps(data.model_dump(exclude={"integrity", "generated_at"}), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    data.integrity = hashlib.sha256(canonical.encode()).hexdigest()
    return data


# ============================== layout graf deterministik ==============================
def graph_layout(gm: GraphMap, max_nodes: int = 400) -> tuple[dict[str, tuple[float, float]], list[Any], list[Any]]:
    """Posisi 0..1 via spring_layout (seed tetap). Untuk graf besar: tampilkan hanya node terpenting (sentralitas)."""
    nodes = sorted(gm.nodes, key=lambda n: (-n.centrality, n.id))[:max_nodes]
    keep = {n.id for n in nodes}
    links = [l for l in gm.links if l.source in keep and l.target in keep]
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(keep)
    g.add_edges_from((l.source, l.target) for l in links)
    pos = nx.spring_layout(g, seed=42, iterations=60, k=1.2 / math.sqrt(max(len(keep), 1))) if keep else {}
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    rx, ry = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
    norm = {k: ((p[0] - min(xs)) / rx, (p[1] - min(ys)) / ry) for k, p in pos.items()}
    return norm, nodes, links


NODE_COLOR = {
    "buzzer_a": "#FF0033", "buzzer_b": "#FF0033", "organic": "#00CC66", "group": "#FFE600", "post": "#F4F0EA", "target": "#FF4D00", "discovered": "#FF007A",
}


def _svg_graph(gm: GraphMap, width: int = 760, height: int = 460) -> str:
    pos, nodes, links = graph_layout(gm)
    pad = 26
    px = lambda v: pad + v * (width - 2 * pad)
    py = lambda v: pad + v * (height - 2 * pad)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Snapshot graf jaringan">',
             f'<rect x="0" y="0" width="{width}" height="{height}" fill="#000000"/>']
    for l in links:
        if l.source in pos and l.target in pos:
            dash = ' stroke-dasharray="7 5"' if l.type == "AMPLIFIES" else ""
            col = "#FF007A" if l.type == "AMPLIFIES" else "#F4F0EA"
            parts.append(f'<line x1="{px(pos[l.source][0]):.1f}" y1="{py(pos[l.source][1]):.1f}" x2="{px(pos[l.target][0]):.1f}" y2="{py(pos[l.target][1]):.1f}" stroke="{col}" stroke-width="{2.5 if l.type == "AMPLIFIES" else 1.5}"{dash}/>')
    labelled = {n.id for n in nodes[:10]}
    for n in nodes:
        if n.id not in pos:
            continue
        x, y = px(pos[n.id][0]), py(pos[n.id][1])
        size = 16 if n.is_patient_zero else 6 + 8 * n.centrality
        if n.is_patient_zero:
            parts.append(f'<rect x="{x - size - 6:.1f}" y="{y - size - 6:.1f}" width="{2 * size + 12:.1f}" height="{2 * size + 12:.1f}" fill="none" stroke="#FF4D00" stroke-width="4"/>')
        parts.append(f'<rect x="{x - size / 2:.1f}" y="{y - size / 2:.1f}" width="{size:.1f}" height="{size:.1f}" fill="{NODE_COLOR.get(n.kind, "#FFFFFF")}" stroke="#F4F0EA" stroke-width="2"/>')
        if n.id in labelled or n.is_patient_zero:
            parts.append(f'<text x="{x + size / 2 + 4:.1f}" y="{y + 4:.1f}" font-family="monospace" font-size="11" font-weight="700" fill="#F4F0EA">{html.escape(clean(n.name, 24))}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ===================================== HTML =====================================
_CSS = """
*{box-sizing:border-box}body{font-family:Consolas,'Courier New',monospace;background:#F4F0EA;color:#000;margin:0;padding:24px;line-height:1.4}
h1,h2,h3{font-family:'Arial Black',Impact,sans-serif;text-transform:uppercase;margin:0}h1{font-size:34px}h2{font-size:22px;border-bottom:8px solid #000;padding-bottom:4px;margin:28px 0 12px}
.box{border:6px solid #000;box-shadow:8px 8px 0 #000;padding:12px;margin:0 0 20px;background:#fff;page-break-inside:avoid}.hdr{background:#FFE600}
.stamp{display:inline-block;border:6px solid #000;padding:4px 10px;font-family:'Arial Black',sans-serif;font-size:20px;text-transform:uppercase;transform:rotate(-3deg)}
.b{background:#FF0033;color:#F4F0EA}.o{background:#00CC66}.warn{background:#FF4D00;border:4px solid #000;padding:6px;margin:6px 0;font-weight:700}
table{border-collapse:collapse;width:100%}td,th{border:3px solid #000;padding:4px 6px;text-align:left;vertical-align:top;font-size:12px;word-break:break-word}th{background:#000;color:#FFE600}
.bar{display:inline-block;width:12px;height:10px;border:2px solid #000;margin-right:1px}.on{background:#FF0033}.ok{background:#00CC66}.off{background:#F4F0EA}
.small{font-size:11px}.mono{word-break:break-all}.foot{border-top:8px solid #000;margin-top:24px;padding-top:8px;font-size:11px}
@media print{body{padding:0;background:#fff}.box{box-shadow:none;border-width:4px}h2{page-break-after:avoid}@page{size:A4;margin:12mm}}
"""


def _bar(v: float | None) -> str:
    if v is None:
        return '<span class="small">tidak teramati</span>'
    n = round(max(0.0, min(1.0, v)) * 10)
    cls = "on" if v >= 0.6 else "ok"
    return "".join(f'<span class="bar {cls if i < n else "off"}"></span>' for i in range(10)) + f' <span class="small">{v:.0%}</span>'


def render_html(d: DossierData, gm: GraphMap) -> str:
    e = html.escape
    out: list[str] = [
        '<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">',
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'\">",
        '<meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>DETEKTO Takedown Dossier {e(d.session_id[:8])}</title><style>{_CSS}</style></head><body>",
        f'<div class="box hdr"><h1>DETEKTO // TAKEDOWN DOSSIER</h1><p class="small">Sesi {e(d.session_id[:8].upper())} · {e(d.generated_at)} · Platform {e(d.platform.upper())} · Model SGD v{d.model_version} · Ambang {d.threshold:.0f}%</p></div>',
        f'<div class="warn">{e(DISCLAIMER)}</div>',
        "<h2>1. Ground Truth</h2><div class=\"box\">",
        f"<p><b>Klaim utama:</b> {e(d.gt_claim or '-')}</p><p><b>Ringkasan objektif:</b> {e(d.gt_summary)}</p><p><b>Baseline netral:</b> {e(d.gt_baseline or '-')}</p>",
        f"<p><b>Keyakinan:</b> {e(d.gt_confidence.upper())} · <b>Berbasis sumber eksternal:</b> {'YA' if d.gt_grounded else 'TIDAK (belum terverifikasi)'}</p>",
    ]
    if d.gt_sources:
        out.append("<p><b>Sumber:</b></p><ul>" + "".join(f"<li class=\"mono\">{e(s)}</li>" for s in d.gt_sources) + "</ul>")
    out.append("</div>")

    out.append("<h2>2. Daftar Tersangka</h2>")
    for s in d.suspects:
        buzz = s.verdict == "BUZZER"
        out.append(f'<div class="box"><h3>@{e(s.username)} <span class="small">({e(s.platform)})</span></h3>')
        out.append(f'<span class="stamp {"b" if buzz else "o"}">{e(f"{s.score:.1f}% BUZZER" if buzz else "ORGANIC CITIZEN")} — TYPE {e(s.buzzer_type)}</span> ')
        out.append(f'<p class="small">{e(s.type_name)} · Skor final {s.score:.1f}% (mentah {s.raw_score:.1f}%) · Ambang {s.threshold:.0f}% · Cakupan data {s.coverage:.0%} · Halaman: {e(s.state)}</p>')
        out.append(f'<p><b>Evidence Gate: {"LOLOS" if s.gate_passed else "MENAHAN"}</b> ({e(", ".join(s.elevated) or "tidak ada sinyal")}) — {e(s.gate_reason)}</p>')
        out.append("<table><tr><th>Fitur</th><th>Nilai</th></tr>" + "".join(f"<tr><td>{e(FEATURE_LABEL[k])}</td><td>{_bar(s.features.get(k))}</td></tr>" for k in FEATURE_NAMES) + "</table>")
        if s.nlp_line:
            out.append(f"<p class=\"small\"><b>NLP:</b> {e(s.nlp_line)}</p>")
        if s.factors:
            out.append(f"<p class=\"small\"><b>Faktor teratas:</b> {e('; '.join(s.factors))}</p>")
        out.append(f"<p class=\"small\"><b>Profil:</b> {e(s.profile_line)}</p>")
        if s.comments:
            out.append("<p class=\"small\"><b>Kutipan komentar (OCR):</b></p><ul>" + "".join(f"<li class=\"small\">{e(c)}</li>" for c in s.comments) + "</ul>")
        out += [f'<div class="warn small">⚠ {e(w)}</div>' for w in s.warnings]
        out.append("</div>")

    out.append("<h2>3. Bukti Jejak Sindikat</h2>")
    any_ev = False
    for s in d.suspects:
        if not (s.syndicate or s.recon or s.copy_paste):
            continue
        any_ev = True
        out.append(f'<div class="box"><h3>@{e(s.username)}</h3>')
        for title, items in (("Tautan grup/sosmed publik", s.syndicate), ("Reverse-image recon & kandidat akun", s.recon), ("Pola copy-paste", s.copy_paste)):
            if items:
                out.append(f"<p><b>{e(title)}:</b></p><ul>" + "".join(f"<li class=\"mono small\">{e(i)}</li>" for i in items) + "</ul>")
        out.append("</div>")
    if not any_ev:
        out.append('<div class="box">Tidak ada tautan sindikat atau hasil reverse-image yang terdeteksi.</div>')
    out.append('<p class="small">Tautan ditampilkan sebagai TEKS dan tidak pernah dikunjungi oleh DETEKTO.</p>')

    out.append(f"<h2>4. Graf Jaringan &amp; Patient Zero</h2><div class=\"box\">{_svg_graph(gm)}")
    st = d.graph.get("stats", {})
    out.append(f"<p class=\"small\">{e(str(st.get('nodes', 0)))} node · {e(str(st.get('edges', 0)))} edge · {e(str(st.get('buzzers', 0)))} buzzer · mode graf: {e(d.graph_mode.upper())}. Merah=Buzzer · Hijau=Organik · Kuning=Grup · Magenta=akun temuan · Kotak oranye=Patient Zero · Garis putus-putus=AMPLIFIES.</p>")
    if d.patient_zero:
        pz = d.patient_zero
        out.append(f"<p><b>PATIENT ZERO (kandidat):</b> {e(str(pz['name']))} [{e(str(pz['node_type']))}] · sentralitas {pz['centrality']:.2f} · derajat {pz['degree']} · {pz['connected_buzzers']} akun buzzer terhubung</p>")
        out.append(f"<p class=\"small\">{e(str(pz['reason']))}" + (f" Kandidat akun: {e(str(pz['boss']))}." if pz["boss"] else "") + f"</p><div class=\"warn small\">{e(str(pz['caveat']))}</div>")
    else:
        out.append("<p>Tidak ada simpul pusat yang memenuhi syarat (butuh terhubung ke ≥2 akun BUZZER).</p>")
    out.append("</div>")
    out.append(
        "<h2>5. Metodologi &amp; Keterbatasan</h2><div class=\"box small\"><ul>"
        "<li>Fitur: umur akun, frekuensi ganti nama, anomali engagement, kemiripan teks (TF-IDF cosine), deviasi ground truth, anomali visual (FFT/hash).</li>"
        "<li>Model: SGDClassifier (log-loss) yang belajar dari koreksi pengguna; ambang mutlak 65%. Evidence Gate mewajibkan ≥2 keluarga sinyal independen dengan minimal satu non-teks.</li>"
        "<li>Heuristik visual/FFT belum dikalibrasi; kemiripan teks bukan bukti koordinasi bila berdiri sendiri; data hanya halaman publik.</li>"
        "<li>Screenshot bukti tidak disimpan (zero-bloat); yang dilampirkan hanyalah kutipan teks hasil OCR.</li></ul></div>"
    )
    out.append(f'<div class="foot">Dibuat lokal oleh DETEKTO — tidak ada data yang dikirim ke pihak ketiga.<br>Hash integritas (SHA-256): <span class="mono">{e(d.integrity)}</span></div></body></html>')
    return "".join(out)


# ====================================== PDF ======================================
def _pdf_safe(value: str) -> str:
    """Helvetica bawaan ReportLab hanya cp1252: karakter di luar itu diganti '?' lalu di-escape agar tidak ditafsirkan sebagai markup."""
    return xml_escape(value.encode("cp1252", "replace").decode("cp1252"))


class _GraphFlowable(Flowable):
    def __init__(self, gm: GraphMap, width: float, height: float) -> None:
        super().__init__()
        self.gm, self.width, self.height = gm, width, height

    def wrap(self, *_: Any) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(colors.black)
        c.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        pos, nodes, links = graph_layout(self.gm)
        pad = 14
        px = lambda v: pad + v * (self.width - 2 * pad)
        py = lambda v: pad + v * (self.height - 2 * pad)
        for l in links:
            if l.source in pos and l.target in pos:
                c.setStrokeColor(colors.HexColor("#FF007A" if l.type == "AMPLIFIES" else "#F4F0EA"))
                c.setLineWidth(1.6 if l.type == "AMPLIFIES" else 0.8)
                c.setDash(4, 3) if l.type == "AMPLIFIES" else c.setDash()
                c.line(px(pos[l.source][0]), py(pos[l.source][1]), px(pos[l.target][0]), py(pos[l.target][1]))
        c.setDash()
        for n in nodes:
            if n.id not in pos:
                continue
            x, y = px(pos[n.id][0]), py(pos[n.id][1])
            size = 12 if n.is_patient_zero else 4 + 6 * n.centrality
            if n.is_patient_zero:
                c.setStrokeColor(colors.HexColor("#FF4D00"))
                c.setLineWidth(2.5)
                c.rect(x - size - 3, y - size - 3, 2 * size + 6, 2 * size + 6, stroke=1, fill=0)
            c.setFillColor(colors.HexColor(NODE_COLOR.get(n.kind, "#FFFFFF")))
            c.setStrokeColor(colors.HexColor("#F4F0EA"))
            c.setLineWidth(1)
            c.rect(x - size / 2, y - size / 2, size, size, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#F4F0EA"))
        c.setFont("Helvetica-Bold", 7)
        for n in nodes[:8]:
            if n.id in pos:
                c.drawString(px(pos[n.id][0]) + 7, py(pos[n.id][1]) - 2, _pdf_plain(clean(n.name, 20)))


def _pdf_plain(value: str) -> str:
    return value.encode("cp1252", "replace").decode("cp1252")


def render_pdf(d: DossierData, gm: GraphMap) -> bytes:
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=11)
    small = ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5)
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=4)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, spaceBefore=12, spaceAfter=4)
    h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=4)
    P = lambda text, style=base: Paragraph(_pdf_safe(text), style)

    def box(content: list[Flowable], bg: Any = colors.white) -> Table:
        t = Table([[content]], colWidths=[180 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 2.2, colors.black), ("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        return t

    story: list[Flowable] = [
        box([P("DETEKTO // TAKEDOWN DOSSIER", h1), P(f"Sesi {d.session_id[:8].upper()} | {d.generated_at} | Platform {d.platform.upper()} | Model SGD v{d.model_version} | Ambang {d.threshold:.0f}%", small)], colors.HexColor("#FFE600")),
        Spacer(1, 4), box([P(DISCLAIMER, small)], colors.HexColor("#FF4D00")),
        P("1. Ground Truth", h2),
        box([P(f"Klaim utama: {d.gt_claim or '-'}"), P(f"Ringkasan objektif: {d.gt_summary}"), P(f"Baseline netral: {d.gt_baseline or '-'}"),
             P(f"Keyakinan: {d.gt_confidence.upper()} | Berbasis sumber eksternal: {'YA' if d.gt_grounded else 'TIDAK (belum terverifikasi)'}", small),
             *[P(f"- {s}", small) for s in d.gt_sources]]),
        P("2. Daftar Tersangka", h2),
    ]
    for s in d.suspects:
        buzz = s.verdict == "BUZZER"
        stamp = Table([[Paragraph(_pdf_safe(f"{s.score:.1f}% BUZZER - TYPE {s.buzzer_type}" if buzz else f"ORGANIC CITIZEN - TYPE {s.buzzer_type}"),
                                  ParagraphStyle("st", fontName="Helvetica-Bold", fontSize=11, textColor=colors.white if buzz else colors.black))]], colWidths=[75 * mm])
        stamp.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 3, colors.black), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FF0033" if buzz else "#00CC66")), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        feats = Table([[P("Fitur", small), P("Nilai", small)]] + [[P(FEATURE_LABEL[k], small), P("tidak teramati" if s.features.get(k) is None else f"{s.features[k]:.0%}", small)] for k in FEATURE_NAMES], colWidths=[70 * mm, 40 * mm])
        feats.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFE600"))]))
        body: list[Flowable] = [
            P(f"@{s.username} ({s.platform})", h3), stamp, Spacer(1, 3),
            P(f"{s.type_name} | Skor final {s.score:.1f}% (mentah {s.raw_score:.1f}%) | Ambang {s.threshold:.0f}% | Cakupan {s.coverage:.0%} | Halaman: {s.state}", small),
            P(f"Evidence Gate: {'LOLOS' if s.gate_passed else 'MENAHAN'} ({', '.join(s.elevated) or 'tidak ada sinyal'}) - {s.gate_reason}", base), Spacer(1, 3), feats,
        ]
        if s.nlp_line:
            body.append(P(f"NLP: {s.nlp_line}", small))
        if s.factors:
            body.append(P("Faktor teratas: " + "; ".join(s.factors), small))
        body.append(P(f"Profil: {s.profile_line}", small))
        body += [P(f"Komentar (OCR): {c}", small) for c in s.comments] + [P(f"! {w}", small) for w in s.warnings]
        story += [KeepTogether([box(body)]), Spacer(1, 6)]

    story.append(P("3. Bukti Jejak Sindikat", h2))
    shown = False
    for s in d.suspects:
        if s.syndicate or s.recon or s.copy_paste:
            shown = True
            items: list[Flowable] = [P(f"@{s.username}", h3)]
            for title, rows in (("Tautan grup/sosmed publik", s.syndicate), ("Reverse-image recon & kandidat akun", s.recon), ("Pola copy-paste", s.copy_paste)):
                if rows:
                    items += [P(title + ":", small)] + [P(f"- {r}", small) for r in rows]
            story += [KeepTogether([box(items)]), Spacer(1, 4)]
    if not shown:
        story.append(box([P("Tidak ada tautan sindikat atau hasil reverse-image yang terdeteksi.")]))
    story.append(P("Tautan ditampilkan sebagai teks dan tidak pernah dikunjungi oleh DETEKTO.", small))

    story += [P("4. Graf Jaringan & Patient Zero", h2), _GraphFlowable(gm, 180 * mm, 95 * mm)]
    st = d.graph.get("stats", {})
    story.append(P(f"{st.get('nodes', 0)} node | {st.get('edges', 0)} edge | {st.get('buzzers', 0)} buzzer | mode graf: {d.graph_mode.upper()}. Merah=Buzzer, Hijau=Organik, Kuning=Grup, Magenta=akun temuan, kotak oranye=Patient Zero, putus-putus=AMPLIFIES.", small))
    if d.patient_zero:
        pz = d.patient_zero
        story += [P(f"PATIENT ZERO (kandidat): {pz['name']} [{pz['node_type']}] | sentralitas {pz['centrality']:.2f} | derajat {pz['degree']} | {pz['connected_buzzers']} akun buzzer terhubung"),
                  P(str(pz["reason"]) + (f" Kandidat akun: {pz['boss']}." if pz["boss"] else ""), small), box([P(str(pz["caveat"]), small)], colors.HexColor("#FF4D00"))]
    else:
        story.append(P("Tidak ada simpul pusat yang memenuhi syarat (butuh terhubung ke >=2 akun BUZZER)."))
    story += [
        P("5. Metodologi & Keterbatasan", h2),
        P("Fitur: umur akun, frekuensi ganti nama, anomali engagement, kemiripan teks (TF-IDF cosine), deviasi ground truth, anomali visual (FFT/hash). "
          "Model SGDClassifier (log-loss) belajar dari koreksi pengguna; ambang mutlak 65%; Evidence Gate mewajibkan >=2 keluarga sinyal independen dengan minimal satu non-teks. "
          "Heuristik visual belum dikalibrasi; kemiripan teks bukan bukti koordinasi bila berdiri sendiri. Screenshot tidak disimpan (zero-bloat); yang dilampirkan hanya kutipan teks OCR.", small),
        Spacer(1, 6), P(f"Dibuat lokal oleh DETEKTO - tidak ada data dikirim ke pihak ketiga. Hash integritas SHA-256: {d.integrity}", small),
    ]

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 8 * mm, f"DETEKTO dossier {d.session_id[:8]} | SHA-256 {d.integrity[:16]}...")
        canvas.drawRightString(195 * mm, 8 * mm, f"Halaman {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm, title=f"DETEKTO Dossier {d.session_id[:8]}", author="DETEKTO", creator="DETEKTO local").build(
        story, onFirstPage=footer, onLaterPages=footer
    )
    return buf.getvalue()

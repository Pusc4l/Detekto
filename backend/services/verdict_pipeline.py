"""DETEKTO :: services/verdict_pipeline.py — Orkestrator Verdict: Fase 3 (komentar) + Fase 4 (dossier) + NLP + SGD -> VerdictCard."""
from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import uuid
from datetime import datetime, timezone

from core.config import get_settings
from core.log_bus import bus
from models.interrogation import AnalysisResult, TargetEntity
from models.swarm import TargetDossier
from models.verdict import EvidenceIn, FeatureSample, NlpReport, SimilarityPartner, VerdictCard, VerdictSet
from services import verdict as V
from services.ephemeral_vault import get_vault, k_swarm
from services.ml_runtime import get_runtime
from services.nlp_engine import aggression_by_user, analyze_similarity, llm_distortion, MIN_TOKENS_FOR_SIMILARITY, normalize_for_similarity


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def username_hash(platform: str, username: str) -> str:
    return hashlib.sha256(f"{platform}:{username.lower()}".encode()).hexdigest()


async def _log(level: str, source: str, message: str) -> None:
    await bus.emit(level, source, message)  # type: ignore[arg-type]


def _group_ids(d: TargetDossier) -> set[tuple[str, str]]:
    return {(l.platform, l.identifier.lower()) for l in d.syndicate_links if l.kind in ("group", "channel", "invite")}


async def build_card(
    *, username: str, platform: str, features: dict[str, float | None], evidence: EvidenceIn, nlp: NlpReport | None, warnings: list[str]
) -> VerdictCard:
    """Hitung vonis untuk satu fitur + bukti. Dipakai pipeline sesi maupun endpoint sampel. Menyimpan jejak ke SQLite (untuk feedback)."""
    rt = await get_runtime()
    x = rt.learner.vector(features)
    raw = await asyncio.to_thread(rt.learner.predict_proba, x)
    gate = V.evaluate_gate(features, evidence)
    final, is_buzzer = V.apply_dictator(raw, gate)
    cov = V.coverage(features)
    warn = list(warnings)
    if cov < 0.5:
        warn.append(f"Cakupan data rendah ({cov:.0%}): fitur yang tidak teramati diisi nilai prior organik.")
    card = VerdictCard(
        verdict_id=uuid.uuid4().hex, username=username, platform=platform,  # type: ignore[arg-type]
        verdict="BUZZER" if is_buzzer else "ORGANIC", buzzer_type=V.classify_type(is_buzzer, features, evidence),
        score=V.display_percent(final), raw_score=V.display_percent(raw), threshold=round(V.threshold() * 100, 1),
        gate=gate, features=features, coverage=cov, nlp=nlp, factors=rt.learner.contributions(x), warnings=warn[:8],
        model_version=rt.learner.version, created_at=_now(),
    )
    await asyncio.to_thread(
        rt.store.save_verdict,
        {
            "verdict_id": card.verdict_id, "username_hash": username_hash(platform, username), "platform": platform,
            "features": json.dumps(features), "evidence": evidence.model_dump_json(), "raw_score": raw, "final_score": final,
            "verdict": card.verdict, "buzzer_type": card.buzzer_type, "model_version": card.model_version, "created_at": card.created_at,
        },
    )
    return card


async def compute_session_verdicts(session_id: str) -> VerdictSet:
    # impor lokal: menghindari impor melingkar dengan swarm_manager
    from workers.swarm_manager import _load_phase3, load_swarm_status

    swarm = await load_swarm_status(session_id)
    phase3 = await _load_phase3(session_id)
    if swarm is None or phase3 is None:
        raise LookupError("SESI / SWARM TIDAK DITEMUKAN ATAU KEDALUWARSA")
    if swarm.status != "done":
        raise RuntimeError("SWARM BELUM SELESAI")
    result: AnalysisResult = phase3[1]
    gt = result.ground_truth
    gt_text = f"{gt.neutral_baseline}\n{gt.objective_summary}" if gt and gt.evidence_grounded else None
    t3: dict[str, TargetEntity] = {t.username.lower(): t for t in result.targets}
    dossiers = {d.username.lower(): d for d in swarm.dossiers}

    comments = {u: [c.text for c in t.comments] for u, t in t3.items() if u in dossiers}
    entries = [(u, c) for u, cs in comments.items() for c in cs]
    thread_hits = {u: [h for h in dossiers[u].copy_paste if h.basis == "thread"] for u in comments}
    sims = await asyncio.to_thread(analyze_similarity, entries, gt_text, thread_hits)
    aggression, engines = await aggression_by_user(comments)
    distortion = await llm_distortion(gt_text or "", comments, _log) if gt_text else None

    comparable_total = sum(1 for _, c in entries if len(normalize_for_similarity(c).split()) >= MIN_TOKENS_FOR_SIMILARITY)
    group_map = {u: _group_ids(d) for u, d in dossiers.items()}

    cards: list[VerdictCard] = []
    for u, d in dossiers.items():
        own = comments.get(u, [])
        sim = sims.get(u)
        measurable = comparable_total >= 2 and any(len(normalize_for_similarity(c).split()) >= MIN_TOKENS_FOR_SIMILARITY for c in own)
        aggr = aggression.get(u) if own else None
        dist = distortion.get(u) if distortion else None
        gt_dev = None if aggr is None else (0.4 * aggr + 0.6 * dist if dist is not None else aggr)
        features = V.compute_features(d.profile, d.vision, sim.top if (sim and measurable) else None, gt_dev)
        entity = t3.get(u)
        evidence = EvidenceIn(
            shared_groups=sum(1 for o, g in group_map.items() if o != u and g & group_map[u]),
            injection_attempt=bool(entity and (entity.injection_flag or any(c.injection_flag for c in entity.comments))),
            reverse_candidates=len(d.candidate_accounts) + (len(d.reverse_image.matches) if d.reverse_image else 0),
            syndicate_links=len(d.syndicate_links),
            profile_empty=bool(d.profile and not d.profile.bio_text and (d.profile.post_count or 0) <= 2),
            copy_partners=sum(1 for p in (sim.partners if sim else []) if p[1] >= 0.75),
        )
        nlp = NlpReport(
            comments_scored=len(own), aggression=aggr, distortion=dist, top_similarity=sim.top if sim else 0.0,
            self_repeat=sim.self_repeat if sim else 0.0,
            partners=[SimilarityPartner(username=n, similarity=s, source=src) for n, s, src in (sim.partners if sim else [])],  # type: ignore[arg-type]
            engines=engines + (["llm-distortion"] if dist is not None else []),
        )
        warnings: list[str] = []
        if d.state not in ("done",):
            warnings.append(f"Halaman profil: {d.state.upper()} — {d.state_detail or 'metadata terbatas'}.")
        cards.append(await build_card(username=entity.username if entity else d.username, platform=d.platform, features=features, evidence=evidence, nlp=nlp, warnings=warnings))
        c = cards[-1]
        await _log(
            "ERROR" if c.verdict == "BUZZER" else "OK", "VERDICT",
            f"@{c.username} // {c.score:.1f}% (MENTAH {c.raw_score:.1f}%) // {c.verdict} TYPE {c.buzzer_type} // GATE {'LOLOS' if c.gate.passed else 'MENAHAN'} // v{c.model_version}",
        )

    removed = await get_vault().purge_session_media(session_id)  # idempoten: memastikan 0 byte gambar tersisa
    gc.collect()
    await _log("OK", "VAULT", f"ZERO-BLOAT TERVERIFIKASI SETELAH VERDICT: {removed} BUFFER TERSISA DIHANCURKAN")
    rt = await get_runtime()
    vs = VerdictSet(session_id=session_id, generated_at=_now(), threshold=round(V.threshold() * 100, 1), model_version=rt.learner.version, media_purged=True, cards=cards)
    await get_vault().put(k_swarm(session_id, "verdicts"), vs.model_dump_json(), get_settings().result_ttl_seconds)
    return vs


async def load_session_verdicts(session_id: str) -> VerdictSet | None:
    raw = await get_vault().get(k_swarm(session_id, "verdicts"))
    return VerdictSet.model_validate_json(raw) if raw else None


def features_from_sample(f: FeatureSample) -> dict[str, float | None]:
    return {k: getattr(f, k) for k in V.compute_features(None, None, None, None)}

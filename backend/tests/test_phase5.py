"""DETEKTO :: tests/test_phase5.py — jalankan: pytest -q  (dari folder backend)"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from core.config import get_settings
from models.interrogation import AnalysisResult, GroundTruthContext, SessionMeta, TargetComment, TargetEntity
from models.swarm import ProfileMetadata, SwarmMeta, TargetDossier, VisionReport, FftResult, FeedUniformity
from models.verdict import EvidenceIn, FEATURE_NAMES
from services import verdict as V
from services.model_store import ModelStore
from services.nlp_engine import analyze_similarity, lexicon_aggression
from services.online_learner import OnlineLearner

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
ORGANIC = dict(account_age_risk=0.05, rename_frequency=0.0, engagement_anomaly=0.05, gt_deviation=0.1, visual_anomaly=0.05)
PHANTOM_A = {**ORGANIC, "copypaste_similarity": 0.97}
BOT = dict(account_age_risk=0.9, rename_frequency=0.6, engagement_anomaly=0.85, copypaste_similarity=0.95, gt_deviation=0.6, visual_anomaly=0.8)


def fresh_learner() -> tuple[OnlineLearner, ModelStore]:
    s = get_settings().model_copy(update={"sqlite_path": str(Path(tempfile.mkdtemp()) / "m.db")})
    store = ModelStore(s)
    store.init()
    lr = OnlineLearner(store, s)
    lr.load()
    return lr, store


def decide(lr: OnlineLearner, features: dict, evidence: EvidenceIn | None = None) -> tuple[float, bool, str]:
    ev = evidence or EvidenceIn()
    full = {n: features.get(n) for n in FEATURE_NAMES}
    raw = lr.predict_proba(lr.vector(full))
    gate = V.evaluate_gate(full, ev)
    final, buzzer = V.apply_dictator(raw, gate)
    return final, buzzer, V.classify_type(buzzer, full, ev)


# ------------------------------------------------------------------ fitur
def test_account_date_and_feature_math() -> None:
    for text in ("March 2023", "Maret 2023", "Joined Mar 2023", "2023-03-15", "15/03/2023"):
        assert V.parse_account_date(text) == datetime(2023, 3, 1 if "15" not in text else 15 if "-" in text else 15, tzinfo=timezone.utc) or V.parse_account_date(text).year == 2023  # type: ignore[union-attr]
    assert V.parse_account_date("tidak jelas") is None
    young = ProfileMetadata(account_creation_date="August 2026", username_change_count=3, follower_count=5, following_count=900, follower_following_ratio=0.006, post_count=2)
    old = ProfileMetadata(account_creation_date="January 2019", username_change_count=0, follower_count=800, following_count=400, follower_following_ratio=2.0, post_count=300)
    assert V.account_age_risk(young, NOW) > 0.9 and V.account_age_risk(old, NOW) == 0.0
    assert V.rename_frequency(young, NOW) == 1.0 and V.rename_frequency(old, NOW) == 0.0
    assert V.engagement_anomaly(young) > 0.9 and V.engagement_anomaly(old) == 0.0
    assert V.account_age_risk(None, NOW) is None and V.engagement_anomaly(ProfileMetadata()) is None
    whale = ProfileMetadata(follower_count=90000, following_count=10, follower_following_ratio=9000.0, post_count=1)
    assert V.engagement_anomaly(whale) == 1.0
    vis = VisionReport(profile_photo=FftResult(score=0.8, hf_ratio=0.1, peak_z=15, face_detected=True, label="suspicious"),
                       feed=FeedUniformity(images_analyzed=10, cluster_ratio=1.0, unique_ratio=0.1, method="phash", flagged=True))
    assert V.visual_anomaly(vis) == pytest.approx(0.6 * 0.8 + 0.4 * 1.0)
    assert V.visual_anomaly(None) is None


# --------------------------------------------------------- PHANTOM A (inti)
def test_phantom_a_high_similarity_but_organic_metadata_is_not_fooled() -> None:
    lr, _ = fresh_learner()
    final, buzzer, typ = decide(lr, PHANTOM_A)
    assert not buzzer and typ == "C" and final < 0.65
    gate = V.evaluate_gate({n: PHANTOM_A.get(n) for n in FEATURE_NAMES}, EvidenceIn())
    assert not gate.passed and gate.elevated == ["narrative_copy"] and "DITAHAN" in gate.reason

    # Varian lebih keras: salinan 100% + agresif (2 sinyal TEKS) tetap tidak cukup tanpa bukti non-teks
    final2, buzzer2, _ = decide(lr, {**PHANTOM_A, "copypaste_similarity": 1.0, "gt_deviation": 0.95})
    assert not buzzer2
    assert "teks" in V.evaluate_gate({**{n: None for n in FEATURE_NAMES}, "copypaste_similarity": 1.0, "gt_deviation": 0.95}, EvidenceIn()).reason

    # Bot sungguhan tetap tertangkap: sinyal akun + visual + salinan menyala bersamaan
    final3, buzzer3, typ3 = decide(lr, BOT, EvidenceIn(profile_empty=True))
    assert buzzer3 and final3 >= 0.65 and typ3 == "A"


def test_gate_still_holds_after_model_poisoning_via_feedback() -> None:
    """Penyerang membanjiri feedback 'copy-paste = buzzer' sampai bobot model miring. Gate harus tetap menahan."""
    lr, _ = fresh_learner()
    x = lr.vector({n: PHANTOM_A.get(n) for n in FEATURE_NAMES})
    for _ in range(400):
        lr.partial_fit(x, 1)
    raw = lr.predict_proba(x)
    assert raw > 0.65                                   # model berhasil "diracuni"
    final, buzzer, typ = decide(lr, PHANTOM_A)
    assert not buzzer and typ == "C" and final < 0.65   # ...tetapi vonis tidak berubah
    assert max(abs(w) for w in lr.weights()[0]) <= 6.0  # bobot tak bisa meledak (clip)


def test_dictator_threshold_is_exact_and_display_is_consistent() -> None:
    from models.verdict import GateReport
    ok = GateReport(passed=True, elevated=["account", "visual"], reason="x")
    no = GateReport(passed=False, elevated=["narrative_copy"], reason="x")
    assert V.apply_dictator(0.65, ok) == (0.65, True)
    assert V.apply_dictator(0.6499, ok)[1] is False
    f, b = V.apply_dictator(0.999, no)
    assert not b and f < 0.65 and V.display_percent(f) == 64.9
    assert V.display_percent(0.64999) == 64.9 and V.display_percent(0.65) == 65.0
    # Tipe
    f_ok = {n: None for n in FEATURE_NAMES}
    assert V.classify_type(False, f_ok, EvidenceIn()) == "C"
    assert V.classify_type(True, {**f_ok, "copypaste_similarity": 0.95, "visual_anomaly": 0.7}, EvidenceIn()) == "A"
    assert V.classify_type(True, {**f_ok, "copypaste_similarity": 0.5, "visual_anomaly": 0.7}, EvidenceIn()) == "B"


def test_network_evidence_counts_as_independent_family() -> None:
    f = {n: None for n in FEATURE_NAMES} | {"copypaste_similarity": 0.9}
    assert not V.evaluate_gate(f, EvidenceIn()).passed
    assert V.evaluate_gate(f, EvidenceIn(shared_groups=1)).passed          # tautan grup yang sama dgn target lain
    assert V.evaluate_gate(f, EvidenceIn(injection_attempt=True)).passed   # percobaan injeksi prompt = manipulasi aktif
    assert not V.evaluate_gate(f, EvidenceIn(syndicate_links=3, reverse_candidates=2)).passed   # tautan/duplikat avatar saja lazim pada organik


# ----------------------------------------------------------------- learner
def test_online_learning_updates_in_milliseconds_and_moves_toward_label() -> None:
    lr, store = fresh_learner()
    x = lr.vector({n: 0.5 for n in FEATURE_NAMES})
    before = lr.predict_proba(x)
    p0, p1, v0, v1, ms = lr.partial_fit(x, 1)
    assert p0 == pytest.approx(before) and p1 > p0 and (v0, v1) == (1, 2) and ms < 100
    for _ in range(10):
        lr.partial_fit(x, 1)
    assert lr.predict_proba(x) > p1 and lr.n_samples == 11


def test_weights_persist_and_restore_exactly_and_invalid_state_is_rejected() -> None:
    lr, store = fresh_learner()
    x = lr.vector({n: 0.4 for n in FEATURE_NAMES})
    lr.partial_fit(x, 0); lr.partial_fit(x, 1); lr.partial_fit(x, 0)
    lr2 = OnlineLearner(store, lr._s)
    assert lr2.load() == "sqlite" and (lr2.version, lr2.n_samples) == (lr.version, lr.n_samples)
    assert lr2.predict_proba(x) == pytest.approx(lr.predict_proba(x), abs=1e-12)
    assert list(lr2.weights()[0]) == pytest.approx(list(lr.weights()[0]))
    # payload beracun (NaN / terlalu besar / fitur salah) ditolak -> bootstrap
    for bad in ({"features": list(FEATURE_NAMES), "coef": [float("nan")] * 6, "intercept": 0},
                {"features": list(FEATURE_NAMES), "coef": [999.0] * 6, "intercept": 0},
                {"features": ["x"] * 6, "coef": [0.0] * 6, "intercept": 0}, {"coef": "evil"}):
        store.save_state(99, 99, bad)
        lr3 = OnlineLearner(store, lr._s)
        assert lr3.load() == "bootstrap" and lr3.version == 1


def test_supabase_sync_push_and_pull_with_mock_transport() -> None:
    seen: list[httpx.Request] = []
    lr, store = fresh_learner()
    store._remote_ok = True
    store._s = store._s.model_copy(update={"supabase_url": "https://x.supabase.co", "supabase_key": "svc-key"})
    payload = lr.payload()

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[{"version": 7, "n_samples": 3, "payload": payload, "updated_at": "t"}])

    transport = httpx.MockTransport(handler)
    assert asyncio.run(store.push_remote_state(5, 2, payload, transport=transport))
    body = json.loads(seen[0].content)
    assert body["instance_id"] == store.instance_id and body["version"] == 5 and seen[0].headers["apikey"] == "svc-key"
    assert "on_conflict=instance_id" in str(seen[0].url) and "merge-duplicates" in seen[0].headers["prefer"]
    remote = asyncio.run(store.pull_remote_state(transport=transport))
    assert remote and remote["version"] == 7
    lr2 = OnlineLearner(store, store._s)
    assert lr2.load(remote) == "supabase" and lr2.version == 7
    assert asyncio.run(store.push_remote_state(1, 1, payload, transport=httpx.MockTransport(lambda r: httpx.Response(500)))) is False


# --------------------------------------------------------------------- NLP
def test_nlp_similarity_and_lexicon() -> None:
    a = "Kebijakan baru ini sangat merugikan rakyat kecil dan harus segera dicabut sekarang juga"
    b = "kebijakan baru ini sgt merugikan rakyat kecil & harus segera dicabut skrg juga!!"
    c = "Saya setuju dengan kebijakan ini karena membantu petani kecil di desa kami"
    r = analyze_similarity([("u1", a), ("u2", b), ("u3", c)], None)
    assert r["u1"].top > 0.95 and r["u3"].top < 0.3 and r["u1"].partners[0][0] == "u2"
    quoted = analyze_similarity([("u1", a), ("u2", b)], a)                 # dua-duanya mengutip ground truth => diskon
    assert quoted["u1"].top == pytest.approx(0.5, abs=0.02)
    short = analyze_similarity([("u1", "mantap"), ("u2", "mantap")], None)  # terlalu pendek: bukan bukti
    assert short["u1"].top == 0.0
    own = analyze_similarity([("u1", a), ("u1", a), ("u2", c)], None)       # akun yang mengulang komentar sama
    assert own["u1"].self_repeat > 0.95
    assert lexicon_aggression("Terima kasih infonya sangat membantu") == 0.0
    assert lexicon_aggression("dasar goblok bodoh!!!") > 0.7 and lexicon_aggression("4nj1ng l0 b0d0h") > 0.6 and lexicon_aggression("anjiiiing") > 0.4


# ------------------------------------------------ API + pipeline end-to-end
SID = "d" * 32
TEXT = "Kebijakan baru ini sangat merugikan rakyat kecil dan harus segera dicabut sekarang juga"


def seed_session(client, vault, dossiers: dict[str, TargetDossier], comments: dict[str, list[TargetComment]], sid: str = SID) -> None:
    meta = SessionMeta(session_id=sid, platform="instagram", context_text="konteks uji", created_at="t")
    targets = [TargetEntity(username=u, comment_count=len(cs), total_likes=0, image_indexes=[0], injection_flag=any(c.injection_flag for c in cs), comments=cs) for u, cs in comments.items()]
    gt = GroundTruthContext(main_claim="c", objective_summary="Pemerintah mengumumkan subsidi energi baru.", neutral_baseline="Subsidi energi diumumkan.", dorking_keywords=["subsidi"],
                            sources=[], confidence="low", evidence_grounded=True, reasoning_engine="x", search_engine="none")
    result = AnalysisResult(session_id=sid, status="done", started_at="t", targets=targets, ground_truth=gt)

    async def go() -> None:
        await vault.create_session(meta, {"context": [], "evidence": []})
        await vault.save_result(sid, result.model_dump_json())
        from services.ephemeral_vault import k_swarm
        await vault.put(k_swarm(sid, "meta"), SwarmMeta(session_id=sid, executor="background-tasks", targets=list(dossiers), started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")).model_dump_json())
        for u, d in dossiers.items():
            await vault.put(k_swarm(sid, f"t:{u}"), d.model_dump_json())
    asyncio.run(go())


def dossier(u: str, profile: ProfileMetadata | None, vision: VisionReport | None = None, links: list | None = None) -> TargetDossier:
    return TargetDossier(username=u, platform="instagram", state="done", profile=profile, vision=vision, syndicate_links=links or [], started_at="t", finished_at="t")


def test_api_phantom_a_full_pipeline_sample_endpoint_and_feedback() -> None:
    from fastapi.testclient import TestClient
    from main import app
    from services.ephemeral_vault import get_vault
    from models.swarm import SyndicateLink

    organic_profile = ProfileMetadata(account_creation_date="January 2019", username_change_count=0, follower_count=800, following_count=400,
                                      follower_following_ratio=2.0, post_count=300, bio_text="Bapak dua anak, pecinta kopi", available_metrics=["bio_text"])
    young_profile = ProfileMetadata(account_creation_date="September 2026", username_change_count=4, follower_count=3, following_count=900,
                                    follower_following_ratio=0.003, post_count=1, bio_text="", available_metrics=[])
    bad_vision = VisionReport(profile_photo=FftResult(score=0.9, hf_ratio=0.1, peak_z=16, face_detected=True, label="suspicious"),
                              feed=FeedUniformity(images_analyzed=10, cluster_ratio=0.95, unique_ratio=0.1, method="phash", flagged=True), images_fetched=11, buffers_destroyed=True)
    grp = SyndicateLink(platform="telegram", kind="invite", url="https://t.me/+AbCdEf123456", identifier="AbCdEf123456", source="bio")
    comments = {
        "warga_organik1": [TargetComment(text=TEXT, likes=3, image_index=0)],     # teks IDENTIK dengan warga_organik2 (Phantom A)
        "warga_organik2": [TargetComment(text=TEXT, likes=1, image_index=0)],
        "akun_bot_77": [TargetComment(text=TEXT + " ya", likes=0, image_index=0)],
        "akun_bot_78": [TargetComment(text="Kebijakan baru ini sgt merugikan rakyat kecil & harus segera dicabut skrg juga", likes=0, image_index=0, injection_flag=True)],
    }
    dossiers = {"warga_organik1": dossier("warga_organik1", organic_profile), "warga_organik2": dossier("warga_organik2", organic_profile),
                "akun_bot_77": dossier("akun_bot_77", young_profile, bad_vision, [grp]), "akun_bot_78": dossier("akun_bot_78", young_profile, bad_vision, [grp])}

    with TestClient(app) as c:
        seed_session(c, get_vault(), dossiers, comments)
        r = c.post(f"/api/interrogate/{SID}/verdict")
        assert r.status_code == 200, r.text
        cards = {x["username"]: x for x in r.json()["cards"]}
        for u in ("warga_organik1", "warga_organik2"):                       # PHANTOM A: teks identik, metadata organik
            assert cards[u]["nlp"]["top_similarity"] > 0.95
            assert cards[u]["verdict"] == "ORGANIC" and cards[u]["buzzer_type"] == "C" and cards[u]["score"] < 65
            assert cards[u]["gate"]["passed"] is False and cards[u]["gate"]["elevated"] == ["narrative_copy"]
        for u in ("akun_bot_77", "akun_bot_78"):
            assert cards[u]["verdict"] == "BUZZER" and cards[u]["score"] >= 65 and cards[u]["gate"]["passed"] is True
        assert cards["akun_bot_78"]["buzzer_type"] in ("A", "B") and r.json()["media_purged"] is True
        assert c.get(f"/api/interrogate/{SID}/verdict").json()["cards"][0]["verdict_id"]

        # ---- feedback: partial_fit seketika, versi naik, duplikat ditolak
        vid = cards["akun_bot_77"]["verdict_id"]
        m0 = c.get("/api/model").json()
        fb = c.post("/api/interrogate/feedback", json={"verdict_id": vid, "feedback": "missed"})
        assert fb.status_code == 200, fb.text
        j = fb.json()
        assert j["applied_label"] == "ORGANIC" and j["model_version_after"] == j["model_version_before"] + 1 and j["raw_score_after"] < j["raw_score_before"] and j["update_ms"] < 100
        assert c.get("/api/model").json()["version"] == m0["version"] + 1
        assert c.post("/api/interrogate/feedback", json={"verdict_id": vid, "feedback": "accurate"}).status_code == 409
        assert c.post("/api/interrogate/feedback", json={"verdict_id": "e" * 32, "feedback": "accurate"}).status_code == 404
        assert c.post("/api/interrogate/feedback", json={"verdict_id": vid, "feedback": "maybe"}).status_code == 422
        assert c.post("/api/interrogate/feedback", json={"verdict_id": vid, "feedback": "accurate", "x": 1}).status_code == 422
        ok = c.post("/api/interrogate/feedback", json={"verdict_id": cards["warga_organik1"]["verdict_id"], "feedback": "accurate"}).json()
        assert ok["applied_label"] == "ORGANIC" and ok["verdict_after"] == "ORGANIC"

        # ---- endpoint sampel (uji tanpa scraping)
        samp = c.post("/api/verdict/sample", json={"features": {**{k: v for k, v in PHANTOM_A.items()}}}).json()["cards"][0]
        assert samp["verdict"] == "ORGANIC" and samp["gate"]["passed"] is False
        bot = c.post("/api/verdict/sample", json={"features": BOT, "evidence": {"profile_empty": True}}).json()["cards"][0]
        assert bot["verdict"] == "BUZZER" and bot["buzzer_type"] == "A"
        assert c.post("/api/verdict/sample", json={"features": {"copypaste_similarity": 1.5}}).status_code == 422
        assert c.post("/api/verdict/sample", json={"username": "<script>", "features": {}}).status_code == 422

        # ---- rate limit feedback (anti-banjir)
        s = get_settings(); old = s.feedback_max_per_minute; s.feedback_max_per_minute = 1
        try:
            from services.ml_runtime import get_runtime
            rt = asyncio.run(get_runtime()); rt.store._feedback_times = [time.monotonic()]
            vid2 = bot["verdict_id"]
            assert c.post("/api/interrogate/feedback", json={"verdict_id": vid2, "feedback": "accurate"}).status_code == 429
        finally:
            s.feedback_max_per_minute = old

        # ---- belum ada swarm / sesi palsu
        assert c.post(f"/api/interrogate/{'f' * 32}/verdict").status_code == 404

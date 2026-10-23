"""DETEKTO :: models/verdict.py — skema Pydantic v2 untuk Fase 5 (NLP, Verdict, Feedback, Model)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.interrogation import Platform

Family = Literal["account", "narrative_copy", "content_hostility", "visual", "network"]
VerdictLabel = Literal["BUZZER", "ORGANIC"]
BuzzerType = Literal["A", "B", "C"]
FEATURE_NAMES = (
    "account_age_risk",
    "rename_frequency",
    "engagement_anomaly",
    "copypaste_similarity",
    "gt_deviation",
    "visual_anomaly",
)


class SimilarityPartner(BaseModel):
    username: str = Field(max_length=30)
    similarity: float = Field(ge=0, le=1)
    source: Literal["tfidf", "thread", "self"]


class NlpReport(BaseModel):
    comments_scored: int = Field(ge=0)
    aggression: float | None = Field(default=None, ge=0, le=1)
    distortion: float | None = Field(default=None, ge=0, le=1)
    top_similarity: float = Field(ge=0, le=1)
    self_repeat: float = Field(ge=0, le=1)
    partners: list[SimilarityPartner] = Field(default_factory=list, max_length=10)
    engines: list[str] = Field(default_factory=list, max_length=6)


class EvidenceIn(BaseModel):
    """Bukti independen dari teks: sinyal jaringan/profil (Fase 4). Dipakai Evidence Gate & klasifikasi tipe."""

    model_config = ConfigDict(extra="forbid")

    shared_groups: int = Field(default=0, ge=0, le=100)
    injection_attempt: bool = False
    reverse_candidates: int = Field(default=0, ge=0, le=100)
    syndicate_links: int = Field(default=0, ge=0, le=100)
    profile_empty: bool = False
    copy_partners: int = Field(default=0, ge=0, le=100)


class GateReport(BaseModel):
    passed: bool
    elevated: list[Family]
    reason: str = Field(max_length=300)


class FactorContribution(BaseModel):
    feature: str = Field(max_length=40)
    value: float
    weight: float
    contribution: float


class VerdictCard(BaseModel):
    verdict_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    username: str = Field(max_length=30)
    platform: Platform
    verdict: VerdictLabel
    buzzer_type: BuzzerType
    score: float = Field(ge=0, le=100)          # skor FINAL (setelah Evidence Gate), dalam persen
    raw_score: float = Field(ge=0, le=100)      # probabilitas mentah model SGD, dalam persen
    threshold: float
    gate: GateReport
    features: dict[str, float | None]
    coverage: float = Field(ge=0, le=1)
    nlp: NlpReport | None = None
    factors: list[FactorContribution] = Field(default_factory=list, max_length=6)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    model_version: int
    created_at: str


class VerdictSet(BaseModel):
    session_id: str
    generated_at: str
    threshold: float
    model_version: int
    media_purged: bool
    cards: list[VerdictCard]


class FeatureSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_age_risk: float | None = Field(default=None, ge=0, le=1)
    rename_frequency: float | None = Field(default=None, ge=0, le=1)
    engagement_anomaly: float | None = Field(default=None, ge=0, le=1)
    copypaste_similarity: float | None = Field(default=None, ge=0, le=1)
    gt_deviation: float | None = Field(default=None, ge=0, le=1)
    visual_anomaly: float | None = Field(default=None, ge=0, le=1)


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(default="sample_user", pattern=r"^[A-Za-z0-9._]{2,30}$")
    platform: Platform = "instagram"
    features: FeatureSample
    evidence: EvidenceIn = Field(default_factory=EvidenceIn)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    feedback: Literal["accurate", "missed"]


class FeedbackResponse(BaseModel):
    verdict_id: str
    applied_label: VerdictLabel
    model_version_before: int
    model_version_after: int
    raw_score_before: float
    raw_score_after: float
    score_after: float
    verdict_after: VerdictLabel
    update_ms: float
    n_samples: int


class WeightEntry(BaseModel):
    name: str
    weight: float


class ModelStatus(BaseModel):
    version: int
    n_samples: int
    source: Literal["sqlite", "supabase", "bootstrap"]
    storage: Literal["sqlite", "supabase+sqlite"]
    weights: list[WeightEntry]
    intercept: float
    threshold: float
    updated_at: str | None

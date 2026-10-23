"""DETEKTO :: models/swarm.py — skema Pydantic v2 untuk Fase 4 (Swarm, Syndicate Crawler, Vision, Graph)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.interrogation import Platform

SocialPlatform = Literal["telegram", "whatsapp", "reddit", "threads", "instagram", "tiktok", "twitter", "facebook", "discord"]
LinkKind = Literal["group", "channel", "invite", "profile", "post"]
LinkSource = Literal["bio", "comment", "thread", "page", "reverse_image", "search"]
TargetState = Literal["queued", "running", "done", "private", "login_wall", "not_found", "blocked", "error"]
SwarmRunStatus = Literal["queued", "running", "done", "error"]
Executor = Literal["celery", "background-tasks"]
PropValue = str | int | float | bool | None


class SyndicateLink(BaseModel):
    platform: SocialPlatform
    kind: LinkKind
    url: str = Field(max_length=300)
    identifier: str = Field(max_length=100)
    source: LinkSource
    evidence: str = Field(default="", max_length=160)


class ProfileMetadata(BaseModel):
    account_creation_date: str | None = Field(default=None, max_length=40)
    username_change_count: int | None = Field(default=None, ge=0, le=1000)
    account_location: str | None = Field(default=None, max_length=80)
    follower_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    follower_following_ratio: float | None = None
    post_count: int | None = Field(default=None, ge=0)
    is_verified: bool | None = None
    bio_text: str = Field(default="", max_length=500)
    available_metrics: list[str] = Field(default_factory=list, max_length=10)
    metric_weights: dict[str, float] = Field(default_factory=dict)
    extraction_engine: str = Field(default="heuristic-regex", max_length=60)


class FftResult(BaseModel):
    score: float = Field(ge=0, le=1)
    hf_ratio: float
    peak_z: float
    face_detected: bool | None = None
    label: Literal["normal", "suspicious", "insufficient"]
    calibrated: bool = False  # heuristik belum dikalibrasi; Fase 5 menjadikannya SATU fitur yang bobotnya dipelajari model


class FeedUniformity(BaseModel):
    images_analyzed: int = Field(ge=0)
    cluster_ratio: float | None = Field(default=None, ge=0, le=1)
    unique_ratio: float | None = Field(default=None, ge=0, le=1)
    method: Literal["phash", "clip", "none"]
    flagged: bool = False


class VisionReport(BaseModel):
    profile_photo: FftResult | None = None
    feed: FeedUniformity | None = None
    images_fetched: int = 0
    images_rejected: int = 0
    buffers_destroyed: bool = False


class CrossPostHit(BaseModel):
    title: str = Field(max_length=200)
    url: str = Field(max_length=500)
    snippet: str = Field(max_length=400)
    engine: Literal["searxng", "duckduckgo"]
    mentions_target: bool = False


class CopyPasteHit(BaseModel):
    other_username: str = Field(max_length=30)
    similarity: float = Field(ge=0, le=1)
    sample: str = Field(max_length=140)
    basis: Literal["screenshot", "thread"]


class CandidateAccount(BaseModel):
    platform: SocialPlatform
    handle: str = Field(max_length=60)
    url: str = Field(max_length=300)
    evidence: Literal["handle_match", "reverse_image"]


class ReverseImageReport(BaseModel):
    status: Literal["skipped", "done", "blocked", "error"]
    reason: str = Field(default="", max_length=200)
    matches: list[CandidateAccount] = Field(default_factory=list, max_length=15)


class TargetDossier(BaseModel):
    username: str = Field(max_length=30)
    platform: Platform
    state: TargetState = "queued"
    state_detail: str = Field(default="", max_length=240)
    profile: ProfileMetadata | None = None
    syndicate_links: list[SyndicateLink] = Field(default_factory=list, max_length=40)
    vision: VisionReport | None = None
    cross_posts: list[CrossPostHit] = Field(default_factory=list, max_length=12)
    copy_paste: list[CopyPasteHit] = Field(default_factory=list, max_length=10)
    reverse_image: ReverseImageReport | None = None
    candidate_accounts: list[CandidateAccount] = Field(default_factory=list, max_length=15)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    started_at: str | None = None
    finished_at: str | None = None


class TargetJob(BaseModel):
    """Payload JSON-serializable untuk Celery / eksekutor in-process (tanpa gambar, hanya teks)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    platform: Platform
    username: str = Field(pattern=r"^[A-Za-z0-9._]{2,30}$")
    comments: list[str] = Field(default_factory=list, max_length=20)
    co_targets: list[str] = Field(default_factory=list, max_length=25)
    peer_comments: dict[str, list[str]] = Field(default_factory=dict, max_length=5)
    keywords: list[str] = Field(default_factory=list, max_length=8)
    post_url: str | None = Field(default=None, max_length=300)
    force_reverse_image: bool = False


class SwarmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_targets: int = Field(default=5, ge=1, le=5)
    force_reverse_image: bool = False


class SwarmMeta(BaseModel):
    session_id: str
    executor: Executor
    targets: list[str]
    started_at: str
    graph_built: bool = False


class SwarmStatus(BaseModel):
    session_id: str
    status: SwarmRunStatus
    executor: Executor
    targets: list[str]
    dossiers: list[TargetDossier]
    started_at: str
    finished_at: str | None = None
    error: str | None = Field(default=None, max_length=300)
    graph_summary: dict[str, int | str] | None = None


class GraphNode(BaseModel):
    label: Literal["Account", "Group", "Post"]
    key: str = Field(max_length=160)
    props: dict[str, PropValue] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    type: Literal["LINKS_TO", "PROMOTES_PROFILE", "SHARES_POST", "CO_COMMENTED", "SAME_GROUP_LINK", "COPY_PASTE", "POSSIBLE_ALT", "AMPLIFIES"]
    from_label: Literal["Account", "Group", "Post"]
    from_key: str
    to_label: Literal["Account", "Group", "Post"]
    to_key: str
    props: dict[str, PropValue] = Field(default_factory=dict)


class GraphBatch(BaseModel):
    session_id: str
    generated_at: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphResponse(BaseModel):
    batch: GraphBatch
    cypher: str
    force_graph: dict[str, list[dict[str, PropValue]]]
    graph_mode: Literal["memgraph", "networkx"]

"""DETEKTO :: models/graph.py — skema Pydantic v2 untuk Fase 6 (GraphMap, Patient Zero, Hive-Mind)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeKind = Literal["buzzer_a", "buzzer_b", "organic", "target", "discovered", "group", "post"]
LinkType = Literal[
    "LINKS_TO", "PROMOTES_PROFILE", "SHARES_POST", "CO_COMMENTED", "SAME_GROUP_LINK", "COPY_PASTE", "POSSIBLE_ALT", "AMPLIFIES"
]


class GraphMapNode(BaseModel):
    id: str = Field(max_length=160)
    label: Literal["Account", "Group", "Post"]
    name: str = Field(max_length=80)
    kind: NodeKind
    platform: str = Field(default="", max_length=20)
    verdict: Literal["BUZZER", "ORGANIC"] | None = None
    buzzer_type: Literal["A", "B", "C"] | None = None
    score: float | None = None
    verdict_id: str | None = None
    centrality: float = Field(ge=0, le=1)
    pagerank: float = Field(ge=0)
    degree: int = Field(ge=0)
    is_patient_zero: bool = False
    distance_to_pz: int | None = None


class GraphMapLink(BaseModel):
    source: str
    target: str
    type: LinkType
    weight: float = 1.0


class PatientZero(BaseModel):
    id: str
    name: str = Field(max_length=80)
    node_type: Literal["account", "group"]
    centrality: float
    degree: int
    connected_buzzers: int
    reason: str = Field(max_length=400)
    boss_account_candidate: str | None = None
    caveat: str = Field(
        default="Sentralitas graf menunjukkan simpul yang paling terhubung, BUKAN bukti identitas atau peran pimpinan. Verifikasi manual wajib sebelum pelaporan.",
        max_length=300,
    )


class GraphStats(BaseModel):
    nodes: int
    edges: int
    buzzers: int
    organics: int
    groups: int
    algorithm: str


class GraphMap(BaseModel):
    session_id: str
    mode: Literal["memgraph", "networkx"]
    nodes: list[GraphMapNode]
    links: list[GraphMapLink]
    patient_zero: PatientZero | None = None
    paths: dict[str, list[str]] = Field(default_factory=dict)
    stats: GraphStats


class HiveSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(description="Persetujuan eksplisit pengguna untuk mengirim hash username + skor ke Hive-Mind.")


class HiveSyncResult(BaseModel):
    mode: Literal["supabase", "sqlite"]
    synced: int
    skipped: int
    max_payload_bytes: int
    note: str = Field(max_length=240)

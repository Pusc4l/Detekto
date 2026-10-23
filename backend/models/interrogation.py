"""DETEKTO :: models/interrogation.py — skema Pydantic v2 untuk upload, OCR, dan Ground Truth (Fase 3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.security import sanitize_text, validate_post_url

Platform = Literal["instagram", "x", "tiktok", "facebook", "youtube"]
Bucket = Literal["context", "evidence"]
AnalysisStatus = Literal["queued", "running", "done", "error"]
Confidence = Literal["low", "medium", "high"]

SESSION_ID_PATTERN = r"^[0-9a-f]{32}$"


# ------------------------------------------------------------- request
class ImageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mime: Literal["image/jpeg"]
    size_bytes: int = Field(alias="bytes", ge=1, lt=2_000_000)
    width: int = Field(ge=1, le=20_000)
    height: int = Field(ge=1, le=20_000)
    base64: str = Field(min_length=8, max_length=2_700_000)


class UploadEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_text: str = Field(default="", max_length=2000)
    context_images: list[ImageIn] = Field(default_factory=list, max_length=10)
    platform: Platform
    post_url: str | None = Field(default=None, max_length=300)
    evidence_images: list[ImageIn] = Field(min_length=1, max_length=10)

    @field_validator("context_text")
    @classmethod
    def _clean_text(cls, v: str) -> str:
        return sanitize_text(v, 2000).strip()

    @model_validator(mode="after")
    def _cross_validate(self) -> "UploadEvidenceRequest":
        if self.post_url is not None and self.post_url.strip():
            self.post_url = validate_post_url(self.post_url, self.platform)
        else:
            self.post_url = None
        if len(self.context_text) < 10 and not self.context_images:
            raise ValueError("Konteks wajib: minimal 10 karakter teks atau 1 gambar konteks")
        return self


# ------------------------------------------------------------ response
class UploadEvidenceResponse(BaseModel):
    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    ttl_seconds: int
    vault_backend: Literal["redis", "memory"]
    accepted_context: int
    accepted_evidence: int
    total_bytes: int


class SessionMeta(BaseModel):
    """Metadata teks (tanpa gambar) yang disimpan di vault bersama media ber-TTL."""

    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    platform: Platform
    post_url: str | None = None
    context_text: str = Field(default="", max_length=2000)
    context_hashes: list[str] = Field(default_factory=list)
    evidence_hashes: list[str] = Field(default_factory=list)
    created_at: str
    media_purged: bool = False


class TargetComment(BaseModel):
    text: str = Field(max_length=500)
    likes: int = Field(ge=0)
    image_index: int = Field(ge=0)
    injection_flag: bool = False


class TargetEntity(BaseModel):
    username: str = Field(max_length=30)
    comment_count: int = Field(ge=0)
    total_likes: int = Field(ge=0)
    image_indexes: list[int]
    injection_flag: bool = False
    comments: list[TargetComment] = Field(max_length=20)


class GroundTruthSource(BaseModel):
    title: str = Field(max_length=200)
    url: str = Field(max_length=500)
    snippet: str = Field(max_length=400)
    engine: Literal["searxng", "duckduckgo"]
    credible: bool = False


class GroundTruthContext(BaseModel):
    main_claim: str = Field(max_length=400)
    objective_summary: str = Field(max_length=1200)
    neutral_baseline: str = Field(max_length=800)
    dorking_keywords: list[str] = Field(max_length=8)
    sources: list[GroundTruthSource] = Field(max_length=8)
    confidence: Confidence
    evidence_grounded: bool
    reasoning_engine: str = Field(max_length=60)
    search_engine: str = Field(max_length=40)
    injection_flags: list[str] = Field(default_factory=list, max_length=12)


class AnalysisResult(BaseModel):
    session_id: str = Field(pattern=SESSION_ID_PATTERN)
    status: AnalysisStatus
    started_at: str
    finished_at: str | None = None
    ocr_engine: str | None = None
    context_image_count: int = 0
    evidence_image_count: int = 0
    targets: list[TargetEntity] = Field(default_factory=list, max_length=25)
    ground_truth: GroundTruthContext | None = None
    warnings: list[str] = Field(default_factory=list, max_length=30)
    error: str | None = Field(default=None, max_length=400)
    media_purged: bool = False


class OcrStatus(BaseModel):
    ready: bool
    engine: Literal["tesseract", "easyocr", "none"]
    message: str = Field(max_length=400)


# ------------------------------------------------------- struktur internal OCR
class OcrLine(BaseModel):
    text: str = Field(max_length=400)
    conf: float = Field(ge=0, le=100)


class OcrPage(BaseModel):
    engine: Literal["tesseract", "easyocr", "dom"]
    lines: list[OcrLine]
    mean_conf: float = Field(ge=0, le=100)

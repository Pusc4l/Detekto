"""DETEKTO :: core/config.py
Konfigurasi terpusat + deteksi otomatis service (basis Auto-Fallback).
Semua nilai berasal dari environment / backend/.env. Tidak ada secret yang di-hardcode.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

_DEFAULT_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "tauri://localhost,http://tauri.localhost,https://tauri.localhost"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DETEKTO"
    app_version: str = "0.1.0"

    # --- Ephemeral vault / broker ---
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_ttl_seconds: int = Field(default=300, ge=1, le=3600)

    # --- Fact-finder ---
    searxng_url: str = "http://127.0.0.1:8080"

    # --- Graph ---
    memgraph_host: str = "127.0.0.1"
    memgraph_port: int = Field(default=7687, ge=1, le=65535)

    # --- Hive-Mind ---
    supabase_url: str = ""
    supabase_key: str = ""
    sqlite_path: str = "detekto_hive.db"

    # --- LLM ---
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    search_timeout_seconds: float = Field(default=6.0, gt=0, le=60)

    # --- Ephemeral vault / ingestion limits ---
    result_ttl_seconds: int = Field(default=900, ge=60, le=7200)
    memory_vault_max_bytes: int = Field(default=256 * 1024 * 1024, ge=1_000_000)
    max_upload_bytes: int = Field(default=56_000_000, ge=1_000_000)

    # --- Swarm (Fase 4) ---
    swarm_max_browser_concurrency: int = Field(default=3, ge=1, le=5)
    swarm_target_timeout_seconds: int = Field(default=120, ge=30, le=600)
    swarm_job_timeout_seconds: int = Field(default=420, ge=60, le=1800)
    scrape_nav_timeout_ms: int = Field(default=25_000, ge=5_000, le=90_000)
    scrape_headless: bool = True
    # Hanya untuk pengujian lokal / mirror: bila diisi, URL profil dibangun dari basis ini, bukan domain platform.
    scrape_test_base_url: str = ""
    reverse_image_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    max_feed_images: int = Field(default=30, ge=1, le=30)
    max_image_fetch_bytes: int = Field(default=3_000_000, ge=100_000, le=10_000_000)

    # --- ML / NLP (Fase 5) ---
    verdict_threshold: float = Field(default=0.65, ge=0.5, le=0.95)  # Strict Dictator: >= ambang = BUZZER, < ambang = ORGANIK
    nlp_use_transformer: bool = False        # True = pakai classifier transformers (butuh: pip install transformers torch)
    nlp_model_id: str = "Hate-speech-CNERG/dehatebert-mono-indonesian"  # checkpoint hate-speech ber-head; indobert-base-p1 polos TIDAK punya head klasifikasi
    feedback_sample_weight: float = Field(default=3.0, ge=0.5, le=10.0)
    feedback_max_per_minute: int = Field(default=30, ge=1, le=600)
    ml_snapshot_path: str = "ml_snapshot.joblib"

    # --- OCR ---
    tesseract_cmd: str = ""
    ocr_lang: str = "eng"
    ocr_timeout_seconds: int = Field(default=40, ge=5, le=300)
    max_ocr_concurrency: int = Field(default=2, ge=1, le=8)

    # --- Task queue ---
    celery_enabled: bool = False

    # --- Probing / CORS ---
    probe_timeout_seconds: float = Field(default=1.5, gt=0, le=10)
    cors_origins: str = _DEFAULT_ORIGINS

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url.startswith("https://") and self.supabase_key)

    @property
    def sqlite_file(self) -> Path:
        p = Path(self.sqlite_path)
        return p if p.is_absolute() else BASE_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()

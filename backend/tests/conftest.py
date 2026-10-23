"""Lingkungan uji deterministik: vault memori (tanpa Redis), SQLite sementara, tanpa SearxNG/Ollama."""
import os
import tempfile

os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:9")
os.environ.setdefault("SEARXNG_URL", "http://127.0.0.1:9")
os.environ.setdefault("OLLAMA_URL", "http://127.0.0.1:9")
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="detekto_test_"), "detekto_hive.db")

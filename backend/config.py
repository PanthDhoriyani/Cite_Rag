"""
CiteRag — Central Configuration
All settings read from .env (or environment variables).
Import this module wherever you need a setting — never call os.getenv() elsewhere.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Database URLs ─────────────────────────────────────────────────────────────
MONGODB_URL       = os.getenv("MONGODB_URL",       "mongodb://localhost:27017")
QDRANT_URL        = os.getenv("QDRANT_URL",        "http://localhost:6333")
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
OLLAMA_URL        = os.getenv("OLLAMA_URL",        "http://localhost:11434")

# ── ML Models ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
RERANKER_MODEL    = os.getenv("RERANKER_MODEL",  "BAAI/bge-reranker-large")
LLM_MODEL         = os.getenv("LLM_MODEL",       "llama3:8b")

# ── Pipeline Tuning ───────────────────────────────────────────────────────────
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE",            "512"))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP",         "128"))
BM25_TOP_K        = int(os.getenv("BM25_TOP_K",            "20"))
VECTOR_TOP_K      = int(os.getenv("VECTOR_TOP_K",          "20"))
RERANKER_TOP_K    = int(os.getenv("RERANKER_TOP_K",        "10"))
CONFIDENCE_THRESH = float(os.getenv("CONFIDENCE_THRESHOLD","0.65"))

# ── Upload Settings ───────────────────────────────────────────────────────────
UPLOAD_DIR  = os.getenv("UPLOAD_DIR",       "uploads")
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

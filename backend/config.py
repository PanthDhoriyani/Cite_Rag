"""
config.py — Central Configuration
==================================
All environment variables are read here once.
Every other file imports from this module — no os.getenv() anywhere else.

To change any setting: edit .env, not this file.
"""
import os
from dotenv import load_dotenv

# Load the .env file from the project root into environment variables
load_dotenv()

# =============================================================================
# Database Connection URLs
# =============================================================================

# MongoDB — stores document status (processing/ready/failed) and full chunk text
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

# Qdrant — stores chunk embedding vectors for semantic (meaning-based) search
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")


# Groq — cloud LLM API key (used in Phase 3 for answer generation)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Cohere — cloud API key for embeddings (embed-english-v3.0) and reranking (rerank-v3.5)
# Free Trial Key: https://dashboard.cohere.com/api-keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")

# =============================================================================
# ML Model Names (Cohere Cloud API — no local model downloads required)
# =============================================================================

# Cohere embedding model: 1024-dim vectors — matches Qdrant collection config
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embed-english-v3.0")

# Cohere reranker model: scores (question, chunk) pairs via Cohere Rerank API
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "rerank-v3.5")

# LLM model: generates the final answer from retrieved evidence (Phase 3)
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# Qdrant vector dimension — must match the embedding model output size
# Cohere embed-english-v3.0 outputs 1024-dim vectors
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# =============================================================================
# Ingestion Pipeline Settings
# =============================================================================

# Chunk size: max characters per text chunk (512 = roughly 100-130 words)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))

# Overlap: how many characters each chunk shares with the next
# Prevents losing context at chunk boundaries
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "128"))

# =============================================================================
# Retrieval Settings (Phase 2)
# =============================================================================

# Number of chunks to retrieve from Elasticsearch (BM25 keyword search)
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "20"))

# Number of chunks to retrieve from Qdrant (semantic/vector search)
VECTOR_TOP_K = int(os.getenv("VECTOR_TOP_K", "20"))

# Number of chunks to keep after reranking (from ~40 merged results → top 10)
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "10"))

# Confidence threshold for Strict Mode — Cohere reranker outputs 0.0–1.0 range
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.30"))

# =============================================================================
# File Upload Settings
# =============================================================================

# Directory where uploaded files are saved (relative to backend/ folder)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# Maximum allowed file size in megabytes
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

# Database and collection names (fixed constants — not overridable via .env)
QDRANT_COLLECTION = "citerag_docs"   # Qdrant collection for all document vectors
MONGO_DB_NAME     = "citerag"        # MongoDB database name

# =============================================================================
# LangSmith Observability
# =============================================================================
# LangSmith traces every LangChain component and any function decorated with
# @traceable. Just set these env vars — no other setup required.

# Enable/disable tracing globally (set to "false" to turn off in production)
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")

# Your LangSmith API key — from https://smith.langchain.com
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")

# Project name shown in the LangSmith dashboard
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "citerag")

# LangSmith API endpoint (default is the cloud hosted version)
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

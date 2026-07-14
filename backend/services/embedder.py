"""
CiteRag — Embedding Service
Loads BAAI/bge-large-en-v1.5 once (lazy singleton) at first call.
Produces 1024-dimensional, L2-normalized embedding vectors per chunk.

Design:
- Model is cached at module level — loaded once, reused across all requests.
- BGE models perform best with normalized embeddings (cosine similarity).
- Batch encoding is used for efficiency when embedding many chunks at once.
"""
from __future__ import annotations

import os
from typing import List

from loguru import logger

EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")

# Lazy singleton — populated on first call to _get_model()
_model = None


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_model():
    """Return the cached SentenceTransformer model, loading it if necessary."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"[Embedder] Loading model '{EMBEDDING_MODEL_NAME}' (first call)...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        test_dim = len(_model.encode("warmup"))
        logger.info(f"[Embedder] Model ready. Embedding dimension: {test_dim}.")
    return _model


# ── Public API ────────────────────────────────────────────────────────────────

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a batch of text strings.

    Args:
        texts: List of strings to embed.

    Returns:
        List of 1024-dimensional float vectors (one per input text).
    """
    model      = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,   # BGE recommendation for cosine similarity
    )
    logger.info(
        f"[Embedder] Generated {len(embeddings)} embeddings, "
        f"shape={embeddings[0].shape}."
    )
    return embeddings.tolist()


def embed_single(text: str) -> List[float]:
    """
    Convenience wrapper to embed a single string (e.g. a user query).

    Returns:
        1024-dimensional float vector.
    """
    return embed_texts([text])[0]


def get_model_name() -> str:
    """Return the configured embedding model name."""
    return EMBEDDING_MODEL_NAME

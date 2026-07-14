"""
CiteRag — Query Router
Phase 1 stub: endpoint registered and validated.
Full hybrid retrieval + reranking implemented in Phase 2.
Full response generation implemented in Phase 3A/3B.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from models.schemas import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    POST /api/query — Ask a question against ingested documents.

    Phase 1: Returns a placeholder response.
    Phase 2: Adds BM25 + vector retrieval and reranking.
    Phase 3: Adds LLM-based generation (Liberal or Strict mode).

    Request body:
        question     (str)         — The user's question.
        document_ids (list | null) — Optional: limit to specific documents.
        domain       (str | null)  — Optional: domain filter.
        mode         (str)         — "liberal" | "strict" (default: "liberal").
    """
    logger.info(
        f"[Query] Received: question='{request.question[:80]}' "
        f"mode='{request.mode}'"
    )

    # ── Phase 1: Stub response ─────────────────────────────────────────────────
    # Full implementation arrives in Phase 2 (retrieval) and Phase 3 (generation).
    return QueryResponse(
        question=request.question,
        mode=request.mode,
        answer=(
            "Query endpoint registered successfully. "
            "Full retrieval and generation pipeline will be implemented in Phase 2 & 3."
        ),
        citations=[],
        confidence=None,
        status="stub",
    )

"""
Query router — POST /api/query

Phase 1  (now):   stub — validates request, returns placeholder
Phase 2  (next):  BM25 + vector retrieval, merge, rerank
Phase 3  (later): LLM answer generation (liberal / strict mode)
"""
from fastapi import APIRouter
from loguru import logger
from schemas import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """
    Ask a question against your uploaded documents.

    Phase 2 retrieval steps (coming next):
      1. BM25 search     → Elasticsearch finds keyword-matching chunks (top 20)
      2. Vector search   → Qdrant finds semantically similar chunks (top 20)
      3. Merge + dedup   → combine both lists, remove duplicates (~25-40 unique)
      4. Rerank          → cross-encoder scores each (question, chunk) pair → top 10

    Phase 3 generation steps (after Phase 2):
      5. Liberal mode  → answer from document first, then AI explanation
      6. Strict mode   → evidence-only answer + citations + confidence score
    """
    logger.info(f"Query: '{req.question[:60]}' | mode={req.mode}")

    # Phase 2 retrieval will be added here
    return QueryResponse(
        question=req.question,
        mode=req.mode,
        answer="Phase 2 retrieval pipeline coming next.",
        status="stub",
    )

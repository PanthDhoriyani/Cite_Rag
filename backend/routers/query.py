"""
routers/query.py — Query Endpoint
====================================
Handles the main RAG query route:

  POST /api/query → Ask a question against uploaded documents

Phase 1 (now):
  Returns a stub response. Retrieval and generation are not yet implemented.

Phase 2 (next):
  Will add:
    - BM25 keyword retrieval (Elasticsearch)
    - Semantic vector retrieval (Qdrant)
    - EnsembleRetriever to merge both
    - CrossEncoderReranker to pick top 10

Phase 3 (after Phase 2):
  Will add:
    - Liberal Mode LCEL chain (document answer + AI explanation)
    - Strict Mode LCEL chain (evidence-only + citations + confidence)
"""
from fastapi import APIRouter
from loguru import logger

# Pydantic models for request/response validation
from schemas import QueryRequest, QueryResponse

router = APIRouter()


# =============================================================================
# POST /api/query
# =============================================================================

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a question against your uploaded documents",
)
def query_documents(req: QueryRequest):
    """
    Ask a question and get a cited answer from the RAG system.

    Request body:
      - question:     The user's question (required)
      - mode:         "liberal" or "strict" (default: "liberal")
      - document_ids: Optional list of document IDs to filter search scope
      - domain:       Optional domain to filter retrieval

    Current status: Phase 1 stub — returns placeholder response.
    Full RAG retrieval and generation will be added in Phase 2 and 3.

    Phase 2 retrieval plan (retrieval.py):
      1. Embed the question with HuggingFaceEmbeddings
      2. BM25 search → Elasticsearch → top 20 chunks by keyword
      3. Vector search → Qdrant → top 20 chunks by semantic similarity
      4. EnsembleRetriever merges both (50/50 weight, Reciprocal Rank Fusion)
      5. CrossEncoderReranker → scores each (question, chunk) pair → top 10

    Phase 3 generation plan (generation.py):
      Liberal Mode:
        LIBERAL_PROMPT | OllamaLLM | StrOutputParser
        Output: "DOCUMENT-BASED ANSWER: ... ADDITIONAL EXPLANATION: ..."

      Strict Mode:
        Check confidence threshold → STRICT_PROMPT | OllamaLLM | StrOutputParser
        Output: answer + citations + confidence score
    """
    logger.info(
        f"[Query] question='{req.question[:60]}' | mode={req.mode}"
    )

    # Phase 2 retrieval will replace this stub
    # Phase 3 generation will replace this stub
    return QueryResponse(
        question=req.question,
        mode=req.mode,
        answer=(
            "Phase 2 and 3 coming next: "
            "retrieval (BM25 + semantic + rerank) and generation (LangChain LCEL chains)."
        ),
        citations=[],
        confidence=None,
        status="stub",
    )

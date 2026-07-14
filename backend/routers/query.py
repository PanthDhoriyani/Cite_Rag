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
from fastapi import APIRouter, HTTPException
from loguru import logger

# Pydantic models for request/response validation
from schemas import QueryRequest, QueryResponse, Citation

# Phase 2: Retrieval Pipeline
from retrieval import retrieve_documents

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

    # --- PHASE 2: HYBRID RETRIEVAL & RERANKING ---
    try:
        # Retrieve top 10 chunks using Qdrant + ES + CrossEncoder
        docs = retrieve_documents(req.question, req.document_ids)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents from databases.")

    # Convert LangChain Document objects into our Citation Pydantic models
    citations = []
    for doc in docs:
        citations.append(Citation(
            document_name=doc.metadata.get("document_name", "Unknown Document"),
            page_number=doc.metadata.get("page_number"),
            chunk_text=doc.page_content,
            chunk_id=doc.metadata.get("chunk_id", "unknown_id"),
        ))
        
    best_score = docs[0].metadata.get("relevance_score") if docs else None

    # Phase 3 generation will replace this stub answer
    return QueryResponse(
        question=req.question,
        mode=req.mode,
        answer=(
            f"Phase 2 complete! I found {len(citations)} relevant chunks across your documents. "
            "Phase 3 (coming next) will pass these chunks to the Ollama LLM to generate a final answer."
        ),
        citations=citations,
        confidence=best_score,  # Expose the top cross-encoder score for testing
        status="ok",
    )

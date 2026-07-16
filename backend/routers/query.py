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

# LangSmith tracing
from langsmith import traceable

# Pydantic models for request/response validation
from schemas import QueryRequest, QueryResponse, Citation

# Phase 2: Retrieval Pipeline
from retrieval import retrieve_documents

# Phase 3: Answer Generation
from generation import generate_liberal_answer, generate_strict_answer

router = APIRouter()


# =============================================================================
# POST /api/query
# =============================================================================

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a question against your uploaded documents",
)
@traceable(name="query_documents", run_type="chain")
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
        LIBERAL_PROMPT | ChatGroq | StrOutputParser
        Output: "DOCUMENT-BASED ANSWER: ... ADDITIONAL EXPLANATION: ..."

      Strict Mode:
        Check confidence threshold → STRICT_PROMPT | ChatGroq | StrOutputParser
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
        
    # --- PHASE 3: ANSWER GENERATION (LCEL) ---
    try:
        if req.mode.lower() == "strict":
            # Identify the domain of the context documents (defaulting to request domain or general)
            doc_domain = docs[0].metadata.get("domain", "general") if docs else "general"
            domain = req.domain or doc_domain
            
            # Generate strict evidence-only answer
            res = generate_strict_answer(req.question, docs, domain)
            
            # If low confidence, clear citations as we did not use them for an answer
            if res.get("status") == "low_confidence":
                citations = []
        else:
            # Generate liberal/educational answer
            res = generate_liberal_answer(req.question, docs)
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate answer from local LLM.")

    return QueryResponse(
        question=req.question,
        mode=req.mode,
        answer=res["answer"],
        citations=citations,
        confidence=res.get("confidence"),
        status=res["status"],
    )

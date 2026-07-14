"""
schemas.py — Pydantic Data Models
===================================
Defines the shape of every request and response in the API.
FastAPI uses these to validate incoming data and serialize outgoing data.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


# =============================================================================
# Domain Enum
# =============================================================================

class Domain(str, Enum):
    """
    The domain/category of the uploaded document.
    Used to route to the correct public verification API in Strict Mode.

    - legal      → government legal portals
    - research   → arXiv, Semantic Scholar, IEEE
    - healthcare → PubMed, WHO guidelines
    - technical  → RFC databases, official docs
    - compliance → FDA, SEC, regulatory sites
    - education  → general educational content
    - general    → no domain-specific verification
    """
    legal      = "legal"
    research   = "research"
    healthcare = "healthcare"
    technical  = "technical"
    compliance = "compliance"
    education  = "education"
    general    = "general"


# =============================================================================
# Upload Models
# =============================================================================

class UploadResponse(BaseModel):
    """
    Returned immediately after a file upload request.
    Ingestion runs in the background — the client polls /api/documents
    to check when status changes from 'processing' to 'ready'.
    """
    document_id: str   # UUID assigned to this document
    filename:    str   # Original filename as uploaded
    status:      str   # Always "processing" on upload response
    message:     str = ""  # Optional human-readable message


# =============================================================================
# Query Models
# =============================================================================

class QueryRequest(BaseModel):
    """
    Sent by the client to ask a question against uploaded documents.

    Fields:
    - question:     The user's question (required)
    - mode:         "liberal" (default) or "strict"
    - document_ids: Optional list of document IDs to search only those docs
    - domain:       Optional domain filter (narrows retrieval results)
    """
    question:     str
    mode:         str                 = "liberal"  # "liberal" | "strict"
    document_ids: Optional[List[str]] = None        # filter to specific docs
    domain:       Optional[str]       = None        # filter by domain


class Citation(BaseModel):
    """
    A single citation linking a part of the answer to a source chunk.
    Returned alongside the answer so users can verify every claim.
    """
    document_name:    str            # e.g. "ResearchPaper.pdf"
    page_number:      Optional[int]  # page where the chunk came from
    chunk_text:       str            # the actual chunk text used as evidence
    chunk_id:         str            # internal ID for the chunk


class QueryResponse(BaseModel):
    """
    Returned after a query is processed.
    Contains the answer text, source citations, and confidence score.

    Fields:
    - answer:     Generated answer text from Ollama LLM
    - citations:  List of source chunks used as evidence
    - confidence: Float 0.0–1.0 (only meaningful in Strict Mode)
    - status:     "ok" | "stub" | "low_confidence" | "no_results"
    """
    question:   str
    mode:       str
    answer:     str
    citations:  List[Citation]     = []
    confidence: Optional[float]    = None
    status:     str                = "ok"

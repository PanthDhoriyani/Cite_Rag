"""
CiteRag — Pydantic Schemas
Data models for all pipeline stages: ingestion, chunking, and API I/O.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Domain Enum ───────────────────────────────────────────────────────────────

class Domain(str, Enum):
    legal      = "legal"
    research   = "research"
    healthcare = "healthcare"
    technical  = "technical"
    compliance = "compliance"
    education  = "education"
    general    = "general"


# ── Chunk-level Models ────────────────────────────────────────────────────────

class ChunkMetadata(BaseModel):
    """
    Metadata attached to every text chunk produced by the ingestion pipeline.
    All fields are captured at ingestion time and cannot be reconstructed later.
    """
    document_id:      str
    document_name:    str
    chunk_id:         str      = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_index:      int                  # 0-based position in the document
    total_chunks:     int                  # filled in after all pages processed
    page_number:      Optional[int] = None
    paragraph_number: Optional[int] = None
    line_start:       Optional[int] = None
    line_end:         Optional[int] = None
    upload_timestamp: datetime
    domain:           Domain


class Chunk(BaseModel):
    """A single text chunk paired with its metadata."""
    chunk_text: str
    metadata:   ChunkMetadata


# ── Document-level Models ─────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    """Top-level document record persisted in MongoDB on upload."""
    document_id:      str      = Field(default_factory=lambda: str(uuid.uuid4()))
    document_name:    str
    file_path:        str
    file_type:        str
    domain:           Domain
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_chunks:     int      = 0
    status:           str      = "processing"   # processing | ready | failed


# ── API Response Models ───────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Returned immediately from POST /api/upload."""
    document_id:   str
    document_name: str
    status:        str
    message:       str


class QueryRequest(BaseModel):
    """Request body for POST /api/query (Phase 2 full implementation)."""
    question:     str
    document_ids: Optional[List[str]] = None  # filter to specific documents
    domain:       Optional[Domain]    = None  # filter by domain
    mode:         str                 = "liberal"  # "strict" | "liberal"


class QueryResponse(BaseModel):
    """Structured response from the query pipeline (Phase 3 full implementation)."""
    question:   str
    mode:       str
    answer:     str
    citations:  List[dict] = []
    confidence: Optional[float] = None
    status:     str = "ok"

"""
CiteRag — Pydantic Schemas
Simple flat models for API request/response shapes.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class Domain(str, Enum):
    legal      = "legal"
    research   = "research"
    healthcare = "healthcare"
    technical  = "technical"
    compliance = "compliance"
    education  = "education"
    general    = "general"


class UploadResponse(BaseModel):
    document_id: str
    filename:    str
    status:      str
    message:     str = ""


class QueryRequest(BaseModel):
    question:     str
    mode:         str           = "liberal"   # "liberal" | "strict"
    document_ids: Optional[List[str]] = None  # filter to specific docs
    domain:       Optional[str] = None        # filter by domain


class QueryResponse(BaseModel):
    question:   str
    mode:       str
    answer:     str
    citations:  List[dict]     = []
    confidence: Optional[float] = None
    status:     str            = "ok"

"""
CiteRag — FastAPI Entry Point
Main application setup: routers, lifespan, health check.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from routers import upload, query


# ── Lifespan: startup / shutdown ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 CiteRag backend starting up...")
    # Placeholder: DB clients and ML model warm-up will be added in later steps
    yield
    logger.info("👋 CiteRag backend shutting down...")


# ── App initialisation ─────────────────────────────────────────────────────────
app = FastAPI(
    title="CiteRag API",
    description="Citation-Aware Multi-Source RAG Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow requests from the React frontend during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(query.router, prefix="/api", tags=["query"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    Returns the operational status of the backend.
    Individual service health checks (Qdrant, MongoDB, ES, Ollama)
    will be added in Phase 5.
    """
    return {"status": "ok", "service": "CiteRag API", "version": "0.1.0"}

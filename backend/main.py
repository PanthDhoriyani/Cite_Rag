"""
main.py — FastAPI Entry Point
================================
This is where the server starts. It:
  1. Creates the FastAPI application
  2. Adds CORS middleware (allows React frontend on port 3000 to call this API)
  3. Registers the upload and query routers
  4. Provides a health check endpoint

Run the server:
  cd backend
  venv\\Scripts\\uvicorn main:app --reload --port 8000

The --reload flag means the server restarts automatically when you save any file.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Import the routers that contain the actual API endpoints
from routers import upload, query


# =============================================================================
# Lifespan — Startup and Shutdown Events
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before the yield runs on startup.
    Code after the yield runs on shutdown.

    Currently just logs startup/shutdown.
    In future: could pre-load models, verify DB connections, etc.
    """
    logger.info("CiteRag API starting up...")
    logger.info("Tip: Visit http://localhost:8000/docs for interactive API docs")
    yield
    logger.info("CiteRag API shut down.")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="CiteRag API",
    description=(
        "Citation-Aware RAG Platform — "
        "upload documents, ask questions, get cited answers."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# CORS Middleware
# =============================================================================
# CORS = Cross-Origin Resource Sharing.
# Without this, the browser blocks API calls from localhost:3000 (React) to
# localhost:8000 (FastAPI) because they're on different ports.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, DELETE, etc.
    allow_headers=["*"],   # any header
)


# =============================================================================
# Routers
# =============================================================================
# prefix="/api" means all routes become /api/upload, /api/documents, etc.

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(query.router,  prefix="/api", tags=["query"])


# =============================================================================
# Health Check
# =============================================================================

@app.get("/api/health", tags=["health"])
def health_check():
    """
    Simple health check endpoint.
    Returns 200 if the backend is running.
    Frontend uses this to check if the backend is reachable before showing the UI.
    """
    return {
        "status":  "ok",
        "service": "CiteRag API",
        "version": "0.1.0",
    }

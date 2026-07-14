"""
CiteRag — FastAPI Entry Point
Starts the server, registers routes, configures CORS.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from routers import upload, query


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CiteRag API starting up...")
    yield
    logger.info("CiteRag API shut down.")


app = FastAPI(
    title="CiteRag API",
    description="Citation-Aware RAG Platform — upload documents, ask questions, get cited answers.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the React frontend (port 3000) to call this backend (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(query.router,  prefix="/api", tags=["query"])


@app.get("/api/health", tags=["health"])
def health():
    """Quick check that the backend is alive."""
    return {"status": "ok", "service": "CiteRag API", "version": "0.1.0"}

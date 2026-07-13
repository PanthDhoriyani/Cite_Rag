# CiteRag — Project Memory
> **Auto-maintained.** Updated after every step or change.
> Use this file to quickly recall what has been done and what is next.

---

## Project Identity

| Field | Value |
|---|---|
| **Project Name** | CiteRag |
| **Full Name** | Citation-Aware Multi-Source RAG Platform |
| **Root Directory** | `d:\projectaalphaa\CiteRag` |
| **Backend** | FastAPI (Python) — `backend/` |
| **Frontend** | React + Tailwind CSS — `frontend/` |
| **Reference Docs** | `PROJECT_PLAN.md`, `project_flow.md` |

---

## Overall Phase Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Document Ingestion Pipeline | 🔄 In Progress |
| Phase 2 | Hybrid Retrieval & Reranking | ⏳ Not Started |
| Phase 3B | Liberal Analysis Mode | ⏳ Not Started |
| Phase 3A | Strict Analysis Mode | ⏳ Not Started |
| Phase 4 | Frontend UI | ⏳ Not Started |
| Phase 5 | Docker Deployment | ⏳ Not Started |
| Phase 6 | Testing & Tuning | ⏳ Not Started |

---

## Phase 1 — Document Ingestion Pipeline

### Step 1.1 — Project Scaffolding & Environment Setup ✅ DONE

**Date completed:** 2026-07-13

**What was done:**
- Created full backend folder structure (`routers/`, `services/`, `db/`, `models/`)
- Created `frontend/src/components/` directory
- Created `uploads/` directory for raw file storage
- Created Python virtual environment at `backend/venv/`
- Installed core packages: `fastapi`, `uvicorn[standard]`, `python-multipart`, `pydantic`, `pydantic-settings`, `python-dotenv`, `loguru`, `aiofiles`
- Created `backend/main.py` — FastAPI app with CORS, lifespan, `/api/health` endpoint
- Created `backend/requirements.txt` — all dependencies for the full project
- Created router stubs: `backend/routers/upload.py`, `backend/routers/query.py`
- Created `__init__.py` for all packages: `routers/`, `services/`, `db/`, `models/`
- Created `.env` with local dev defaults and Docker Compose values commented

**Validation passed:**
- ✅ `uvicorn main:app` starts without errors
- ✅ `GET /api/health` → `{ "status": "ok", "service": "CiteRag API", "version": "0.1.0" }`

**Key decisions made:**
- Using `loguru` instead of Python stdlib `logging` (cleaner async-friendly output)
- Using `motor` (async MongoDB driver) alongside `pymongo` for async FastAPI compatibility
- `.env` contains both local and Docker URLs (Docker ones commented out) to avoid confusion during deployment switch
- Router stubs created now so `main.py` imports work from Day 1 — no broken imports as steps are built

---

### Step 1.2 — File Upload Endpoint ⏳ NOT STARTED

**What will be done:**
- Implement `POST /api/upload` in `backend/routers/upload.py`
- Validate file type (PDF, DOCX, TXT) and size (max 50MB)
- Save raw file to `uploads/` with UUID filename
- Return `{ document_id, filename, status: "processing" }`
- Trigger background ingestion pipeline via `BackgroundTasks`

---

### Step 1.3 — Text Extraction Service ⏳ NOT STARTED

**What will be done:**
- Create `backend/services/extractor.py`
- PyMuPDF → pdfplumber → Tesseract fallback chain for PDFs
- DOCX via `python-docx`, TXT via plain read

---

### Step 1.4 — Metadata Extraction ⏳ NOT STARTED

**What will be done:**
- Capture `document_id`, `page_number`, `paragraph_number`, `line_start/end`, `domain`, etc.
- Create Pydantic models in `backend/models/schemas.py`

---

### Step 1.5 — Semantic Chunking ⏳ NOT STARTED

**What will be done:**
- Create `backend/services/chunker.py`
- LangChain `RecursiveCharacterTextSplitter` — 512 tokens / 128 overlap

---

### Step 1.6 — Embedding Generation ⏳ NOT STARTED

**What will be done:**
- Create `backend/services/embedder.py`
- Load `BAAI/bge-large-en-v1.5` once at startup, generate 1024-dim vectors

---

### Step 1.7 — Database Clients Setup ⏳ NOT STARTED

**What will be done:**
- Create `backend/db/qdrant_client.py`, `mongo_client.py`, `elastic_client.py`
- Set up connections, collections/indexes

---

### Step 1.8 — Storage Pipeline (Wire Everything) ⏳ NOT STARTED

**What will be done:**
- Wire extractor → chunker → embedder → Qdrant + MongoDB + Elasticsearch

---

## Environment & Tooling

| Tool | Version / Notes |
|---|---|
| Python | System Python (3.x) |
| Virtual env | `backend/venv/` |
| FastAPI | 0.139.0 (installed) |
| Uvicorn | 0.51.0 (installed) |
| Pydantic | 2.13.4 (installed) |
| Dev server command | `cd backend && .\venv\Scripts\uvicorn main:app --reload` |

---

## Key Config Values (from .env)

| Variable | Value |
|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` |
| `RERANKER_MODEL` | `BAAI/bge-reranker-large` |
| `LLM_MODEL` | `llama3:8b` |
| `CONFIDENCE_THRESHOLD` | `0.65` |
| `CHUNK_SIZE` | `512` |
| `CHUNK_OVERLAP` | `128` |
| `BM25_TOP_K` | `20` |
| `VECTOR_TOP_K` | `20` |
| `RERANKER_TOP_K` | `10` |
| `MAX_FILE_SIZE_MB` | `50` |

---

## Design Rules Enforced So Far

- ✅ Router stubs created from Day 1 — no broken imports
- ✅ All config in `.env` — no hardcoded URLs or thresholds in code
- ✅ CORS configured for `localhost:3000` (React dev server)
- ✅ Lifespan hook in place for future model warm-up on startup

---

*Last updated: Step 1.1 complete — 2026-07-13*

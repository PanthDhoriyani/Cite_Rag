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
| **Reference Docs** | `PROJECT_PLAN.md`, `project_flow.md`, `explain.md`, `about.md` |

---

## Overall Phase Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Document Ingestion Pipeline | ✅ Complete |
| Phase 2 | Hybrid Retrieval & Reranking | ⏳ Not Started |
| Phase 3B | Liberal Analysis Mode | ⏳ Not Started |
| Phase 3A | Strict Analysis Mode | ⏳ Not Started |
| Phase 4 | Frontend UI | ⏳ Not Started |
| Phase 5 | Docker Deployment | ⏳ Not Started |
| Phase 6 | Testing & Tuning | ⏳ Not Started |

---

## Phase 1 — Document Ingestion Pipeline ✅ COMPLETE

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

### Step 1.2 — File Upload Endpoint ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Replaced stub in `backend/routers/upload.py` with full implementation
- Implemented `POST /api/upload`:
  - Extension whitelist: `{pdf, docx, txt}` — HTTP 422 on violation
  - Size check: reads file into memory, rejects > 50 MB — HTTP 422
  - UUID-based file naming: saved as `{uuid}.{ext}` in `uploads/`
  - Accepts `domain` form field (Domain enum — 7 values)
  - Inserts MongoDB document record immediately (status: `"processing"`)
  - Triggers ingestion pipeline via `BackgroundTasks` — returns HTTP 202 instantly
- Implemented `GET /api/documents` — lists all documents with status
- Implemented `DELETE /api/documents/{id}` — background deletion from all 3 stores

---

### Step 1.3 — Text Extraction Service ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/services/extractor.py`
- `extract_text(file_path, file_type)` dispatches to the correct handler:
  - **PDF:** `_extract_with_pymupdf()` → fallback to `_extract_with_tesseract()` if total chars < 100
  - **DOCX:** `_extract_docx()` via python-docx paragraphs
  - **TXT:** `_extract_txt()` plain UTF-8 read
- Returns `List[{"page_number": int, "text": str}]` preserving page-level boundaries
- Tesseract renders pages at 300 DPI PNG via PyMuPDF before OCR

---

### Step 1.4 — Metadata Models ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/models/schemas.py` with all Pydantic models:
  - `Domain` enum: `legal | research | healthcare | technical | compliance | education | general`
  - `ChunkMetadata`: 11 fields — all required metadata per chunk
  - `Chunk`: pairs chunk_text with ChunkMetadata
  - `DocumentInfo`: document-level record for MongoDB
  - `UploadResponse`, `QueryRequest`, `QueryResponse`: API contract models

---

### Step 1.5 — Semantic Chunking ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/services/chunker.py`
- Used `langchain_text_splitters.RecursiveCharacterTextSplitter` (LangChain 0.2+ correct import)
- Chunk size: **512** · Overlap: **128** (configurable via `.env`)
- Separator priority: `"\n\n"` → `"\n"` → `" "` → `""`
- Pages chunked individually to preserve `page_number` per chunk
- `total_chunks` backfilled after all pages processed

**Bug fixed:** `langchain.text_splitter` (old) → `langchain_text_splitters` (LangChain 0.2+)

---

### Step 1.6 — Embedding Generation ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/services/embedder.py`
- Lazy singleton model: `BAAI/bge-large-en-v1.5` loaded once on first call, reused forever
- `embed_texts(texts)` — batch encoding, `normalize_embeddings=True`, returns 1024-dim vectors
- `embed_single(text)` — convenience wrapper for single queries (Phase 2 ready)

---

### Step 1.7 — Database Clients Setup ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/db/qdrant_client.py`:
  - Collection: `"documents"`, 1024-dim, COSINE distance
  - Functions: `ensure_collection()`, `upsert_vectors()`, `delete_by_document_id()`, `search_vectors()`
- Created `backend/db/mongo_client.py`:
  - DB: `citerag`, Collections: `chunks` + `documents`
  - Functions: full CRUD for chunks and document records
- Created `backend/db/elastic_client.py`:
  - Index: `citerag_chunks`, field mapping with `english` analyzer on `chunk_text`
  - Functions: `ensure_index()`, `index_chunks()`, `bm25_search()`, `delete_by_document_id()`

---

### Step 1.8 — Storage Pipeline ✅ DONE

**Date completed:** 2026-07-14

**What was done:**
- Created `backend/services/ingestion.py` — full pipeline orchestrator
- Pipeline: extract → chunk → embed → upsert to Qdrant → insert to MongoDB → index to Elasticsearch
- Error handling: status updated to `"failed"` at any step; success updates to `"ready"`
- Called via FastAPI `BackgroundTasks` from upload endpoint

---

### Phase 1 Summary — Files Created

| File | Purpose |
|---|---|
| `backend/models/schemas.py` | Pydantic data models |
| `backend/services/extractor.py` | PDF/DOCX/TXT text extraction |
| `backend/services/chunker.py` | Semantic chunking (512/128) |
| `backend/services/embedder.py` | BGE embedding generation |
| `backend/db/qdrant_client.py` | Qdrant vector DB client |
| `backend/db/mongo_client.py` | MongoDB client |
| `backend/db/elastic_client.py` | Elasticsearch BM25 client |
| `backend/services/ingestion.py` | Full pipeline orchestrator |
| `backend/routers/upload.py` | Upload + document management API |
| `backend/routers/query.py` | Query endpoint (Phase 1 stub) |
| `explain.md` | Phase 1 completion documentation |
| `about.md` | Technology reference guide |

**All imports verified clean:** ✅ 2026-07-14

---

## What's Next — Phase 2

Phase 2 will build on the DB read functions already stubbed in Phase 1:
- `qdrant_client.search_vectors()` — semantic nearest-neighbour search
- `elastic_client.bm25_search()` — keyword BM25 search
- `mongo_client.get_chunks_by_ids()` — hydrate results with full text

**Files to create:**
- `backend/services/retriever.py` — BM25 + vector retrieval, merge, dedup (Steps 2.2–2.4)
- `backend/services/reranker.py` — `BAAI/bge-reranker-large` cross-encoder (Step 2.5)
- `backend/routers/query.py` — full query pipeline replacing stub (Step 2.1)
- `backend/models/schemas.py` — extend with retrieval result models

---

## Environment & Tooling

| Tool | Version / Notes |
|---|---|
| Python | System Python (3.x) in `backend/venv/` |
| FastAPI | 0.111.0 |
| Uvicorn | 0.30.1 |
| Pydantic | 2.7.1 |
| LangChain | 0.2.5 (text splitter: `langchain_text_splitters`) |
| loguru | 0.7.2 |
| sentence-transformers | 3.0.1 |
| qdrant-client | 1.9.1 |
| pymongo | 4.7.2 |
| elasticsearch | 8.13.2 |
| PyMuPDF | 1.24.5 |
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
| `MONGODB_URL` | `mongodb://localhost:27017` |
| `QDRANT_URL` | `http://localhost:6333` |
| `ELASTICSEARCH_URL` | `http://localhost:9200` |
| `OLLAMA_URL` | `http://localhost:11434` |

---

## Design Rules Enforced So Far

- ✅ Router stubs created from Day 1 — no broken imports
- ✅ All config in `.env` — no hardcoded URLs or thresholds in code
- ✅ CORS configured for `localhost:3000` (React dev server)
- ✅ Lifespan hook in place for future model warm-up on startup
- ✅ Singleton embedding model — loaded once, not per request
- ✅ Page-level extraction — `page_number` captured before chunking, cannot be reconstructed later
- ✅ Per-page chunking — `page_number` metadata is exact, not estimated
- ✅ Metadata backfilled — `total_chunks` set after all pages processed
- ✅ Three-store deletion — removing a document cleans Qdrant + MongoDB + Elasticsearch

---

*Last updated: Phase 1 complete — 2026-07-14*

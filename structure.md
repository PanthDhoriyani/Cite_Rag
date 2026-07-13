# CiteRag — Project Structure
> **Auto-maintained.** Updated after every step or change.
> Describes every folder and file: its purpose, what code it contains, and what that code does.

---

## Root Directory: `d:\projectaalphaa\CiteRag\`

```
CiteRag/
├── backend/                  ← FastAPI Python backend
│   ├── venv/                 ← Python virtual environment (not committed to git)
│   ├── routers/              ← API endpoint handlers
│   ├── services/             ← Core business logic (extraction, chunking, retrieval, etc.)
│   ├── db/                   ← Database client wrappers
│   ├── models/               ← Pydantic data models / schemas
│   ├── main.py               ← FastAPI app entry point
│   └── requirements.txt      ← Python dependencies
│
├── frontend/                 ← React + Tailwind CSS frontend (scaffolded in Phase 4)
│   └── src/
│       └── components/       ← React UI components
│
├── uploads/                  ← Raw uploaded files stored here (not committed to git)
│
├── .env                      ← Environment variables (all service URLs, model names, thresholds)
├── PROJECT_PLAN.md           ← Full architecture and design reference
├── project_flow.md           ← Step-by-step build roadmap
├── memory.md                 ← Project memory — what's done, what's next
└── structure.md              ← This file
```

---

## `backend/` — FastAPI Backend

The entire server-side application. Runs on **port 8000**.
Start command: `cd backend && .\venv\Scripts\uvicorn main:app --reload`

---

### `backend/main.py`

**Status:** ✅ Created (Step 1.1)

**Purpose:** FastAPI application entry point. Everything starts here.

**What it does:**
- Creates the `FastAPI` app instance with title, description, and version
- Registers **CORS middleware** — allows requests from `http://localhost:3000` (React dev server)
- Registers the **lifespan** context manager — runs startup/shutdown hooks (model warm-up will be added here in later steps)
- Registers all **API routers** with prefix `/api`
- Exposes `GET /api/health` endpoint

**Current endpoints provided:**
| Method | Route | Description |
|---|---|---|
| `GET` | `/api/health` | Returns `{ status, service, version }` — confirms backend is alive |

**Will grow to include** (as steps complete):
- `POST /api/upload` (Step 1.2)
- `GET /api/documents` (Step 4.8)
- `DELETE /api/documents/{id}` (Step 4.8)
- `POST /api/query` (Step 2.1)

```python
# Core structure of main.py
app = FastAPI(title="CiteRag API", ...)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], ...)
app.include_router(upload.router, prefix="/api")
app.include_router(query.router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "CiteRag API", "version": "0.1.0"}
```

---

### `backend/requirements.txt`

**Status:** ✅ Created (Step 1.1)

**Purpose:** Declares all Python package dependencies for the backend.

**Dependency groups:**

| Group | Packages | Purpose |
|---|---|---|
| Web Framework | `fastapi`, `uvicorn[standard]`, `python-multipart` | HTTP server and file upload |
| Validation | `pydantic`, `pydantic-settings` | Request/response models and settings |
| PDF Extraction | `PyMuPDF`, `pdfplumber`, `pytesseract`, `Pillow` | Multi-strategy PDF text extraction |
| Document Parsing | `python-docx` | DOCX file text extraction |
| RAG Framework | `langchain`, `langchain-community` | Text splitting, LLM chains |
| Embeddings & Reranking | `sentence-transformers` | BGE embedding + cross-encoder reranker |
| Vector DB | `qdrant-client` | Connect to Qdrant for vector storage/search |
| Document DB | `pymongo`, `motor` | MongoDB for metadata + full chunk text storage |
| Keyword Search | `elasticsearch` | BM25 keyword retrieval |
| LLM | `httpx` | HTTP calls to Ollama REST API |
| Utilities | `python-dotenv`, `loguru`, `aiofiles` | Env vars, logging, async file I/O |

**Currently installed (Step 1.1):**
`fastapi`, `uvicorn`, `python-multipart`, `pydantic`, `pydantic-settings`, `python-dotenv`, `loguru`, `aiofiles`

**Remaining to install** (when each step begins):
- Step 1.3: `PyMuPDF`, `pdfplumber`, `pytesseract`, `Pillow`, `python-docx`
- Step 1.5: `langchain`, `langchain-community`
- Step 1.6: `sentence-transformers`
- Step 1.7: `qdrant-client`, `pymongo`, `motor`, `elasticsearch`
- Step 3B.2: `httpx` (for Ollama)

---

### `backend/routers/`

**Status:** ✅ Directory created (Step 1.1)

**Purpose:** Contains all FastAPI router files. Each file groups related API endpoints.
Routers are registered in `main.py` with the `/api` prefix.

---

#### `backend/routers/__init__.py`

**Status:** ✅ Created (Step 1.1)
**Purpose:** Marks `routers/` as a Python package so `from routers import upload` works.
**Contents:** Single comment line — no logic.

---

#### `backend/routers/upload.py`

**Status:** 🔲 Stub created (Step 1.1) — Full implementation in Step 1.2

**Purpose:** Handles all document upload and document management endpoints.

**Current state:** Minimal stub — just creates an empty `APIRouter`. No endpoints yet.

**Will implement (Step 1.2):**
```
POST   /api/upload            → Upload a PDF/DOCX/TXT file
GET    /api/documents         → List all uploaded documents (Step 4.8)
DELETE /api/documents/{id}    → Delete a document from all stores (Step 4.8)
```

**Key logic to be added:**
- File type validation (whitelist: `.pdf`, `.docx`, `.txt`)
- File size check (reject > 50MB)
- Save file to `uploads/` with UUID filename
- Generate and return `document_id`
- Trigger background ingestion via `BackgroundTasks`

---

#### `backend/routers/query.py`

**Status:** 🔲 Stub created (Step 1.1) — Full implementation in Step 2.1

**Purpose:** Handles the user query endpoint — routes questions through retrieval and generation pipelines.

**Current state:** Minimal stub — just creates an empty `APIRouter`. No endpoints yet.

**Will implement (Step 2.1):**
```
POST /api/query → Accept question + mode + optional filters → return structured answer
```

**Request body (to be added):**
```json
{
  "question": "string",
  "document_ids": ["uuid1"],   // optional
  "domain": "healthcare",       // optional
  "mode": "strict" | "liberal"
}
```

---

### `backend/services/`

**Status:** ✅ Directory created (Step 1.1)

**Purpose:** Core business logic layer. Each file is a focused service module.
Services are called by routers — routers handle HTTP concerns, services handle domain logic.

---

#### `backend/services/__init__.py`

**Status:** ✅ Created (Step 1.1)
**Purpose:** Marks `services/` as a Python package.
**Contents:** Single comment line — no logic.

---

#### `backend/services/extractor.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.3

**Will do:**
- Accept a file path, determine file type
- Route to correct extractor:
  - PDF → try `PyMuPDF` first; if text < 100 chars → fallback to `Tesseract OCR`
  - PDF with tables → `pdfplumber`
  - DOCX → `python-docx`
  - TXT → plain `open().read()`
- Return raw text with page-level boundaries preserved

---

#### `backend/services/chunker.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.5

**Will do:**
- Accept raw text + document metadata
- Use `LangChain RecursiveCharacterTextSplitter` (chunk: 512, overlap: 128)
- Return list of `{ chunk_text, metadata }` objects
- Each chunk carries full metadata linkage (page, paragraph, document_id)

---

#### `backend/services/embedder.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.6

**Will do:**
- Load `BAAI/bge-large-en-v1.5` at module-level (cached — not reloaded per request)
- Expose `generate_embedding(text: str) -> list[float]` — returns 1024-dim vector
- Used by the ingestion pipeline to embed each chunk

---

#### `backend/services/retriever.py` ⏳ NOT YET CREATED

**Planned for:** Step 2.2 / 2.3 / 2.4

**Will do:**
- `bm25_retrieve(question, top_k=20)` — Elasticsearch multi_match query
- `vector_retrieve(question, top_k=20)` — Qdrant nearest-neighbor search
- `merge_results(bm25, vector)` — deduplicate by chunk_id, return 25–40 unique chunks

---

#### `backend/services/reranker.py` ⏳ NOT YET CREATED

**Planned for:** Step 2.5

**Will do:**
- Load `BAAI/bge-reranker-large` at module-level
- `rerank(question, chunks, top_k=10)` — score each `(question, chunk)` pair
- Return top-10 chunks sorted by relevance score
- Score stored per chunk for downstream confidence calculation

---

#### `backend/services/liberal_mode.py` ⏳ NOT YET CREATED

**Planned for:** Step 3B.1

**Will do:**
- Accept top reranked chunks
- Call Ollama with liberal system prompt (document-first, then AI expansion allowed)
- Parse output into two sections: `DOCUMENT-BASED ANSWER` / `ADDITIONAL EXPLANATION`
- Attach soft citations (doc name, page, paragraph)
- Return structured `QueryResponse`

---

#### `backend/services/strict_mode.py` ⏳ NOT YET CREATED

**Planned for:** Step 3A.1 onwards

**Will do:**
- `validate_evidence(chunks, threshold=0.65)` — reject if top chunk score < threshold
- `calculate_confidence(...)` — 0.0–1.0 score from reranker score + consistency + domain trust
- `check_consistency(doc_claims, public_evidence)` — Verified / Contradiction / Insufficient
- Call Ollama with strict system prompt (evidence-only, no speculation)
- Assemble full structured output: answer + citation + public source + consistency + confidence

---

#### `backend/services/verifier.py` ⏳ NOT YET CREATED

**Planned for:** Step 3A.2

**Will do:**
- Domain-routing to public APIs:
  - `healthcare` → PubMed API
  - `research` → arXiv API, Semantic Scholar
  - `legal` → Government legal portals
  - `technical` → RFC databases
  - `compliance` → FDA, SEC sites
- Extract key claims from top chunks
- Query the relevant public API
- Return public evidence paragraphs + source URLs

---

### `backend/db/`

**Status:** ✅ Directory created (Step 1.1)

**Purpose:** Database client wrappers. One file per database. Handles connections, reads, and writes.
Services call these — never directly call the DB from routers.

---

#### `backend/db/__init__.py`

**Status:** ✅ Created (Step 1.1)
**Purpose:** Marks `db/` as a Python package.

---

#### `backend/db/qdrant_client.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.7

**Will do:**
- Connect to Qdrant at `QDRANT_URL` from `.env`
- Create/ensure collection exists (`documents`, cosine similarity, 1024 dims)
- `upsert_vectors(chunk_id, vector, metadata)` — store embedding + metadata payload
- `search_vectors(query_vector, top_k, filters)` — nearest-neighbor search

---

#### `backend/db/mongo_client.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.7

**Will do:**
- Connect to MongoDB at `MONGODB_URL` from `.env`
- `insert_chunk(chunk_text, metadata)` — store full text + metadata
- `get_chunks_by_ids(chunk_ids)` — fetch full text for merged retrieval results
- `get_documents()` — list all documents (for Document Manager)
- `delete_document(document_id)` — remove all chunks for a document

---

#### `backend/db/elastic_client.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.7

**Will do:**
- Connect to Elasticsearch at `ELASTICSEARCH_URL` from `.env`
- Create index with standard analyzer for BM25
- `index_chunk(chunk_id, chunk_text, document_name)` — index chunk for keyword search
- `bm25_search(query, top_k, filters)` — multi_match query → returns chunk IDs + BM25 scores

---

### `backend/models/`

**Status:** ✅ Directory created (Step 1.1)

**Purpose:** Pydantic data models used across the application for type safety and validation.

---

#### `backend/models/__init__.py`

**Status:** ✅ Created (Step 1.1)
**Purpose:** Marks `models/` as a Python package.

---

#### `backend/models/schemas.py` ⏳ NOT YET CREATED

**Planned for:** Step 1.4

**Will contain Pydantic models:**

| Model | Used for |
|---|---|
| `ChunkMetadata` | Metadata attached to every stored chunk |
| `DocumentInfo` | Info about an uploaded document |
| `UploadResponse` | Response from `POST /api/upload` |
| `QueryRequest` | Request body for `POST /api/query` |
| `CitationCard` | A single citation (doc name, page, chunk text, public source) |
| `StrictQueryResponse` | Full strict mode output structure |
| `LiberalQueryResponse` | Full liberal mode output structure |

---

### `backend/venv/`

**Status:** ✅ Created (Step 1.1)

**Purpose:** Python virtual environment. Contains all installed packages isolated from the system Python.
**Do not commit to git** — add `venv/` to `.gitignore`.

**Activate command (Windows):** `.\venv\Scripts\activate`

---

## `frontend/` — React Frontend

**Status:** 🔲 Directory structure created. App scaffolding in Phase 4.

**Purpose:** User-facing web application. Built with React + Tailwind CSS. Runs on **port 3000**.

---

### `frontend/src/components/`

**Status:** ✅ Directory created (Step 1.1)

**Purpose:** All React UI component files. One component per file.

**Components to be created (Phase 4):**

| File | Step | Purpose |
|---|---|---|
| `UploadZone.jsx` | 4.2 | Drag-and-drop file uploader with progress and domain selector |
| `ModeToggle.jsx` | 4.3 | Strict Mode / Liberal Mode toggle switch |
| `QueryInput.jsx` | 4.4 | Question input, domain filter, document filter, submit button |
| `StrictAnswerView.jsx` | 4.5 | Strict mode answer with expandable citation cards and confidence bar |
| `LiberalAnswerView.jsx` | 4.6 | Two-section liberal mode answer (document vs AI) |
| `DocumentManager.jsx` | 4.7 | Uploaded document list with delete and re-index actions |

---

## `uploads/`

**Status:** ✅ Created (Step 1.1)

**Purpose:** Raw uploaded files are stored here after `POST /api/upload`.
Files are renamed to `<document_id>.<ext>` (UUID-based) to avoid collisions.
**Do not commit to git** — add `uploads/` to `.gitignore`.

---

## Root-Level Files

---

### `.env`

**Status:** ✅ Created (Step 1.1)

**Purpose:** All environment variables in one place. Code reads from here — no hardcoded URLs or values.

**Variable groups:**

| Group | Variables |
|---|---|
| Database URLs | `MONGODB_URL`, `QDRANT_URL`, `ELASTICSEARCH_URL` |
| LLM Runtime | `OLLAMA_URL` |
| ML Models | `EMBEDDING_MODEL`, `RERANKER_MODEL`, `LLM_MODEL` |
| Pipeline Tuning | `CONFIDENCE_THRESHOLD`, `BM25_TOP_K`, `VECTOR_TOP_K`, `RERANKER_TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP` |
| Upload | `UPLOAD_DIR`, `MAX_FILE_SIZE_MB` |
| App | `APP_ENV`, `LOG_LEVEL` |

**Current values:** Local dev URLs (`localhost`). Docker Compose URLs are commented out for easy switch during Phase 5.

---

### `PROJECT_PLAN.md`

**Status:** ✅ Pre-existing reference document

**Purpose:** Master architecture and design document. Describes the full system — tech stack, all phases, folder structure, key design rules. **Do not modify during development** — this is the source of truth.

---

### `project_flow.md`

**Status:** ✅ Created before development began

**Purpose:** Translates `PROJECT_PLAN.md` into a concrete sequential build guide. Contains step-by-step actions, files to create, code snippets, and validation checklists for every step across all phases.

---

### `memory.md`

**Status:** ✅ Created (Step 1.1)

**Purpose:** Living project memory. Tracks what has been completed, what's next, decisions made, and key notes per step. Updated after every step.

---

### `structure.md`

**Status:** ✅ Created (Step 1.1) — This file

**Purpose:** Documents every folder and file in the project — what it is, why it exists, and what code it contains / will contain. Updated whenever files or folders are added or modified.

---

## Files To Be Created (Future Steps)

| File | Step | Phase |
|---|---|---|
| `backend/models/schemas.py` | 1.4 | Phase 1 |
| `backend/services/extractor.py` | 1.3 | Phase 1 |
| `backend/services/chunker.py` | 1.5 | Phase 1 |
| `backend/services/embedder.py` | 1.6 | Phase 1 |
| `backend/db/qdrant_client.py` | 1.7 | Phase 1 |
| `backend/db/mongo_client.py` | 1.7 | Phase 1 |
| `backend/db/elastic_client.py` | 1.7 | Phase 1 |
| `backend/services/retriever.py` | 2.2 | Phase 2 |
| `backend/services/reranker.py` | 2.5 | Phase 2 |
| `backend/services/liberal_mode.py` | 3B.1 | Phase 3B |
| `backend/services/strict_mode.py` | 3A.1 | Phase 3A |
| `backend/services/verifier.py` | 3A.2 | Phase 3A |
| `frontend/src/App.jsx` | 4.1 | Phase 4 |
| `frontend/src/components/UploadZone.jsx` | 4.2 | Phase 4 |
| `frontend/src/components/ModeToggle.jsx` | 4.3 | Phase 4 |
| `frontend/src/components/QueryInput.jsx` | 4.4 | Phase 4 |
| `frontend/src/components/StrictAnswerView.jsx` | 4.5 | Phase 4 |
| `frontend/src/components/LiberalAnswerView.jsx` | 4.6 | Phase 4 |
| `frontend/src/components/DocumentManager.jsx` | 4.7 | Phase 4 |
| `backend/Dockerfile` | 5.1 | Phase 5 |
| `frontend/Dockerfile` | 5.2 | Phase 5 |
| `docker-compose.yml` | 5.3 | Phase 5 |

---

*Last updated: Step 1.1 complete — 2026-07-13*

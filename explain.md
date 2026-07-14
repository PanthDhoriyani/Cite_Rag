# CiteRag — Phase 1 Completion Report
## What Was Built, File by File

> **Phase 1 Goal:** Accept uploaded files, extract text, chunk them, generate embeddings,
> and store everything across three databases (Qdrant · MongoDB · Elasticsearch).

---

## Quick Summary — Files Created / Modified

| File | Status | Step |
|------|--------|------|
| `backend/models/schemas.py` | ✅ NEW | 1.4 |
| `backend/services/extractor.py` | ✅ NEW | 1.3 |
| `backend/services/chunker.py` | ✅ NEW | 1.5 |
| `backend/services/embedder.py` | ✅ NEW | 1.6 |
| `backend/db/qdrant_client.py` | ✅ NEW | 1.7 |
| `backend/db/mongo_client.py` | ✅ NEW | 1.7 |
| `backend/db/elastic_client.py` | ✅ NEW | 1.7 |
| `backend/services/ingestion.py` | ✅ NEW | 1.8 |
| `backend/routers/upload.py` | ✅ REPLACED stub | 1.2 + 1.8 |
| `backend/routers/query.py` | ✅ UPGRADED stub | pre-Phase 2 |
| `backend/main.py` | ✔ Already complete | 1.1 |
| `backend/requirements.txt` | ✔ Already complete | 1.1 |
| `.env` | ✔ Already complete | 1.1 |

---

## Step-by-Step: What Was Done

### Step 1.1 — Project Scaffolding *(already done)*
The root folder structure, virtual environment, `requirements.txt`, `.env`, and `backend/main.py`
were already in place before Phase 1 completion work began.

- **`main.py`** sets up FastAPI with CORS middleware, a lifespan context manager (startup/shutdown
  logging), and registers the upload and query routers.
- **`.env`** contains all service URLs (MongoDB, Qdrant, Elasticsearch, Ollama) and tuneable
  pipeline parameters (chunk size, overlap, top-k values, confidence threshold).
- **`requirements.txt`** pins all 20+ dependencies including FastAPI, LangChain, sentence-transformers,
  PyMuPDF, qdrant-client, pymongo, elasticsearch, and loguru.

---

### Step 1.2 — File Upload Endpoint
**File:** `backend/routers/upload.py` *(replaced stub)*

**What was added:**

#### `POST /api/upload`
- Accepts `PDF`, `DOCX`, and `TXT` files via multipart form upload.
- **Extension whitelist validation** — rejects anything not in `{pdf, docx, txt}` with HTTP 422.
- **Size validation** — reads full file into memory, rejects files > 50 MB (configurable via
  `MAX_FILE_SIZE_MB` env var) with HTTP 422.
- **UUID-based file naming** — saves file as `{uuid}.{ext}` inside the `uploads/` directory
  so original filenames can't cause path collisions or injection.
- **Accepts a `domain` form field** — one of `legal | research | healthcare | technical |
  compliance | education | general` (defaults to `general`).
- **Creates a MongoDB document record** immediately (status = `"processing"`) so the client
  can track progress via `GET /api/documents`.
- **Triggers the ingestion pipeline via FastAPI `BackgroundTasks`** — returns `document_id`
  to the client immediately (HTTP 202) without blocking on the heavy processing.

#### `GET /api/documents`
- Returns all uploaded document records from MongoDB.
- Includes `status` field: `"processing"` → `"ready"` → `"failed"`.

#### `DELETE /api/documents/{document_id}`
- Queues deletion via `BackgroundTasks`.
- Removes the document from **all three stores**: Qdrant vectors, Elasticsearch index,
  MongoDB chunks + document record.
- Errors in any single store are logged as warnings so the others still get cleaned up.

---

### Step 1.3 — Text Extraction Service
**File:** `backend/services/extractor.py` *(new)*

**What was added:**

The public function `extract_text(file_path, file_type)` returns a list of page dicts:
```
[{"page_number": int, "text": str}, ...]
```
Page-level granularity is preserved here because `page_number` metadata **cannot be
reconstructed later** once text is merged.

#### PDF Extraction — PyMuPDF + Tesseract fallback
```
_extract_pdf(path)
  ├── _extract_with_pymupdf(path)    ← try first (fast, accurate for digital PDFs)
  └── _extract_with_tesseract(path)  ← fallback if total text < 100 chars (scanned PDF)
```
- **PyMuPDF (`fitz`)** — opens each page and calls `page.get_text("text")`.
  Returns one dict per PDF page with the raw text string.
- **Tesseract OCR fallback** — renders each page to a 300-DPI PNG using PyMuPDF's
  `get_pixmap()`, passes the image to `pytesseract.image_to_string()`.
  Activated automatically when digital extraction yields < 100 characters total.

#### DOCX Extraction
- Uses `python-docx`'s `Document` class.
- Iterates all paragraphs, filters blank ones, joins with `\n`.
- Treated as a single logical page (DOCX has no native page concept in python-docx).

#### TXT Extraction
- Plain `Path.read_text(encoding="utf-8", errors="replace")`.
- Treated as a single page.

---

### Step 1.4 — Metadata Models
**File:** `backend/models/schemas.py` *(new)*

**What was added:**

#### `Domain` (Enum)
Six document domains used for retrieval filtering and public verification routing in Phase 3A:
`legal | research | healthcare | technical | compliance | education | general`

#### `ChunkMetadata` (Pydantic BaseModel)
Every field the project plan requires, captured at ingestion time:
```
document_id       — UUID of the parent document
document_name     — original filename (preserved for citations)
chunk_id          — UUID auto-generated per chunk
chunk_index       — 0-based global position in the document
total_chunks      — total chunk count (backfilled after processing all pages)
page_number       — which PDF page the chunk came from
paragraph_number  — position of this chunk within its page
line_start        — first line of the chunk (relative to chunk)
line_end          — last line of the chunk
upload_timestamp  — UTC time of upload
domain            — Domain enum value
```

#### `Chunk` (Pydantic BaseModel)
Pairs a `chunk_text` string with its `ChunkMetadata`.

#### `DocumentInfo` (Pydantic BaseModel)
Top-level document record stored in MongoDB on upload.
Contains file-level metadata + `status` + `total_chunks`.

#### `UploadResponse`, `QueryRequest`, `QueryResponse`
API contract models — `UploadResponse` is returned by `POST /api/upload`; the query
models are wired in Phase 2/3.

---

### Step 1.5 — Semantic Chunking
**File:** `backend/services/chunker.py` *(new)*

**What was added:**

#### `chunk_pages(pages, document_id, document_name, domain, upload_timestamp)`
- Uses **LangChain `RecursiveCharacterTextSplitter`** from `langchain_text_splitters` package
  (correct import path for LangChain 0.2+).
- **Chunk size: 512** tokens · **Overlap: 128** tokens (both configurable via `.env`).
- **Separator priority:** `"\n\n"` → `"\n"` → `" "` → `""` — prefers paragraph and
  line breaks before splitting mid-word.

**Metadata preservation strategy:**
- Pages are chunked **one at a time** (not concatenated) so `page_number` stays accurate.
- `paragraph_number` = the chunk's position within its source page (1-indexed).
- `line_start` / `line_end` are computed from the chunk text's own line count.
- `chunk_index` is a **global running counter** across all pages.
- `total_chunks` is **backfilled** after all pages are processed.

---

### Step 1.6 — Embedding Generation
**File:** `backend/services/embedder.py` *(new)*

**What was added:**

#### Singleton model loading
```python
_model = None   # module-level cache

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    return _model
```
The model is loaded **once on first call** and reused for all subsequent requests.
This avoids the ~3–5 second model-load penalty on every ingestion.

#### `embed_texts(texts) → List[List[float]]`
- Batch-encodes a list of chunk texts.
- `normalize_embeddings=True` — BGE models are designed for cosine similarity;
  normalization ensures correct behaviour with Qdrant's COSINE distance metric.
- Returns a list of **1024-dimensional float vectors** (one per input text).

#### `embed_single(text) → List[float]`
- Convenience wrapper for embedding a single query string (used by Phase 2 retriever).

---

### Step 1.7 — Database Clients

#### `backend/db/qdrant_client.py` *(new)*

| Function | Purpose |
|---|---|
| `get_client()` | Returns a `QdrantClient` connected to `QDRANT_URL` |
| `ensure_collection()` | Creates the `"documents"` collection if not present (1024-dim, COSINE) |
| `upsert_vectors(chunk_ids, embeddings, payloads)` | Bulk-upserts `PointStruct` objects into Qdrant |
| `delete_by_document_id(document_id)` | Payload-filter delete — removes all points for a document |
| `search_vectors(query_vector, top_k, filter_dict)` | Nearest-neighbour semantic search (Phase 2 ready) |

Collection spec:
- **Size:** 1024 (matching `BAAI/bge-large-en-v1.5` output dimension)
- **Distance:** `COSINE` (works correctly with L2-normalized BGE embeddings)
- Each point's **payload** = full `ChunkMetadata` dict, enabling filtered search without
  a MongoDB round-trip.

---

#### `backend/db/mongo_client.py` *(new)*

| Collection | Stores |
|---|---|
| `citerag.chunks` | One document per chunk: `{chunk_id, chunk_text, metadata}` |
| `citerag.documents` | One document per upload: `{document_id, document_name, status, total_chunks, ...}` |

| Function | Purpose |
|---|---|
| `insert_chunks(chunks_data)` | Bulk insert into `chunks` collection |
| `insert_document(doc_data)` | Insert document record on upload |
| `update_document_status(id, status, total_chunks)` | Called at pipeline end (ready/failed) |
| `list_documents()` | Powers `GET /api/documents` |
| `get_document(id)` | Single document lookup |
| `get_chunks_by_document(id)` | All chunks for a document |
| `get_chunks_by_ids(ids)` | Hydrate Qdrant/ES results with full text (Phase 2) |
| `delete_document(id)` | Removes document + all its chunks |

---

#### `backend/db/elastic_client.py` *(new)*

Index `citerag_chunks` field mapping:

```
chunk_id         → keyword   (exact match for dedup in Phase 2)
document_id      → keyword   (filter by document)
document_name    → text      (searchable)
chunk_text       → text, english analyzer  (stemming + stop-word removal for BM25)
page_number      → integer
paragraph_number → integer
domain           → keyword   (domain filter)
chunk_index      → integer
```

| Function | Purpose |
|---|---|
| `ensure_index()` | Creates the index with mapping if not present |
| `index_chunks(chunks_data)` | Bulk-indexes via `elasticsearch.helpers.bulk()` |
| `delete_by_document_id(id)` | `delete_by_query` on `document_id` field |
| `bm25_search(query, top_k, ...)` | Multi-match BM25 search (Phase 2 retriever ready) |

---

### Step 1.8 — Storage Pipeline (Wire Everything Together)
**File:** `backend/services/ingestion.py` *(new)*

#### `run_ingestion(document_id, file_path, document_name, file_type, domain, upload_timestamp)`

The single orchestrator function that calls all services in sequence.
Called from `upload.py`'s `BackgroundTasks`. Failure at any step updates the document
status to `"failed"` in MongoDB.

**Pipeline sequence:**
```
1. ensure_collection()  +  ensure_index()     ← idempotent DB setup
2. extract_text()                              ← extractor.py
3. chunk_pages()                               ← chunker.py (512/128)
4. embed_texts()                               ← embedder.py (BGE 1024-dim)
5a. qdrant_client.upsert_vectors()             ← vectors + metadata payload
5b. mongo_client.insert_chunks()               ← full chunk text + metadata
    mongo_client.update_document_status()      ← status → "ready"
5c. elastic_client.index_chunks()              ← BM25 keyword index
```

**Error handling:**
- Extraction yields < 10 chars → status = `"failed"`, abort.
- Chunker produces 0 chunks → status = `"failed"`, abort.
- Any unhandled exception → full traceback logged, status = `"failed"`.
- Successful completion → status = `"ready"`, `total_chunks` persisted.

---

### Query Router — Phase 1 Stub Upgrade
**File:** `backend/routers/query.py` *(upgraded)*

The original 9-line stub was upgraded to:
- Import and wire `QueryRequest` / `QueryResponse` Pydantic models.
- Define `POST /api/query` with full request body validation (question, mode, filters).
- Return a descriptive stub response (HTTP 200) so the endpoint is testable in Phase 1.
- Log the incoming question and mode on every request.
- Full hybrid retrieval + LLM generation will be filled in during Phase 2 & 3.

---

## Data Flow Diagram

```
User uploads file
      │
      ▼
POST /api/upload
      │
      ├── Validate extension (whitelist: pdf, docx, txt)
      ├── Validate size (max 50 MB)
      ├── Save  uploads/{uuid}.{ext}
      ├── Insert document record → MongoDB  (status: "processing")
      └── BackgroundTasks.add_task(run_ingestion)   ← returns 202 immediately
                │
                ▼
         run_ingestion()
                │
                ├─ 1. ensure_collection() + ensure_index()
                │
                ├─ 2. extract_text()
                │       ├── PDF  → PyMuPDF  →  [fallback: Tesseract 300-DPI OCR]
                │       ├── DOCX → python-docx paragraphs
                │       └── TXT  → plain read
                │       returns: [{page_number: int, text: str}, ...]
                │
                ├─ 3. chunk_pages()
                │       RecursiveCharacterTextSplitter  (512 / 128 overlap)
                │       Chunked per-page to preserve page_number metadata
                │       total_chunks backfilled after all pages processed
                │       returns: [Chunk(chunk_text, ChunkMetadata), ...]
                │
                ├─ 4. embed_texts()
                │       BAAI/bge-large-en-v1.5  (singleton, loaded once)
                │       normalize_embeddings=True → cosine-similarity ready
                │       returns: [[float ×1024], ...]
                │
                ├─ 5a. qdrant_client.upsert_vectors()
                │         chunk_id as point ID  +  embedding  +  metadata payload
                │
                ├─ 5b. mongo_client.insert_chunks()
                │         {chunk_id, chunk_text, metadata}  ×  N chunks
                │       mongo_client.update_document_status() → "ready"
                │
                └─ 5c. elastic_client.index_chunks()
                          {chunk_id, chunk_text, metadata fields}  ×  N chunks
                          Indexed for BM25 retrieval in Phase 2
```

---

## Phase 1 Final Checklist

| Item | Status |
|---|---|
| Project scaffolding (folders, main.py, requirements, .env) | ✅ Done (pre-existing) |
| File upload API (`POST /api/upload`) | ✅ Done |
| Extension whitelist + size validation (422 on invalid) | ✅ Done |
| UUID file naming + `uploads/` directory auto-creation | ✅ Done |
| Domain field on upload | ✅ Done |
| List documents (`GET /api/documents`) | ✅ Done |
| Delete document (`DELETE /api/documents/{id}`) from all 3 stores | ✅ Done |
| Text extraction — PyMuPDF (digital PDF, page-by-page) | ✅ Done |
| Text extraction — Tesseract OCR fallback (scanned/image PDF) | ✅ Done |
| Text extraction — DOCX (python-docx) | ✅ Done |
| Text extraction — TXT (plain read) | ✅ Done |
| Page-level text boundaries preserved for metadata | ✅ Done |
| Pydantic models: `ChunkMetadata`, `Chunk`, `DocumentInfo` | ✅ Done |
| Pydantic models: `UploadResponse`, `QueryRequest`, `QueryResponse` | ✅ Done |
| `Domain` enum with 7 values | ✅ Done |
| Semantic chunking (`RecursiveCharacterTextSplitter` 512/128) | ✅ Done |
| All metadata fields captured per chunk | ✅ Done |
| BGE embeddings (`BAAI/bge-large-en-v1.5`, 1024-dim, normalized) | ✅ Done |
| Singleton model loading (no per-request reload) | ✅ Done |
| Qdrant client — collection creation (1024-dim COSINE) + upsert | ✅ Done |
| MongoDB client — chunks + document record CRUD | ✅ Done |
| Elasticsearch client — index creation + bulk index (english analyzer) | ✅ Done |
| Full ingestion pipeline orchestrator (`ingestion.py`) | ✅ Done |
| BackgroundTask trigger from upload endpoint | ✅ Done |
| Document status tracking (`processing` → `ready` / `failed`) | ✅ Done |
| All imports verified — no import errors | ✅ Verified |

---

## What Phase 2 Will Add

The three database client modules already include **read functions ready for Phase 2**:
- `qdrant_client.search_vectors()` — nearest-neighbour semantic retrieval
- `elastic_client.bm25_search()` — multi-match BM25 keyword retrieval
- `mongo_client.get_chunks_by_ids()` — hydrate results with full chunk text

Phase 2 will create:
- `backend/services/retriever.py` — BM25 + vector retrieval, result merging, deduplication
- `backend/services/reranker.py` — `BAAI/bge-reranker-large` cross-encoder reranking
- `backend/routers/query.py` — full query pipeline replacing the stub

---

*Generated at Phase 1 completion — 2026-07-14*
*Reference: project_flow.md §Phase 1*

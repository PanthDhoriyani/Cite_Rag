# CiteRag — Complete Project Guide
> Everything in one place: what the project is, how it's built, every file explained,
> the full build roadmap, and what has been completed so far — all in plain, easy language.

---

## 1. What is CiteRag?

CiteRag stands for **Citation-Aware RAG Platform**.

**RAG** = Retrieval-Augmented Generation. In simple words:
> Instead of asking an AI to answer from its own memory, we first **search our uploaded documents**, pick the most relevant pieces, and then let the AI answer **only using those pieces as evidence**.

This makes every answer **trustworthy and traceable** — you can always see exactly which page and paragraph the answer came from.

### Two Answer Modes

| Mode | What it does |
|---|---|
| **Strict Mode** | Answers ONLY from your document. Every sentence has a citation. If evidence is weak, it refuses to answer rather than guess. |
| **Liberal Mode** | Answers from your document first, then adds broader AI explanation. Clearly labels what came from the document vs what is AI knowledge. |

### The Full Journey of a Question
```
You upload a research paper / legal doc / medical report
           ↓
You ask: "What is the recommended treatment?"
           ↓
System searches the document (by keyword AND by meaning)
           ↓
Top matching paragraphs are found and re-scored for relevance
           ↓
AI reads those paragraphs and writes a cited answer
           ↓
You get: answer + exact page/paragraph source + confidence score
```

---

## 2. Project Folder Structure

```
CiteRag/
├── backend/                 ← Python FastAPI server (runs on port 8000)
│   ├── main.py              ← App entry point — starts everything
│   ├── requirements.txt     ← All Python packages needed
│   ├── .env                 ← All config values (URLs, model names, thresholds)
│   │
│   ├── routers/             ← API endpoints (what URLs the server listens to)
│   │   ├── upload.py        ← Handles file uploads + document management
│   │   └── query.py         ← Handles user questions
│   │
│   ├── services/            ← Core logic (the brain of the system)
│   │   ├── extractor.py     ← Reads text from PDF / DOCX / TXT files
│   │   ├── chunker.py       ← Splits text into small overlapping pieces
│   │   ├── embedder.py      ← Converts text into numbers (vectors)
│   │   ├── ingestion.py     ← Runs the full pipeline: extract → chunk → embed → store
│   │   ├── retriever.py     ← [Phase 2] Searches databases for relevant chunks
│   │   ├── reranker.py      ← [Phase 2] Re-scores results by relevance
│   │   ├── liberal_mode.py  ← [Phase 3B] Generates liberal mode answers
│   │   ├── strict_mode.py   ← [Phase 3A] Generates strict cited answers
│   │   └── verifier.py      ← [Phase 3A] Checks claims against public sources
│   │
│   ├── db/                  ← Database clients (talk to the 3 databases)
│   │   ├── qdrant_client.py    ← Talks to Qdrant (vector / semantic search)
│   │   ├── mongo_client.py     ← Talks to MongoDB (stores full text)
│   │   └── elastic_client.py  ← Talks to Elasticsearch (keyword search)
│   │
│   └── models/              ← Data shape definitions
│       └── schemas.py       ← All Pydantic models (data structures)
│
├── frontend/                ← React web app (runs on port 3000) [Phase 4]
│   └── src/
│       └── components/      ← UI building blocks
│           ├── UploadZone.jsx       ← Drag-and-drop file uploader
│           ├── ModeToggle.jsx       ← Switch between Strict / Liberal
│           ├── QueryInput.jsx       ← Question input box
│           ├── StrictAnswerView.jsx ← Shows cited answer with confidence
│           ├── LiberalAnswerView.jsx← Shows two-section answer
│           └── DocumentManager.jsx  ← Lists uploaded docs, delete button
│
├── uploads/                 ← Raw uploaded files stored here (not in git)
│
├── .env                     ← Config: DB URLs, model names, thresholds
├── explain.md               ← This file
├── about.md                 ← Technology reference guide
├── memory.md                ← Project progress tracker
├── structure.md             ← Original detailed file reference
└── project_flow.md          ← Original step-by-step build roadmap
```

---

## 3. Every File Explained

### `backend/main.py` — The Starting Point
This is where FastAPI starts. Think of it as the reception desk of the whole server.

**What it does:**
- Creates the web server
- Allows the React frontend (on port 3000) to talk to the backend (CORS)
- Logs when the server starts and stops
- Registers all the route files (`upload.py` and `query.py`)
- Provides the health check endpoint: `GET /api/health` → `{ "status": "ok" }`

---

### `backend/requirements.txt` — Package List
Lists every Python library the project needs. Run `pip install -r requirements.txt` to install them all.

| Group | Libraries |
|---|---|
| Web server | fastapi, uvicorn, python-multipart |
| Data validation | pydantic, pydantic-settings |
| PDF reading | PyMuPDF, pdfplumber, pytesseract, Pillow |
| Word docs | python-docx |
| Text splitting | langchain, langchain-community |
| AI embeddings | sentence-transformers |
| Vector database | qdrant-client |
| Document database | pymongo, motor |
| Search engine | elasticsearch |
| LLM calls | httpx |
| Utilities | python-dotenv, loguru, aiofiles |

---

### `.env` — All Configuration
One file to hold every setting. Nothing is hardcoded in the actual Python files.

```
MONGODB_URL=mongodb://localhost:27017         ← where MongoDB is running
QDRANT_URL=http://localhost:6333              ← where Qdrant is running
ELASTICSEARCH_URL=http://localhost:9200       ← where Elasticsearch is running
OLLAMA_URL=http://localhost:11434             ← where the local LLM is running

EMBEDDING_MODEL=BAAI/bge-large-en-v1.5       ← which model to use for embeddings
RERANKER_MODEL=BAAI/bge-reranker-large        ← which model to use for reranking
LLM_MODEL=llama3:8b                           ← which LLM to use for answers

CHUNK_SIZE=512                                ← how many characters per chunk
CHUNK_OVERLAP=128                             ← how many characters to overlap
CONFIDENCE_THRESHOLD=0.65                     ← minimum score to attempt an answer
MAX_FILE_SIZE_MB=50                           ← biggest file allowed to upload
```

---

### `backend/models/schemas.py` — Data Shapes ✅ Done (Phase 1)
Defines what every piece of data looks like using Pydantic. Like a contract — if data doesn't match the shape, it's rejected automatically.

**`Domain` (enum):** The 7 document types:
`legal · research · healthcare · technical · compliance · education · general`

**`ChunkMetadata`:** Every piece of info saved for each text chunk:
```
document_id       → which document this chunk came from
document_name     → the original filename (e.g. "ResearchPaper.pdf")
chunk_id          → unique ID for this chunk
chunk_index       → chunk number 0, 1, 2, 3... in the document
total_chunks      → how many chunks the whole document was split into
page_number       → which page this chunk is from
paragraph_number  → which paragraph on that page
line_start/end    → line range within the chunk
upload_timestamp  → when the file was uploaded
domain            → legal / research / healthcare / etc.
```

**`Chunk`:** The chunk text + its metadata together.

**`DocumentInfo`:** One record per uploaded file: name, path, domain, status, total chunks.

**`UploadResponse`:** What the API sends back when you upload a file.

**`QueryRequest`:** What the API expects when you ask a question: question text, mode, optional filters.

**`QueryResponse`:** What the API sends back: answer, citations, confidence score.

---

### `backend/routers/upload.py` — File Upload API ✅ Done (Phase 1)
Handles everything to do with uploading and managing documents.

#### `POST /api/upload` — Upload a file
1. Check the file extension — only `pdf`, `docx`, `txt` allowed (HTTP 422 if wrong)
2. Check the file size — max 50 MB (HTTP 422 if too big)
3. Save the file as `uploads/{random-uuid}.{ext}` — UUID prevents name collisions
4. Accept a `domain` field in the form (which type of document is this?)
5. Create a record in MongoDB immediately with `status: "processing"`
6. Start the ingestion pipeline **in the background** — returns the `document_id` to you right away without waiting
7. Returns: `{ document_id, document_name, status: "processing", message }`

#### `GET /api/documents` — List all documents
Returns every uploaded document with its current status (`processing` / `ready` / `failed`).

#### `DELETE /api/documents/{id}` — Delete a document
Removes the document from all 3 databases (Qdrant, MongoDB, Elasticsearch) in the background.

---

### `backend/routers/query.py` — Question Answering API ✅ Phase 1 stub, full in Phase 2+
Handles user questions.

#### `POST /api/query` — Ask a question
Request body:
```json
{
  "question": "What is the recommended dosage?",
  "mode": "strict",
  "document_ids": ["uuid1"],   // optional: search only these documents
  "domain": "healthcare"       // optional: filter by domain
}
```
- **Phase 1:** Returns a stub response (endpoint works but pipeline not wired yet)
- **Phase 2:** Will search Elasticsearch + Qdrant, merge results, rerank
- **Phase 3:** Will generate an AI answer with citations

---

### `backend/services/extractor.py` — Text Extraction ✅ Done (Phase 1)
Reads text out of uploaded files. Returns a list of pages, each with a page number and its text.

```
extract_text("file.pdf", "pdf")
  → [{"page_number": 1, "text": "..."}, {"page_number": 2, "text": "..."}, ...]
```

**For PDFs:**
- First tries **PyMuPDF** — very fast, works on normal PDFs
- If the total extracted text is less than 100 characters → the PDF is probably scanned (just images)
- Falls back to **Tesseract OCR** — renders each page as a 300 DPI image and reads the text from the image

**For DOCX:**
- Uses **python-docx** — reads all paragraphs and joins them
- Treated as one page (Word files don't have strict page boundaries in code)

**For TXT:**
- Just reads the file directly as UTF-8 text

> **Why preserve page numbers?** Because once we merge all the text together, we can never figure out which page something was on. Page numbers are captured here and saved forever as metadata.

---

### `backend/services/chunker.py` — Text Splitting ✅ Done (Phase 1)
Splits the extracted text into small overlapping pieces called **chunks**.

**Why chunk at all?** AI embedding models have a size limit. A 100-page document can't be fed in one go. We split it into ~512-character pieces so each one can be searched and embedded individually.

**How it splits:**
- Uses LangChain's `RecursiveCharacterTextSplitter`
- Chunk size: **512 characters**
- Overlap: **128 characters** (so context isn't lost at the boundary between chunks)
- Prefers to split at `\n\n` (paragraph) → `\n` (line) → space → character (as last resort)

```
Full page text
    ↓ split
[Chunk 1: chars 0–512]
[Chunk 2: chars 384–896]   ← overlaps with chunk 1 by 128 chars
[Chunk 3: chars 768–1280]  ← overlaps with chunk 2 by 128 chars
...
```

**Each chunk gets tagged with:** page number, paragraph number within the page, line range, document ID, chunk index, total chunks.

---

### `backend/services/embedder.py` — Embedding Generation ✅ Done (Phase 1)
Converts text into numbers (vectors) that represent meaning.

**Model used:** `BAAI/bge-large-en-v1.5`
- Produces a vector of **1024 numbers** for any piece of text
- Two texts with similar meanings → their vectors are close together in space
- Two texts with different topics → their vectors are far apart
- Loaded **once** when first needed, then reused forever (no reload per request)

```python
embed_texts(["the sky is blue", "azure color of the sky"])
# Returns two vectors that are very close together

embed_texts(["the sky is blue", "tax regulations in 2024"])
# Returns two vectors that are far apart
```

**Why normalize?** BGE model works best with normalized vectors (cosine similarity). Normalization makes the math accurate for Qdrant's search.

---

### `backend/services/ingestion.py` — The Full Pipeline ✅ Done (Phase 1)
The orchestrator that calls all the other services in the right order.

Called automatically in the background after a file is uploaded.

**Step-by-step what happens:**
```
1. Make sure Qdrant collection exists and Elasticsearch index exists
2. Extract text from the file (page by page)
3. Split text into chunks (512/128 overlap, per page)
4. Convert all chunks to 1024-dim embedding vectors
5a. Store in Qdrant: [chunk_id, vector, metadata]
5b. Store in MongoDB: [chunk_id, full_text, metadata] → update status to "ready"
5c. Store in Elasticsearch: [chunk_id, text] → BM25 indexed
```

If anything fails at any step → document status is set to `"failed"` and the error is logged.

---

### `backend/db/qdrant_client.py` — Qdrant Connection ✅ Done (Phase 1)
Handles all communication with the Qdrant vector database.

**What Qdrant stores:** Each chunk's embedding vector (1024 numbers) + metadata as payload.

**Collection settings:**
- Name: `documents`
- Dimensions: 1024 (matches the BGE model output)
- Distance: COSINE (best for normalized vectors)

**What the functions do:**
| Function | Does |
|---|---|
| `ensure_collection()` | Creates the collection if it doesn't exist yet |
| `upsert_vectors()` | Saves embeddings + metadata for all chunks |
| `search_vectors()` | Finds the N most similar chunks to a query vector |
| `delete_by_document_id()` | Removes all vectors for a deleted document |

---

### `backend/db/mongo_client.py` — MongoDB Connection ✅ Done (Phase 1)
Handles all communication with MongoDB.

**Database:** `citerag`
**Collections:**
- `chunks` — one record per text chunk (full text + all metadata)
- `documents` — one record per uploaded file (name, status, chunk count)

**Why MongoDB for this?** It stores the complete chunk text. Qdrant and Elasticsearch store small representations for searching, but MongoDB holds the full content so we can retrieve the actual text when building an answer.

**Status tracking:** When you upload → `"processing"`. When ingestion finishes → `"ready"`. If it fails → `"failed"`.

---

### `backend/db/elastic_client.py` — Elasticsearch Connection ✅ Done (Phase 1)
Handles all communication with Elasticsearch.

**Index:** `citerag_chunks`

**What Elasticsearch stores:** Each chunk's text in a way that supports fast keyword search (BM25 algorithm).

**English analyzer:** Automatically strips stop words ("the", "a", "is") and stems words ("running" → "run") so keyword matching is smarter.

**What the functions do:**
| Function | Does |
|---|---|
| `ensure_index()` | Creates the index with field mapping if needed |
| `index_chunks()` | Saves chunks in bulk for keyword searching |
| `bm25_search()` | Runs a keyword search, returns top N matching chunks |
| `delete_by_document_id()` | Removes all chunks for a deleted document |

---

### Future Services (Not Built Yet)

| File | Phase | What it will do |
|---|---|---|
| `retriever.py` | Phase 2 | BM25 search + vector search + merge + dedup |
| `reranker.py` | Phase 2 | Re-score top ~40 results → pick top 10 |
| `liberal_mode.py` | Phase 3B | Generate doc-first answer + AI explanation section |
| `strict_mode.py` | Phase 3A | Validate evidence threshold, confidence score, strict answer |
| `verifier.py` | Phase 3A | Call PubMed / arXiv / legal APIs to verify claims |

---

## 4. Build Roadmap — All 6 Phases

### Phase 1 — Document Ingestion Pipeline ✅ COMPLETE
**Goal:** Accept files → extract text → chunk → embed → store in 3 databases

| Step | What was built |
|---|---|
| 1.1 | Project structure, main.py, .env, requirements.txt |
| 1.2 | Upload API: POST /api/upload, GET/DELETE /api/documents |
| 1.3 | Text extraction: PyMuPDF + Tesseract + DOCX + TXT |
| 1.4 | Pydantic models: ChunkMetadata, DocumentInfo, etc. |
| 1.5 | Chunking: RecursiveCharacterTextSplitter 512/128 |
| 1.6 | Embeddings: BAAI/bge-large-en-v1.5, 1024-dim singleton |
| 1.7 | DB clients: Qdrant, MongoDB, Elasticsearch |
| 1.8 | Ingestion pipeline: wire all steps together |

---

### Phase 2 — Hybrid Retrieval & Reranking ⏳ Next
**Goal:** Given a question, find the most relevant chunks from all 3 stores

**Steps:**
- **2.1** Build the full `POST /api/query` endpoint (replaces stub)
- **2.2** BM25 keyword retrieval from Elasticsearch (top 20 chunks)
- **2.3** Semantic vector retrieval from Qdrant (top 20 chunks by meaning)
- **2.4** Merge both result lists, remove duplicates (25–40 unique chunks)
- **2.5** Re-rank using `BAAI/bge-reranker-large` cross-encoder → pick top 10

**Why use both keyword AND semantic search?**
- Keyword search is great for exact terms (drug names, law codes, specific numbers)
- Semantic search is great for meaning (finds "heart treatment" when you type "cardiac therapy")
- Together they catch more relevant chunks than either alone

**Why rerank?**
- The first round of searching (bi-encoder) is fast but approximate
- The reranker (cross-encoder) reads question + chunk together and gives a precise relevance score
- It's slower but much more accurate — used on the ~40 merged results, not on everything

---

### Phase 3B — Liberal Analysis Mode ⏳ After Phase 2
**Goal:** Generate answers that are helpful and educational

**Steps:**
- **3B.1** Build `liberal_mode.py` service
- **3B.2** Connect to Ollama (local LLM — llama3:8b)
- **3B.3** Parse output into two clear sections:
  ```
  DOCUMENT-BASED ANSWER:
  [Answer from the uploaded document with soft citations]
  Source: ResearchPaper.pdf, Page 4, Paragraph 2

  ---

  ADDITIONAL EXPLANATION:
  [Broader context, examples, and analogies added by AI]
  ```
- **3B.4** Wire to `POST /api/query` for `mode: "liberal"`

**Why build this before Strict Mode?** Liberal mode doesn't need public API calls (PubMed, arXiv), so it's simpler to build and validates the full RAG pipeline end-to-end first.

---

### Phase 3A — Strict Analysis Mode ⏳ After Phase 3B
**Goal:** Zero-hallucination, fully cited, publicly verified answers

**Steps:**
- **3A.1** Evidence threshold check — if top chunk score < 0.65 → refuse to answer
- **3A.2** Call public APIs to verify claims:
  - Healthcare documents → PubMed API
  - Research papers → arXiv API / Semantic Scholar
  - Legal documents → Government legal portals
  - Technical documents → RFC databases
  - Compliance → FDA, SEC sites
- **3A.3** Consistency check: does the document claim match the public source?
  - `Verified` / `Contradiction detected` / `Insufficient public evidence`
- **3A.4** Confidence score (0.0 to 1.0):
  - Below 0.5 → reject: "Low confidence — answer not generated"
  - 0.5–0.75 → answer with warning banner
  - Above 0.75 → full answer with all citations
- **3A.5** Strict LLM prompt: answer ONLY from the provided evidence, never speculate
- **3A.6** Assemble full output: answer + document citation + public source + consistency + confidence

---

### Phase 4 — Frontend UI ⏳
**Goal:** A React web app for uploading documents and asking questions

**Components to build:**
| Component | What it shows |
|---|---|
| `UploadZone.jsx` | Drag-and-drop uploader, progress bar, domain dropdown |
| `ModeToggle.jsx` | Toggle switch: Strict Mode ↔ Liberal Mode |
| `QueryInput.jsx` | Question text box, document filter, submit button |
| `StrictAnswerView.jsx` | Answer + expandable citation cards + confidence progress bar |
| `LiberalAnswerView.jsx` | Two-panel view: "From your document" + "AI explanation" |
| `DocumentManager.jsx` | List of uploaded docs with delete button |

---

### Phase 5 — Docker Deployment ⏳
**Goal:** One command to start the entire stack

```bash
docker-compose up
```

Starts all 6 services:

| Service | What it runs | Port |
|---|---|---|
| `backend` | FastAPI Python server | 8000 |
| `frontend` | React app via Nginx | 3000 |
| `qdrant` | Qdrant vector database | 6333 |
| `mongodb` | MongoDB document database | 27017 |
| `elasticsearch` | Elasticsearch search engine | 9200 |
| `ollama` | Local LLM runtime | 11434 |

---

### Phase 6 — Testing & Tuning ⏳
**Goal:** Validate and fine-tune the whole system

- Upload test documents across different domains (PDF, DOCX)
- Run queries in both modes
- Tune chunk size (try 256/64 and 768/192, compare retrieval quality)
- Tune confidence threshold (try 0.5 and 0.75)
- Test public API verification per domain
- Full frontend UX walkthrough

---

## 5. How the Three Databases Work Together

Every chunk is stored in **all three databases simultaneously** during ingestion:

```
One chunk → stored in 3 places at once:

┌─────────────────┬──────────────────────────────────┬────────────────────────┐
│    Database     │        What it holds              │    Used for            │
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│    Qdrant       │  1024-number vector + metadata    │  Semantic (meaning)    │
│                 │  "what the chunk means"           │  search                │
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│    MongoDB      │  Full chunk text + all metadata   │  Storing & retrieving  │
│                 │  "the actual words"               │  full content          │
├─────────────────┼──────────────────────────────────┼────────────────────────┤
│  Elasticsearch  │  Text indexed for keywords        │  BM25 keyword          │
│                 │  "which words are in the chunk"   │  search                │
└─────────────────┴──────────────────────────────────┴────────────────────────┘
```

When you ask a question in Phase 2:
1. Elasticsearch finds chunks that **contain similar words** to your question (keyword match)
2. Qdrant finds chunks that **mean something similar** to your question (semantic match)
3. Both results are merged and duplicates removed
4. MongoDB supplies the full text for each result
5. The reranker scores each one and picks the best 10

---

## 6. Key Design Rules (Always Enforced)

| Rule | Why |
|---|---|
| **No hallucination** | Strict Mode refuses to answer if evidence score < 0.65 |
| **Every claim must have a citation** | Strict Mode: no sentence without a chunk source |
| **Always rerank** | Never skip the reranker — it's the quality gate before the LLM |
| **Label everything in Liberal Mode** | Never silently mix document content and AI content |
| **Low confidence = rejection** | A bad answer is worse than no answer |
| **Metadata is captured at ingestion** | Page/paragraph numbers CANNOT be reconstructed later |
| **Always chunk with overlap** | Lost context at boundaries = bad retrieval |
| **Route to the right public API** | PubMed is for healthcare, not for legal documents |
| **All config in .env** | Never hardcode URLs, model names, or thresholds |

---

## 7. Complete Current Status

### Files Built (Phase 1 Complete)

| File | Status | What it does |
|---|---|---|
| `backend/main.py` | ✅ Done | FastAPI app, CORS, health check |
| `backend/requirements.txt` | ✅ Done | All dependencies listed |
| `.env` | ✅ Done | All config values |
| `backend/models/schemas.py` | ✅ Done | All Pydantic data models |
| `backend/services/extractor.py` | ✅ Done | PDF/DOCX/TXT text extraction |
| `backend/services/chunker.py` | ✅ Done | 512/128 overlap text splitting |
| `backend/services/embedder.py` | ✅ Done | BGE 1024-dim embeddings |
| `backend/services/ingestion.py` | ✅ Done | Full pipeline orchestrator |
| `backend/db/qdrant_client.py` | ✅ Done | Qdrant CRUD + semantic search |
| `backend/db/mongo_client.py` | ✅ Done | MongoDB CRUD for chunks + docs |
| `backend/db/elastic_client.py` | ✅ Done | Elasticsearch BM25 indexing |
| `backend/routers/upload.py` | ✅ Done | Upload + list + delete API |
| `backend/routers/query.py` | ✅ Stub | Query endpoint (Phase 2 will complete) |

### Files To Be Created

| File | Phase | What it will do |
|---|---|---|
| `backend/services/retriever.py` | Phase 2 | BM25 + vector search + merge |
| `backend/services/reranker.py` | Phase 2 | Cross-encoder reranking |
| `backend/services/liberal_mode.py` | Phase 3B | Liberal answer generation |
| `backend/services/strict_mode.py` | Phase 3A | Strict cited answer + confidence |
| `backend/services/verifier.py` | Phase 3A | Public source verification |
| `frontend/src/App.jsx` | Phase 4 | React app root |
| `frontend/src/components/UploadZone.jsx` | Phase 4 | File upload UI |
| `frontend/src/components/ModeToggle.jsx` | Phase 4 | Strict/Liberal toggle |
| `frontend/src/components/QueryInput.jsx` | Phase 4 | Question input UI |
| `frontend/src/components/StrictAnswerView.jsx` | Phase 4 | Cited answer view |
| `frontend/src/components/LiberalAnswerView.jsx` | Phase 4 | Two-section answer view |
| `frontend/src/components/DocumentManager.jsx` | Phase 4 | Document list + delete |
| `backend/Dockerfile` | Phase 5 | Container for backend |
| `frontend/Dockerfile` | Phase 5 | Container for frontend |
| `docker-compose.yml` | Phase 5 | Starts all 6 services together |

---

*Last updated: Phase 1 complete — 2026-07-14*
*Combines: explain.md + project_flow.md + structure.md*

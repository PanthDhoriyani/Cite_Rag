# 📖 CiteRag — Comprehensive Project Architecture & File Reference

This document provides a complete technical explanation of **CiteRag**: why each file and folder exists, what role it plays, when and where it is executed, and how data flows through the system end-to-end.

---

## 📐 System Architecture Overview

CiteRag is a **Citation-Aware Hybrid Retrieval-Augmented Generation (RAG)** platform designed to answer user questions using uploaded custom documents with zero hallucination guarantee in Strict mode.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER (Static Web)                     │
│  frontend/index.html — Vanilla Single Page Application (HTML/CSS/JS)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │  HTTP / REST API Calls
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        BACKEND LAYER (FastAPI API)                     │
│  backend/main.py ──▶ Router dispatch (upload.py & query.py)            │
└───────┬────────────────────────────────────────────────────────┬───────┘
        │ (Upload Action)                                         │ (Query Action)
        ▼                                                         ▼
┌───────────────────────────────┐               ┌────────────────────────────────┐
│ INGESTION PIPELINE            │               │ RETRIEVAL & GENERATION PIPELINE│
│ backend/pipeline.py           │               │ backend/retrieval.py           │
│ 1. Load: PyMuPDF / OCR        │               │ 1. Vector Search (Qdrant)      │
│ 2. Split: Recursive Splitter  │               │ 2. Keyword Search (MongoDB)    │
│ 3. Embed: BAAI/bge-large-en   │               │ 3. Merge: Ensemble (RRF)       │
│ 4. Store: Qdrant + MongoDB    │               │ 4. Rerank: Cross-Encoder       │
└──────────────┬────────────────┘               └───────────────┬────────────────┘
               │                                                │
               ▼                                                ▼
┌───────────────────────────────┐               ┌────────────────────────────────┐
│ CLOUD STORAGE BACKENDS        │               │ LLM GENERATION & VERIFICATION  │
│ 1. Qdrant Cloud (Vectors)     │               │ backend/generation.py          │
│ 2. MongoDB Atlas (Chunks & DB)│               │  - Liberal Mode LCEL Chain     │
└───────────────────────────────┘               │  - Strict Mode LCEL Chain      │
                                                │ backend/verifier.py            │
                                                │  - PubMed & arXiv Claims API   │
                                                └────────────────────────────────┘
```

---

## 🗂️ Complete Directory & File Structure Breakdown

```
CiteRag/
├── backend/
│   ├── db/
│   │   └── mongo_client.py     # MongoDB database client & text index operations
│   ├── routers/
│   │   ├── upload.py           # Upload, list, delete, rename & highlight endpoints
│   │   └── query.py            # RAG query processing route
│   ├── config.py               # Central environment variables & setup singleton
│   ├── main.py                 # FastAPI application entrypoint & middleware setup
│   ├── schemas.py              # Pydantic data validation contracts & models
│   ├── pipeline.py             # Document loading, OCR, chunking & vector storage
│   ├── retrieval.py            # Qdrant + MongoDB hybrid search & cross-encoder reranker
│   ├── generation.py           # Groq LLM answer generation (Liberal & Strict chains)
│   ├── verifier.py             # External API verification (PubMed & arXiv)
│   ├── Dockerfile              # Container definition for Railway deployment
│   ├── .dockerignore            # Excludes unnecessary local files from Docker image
│   ├── railway.json            # Deployment configuration for Railway
│   └── requirements.txt        # Backend Python dependency specification
├── frontend/
│   └── index.html              # Modern dark-mode SPA (HTML5 + CSS3 + Vanilla JS)
├── .env                        # Private environment keys (NOT committed to git)
├── .env.example                # Blueprint for environment variables
├── .gitignore                  # Specifies untracked files for Git
├── README.md                   # Public project overview & instructions
├── PROJECT_PLAN.md             # High-level architecture & completed technical phases
├── DEPLOYMENT.md               # Detailed step-by-step production deployment guide
└── explain.md                  # Detailed architectural component explanation (this file)
```

---

## 📄 File-by-File Technical Deep Dive

### 1. Root Configuration & Documentation Files

#### `frontend/index.html`
* **Role:** Complete user interface (Single Page Application).
* **Why it's used:** Serves as the entire client frontend UI without requiring complex build tools, Webpack, Node.js, or frontend frameworks.
* **When executed:** Runs inside the user's web browser whenever they open the web application.
* **Key Features:**
  * Document Drag-and-Drop upload panel with domain selector.
  * Real-time polling for document ingestion status (`processing` → `ready`).
  * Scoped document selection (checkbox filters).
  * Answer mode switcher (Liberal vs. Strict Mode).
  * Rendered markdown response container with interactive citation tags.
  * Inline PDF Highlight overlay popup container.
  * Backend settings modal storing the FastAPI URL in `localStorage`.

#### `backend/config.py`
* **Role:** Central configuration & environment variable loader.
* **Why it's used:** Ensures `os.getenv()` is called only once in the entire codebase. Prevents secret leakage, missing variable bugs, and ensures all files import consistent settings.
* **When executed:** Evaluated immediately when the Python process imports any backend file.
* **Key Variables Handled:** `MONGODB_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROQ_API_KEY`, `EMBEDDING_MODEL`, `RERANKER_MODEL`, `LLM_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CONFIDENCE_THRESHOLD`, `LANGCHAIN_API_KEY`.

#### `backend/main.py`
* **Role:** FastAPI application factory and entry point.
* **Why it's used:** Initializes FastAPI, attaches Cross-Origin Resource Sharing (CORS) middleware, includes all backend API routers, and defines the system health check endpoint.
* **When executed:** Runs on server launch when Uvicorn starts (`python -m uvicorn main:app`).
* **Key Components:**
  * `load_dotenv()` invocation at line 24 (crucial for LangSmith tracing).
  * `CORSMiddleware`: Allows frontend calls from any domain.
  * Router Inclusion: Mounts `/api/upload`, `/api/documents`, and `/api/query`.
  * `GET /api/health`: Light health check endpoint for deployment monitoring.

#### `backend/schemas.py`
* **Role:** Pydantic Data Contract Definitions.
* **Why it's used:** Enforces strict data types for incoming HTTP requests and outgoing HTTP responses. FastAPI uses these schemas for automatic JSON serialization, deserialization, and OpenAPI documentation validation.
* **Key Models:**
  * `Domain`: Enum of support categories (`legal`, `research`, `healthcare`, etc.).
  * `UploadResponse`: Response returned upon successful document upload.
  * `QueryRequest`: Contract for user queries (includes question text, selected mode, scope filters).
  * `Citation`: Struct describing a source chunk (document name, page number, chunk text, chunk ID).
  * `QueryResponse`: Final structure sent back to client (answer text, array of citations, confidence score).

---

### 2. Database & Data Storage Layer

#### `backend/db/mongo_client.py`
* **Role:** MongoDB Atlas connection manager and document/chunk CRUD operations.
* **Why it's used:** MongoDB is used for tracking document statuses and storing full text chunk content alongside full-text keyword search index definitions (`$text` index).
* **When executed:** Called during file upload, pipeline ingestion background tasks, retrieval keyword search, document deletion, and document renaming.
* **Key Functions:**
  * `save_document()` / `update_status()`: Tracks document lifecycle state (`processing` -> `ready` / `failed`).
  * `save_chunks()` / `get_chunks()`: Inserts and retrieves chunk text for citations.
  * Full-text Index Creation: Initializes `chunks.create_index([("chunk_text", "text")])` on startup.

---

### 3. Ingestion & Retrieval Layer (LangChain & Vector Core)

#### `backend/pipeline.py`
* **Role:** Document ingestion, text splitting, vector embedding, and storage pipeline.
* **Why it's used:** Converts raw uploaded files (PDF, DOCX, TXT) into searchable structured data blocks.
* **When executed:** Triggered as a FastAPI `BackgroundTask` right after a user uploads a document.
* **Step-by-Step Internal Workflow:**
  1. `load()`: Uses `PyMuPDFLoader` (PDF), `Docx2txtLoader` (DOCX), or `TextLoader` (TXT).
     * *Scanned PDF Detection:* If total extracted characters < 100, calls `_ocr_load()` using **Tesseract OCR** (`pytesseract`) to extract text from images.
  2. `split()`: Uses `RecursiveCharacterTextSplitter` (512 char chunks, 128 overlap). Injects rich metadata into every chunk (`chunk_id`, `document_id`, `document_name`, `domain`, `page_number`).
  3. `store()`: Embeds chunks using `HuggingFaceEmbeddings` (`BAAI/bge-large-en-v1.5`), stores dense vectors in **Qdrant Cloud**, and stores text records in **MongoDB Atlas**.
  4. Status update: Marks MongoDB document status as `"ready"`.

#### `backend/retrieval.py`
* **Role:** Hybrid Semantic-Keyword Retrieval & Cross-Encoder Reranking Engine.
* **Why it's used:** Standard vector search misses exact keyword matches (e.g. part numbers, names), while standard keyword search misses semantic context. `retrieval.py` merges both approaches for maximum accuracy.
* **When executed:** Runs when a user submits a query to `/api/query`.
* **Step-by-Step Internal Workflow:**
  1. **Semantic Retriever (`qdrant_retriever`):** Searches Qdrant Cloud using vector similarity to retrieve Top 20 chunks based on meaning.
  2. **Keyword Retriever (`MongoDBTextRetriever`):** Queries MongoDB's `$text` index to retrieve Top 20 chunks based on exact word matches.
  3. **Hybrid Merger (`EnsembleRetriever`):** Merges semantic + keyword results (~40 total chunks) using **Reciprocal Rank Fusion (RRF)** with equal 50/50 weighting.
  4. **Cross-Encoder Reranker (`CrossEncoderReranker`):** Uses `BAAI/bge-reranker-large` to read `(Question, Chunk)` pairs simultaneously, assigning precision relevance scores and returning the **Top 10** chunks.

---

### 4. Generation & Verification Layer

#### `backend/generation.py`
* **Role:** LLM Prompting, LCEL Chains, and Answer Generation.
* **Why it's used:** Formats retrieved evidence chunks into structured context prompts and sends them to Groq's high-speed cloud LLM (`llama-3.1-8b-instant`).
* **When executed:** Runs after `retrieval.py` completes retrieving chunks.
* **Modes Supported:**
  * **Liberal Mode (`generate_liberal_answer`):**
    * Instructs LLM to write a `DOCUMENT-BASED ANSWER` first, followed by `ADDITIONAL EXPLANATION` based on AI general knowledge.
  * **Strict Mode (`generate_strict_answer`):**
    * Converts raw reranker logit score to a 0.0–1.0 probability using `_sigmoid()`.
    * If top chunk score < `CONFIDENCE_THRESHOLD` (0.30), immediately refuses to answer (`"Insufficient evidence in the uploaded documents."`).
    * Computes confidence score (average of top 3 chunk scores).
    * Enforces strict evidence-only answering with mandatory inline source citations.
    * Calls `verifier.py` to append external verification sources if applicable.

#### `backend/verifier.py`
* **Role:** External Scientific & Medical Claim Verification.
* **Why it's used:** Provides real-world cross-checks for strict research or healthcare queries against official public databases.
* **When executed:** Called by `generation.py` during Strict Mode generation.
* **Routing Logic:**
  * `domain == "healthcare"` ──▶ Calls **PubMed API** (`eutils.ncbi.nlm.nih.gov`) to find matching medical paper IDs.
  * `domain == "research"` ──▶ Calls **arXiv API** (`export.arxiv.org`) to locate preprints matching key terms.

---

### 5. API Routing Layer

#### `backend/routers/upload.py`
* **Role:** Document Management API HTTP Router.
* **Endpoints:**
  * `POST /api/upload`: Validates file size/extension, saves to `uploads/`, records MongoDB document entry, and launches background ingestion task.
  * `GET /api/documents`: Returns list of all uploaded documents with current status.
  * `DELETE /api/documents/{id}`: Deletes document & chunks from Qdrant and MongoDB.
  * `PATCH /api/documents/{id}/rename`: Renames document in both MongoDB and Qdrant payloads.
  * `GET /api/chunks/{chunk_id}/highlight`: Fetches source PDF from disk, locates chunk text on the specified page using PyMuPDF, applies a bright yellow highlight annotation, and returns a 2x zoom base64 PNG image.

#### `backend/routers/query.py`
* **Role:** RAG Query Processing Router.
* **Endpoints:**
  * `POST /api/query`: Receives question + parameters, calls `retrieval.py` to get top chunks, builds `Citation` objects, passes docs to `generation.py`, and returns the `QueryResponse`.

---

### 6. Deployment & Build Configuration Files

#### `backend/Dockerfile`
* **Role:** Container creation script for production deployment.
* **Key Instructions:**
  * Base Image: `python:3.12-slim`
  * Installs system packages: `tesseract-ocr` (OCR support), `libgl1` (PyMuPDF headless support), `curl` (health check).
  * Installs requirements from `requirements.txt`.
  * Pre-creates `uploads/` directory.
  * Healthcheck definition: `curl -f http://localhost:8000/api/health`.
  * Entry command: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`.

#### `backend/railway.json`
* **Role:** Railway Cloud Platform build descriptor.
* **Key Configuration:** Directs Railway to build using `Dockerfile` and configures healthcheck paths and automatic restart policies.

---

## 🔄 End-to-End Execution Lifecycles

### Transaction Lifecycle A: Document Upload & Ingestion

```
User selects PDF file in frontend/index.html
  │
  ├─▶ POST /api/upload (routers/upload.py)
  │     ├─▶ Check extension & file size (<50MB)
  │     ├─▶ Save raw file to uploads/{uuid}.pdf
  │     ├─▶ Save document record in MongoDB (status="processing")
  │     └─▶ Trigger BackgroundTask: pipeline.run()
  │
  └─▶ [Background Execution in backend/pipeline.py]
        ├─▶ load(): PyMuPDFLoader extracts text + page metadata
        │     └─▶ (Fallback if <100 chars): _ocr_load() via Tesseract OCR
        ├─▶ split(): RecursiveCharacterTextSplitter splits into 512-char chunks
        ├─▶ store():
        │     ├─▶ HuggingFaceEmbeddings computes 1024-dim vectors
        │     ├─▶ QdrantVectorStore uploads vectors to Qdrant Cloud
        │     └─▶ mongo.save_chunks() writes text + metadata to MongoDB Atlas
        └─▶ mongo.update_status(): Set status="ready"
```

---

### Transaction Lifecycle B: Hybrid Search & Answer Generation

```
User submits question in frontend/index.html
  │
  ├─▶ POST /api/query (routers/query.py)
  │     │
  │     ├─▶ 1. RETRIEVAL (backend/retrieval.py)
  │     │     ├─▶ Qdrant Vector Search ──▶ Top 20 semantic chunks
  │     │     ├─▶ MongoDB $text Search ───▶ Top 20 keyword chunks
  │     │     ├─▶ EnsembleRetriever    ───▶ Merges ~40 chunks via RRF
  │     │     └─▶ CrossEncoderReranker ───▶ BAAI/bge-reranker-large scores & outputs Top 10
  │     │
  │     ├─▶ 2. GENERATION (backend/generation.py)
  │     │     ├─▶ Liberal Mode: LIBERAL_PROMPT | ChatGroq ──▶ Doc Answer + AI Explanation
  │     │     └─▶ Strict Mode:
  │     │           ├─▶ Check top score vs 0.30 confidence threshold
  │     │           ├─▶ STRICT_PROMPT | ChatGroq ──▶ Evidence-only cited text
  │     │           └─▶ verify_claim() (verifier.py) ──▶ Queries PubMed/arXiv API
  │     │
  │     └─▶ Return JSON response (QueryResponse) to frontend/index.html
  │
  └─▶ UI renders answer card with clickable citation buttons
```

---

### Transaction Lifecycle C: Citation PDF Highlighting

```
User clicks citation eye icon (👁) in frontend/index.html
  │
  ├─▶ GET /api/chunks/{chunk_id}/highlight (routers/upload.py)
  │     ├─▶ Fetch chunk details (chunk_text, page_number, document_id) from MongoDB
  │     ├─▶ Locate PDF on server disk (`uploads/{document_id}.pdf`)
  │     ├─▶ Open PDF via PyMuPDF (fitz) and navigate to page_number
  │     ├─▶ Search page for chunk text snippet
  │     ├─▶ Apply bright yellow highlight annotation (`stroke=[1, 0.92, 0.1]`)
  │     ├─▶ Render page as 2x resolution PNG image
  │     └─▶ Return base64 encoded PNG string
  │
  └─▶ Frontend decodes base64 string and displays rendered page image inline
```

---

## 🗄️ Summary of Key Technical Choices

| Requirement | Solution | Why Chosen |
|---|---|---|
| **Semantic Vector DB** | Qdrant Cloud | Fast cosine similarity search for 1024-dim dense vectors. |
| **Keyword DB** | MongoDB Atlas `$text` | Native full-text indexing without requiring extra Elasticsearch server cluster. |
| **Reranking** | `BAAI/bge-reranker-large` | Cross-encoder architecture evaluates question & answer jointly for superior precision over dual-encoder vector search alone. |
| **LLM Provider** | Groq API (`llama-3.1-8b-instant`) | Near-instant token generation speed (~300 tokens/sec) for real-time response times. |
| **Tracing / Telemetry** | LangSmith (`@traceable`) | Full observability into latency, context inputs, LLM outputs, and pipeline performance. |
| **Frontend UI** | Vanilla Single Page Application | Lightweight, zero build overhead, fast loading, no frontend framework dependency. |

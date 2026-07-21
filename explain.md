# 📖 CiteRag — Simple Technical & Architectural Guide

Welcome to the comprehensive guide for **CiteRag**! This document explains how the entire project works in simple, clear language: how the frontend and backend talk to each other, how data flows step-by-step, and what every file and folder in the repository does.

---

## 💡 What is CiteRag? (In Simple Words)

Imagine you have a 100-page PDF research paper or medical report, and you want to ask questions about it. 
- A regular AI might make up facts (hallucinate) or give generic answers.
- **CiteRag** reads your document, breaks it down into small chunks, stores them in secure cloud databases, and when you ask a question, it finds the **exact page and text**, quotes it with **citations**, scores its own confidence, and can even **highlight the exact yellow text on the PDF page** right inside your browser!

---

## 🔄 End-to-End System Integration Flow

Here is how the **Frontend** and **Backend** work together when a user interacts with the app:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Web Browser)                          │
│  frontend/index.html — HTML5 / CSS3 / Vanilla JavaScript               │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │  HTTP / REST API Calls (JSON)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   BACKEND API (FastAPI on Railway)                     │
│  backend/main.py — Listens for incoming web requests                   │
└───────┬────────────────────────────────────────────────────────┬───────┘
        │ (Upload File Action)                                   │ (Ask Question Action)
        ▼                                                        ▼
┌───────────────────────────────┐               ┌────────────────────────────────┐
│  INGESTION PIPELINE           │               │  HYBRID RETRIEVAL & GENERATION │
│  backend/pipeline.py          │               │  backend/retrieval.py          │
│  1. Extract text (PyMuPDF/OCR)│               │  1. Vector search (Qdrant)     │
│  2. Split into 512-char chunks│               │  2. Keyword search (MongoDB)   │
│  3. Calculate 1024-dim vectors│               │  3. Merge via RRF Fusion       │
│  4. Save to Cloud DBs         │               │  4. Rerank via Cohere API      │
└──────────────┬────────────────┘               │  backend/generation.py         │
               │                                │  5. LLM Answer (ChatGroq)      │
               ▼                                │  backend/verifier.py           │
┌───────────────────────────────┐               │  6. Verify PubMed/arXiv        │
│    CLOUD STORAGE BACKENDS     │               └────────────────────────────────┘
│ 1. Qdrant Cloud (Vectors)     │                                │ (Click PDF Highlight)
│ 2. MongoDB Atlas (Chunks/Text)│                                ▼
└───────────────────────────────┘               ┌────────────────────────────────┐
                                                │  PDF HIGHLIGHT RENDERER        │
                                                │  backend/routers/upload.py     │
                                                │  1. Find PDF page on server    │
                                                │  2. Search snippet & highlight │
                                                │  3. Render page to PNG image   │
                                                └────────────────────────────────┘
```

### Step-by-Step User Actions:

1. **Document Upload:**
   - User drags a PDF onto `index.html`.
   - Frontend sends a `POST /api/upload` request to FastAPI.
   - Backend saves the file, creates a record in MongoDB with `status: "processing"`, and launches `pipeline.py` as a **Background Task**.
   - Frontend polls `GET /api/documents` every 2 seconds until status changes to `status: "ready"`.

2. **Asking a Question:**
   - User types a question, selects **Strict Mode** or **Liberal Mode**, and clicks Send.
   - Frontend sends `POST /api/query` to FastAPI.
   - Backend runs **Hybrid Retrieval**:
     - Searches **Qdrant Cloud** for vector meaning match (Top 20).
     - Searches **MongoDB Atlas** for exact keyword text match (Top 20).
     - Combines results using **Reciprocal Rank Fusion (RRF)**.
     - Passes candidates to **Cohere Rerank v3.5 API** to select the Top 10 most relevant chunks.
   - Backend passes top chunks to **Groq Cloud LLM** (`llama-3.1-8b-instant`) to generate a cited response.
   - In Strict Mode, backend checks external databases (**PubMed** for healthcare, **arXiv** for research) to verify claims.
   - Response is returned as JSON and rendered formatted in `index.html`.

3. **PDF Highlight Viewing:**
   - User clicks **"📄 View PDF Page Highlight"** under a citation tag.
   - Frontend calls `GET /api/chunks/{chunk_id}/highlight`.
   - Backend loads the PDF page via **PyMuPDF**, uses multi-strategy snippet searching to locate the exact text, draws a bright yellow highlight box, renders the page to a PNG image, and returns it as a Base64 string.
   - Frontend displays the highlighted page image in a popup overlay!

---

## 🗂️ Files and Folders Reference

Here is the exact purpose of every directory and file in the codebase:

```
CiteRag/
├── backend/
│   ├── db/
│   │   └── mongo_client.py     # MongoDB database client
│   ├── routers/
│   │   ├── upload.py           # File management & PDF highlight routes
│   │   └── query.py            # Question answering RAG route
│   ├── config.py               # Settings & environment variables
│   ├── main.py                 # FastAPI application entrypoint
│   ├── schemas.py              # Pydantic data schemas
│   ├── pipeline.py             # Document loading, OCR, chunking & storing
│   ├── retrieval.py            # Hybrid vector search + reranking
│   ├── generation.py           # LLM answer generation (Liberal & Strict)
│   ├── verifier.py             # PubMed & arXiv claim verifier
│   ├── Dockerfile              # Docker container definition
│   ├── .dockerignore            # Excluded files for Docker build
│   ├── railway.json            # Deployment configuration for Railway
│   └── requirements.txt        # Python package dependencies
├── frontend/
│   └── index.html              # Frontend user interface (Single File SPA)
├── docker-compose.yml          # Container orchestration config
├── .env                        # Local secret API keys (Git ignored)
├── .env.example                # Template for environment variables
├── .gitignore                  # Git untracked files specification
├── README.md                   # Public repository documentation
├── PROJECT_PLAN.md             # Architecture overview & completion status
├── DEPLOYMENT.md               # Production deployment instructions
└── explain.md                  # Detailed architectural explanation (this file)
```

---

### Detailed File Explanations:

#### 1. `frontend/index.html`
- **What it is:** The complete single-page Web UI built using modern HTML5, CSS3, and JavaScript.
- **Why it is used:** Keeps the frontend simple and fast without requiring Node.js, Webpack, or npm build pipelines.
- **What it does:** Renders the dark-mode theme, drag-and-drop file upload, real-time ingestion status indicators, document checkboxes, answer mode switcher, interactive citation tags, and PDF highlight popups.

#### 2. `backend/config.py`
- **What it is:** Central configuration module.
- **Why it is used:** Reads environment variables (`.env`, system env vars) in one place so no other file needs to call `os.getenv()`.
- **What it does:** Enhanced to search `.env`, `../.env`, and `/app/.env` (inside Docker) so settings are loaded cleanly in both local and container environments.

#### 3. `backend/main.py`
- **What it is:** FastAPI web server entrypoint.
- **Why it is used:** Starts the server, sets up CORS middleware (allowing web browsers to talk to the API), registers routers, and exposes health endpoints (`/api/health`, `/health`, `/`).

#### 4. `backend/schemas.py`
- **What it is:** Data contract definition file using Pydantic.
- **Why it is used:** Validates input data from the frontend and structures outgoing JSON API responses.

#### 5. `backend/db/mongo_client.py`
- **What it is:** Database client for **MongoDB Atlas**.
- **Why it is used:** Manages two collections: `documents` (tracks file status like "processing" or "ready") and `chunks` (stores full text, page numbers, and `$text` search index).

#### 6. `backend/pipeline.py`
- **What it is:** Ingestion pipeline engine.
- **Why it is used:** Takes an uploaded file, extracts text using PyMuPDF (or Tesseract OCR if scanned), splits it into 512-character chunks with 128-character overlap, generates 1024-dimensional vectors using Cohere Embeddings, and saves vectors to **Qdrant Cloud** and text to **MongoDB Atlas**.

#### 7. `backend/retrieval.py`
- **What it is:** Hybrid search and reranking engine.
- **Why it is used:** Finds the best document chunks for a question. It combines semantic vector search from Qdrant + exact keyword text search from MongoDB via Reciprocal Rank Fusion (RRF), then passes candidate chunks to **Cohere Rerank v3.5** to select the top 10 chunks.

#### 8. `backend/generation.py`
- **What it is:** Answer generation module using LangChain and ChatGroq.
- **Why it is used:** Prompts the Groq Cloud LLM (`llama-3.1-8b-instant`) to write answers.
  - **Liberal Mode:** Answers from documents first, then adds broader educational context.
  - **Strict Mode:** Evidence-only answers with mandatory citations and confidence score. Refuses to answer if confidence is below `0.30`.

#### 9. `backend/verifier.py`
- **What it is:** External claim verification tool.
- **Why it is used:** In Strict Mode, when domain is `healthcare` or `research`, it queries live APIs (**PubMed** or **arXiv**) to cross-check scientific facts against published literature.

#### 10. `backend/routers/upload.py`
- **What it is:** API router for file management and PDF rendering.
- **Why it is used:** Handles `POST /api/upload`, `GET /api/documents`, `DELETE /api/documents/{id}`, and `GET /api/chunks/{chunk_id}/highlight`. Includes multi-strategy snippet searching for PDF yellow highlighting.

#### 11. `backend/routers/query.py`
- **What it is:** API router for question answering.
- **Why it is used:** Handles `POST /api/query`, connecting retrieval, generation, confidence calculation, and claim verification into a single clean API response.

#### 12. `backend/Dockerfile` & `docker-compose.yml`
- **What they are:** Container setup files.
- **Why they are used:** Package the FastAPI application into an isolated, secure Docker container running as a non-root user (`appuser`) with health checks, making local execution and Railway deployment identical and reliable.

---

## ☁️ Cloud Infrastructure & Data Storage

Here is where every piece of data is stored:

1. **MongoDB Atlas (Cloud Database):**
   - Stores document metadata, file statuses, full text of every chunk, and native `$text` full-text search indexes.
   - **Persistence:** 🔒 Permanent cloud storage (survives container restarts).

2. **Qdrant Cloud (Cloud Vector Database):**
   - Stores 1024-dimensional dense embedding vectors for fast cosine similarity search.
   - **Persistence:** 🔒 Permanent cloud storage (survives container restarts).

3. **Groq Cloud & Cohere Cloud APIs:**
   - Handles fast LLM inference, embedding calculations, and cross-encoder reranking.

4. **Railway Cloud Hosting:**
   - Hosts the backend Docker container in production with live domain `https://virtuous-tenderness-production.up.railway.app`.

---

## 🛠️ Recent Improvements & Fixes Implemented

- **Safe Module Startup:** Wrapped cloud client initializations (`ChatGroq`, `CohereEmbeddings`, `CohereRerank`, `QdrantVectorStore`) in safe fallbacks so container startup never crashes if environment variables are temporarily delayed.
- **Enhanced PDF Highlight Search:** Implemented multi-strategy snippet search (cleaned prefixes, multi-word phrases, line snippets) to guarantee bounding box yellow highlights on PDF pages.
- **Cross-Platform File Resolution:** Normalized Windows (`\`) and Linux (`/`) path separators for seamless execution locally and on Railway.
- **Docker Compose Setup:** Created `docker-compose.yml` for 1-click local containerized execution.

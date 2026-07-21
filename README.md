# 📚 CiteRag — Citation-Aware RAG Workbench

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/LLM-Groq%20%7C%20llama--3.1--8b-F55036?logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/VectorDB-Qdrant%20Cloud-DC143C?logo=qdrant&logoColor=white" alt="Qdrant">
  <img src="https://img.shields.io/badge/Database-MongoDB%20Atlas-47A248?logo=mongodb&logoColor=white" alt="MongoDB Atlas">
  <img src="https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white" alt="Railway">
  <img src="https://img.shields.io/badge/Frontend-Netlify-00C7B7?logo=netlify&logoColor=white" alt="Netlify">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

<p align="center">
  A citation-aware hybrid RAG workbench that delivers document-grounded answers with inline citations, confidence scoring, PDF highlighting, and external claim verification.
</p>

---

## 🌟 Overview

CiteRag is a production-quality Retrieval-Augmented Generation (RAG) system that lets you upload your own documents and ask natural language questions about them. Unlike generic chat tools, CiteRag:

- **Grounds every answer in your documents** with precise page-level citations
- **Refuses to hallucinate** in Strict Mode when evidence is insufficient
- **Scores its own confidence** based on reranker scores from a Cross-Encoder model
- **Verifies medical/scientific claims** against PubMed and arXiv automatically
- **Highlights cited text** directly on the rendered PDF page in the browser
- **Persists all data to the cloud** — documents survive server restarts

Built on **LangChain** with a **vanilla HTML/JS frontend** and a **FastAPI** backend, using cloud-hosted **Qdrant** and **MongoDB Atlas** for durable storage and **Groq API** for fast LLM inference.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| 🔍 **Hybrid Retrieval** | Fuses semantic search (Qdrant) + keyword search (MongoDB `$text`) via Reciprocal Rank Fusion |
| 🎯 **Cross-Encoder Reranking** | `BAAI/bge-reranker-large` scores every (question, chunk) pair — keeps top 10 |
| 📝 **Liberal Mode** | Doc-based answer + broader AI explanation, clearly labeled |
| 🔒 **Strict Mode** | Evidence-only, citations mandatory, confidence scored; refuses below threshold |
| 📄 **Inline PDF Highlighter** | Renders cited PDF pages with matching text highlighted in yellow |
| 📊 **Full Observability** | Ingestion, retrieval, generation, and verifications traced via **LangSmith** |
| 🧪 **Claim Verification** | PubMed + arXiv API cross-checks for research/health domain documents |
| 🖼️ **OCR Fallback** | Tesseract OCR extracts text from scanned/image-only PDFs |
| ✏️ **Inline Renaming** | Rename documents across MongoDB + Qdrant in one click |
| ☁️ **Persistent Cloud Storage** | Files, chunks, and vectors survive session and server restarts |

---

## 🛠️ Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **Web API** | FastAPI (Python) | Backend API + async background ingestion tasks |
| **Frontend UI** | Vanilla HTML / CSS / JS | Lightweight dark-mode SPA — no build step |
| **RAG Core** | LangChain | Pipeline orchestrator, LCEL chains, retrievers |
| **Vector Database** | Qdrant Cloud | Semantic search — 1024-dim cosine similarity |
| **Keyword / Metadata DB** | MongoDB Atlas | `$text` index keyword search + document status tracking |
| **Observability** | LangSmith | Full execution tracing and quality monitoring |
| **PDF Rendering** | PyMuPDF (fitz) | Page rendering, text search, highlight annotation, PNG export |
| **Embedding Model** | BAAI/bge-large-en-v1.5 | 1024-dimensional dense text embeddings |
| **Reranker Model** | BAAI/bge-reranker-large | Cross-Encoder precision relevance scoring |
| **LLM Inference** | ChatGroq (llama-3.1-8b-instant) | Cloud-hosted fast answer generation |
| **Deployment** | Docker → Railway (backend) + Netlify (frontend) | Production hosting |

---

## ⚙️ How It Works

```
Upload PDF / DOCX / TXT
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                    │
│  PyMuPDF → OCR Fallback → RecursiveTextSplitter(512)   │
│  → HuggingFaceEmbeddings → Qdrant (vectors)            │
│                          → MongoDB  (text + metadata)  │
└─────────────────────────────────────────────────────────┘
        │
        ▼  (Ask a Question)
┌─────────────────────────────────────────────────────────┐
│                   RETRIEVAL PIPELINE                    │
│  Qdrant Semantic Search   (Top 20)                     │
│    + MongoDB $text Search (Top 20)                     │
│    → EnsembleRetriever (RRF Fusion)                    │
│    → CrossEncoderReranker (Top 10)                     │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────┐     ┌──────────────────────────┐
│     LIBERAL MODE     │     │       STRICT MODE        │
│                      │     │                          │
│ LCEL Chain:          │     │ 1. sigmoid(logit) ≥ 0.30 │
│ Prompt → ChatGroq →  │     │ 2. Avg top-3 = confidence│
│ StrOutputParser      │     │ 3. LCEL strict chain     │
│                      │     │ 4. Verify → PubMed/arXiv │
└──────────────────────┘     └──────────────────────────┘
        │                              │
        └──────────────────────────────┘
                        │
                        ▼
            Answer + Citations + Confidence
```

---

## 📂 Supported File Types

| Format | Loader | Notes |
|---|---|---|
| `.pdf` | PyMuPDFLoader | Page-by-page extraction; OCR fallback for scanned pages |
| `.docx` | Docx2txtLoader | Full document text extraction |
| `.txt` | TextLoader | Plain UTF-8 text files |

---

## 📁 Repository Structure

```
CiteRag/
├── backend/
│   ├── db/
│   │   ├── __init__.py
│   │   └── mongo_client.py     # MongoDB client, text index, chunk CRUD
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── upload.py           # POST /upload, GET /documents, DELETE, PATCH rename, GET highlight
│   │   └── query.py            # POST /query — retrieval + generation
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Central env-var loader (single import point)
│   ├── schemas.py              # Pydantic request / response models
│   ├── pipeline.py             # Ingestion: load → split → embed → store (LangSmith traced)
│   ├── retrieval.py            # Hybrid search + cross-encoder reranking (LangSmith traced)
│   ├── generation.py           # LCEL liberal & strict answer chains (LangSmith traced)
│   ├── verifier.py             # PubMed & arXiv claim verifier (LangSmith traced)
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile              # Container — includes tesseract-ocr + healthcheck
│   ├── .dockerignore
│   └── railway.json            # Railway deployment config
├── frontend/
│   └── index.html              # Full SPA — dark-mode UI, no build step required
├── .env                        # Local secrets (git-ignored)
├── .env.example                # Credential template
├── .gitignore
└── README.md
```

---

## 🔧 Local Development Setup

### Prerequisites
- Python 3.12
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed and on your system `PATH` (Windows: add install dir to PATH)

### Required Cloud Services (All Free Tiers Work)
| Service | Purpose | Free Tier |
|---|---|---|
| [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) | Document metadata + chunk text storage | M0 Free Cluster |
| [Qdrant Cloud](https://cloud.qdrant.io/) | Vector embeddings storage | 1 GB Free |
| [Groq API](https://console.groq.com/) | LLM inference (llama-3.1-8b-instant) | Free developer key |
| [LangSmith](https://smith.langchain.com) | Observability / tracing | Free |

### Step 1 — Clone & configure
```bash
git clone https://github.com/PanthDhoriyani/Cite_Rag.git
cd Cite_Rag
cp .env.example .env       # then fill in your keys
```

### Step 2 — Install dependencies
```bash
python -m venv backend/venv

# Windows
backend\venv\Scripts\activate

# macOS / Linux
source backend/venv/bin/activate

pip install -r backend/requirements.txt
```

### Step 3 — Run the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

Swagger docs available at `http://localhost:8000/docs`

### Step 4 — Open the frontend
Open `frontend/index.html` directly in your browser (double-click the file, or use a local server like `npx serve frontend/`).

Click the **status dot** in the top-right → set Backend URL to `http://localhost:8000` → Save.

---

## 🎯 Usage Guide

1. **Upload** — Drag-and-drop a PDF, DOCX, or TXT in the sidebar. Pick a domain tag.
2. **Wait** — Status changes from `Processing…` → `Ready (N chunks)` automatically (auto-polls).
3. **Select docs** — Check the documents you want to include in the search scope.
4. **Choose mode** — Toggle **Liberal** (educational) or **Strict** (evidence-only) in the main panel.
5. **Ask** — Type your question and press Enter.
6. **View citations** — Expand citation cards; click 👁 to see the highlighted PDF page.
7. **Rename** — Click ✏️ next to any document to rename it across all databases.
8. **Delete** — Click 🗑️ to permanently remove a document and all its vectors/chunks.

---

## 🚢 Deployment

### Architecture

```
[Netlify]  ──HTTPS──▶  [Railway]  ──────▶  [Qdrant Cloud]
 Static HTML              FastAPI               Vectors
 frontend/index.html      Docker                  │
                              │                   │
                          [MongoDB Atlas] ◀────────┘
                            Metadata + Chunks
```

### Backend → Railway

1. Push code to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo** → select this repo.
3. In Railway service **Settings → Source**, set **Root Directory** to `backend`.
4. Add all environment variables from `.env` in the **Variables** tab (see `.env.example`).
5. Railway auto-builds and deploys. First build takes ~5–10 min (downloads ML models).
6. Copy your Railway public URL (e.g. `https://citerag-backend.up.railway.app`).

### Frontend → Netlify

**Quickest (drag-and-drop):**
1. Go to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Drag the `frontend/` folder onto the page.
3. Done — instant public URL.

**Or via GitHub (auto-deploy on push):**
1. Netlify → New site → Import from GitHub.
2. Base directory: `frontend` | Build command: *(blank)* | Publish directory: `frontend`.

**After both are live:**
- Open the Netlify URL.
- Click the status dot → paste your Railway URL → Save.

> **Tip:** To bake the Railway URL in as the default (instead of `localhost:8000`), edit line 488 in `frontend/index.html`:
> ```js
> let BACKEND = localStorage.getItem('citerag_backend') || 'https://your-app.up.railway.app';
> ```

---

## 🔑 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URL` | ✅ | MongoDB Atlas connection string |
| `QDRANT_URL` | ✅ | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | ✅ | Qdrant API key |
| `GROQ_API_KEY` | ✅ | Groq API key |
| `EMBEDDING_MODEL` | — | Default: `BAAI/bge-large-en-v1.5` |
| `RERANKER_MODEL` | — | Default: `BAAI/bge-reranker-large` |
| `LLM_MODEL` | — | Default: `llama-3.1-8b-instant` |
| `CHUNK_SIZE` | — | Default: `512` |
| `CHUNK_OVERLAP` | — | Default: `128` |
| `CONFIDENCE_THRESHOLD` | — | Default: `0.30` (sigmoid-normalized) |
| `UPLOAD_DIR` | — | Default: `uploads` |
| `MAX_FILE_SIZE_MB` | — | Default: `50` |
| `LANGCHAIN_TRACING_V2` | — | `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | — | LangSmith project name |

---

## 📖 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/upload` | Upload a document (multipart/form-data) |
| `GET` | `/api/documents` | List all documents and their status |
| `DELETE` | `/api/documents/{id}` | Delete a document from all stores |
| `PATCH` | `/api/documents/{id}/rename` | Rename a document across all stores |
| `POST` | `/api/query` | Ask a question — returns answer + citations |
| `GET` | `/api/chunks/{chunk_id}/highlight` | Render highlighted PDF page for a citation |

Interactive docs: `https://your-railway-url.up.railway.app/docs`

---

## 📄 License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

<p align="center">Built with ❤️ using LangChain · FastAPI · Qdrant · MongoDB · Groq · Railway · Netlify</p>

# 📚 CiteRag — Citation-Aware RAG Workbench

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/LLM-Groq%20%7C%20llama--3.1--8b-F55036?logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/Embeddings-Cohere%20v3.0-6B46C1?logo=cohere&logoColor=white" alt="Cohere">
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

CiteRag is a production-quality Retrieval-Augmented Generation (RAG) system that lets you upload your own documents (PDF, DOCX, TXT) and ask natural language questions about them. Unlike generic chat tools, CiteRag:

- **Grounds every answer in your documents** with precise page-level citations
- **Refuses to hallucinate** in Strict Mode when evidence is insufficient
- **Scores its own confidence** based on Cohere Reranker relevance scores
- **Verifies medical/scientific claims** against PubMed and arXiv automatically
- **Highlights cited text** directly on the rendered PDF page in the browser with smart multi-strategy snippet matching
- **Persists all data to the cloud** — document text and vectors survive server restarts (MongoDB Atlas + Qdrant Cloud)

Built on **LangChain** with a **vanilla HTML/JS frontend** and a **FastAPI** backend containerized via **Docker** and deployed on **Railway**.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| 🔍 **Hybrid Retrieval** | Fuses semantic search (Qdrant Cloud) + keyword search (MongoDB `$text`) via Reciprocal Rank Fusion |
| 🎯 **Cloud Reranking** | `Cohere Rerank v3.5` scores every (question, chunk) pair — keeps top 10 relevant chunks |
| 📝 **Liberal Mode** | Doc-based answer + broader AI explanation, clearly labeled in separate sections |
| 🔒 **Strict Mode** | Evidence-only, citations mandatory, confidence scored; refuses below threshold |
| 📄 **Inline PDF Highlighter** | Renders cited PDF pages as PNG images with matching text highlighted in yellow |
| 📊 **Full Observability** | Ingestion, retrieval, generation, and verifications traced via **LangSmith** |
| 🧪 **Claim Verification** | PubMed + arXiv API cross-checks for research/health domain documents |
| 🖼️ **OCR Fallback** | Tesseract OCR extracts text from scanned/image-only PDFs |
| ✏️ **Inline Renaming** | Rename documents across MongoDB + Qdrant in one click |
| ☁️ **Persistent Cloud Storage** | Chunks, text, and vector embeddings stored permanently in MongoDB Atlas + Qdrant Cloud |

---

## 🛠️ Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **Web API** | FastAPI (Python 3.12) | Backend API + async background ingestion tasks |
| **Frontend UI** | Vanilla HTML / CSS / JS | Lightweight dark-mode SPA — no npm build step required |
| **RAG Core** | LangChain 0.3 | Pipeline orchestrator, LCEL chains, retrievers |
| **Vector Database** | Qdrant Cloud | Semantic search — 1024-dim cosine similarity |
| **Keyword / Metadata DB** | MongoDB Atlas | `$text` index keyword search + document status tracking |
| **Observability** | LangSmith | Full execution tracing and quality monitoring |
| **PDF Rendering** | PyMuPDF (fitz) | Page rendering, multi-strategy text search, highlight annotation, PNG export |
| **Embedding Model** | Cohere Cloud (`embed-english-v3.0`) | 1024-dimensional dense text embeddings |
| **Reranker Model** | Cohere Cloud (`rerank-v3.5`) | High-precision relevance scoring |
| **LLM Inference** | ChatGroq (`llama-3.1-8b-instant`) | Cloud-hosted ultra-fast answer generation |
| **Containerization** | Docker & Docker Compose | Containerized runtime with non-root security & health checks |
| **Deployment** | Railway (Backend) + Netlify (Frontend) | Production cloud infrastructure |

---

## ⚙️ System Architecture & Workflow

```
Upload PDF / DOCX / TXT
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                    │
│  PyMuPDF → OCR Fallback → RecursiveTextSplitter(512)   │
│  → CohereEmbeddings → Qdrant Cloud (vectors)           │
│                      → MongoDB Atlas (text + metadata)  │
└─────────────────────────────────────────────────────────┘
        │
        ▼  (Ask a Question)
┌─────────────────────────────────────────────────────────┐
│                   RETRIEVAL PIPELINE                    │
│  Qdrant Semantic Search   (Top 20)                     │
│    + MongoDB $text Search (Top 20)                     │
│    → EnsembleRetriever (RRF Fusion)                    │
│    → CohereRerank v3.5    (Top 10)                     │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────┐     ┌──────────────────────────┐
│     LIBERAL MODE     │     │       STRICT MODE        │
│                      │     │                          │
│ LCEL Chain:          │     │ 1. Confidence threshold  │
│ Prompt → ChatGroq →  │     │ 2. Avg top-3 = confidence│
│ StrOutputParser      │     │ 3. LCEL strict chain     │
│                      │     │ 4. Verify → PubMed/arXiv │
└──────────────────────┘     └──────────────────────────┘
```

---

## 📂 Project Structure

```
CiteRag/
├── backend/
│   ├── db/
│   │   └── mongo_client.py     # MongoDB database client & text search queries
│   ├── routers/
│   │   ├── upload.py           # Upload, list, delete, rename & highlight endpoints
│   │   └── query.py            # RAG query processing endpoint
│   ├── config.py               # Central environment configuration & setup singleton
│   ├── main.py                 # FastAPI application entrypoint & middleware setup
│   ├── schemas.py              # Pydantic data validation schemas
│   ├── pipeline.py             # Document loading, OCR, chunking & vector storage
│   ├── retrieval.py            # Qdrant + MongoDB hybrid search & Cohere reranker
│   ├── generation.py           # Groq LLM answer generation (Liberal & Strict chains)
│   ├── verifier.py             # External API verification (PubMed & arXiv)
│   ├── Dockerfile              # Container definition for Railway deployment
│   ├── .dockerignore            # Excludes unnecessary files from Docker image
│   ├── railway.json            # Deployment configuration for Railway
│   └── requirements.txt        # Backend Python dependency specification
├── frontend/
│   └── index.html              # Modern dark-mode SPA (HTML5 + CSS3 + Vanilla JS)
├── docker-compose.yml          # Docker Compose configuration for local/container setup
├── .env                        # Private environment keys (NOT committed to git)
├── .env.example                # Blueprint for environment variables
├── .gitignore                  # Specifies untracked files for Git
├── README.md                   # Project overview & documentation
├── PROJECT_PLAN.md             # Completed technical phases & architecture overview
├── DEPLOYMENT.md               # Detailed step-by-step production deployment guide
└── explain.md                  # Comprehensive technical explanation & file reference
```

---

## 🏃 Quick Start — Local Development

### Step 1 — Clone Repository & Setup `.env`
```bash
git clone https://github.com/PanthDhoriyani/Cite_Rag.git
cd Cite_Rag
cp .env.example .env
```
Fill in your API keys in `.env` (`MONGODB_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`).

### Step 2 — Option A: Run via Docker Compose (Recommended)
```bash
docker compose up --build
```
The backend API will be live at `http://localhost:8000`.

### Step 3 — Option B: Run via Python Virtual Environment
```bash
# Navigate to backend
cd backend

# Create & activate virtual environment
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate   # On macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start backend server
python -m uvicorn main:app --reload --port 8000
```

### Step 4 — Open Frontend
Double click `frontend/index.html` or open it in any web browser. It connects automatically to your backend!

---

## 🚢 Deployment Overview

- **Backend (FastAPI + Docker):** Deployed on **Railway** with health checks at `/api/health`.
- **Frontend (Static HTML/JS):** Deployed on **Netlify** / local browser pointing to the Railway API URL.

For step-by-step instructions, see [DEPLOYMENT.md](file:///d:/projectaalphaa/CiteRag/DEPLOYMENT.md).

---

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.

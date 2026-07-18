# 📚 CiteRag Answer Workbench

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/LLM-Groq%20%7C%20llama--3.1--8b-F55036?logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/VectorDB-Qdrant%20Cloud-DC143C?logo=qdrant&logoColor=white" alt="Qdrant">
  <img src="https://img.shields.io/badge/Database-MongoDB%20Atlas-47A248?logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/Docker-Containerised-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Deploy-HuggingFace%20Spaces-FFD21E?logo=huggingface&logoColor=black" alt="HF Spaces">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

<p align="center">
  A citation-aware, hybrid RAG workbench that delivers document-grounded answers with inline citations, confidence scoring, and external claim verification.
</p>

---

## 🌟 Overview

CiteRag is a production-quality Retrieval-Augmented Generation (RAG) system that allows you to upload your own documents and ask natural language questions about them. Unlike generic chat tools, CiteRag:

- **Grounds every answer in your documents** with precise page-level citations
- **Refuses to hallucinate** in Strict Mode when evidence is insufficient
- **Scores its own confidence** based on reranker scores from a Cross-Encoder model
- **Verifies medical/scientific claims** against PubMed and arXiv automatically
- **Persists all data to the cloud** — documents survive server restarts and browser session closures

Built on **LangChain** with a **Streamlit** frontend and a **FastAPI** backend, CiteRag uses cloud-hosted **Qdrant** and **MongoDB Atlas** for durable storage and **Groq API** (`llama-3.1-8b-instant`) for blazing-fast LLM inference.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| 🔍 **Hybrid Retrieval** | Fuses semantic search (Qdrant) + keyword search (MongoDB `$text`) via Reciprocal Rank Fusion |
| 🎯 **Cross-Encoder Reranking** | `BAAI/bge-reranker-large` scores every (question, chunk) pair and keeps the top 10 |
| 📝 **Liberal Mode** | Doc-based answer + broader AI explanation, clearly labeled |
| 🔒 **Strict Mode** | Evidence-only, citations mandatory, confidence scored; sigmoid-normalized reranker score must exceed 0.30 threshold |
| 📄 **Inline PDF Highlighter** | Open cited chunks directly in the UI as rendered PDF pages with matching text highlighted in yellow |
| 📊 **Full Observability** | Ingestion, retrieval, LLM generation, and external verifications traced via **LangSmith** |
| 🧪 **Claim Verification** | PubMed + arXiv API cross-checks for research/health domain docs |
| 🖼️ **OCR Fallback** | Tesseract OCR extracts text from scanned/image-only PDFs |
| ✏️ **Inline Renaming** | Rename documents across all databases (MongoDB + Qdrant) in one click |
| 🕐 **Upload Timestamps** | Every file displays its ingestion date and time in the sidebar |
| ☁️ **Persistent Storage** | All files, chunks, and vectors survive session/server restarts |

---

## 🛠️ Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **Web API** | FastAPI (Python) | High-performance backend & async background tasks |
| **Frontend UI** | Streamlit (Python) | Interactive dark-mode dashboard |
| **RAG Core** | LangChain | Pipeline orchestrator, LCEL chains, retrievers |
| **Vector Database** | Qdrant Cloud | Semantic search engine (1024-dim cosine similarity) |
| **Keyword/Text DB** | MongoDB Atlas | Native `$text` index keyword matching & document metadata |
| **Observability** | LangSmith | Full execution tracing, latency analysis, and quality monitoring |
| **PDF Rendering** | PyMuPDF (fitz) | Dynamic PDF page text-search, annotation highlighting, and PNG rendering |
| **Embedding Model** | BAAI/bge-large-en-v1.5 | 1024-dimensional dense text embeddings |
| **Reranker Model** | BAAI/bge-reranker-large | Deep Cross-Encoder for precision relevance scoring |
| **LLM Inference** | ChatGroq (llama-3.1-8b-instant) | Cloud-hosted ultra-fast answer generation |

---

## ⚙️ How It Works

```
 Upload PDF/DOCX/TXT
        │
        ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   INGESTION PIPELINE                    │
 │  PyMuPDF → OCR Fallback → RecursiveTextSplitter (512)   │
 │  → HuggingFaceEmbeddings → Qdrant (vectors)             │
 │                          → MongoDB (text chunks)         │
 └─────────────────────────────────────────────────────────┘
        │
        ▼ (Ask a Question)
 ┌─────────────────────────────────────────────────────────┐
 │                   RETRIEVAL PIPELINE                    │
 │  Qdrant Semantic Search (Top 20)                        │
 │    +  MongoDB $text Search (Top 20)                     │
 │    → EnsembleRetriever (RRF Fusion)                     │
 │    → CrossEncoderReranker (Top 10)                      │
 └─────────────────────────────────────────────────────────┘
        │
        ▼
 ┌──────────────────────┐     ┌──────────────────────────┐
 │     LIBERAL MODE     │     │       STRICT MODE        │
 │                      │     │                          │
 │ LCEL Chain:          │     │ 1. sigmoid(logit) ≥ 0.30 │
 │ Prompt → ChatGroq →  │     │ 2. Avg top-3 = confidence│
 │ StrOutputParser      │     │ 3. LCEL strict chain     │
 │                      │     │ 4. Verify vs PubMed/arXiv│
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
│   │   └── mongo_client.py  # MongoDB client setup, text index creation & chunk lookup
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── query.py         # QA & retrieval routes (traced)
│   │   └── upload.py        # Ingestion, status, delete, rename & chunk highlight rendering
│   ├── main.py              # FastAPI app entry point (dotenv loaded at top)
│   ├── config.py            # Centralised env variable loader (with LangSmith config)
│   ├── schemas.py           # Pydantic request/response models
│   ├── pipeline.py          # Ingestion pipeline (OCR, split, embed, store - traced)
│   ├── retrieval.py         # Hybrid search fusion & cross-encoder reranking (traced)
│   ├── generation.py        # LCEL liberal & strict answer chains (ChatGroq - traced)
│   ├── verifier.py          # PubMed & arXiv E-utilities claim verifier (traced)
│   ├── test_langsmith.py    # Diagnostic script to test LangSmith connection
│   ├── frontend.py          # Streamlit UI dashboard (persists state across PDF toggle clicks)
│   └── requirements.txt     # Python dependencies
├── Dockerfile               # Container image (pre-downloads ML models at build time)
├── supervisord.conf         # Manages FastAPI + Streamlit as two supervised processes
├── docker-compose.yml       # Local development (one-command start)
├── .dockerignore            # Excludes venv, .env, uploads, cache from image
├── .env                     # Local credentials (git-ignored)
├── .env.example             # Credential template
├── working.md               # Detailed user-action ↔ backend transaction guide
├── about.md                 # Component-level technical descriptions
├── explain.md               # Phase-by-phase build explanation
└── README.md                # This file
```

---

## 🔧 Installation & Setup

### Prerequisites
- Python 3.10 or higher
- [Tesseract OCR Engine](https://github.com/UB-Mannheim/tesseract/wiki) — install and add to your system `PATH` for scanned PDF support

### Required Cloud Services (All Free Tiers Work)
- 🍃 [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) — Free M0 cluster
- 🔴 [Qdrant Cloud](https://cloud.qdrant.io/) — Free 1GB cluster
- ⚡ [Groq API](https://console.groq.com/) — Free developer API key

### Step 1: Clone the Repository
```bash
git clone https://github.com/PanthDhoriyani/Cite_Rag.git
cd Cite_Rag
```

### Step 2: Configure Environment Variables
```bash
# Copy the example config
cp .env.example .env
```

Open `.env` and fill in your credentials:
```env
MONGODB_URL=mongodb+srv://<user>:<password>@cluster.mongodb.net
QDRANT_URL=https://<cluster-id>.aws.cloud.qdrant.io
QDRANT_API_KEY=<your-qdrant-api-key>
GROQ_API_KEY=gsk_<your-groq-api-key>

EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama-3.1-8b-instant

CHUNK_SIZE=512
CHUNK_OVERLAP=128
```

### Step 3: Create Virtual Environment & Install Dependencies
```bash
# Create virtual environment
python -m venv backend/venv

# Activate (Windows)
backend\venv\Scripts\activate

# Activate (macOS/Linux)
source backend/venv/bin/activate

# Install packages
pip install -r backend/requirements.txt
```

---

## ▶️ Running the Application

### Option A — Docker (Recommended)

```bash
# First run (downloads ML models into the image — ~15-25 min)
docker compose up --build

# Subsequent runs
docker compose up
```

| URL | What |
|---|---|
| http://localhost:7860 | Streamlit UI |
| http://localhost:8000/api/health | FastAPI health check |
| http://localhost:8000/docs | Swagger API docs |

### Option B — Manual (Two Terminals)

Open **two terminal windows**, both inside the `backend/` directory with the virtual environment activated.

**Terminal 1 — FastAPI Backend:**
```bash
cd backend
venv\Scripts\activate        # Windows
python -m uvicorn main:app --reload --port 8000
```
> Swagger API docs available at `http://localhost:8000/docs`

**Terminal 2 — Streamlit Dashboard:**
```bash
cd backend
venv\Scripts\activate        # Windows
streamlit run frontend.py
```
> Dashboard opens automatically at **`http://localhost:8501`**

---

## 🎯 Usage Guide

1. **Upload a Document** — Drag-and-drop a PDF, DOCX, or TXT file in the sidebar. Select a domain tag (General, Research, Healthcare, Legal, Finance) to enable domain-specific verification.
2. **Wait for Ingestion** — The sidebar status badge will update from `Processing...` to `Ready (N chunks)` automatically. The upload timestamp is shown next to the badge.
3. **Scope Your Search** — Check the checkboxes next to documents you want to include in retrieval. Unchecked documents are excluded.
4. **Choose a Mode** — Toggle between **Liberal** and **Strict** in the main panel.
5. **Ask a Question** — Type your question and press Enter.
6. **Rename a Document** — Click the ✏️ pencil icon next to any document, type the new name, and click Save.
7. **Delete a Document** — Click the 🗑️ icon to permanently remove the document, all its chunks, and all associated vectors.

---

## 🚢 Deployment

CiteRag is containerised and ready to deploy on **Hugging Face Spaces** (free, no GPU needed).

### Why Hugging Face Spaces?
- **Free** CPU Basic tier: 2 vCPU, **16 GB RAM** — enough for the 2-3 GB ML models
- No sleep/idle shutdown
- Supports Docker SDK — run both FastAPI + Streamlit in one container

### Steps

1. **Create a Space** at https://huggingface.co/spaces → SDK: Docker → Hardware: CPU Basic
2. **Push code:**
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/citerag
   git push hf main
   ```
3. **Set Repository Secrets** (Settings → Repository secrets):

   | Secret | Value |
   |---|---|
   | `MONGODB_URL` | MongoDB Atlas connection string |
   | `QDRANT_URL` | Qdrant Cloud cluster URL |
   | `QDRANT_API_KEY` | Qdrant API key |
   | `GROQ_API_KEY` | Groq API key |
   | `LANGCHAIN_API_KEY` | LangSmith API key (optional) |

4. HF Spaces auto-builds on every push. First build: ~15-25 min.

---

## 📖 Documentation

| File | Description |
|---|---|
| [working.md](working.md) | Full user-action → API → database transaction walkthrough |
| [about.md](about.md) | Deep-dive into each technology component |
| [explain.md](explain.md) | Phase-by-phase explanation of how the system was built |

---

## 📄 License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

<p align="center">Built with ❤️ using LangChain, FastAPI, Streamlit, Qdrant, MongoDB, Groq, and Docker.</p>

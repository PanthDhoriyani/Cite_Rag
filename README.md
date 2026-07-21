# 📚 CiteRag — Citation-Aware Hybrid RAG Workbench

<p align="center">
  <img src="https://img.shields.io/badge/Live%20Demo-citerag.netlify.app-00C7B7?style=for-the-badge&logo=netlify&logoColor=white" alt="Live Demo">
  <img src="https://img.shields.io/badge/API%20Docs-Railway%20Live-0B0D0E?style=for-the-badge&logo=railway&logoColor=white" alt="API Docs">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/LLM-Groq%20%7C%20llama--3.1--8b-F55036?logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/Embeddings-Cohere%20v3.0-6B46C1?logo=cohere&logoColor=white" alt="Cohere">
  <img src="https://img.shields.io/badge/VectorDB-Qdrant%20Cloud-DC143C?logo=qdrant&logoColor=white" alt="Qdrant">
  <img src="https://img.shields.io/badge/Database-MongoDB%20Atlas-47A248?logo=mongodb&logoColor=white" alt="MongoDB Atlas">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

<p align="center">
  A production-grade, citation-aware hybrid Retrieval-Augmented Generation (RAG) system engineered for high-precision document intelligence with page-level inline citations, Cross-Encoder reranking, PDF page highlight rendering, and automated external claim verification.
</p>

---

## 🌐 Live Public Links

- **🚀 Live Application (Frontend):** [https://citerag.netlify.app](https://citerag.netlify.app/)
- **⚡ Production API & Swagger Docs:** [https://virtuous-tenderness-production.up.railway.app/docs](https://virtuous-tenderness-production.up.railway.app/docs)
- **🟢 API Health Status:** [https://virtuous-tenderness-production.up.railway.app/api/health](https://virtuous-tenderness-production.up.railway.app/api/health)

---

## 💼 Resume Bullet Points & Technical Highlights

> *Copy/paste these bullet points directly into your resume under **Projects** or **Experience**:*

- **Built & Deployed End-to-End Hybrid RAG Pipeline:** Engineered a Citation-Aware RAG platform using **FastAPI**, **LangChain**, and **Python 3.12**, integrating **Qdrant Cloud** vector search with **MongoDB Atlas** `$text` full-text search via **Reciprocal Rank Fusion (RRF)** to maximize retrieval recall.
- **Implemented Cloud Cross-Encoder Reranking:** Integrated **Cohere Rerank v3.5 API** to re-score candidate text chunks, boosting precision and reducing noise before feeding evidence into **ChatGroq (`llama-3.1-8b-instant`)**.
- **Zero-Hallucination Strict Mode Engine:** Designed a confidence-scoring algorithm with configurable probability thresholds (`< 0.30` rejection), guaranteeing document-grounded evidence answers with mandatory page-level inline citations.
- **Dynamic PDF Highlight Rendering:** Built a PyMuPDF (`fitz`) engine in FastAPI featuring multi-strategy fuzzy snippet matching to dynamically annotate cited PDF text in yellow and stream rendered Base64 PNG page overlays to the browser.
- **Automated External Claim Verification:** Integrated live **PubMed** and **arXiv** REST APIs to cross-verify medical and scientific claims in real-time against peer-reviewed research databases.
- **Full Observability & Dockerized Cloud Deployment:** Implemented **LangSmith** distributed tracing across all pipeline functions, containerized backend with **Docker & Docker Compose** (non-root security), and deployed CI/CD pipeline on **Railway** (backend) and **Netlify** (frontend).

---

## 🌟 Key Features

| Feature | Technical Implementation |
|---|---|
| 🔍 **Hybrid Search & Fusion** | Fuses Qdrant vector cosine similarity + MongoDB `$text` full-text search via Reciprocal Rank Fusion |
| 🎯 **Cross-Encoder Reranking** | `Cohere Rerank v3.5` scores every (question, chunk) pair to extract Top-10 high-precision chunks |
| 🔒 **Strict Mode (Zero Hallucination)** | Refuses to answer if retrieval confidence `< 0.30`; mandates exact inline chunk & page citations |
| 📝 **Liberal Mode (Educational)** | Generates structured document-based evidence answers + broader AI concept explanations |
| 📄 **Dynamic PDF Highlight Overlay** | Locates text snippets in original PDFs using PyMuPDF and renders high-res highlighted PNG images |
| 🧪 **PubMed & arXiv Claim Verifier** | Live REST API integration cross-checks scientific claims against public medical & research databases |
| 🖼️ **OCR Fallback Support** | Integrated **Tesseract OCR** for automatic fallback text extraction on scanned/image-only PDFs |
| 📊 **End-to-End Tracing** | Instrumented with **LangSmith** `@traceable` decorators for complete latency and quality observability |
| ☁️ **Cloud Data Persistence** | Document chunks, text, and 1024-dim vectors permanently stored in **MongoDB Atlas** & **Qdrant Cloud** |

---

## 🛠️ Tech Stack & Infrastructure Architecture

```
                               ┌────────────────────────────────────────────────────────┐
                               │                 FRONTEND (Netlify CDN)                 │
                               │  https://citerag.netlify.app — Single Page SPA (HTML/JS)│
                               └───────────────────────────┬────────────────────────────┘
                                                           │  HTTPS REST API
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │              BACKEND CONTAINER (Railway)               │
                               │  https://virtuous-tenderness-production.up.railway.app  │
                               │  FastAPI + Uvicorn + PyMuPDF + Docker Runtime          │
                               └─────────────┬──────────────────────────┬───────────────┘
                                             │                          │
                               (Ingestion & Retrieval)             (LLM & Verification)
                                             │                          │
                                             ▼                          ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐ ┌───────────────────────────────┐
│         Qdrant Cloud          │ │         MongoDB Atlas         │ │       Cloud AI Services       │
│  Semantic Vector Database     │ │ Full Chunks + Text Index      │ │ • Groq Cloud (llama-3.1-8b)   │
│  1024-dim Dense Embeddings    │ │ Document Status Tracking      │ │ • Cohere Rerank & Embed v3.0  │
└───────────────────────────────┘ └───────────────────────────────┘ │ • PubMed & arXiv REST APIs    │
                                                                    └───────────────────────────────┘
```

---

## 📂 Repository File Structure

```
CiteRag/
├── backend/
│   ├── db/
│   │   └── mongo_client.py     # MongoDB Atlas client, collection schemas & $text index
│   ├── routers/
│   │   ├── upload.py           # File upload, list, delete, rename & PDF highlight routes
│   │   └── query.py            # Hybrid retrieval, generation & verification route
│   ├── config.py               # Singleton environment configuration manager
│   ├── main.py                 # FastAPI entrypoint, CORS middleware & health routes
│   ├── schemas.py              # Pydantic request/response validation contracts
│   ├── pipeline.py             # Ingestion engine (PyMuPDF, OCR, RecursiveSplitter)
│   ├── retrieval.py            # Hybrid retriever (Qdrant + MongoDB) + Cohere Reranker
│   ├── generation.py           # LCEL answer generation chains (Liberal & Strict Modes)
│   ├── verifier.py             # PubMed and arXiv claim verification engine
│   ├── Dockerfile              # Production Dockerfile (Python 3.12-slim, non-root user)
│   ├── .dockerignore            # Excludes unnecessary files from Docker context
│   ├── railway.json            # Deployment orchestration configuration
│   └── requirements.txt        # Backend dependencies specification
├── frontend/
│   └── index.html              # Dark-mode Single Page Application (HTML5 / CSS3 / JS)
├── docker-compose.yml          # Container orchestration for local execution
├── .env.example                # Blueprint for required environment variables
├── DEPLOYMENT.md               # Production deployment walkthrough
└── explain.md                  # Comprehensive technical & architectural deep dive
```

---

## 🚀 Quick Start — Local Execution

### 1. Clone & Setup `.env`
```bash
git clone https://github.com/PanthDhoriyani/Cite_Rag.git
cd Cite_Rag
cp .env.example .env
```
*Fill in your cloud credentials in `.env` (`MONGODB_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`).*

### 2. Option A: Run via Docker Compose (Recommended)
```bash
docker compose up --build
```
*The API will start locally at `http://localhost:8000`.*

### 3. Option B: Run via Python Virtual Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

---

## 📄 License

This project is licensed under the MIT License — see the LICENSE file for details.

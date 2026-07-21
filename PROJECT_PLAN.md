# CiteRag — Project Overview & Architecture Plan

> Citation-Aware Hybrid RAG Platform  
> Built with LangChain · FastAPI · Qdrant Cloud · MongoDB Atlas · Groq · Cohere · Railway

---

## 📌 Project Goals & Capabilities

CiteRag is a trustworthy AI evidence-retrieval platform that:

- Accepts document uploads (PDF, DOCX, TXT)
- Ingests them through a multi-step LangChain pipeline: load → split → embed → store
- Stores vectors in **Qdrant Cloud** and full text + metadata in **MongoDB Atlas**
- Retrieves relevant chunks via hybrid semantic + keyword search with **Cohere Rerank v3.5**
- Generates cited answers using **Groq LLM** (`llama-3.1-8b-instant`) via LCEL chains
- Supports two answer modes: **Strict** (citation-mandatory, confidence-scored) and **Liberal** (educational)
- Renders cited PDF pages with yellow highlights directly in the browser
- Automatically cross-verifies scientific/medical claims against **PubMed** and **arXiv** APIs
- Traces execution end-to-end via **LangSmith**

---

## 🛠️ Tech Stack Matrix

| Layer | Technology | Status |
|---|---|---|
| **Web API** | FastAPI (Python 3.12) | ✅ Production |
| **Frontend** | Vanilla HTML / CSS / JS (Single File SPA) | ✅ Production |
| **RAG Framework** | LangChain 0.3 | ✅ Production |
| **PDF Extraction** | PyMuPDFLoader + Tesseract OCR fallback | ✅ Production |
| **DOCX Loading** | Docx2txtLoader | ✅ Production |
| **Text Chunking** | RecursiveCharacterTextSplitter (512 size / 128 overlap) | ✅ Production |
| **Embeddings** | Cohere Cloud — `embed-english-v3.0` (1024-dim) | ✅ Production |
| **Vector DB** | QdrantVectorStore (Qdrant Cloud) | ✅ Production |
| **Keyword Search** | MongoDB native `$text` full-text index | ✅ Production |
| **Metadata DB** | MongoDB Atlas (pymongo) | ✅ Production |
| **Hybrid Retrieval** | EnsembleRetriever (Qdrant + custom MongoDBTextRetriever) via RRF | ✅ Production |
| **Reranking** | ContextualCompressionRetriever + CohereRerank (`rerank-v3.5`) | ✅ Production |
| **LLM Inference** | ChatGroq — `llama-3.1-8b-instant` | ✅ Production |
| **Chain DSL** | LCEL (LangChain Expression Language) | ✅ Production |
| **Observability** | LangSmith (full pipeline tracing via `@traceable`) | ✅ Production |
| **PDF Highlighter** | PyMuPDF (fitz) — multi-strategy snippet search + PNG render | ✅ Production |
| **Containerization** | Docker + Docker Compose (Non-root user + Healthcheck) | ✅ Production |
| **Deployment** | Railway (Backend Docker Container) + Netlify (Frontend) | ✅ Production |

---

## 📐 System Architecture Diagram

```
[User — Web Browser Frontend]
        │  HTTPS REST API
        ▼
[FastAPI Backend — Railway Container]
        │
        ├── POST /api/upload
        │       └─▶ pipeline.run() [BackgroundTask]
        │               ├─▶ load()   — PyMuPDF / Docx2txt / TextLoader / Tesseract OCR
        │               ├─▶ split()  — RecursiveCharacterTextSplitter + metadata
        │               └─▶ store()  — QdrantVectorStore + mongo.save_chunks()
        │
        ├── POST /api/query
        │       ├─▶ retrieve_documents()
        │       │       ├─▶ Qdrant semantic search (top 20)
        │       │       ├─▶ MongoDB $text search   (top 20)
        │       │       ├─▶ EnsembleRetriever (RRF merge)
        │       │       └─▶ CohereRerank v3.5       (top 10)
        │       └─▶ generate_liberal_answer() | generate_strict_answer()
        │               ├─▶ LCEL Chain: Prompt → ChatGroq → StrOutputParser
        │               └─▶ verify_claim() [PubMed / arXiv APIs]
        │
        └── GET /api/chunks/{id}/highlight
                └─▶ PyMuPDF render page → yellow highlight → base64 PNG

┌───────────────────────────────┐               ┌───────────────────────────────┐
│         Qdrant Cloud          │               │         MongoDB Atlas         │
│  Vectors (1024-dim similarity)│               │ Full Chunks + Metadata + Text │
└───────────────────────────────┘               └───────────────────────────────┘
```

---

## 🏁 Completed Implementation Phases

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Document ingestion — LangChain pipeline (load → split → embed → store) | ✅ Complete |
| **Phase 2** | Hybrid retrieval (Qdrant + MongoDB) + Cohere Rerank v3.5 | ✅ Complete |
| **Phase 3A** | Strict Mode — evidence-only, confidence scoring, claim verification | ✅ Complete |
| **Phase 3B** | Liberal Mode — document answer + general AI explanation | ✅ Complete |
| **Phase 4** | Frontend — modern dark-mode SPA (HTML/CSS/JS) | ✅ Complete |
| **Phase 5** | Observability — LangSmith `@traceable` on all pipeline functions | ✅ Complete |
| **Phase 6** | PDF chunk highlighter — multi-strategy snippet search + PNG export | ✅ Complete |
| **Phase 7** | Dockerization & Docker Compose setup (non-root security & health checks) | ✅ Complete |
| **Phase 8** | Production deployment on Railway with cloud persistent databases | ✅ Complete |

---

## 🔒 Architectural Principles & Design Rules

1. **Zero Hallucination in Strict Mode:** If retrieval confidence is below threshold (`0.30`), refuse to answer.
2. **Mandatory Page-Level Citations:** Every Strict Mode answer must reference exact document chunks with page numbers.
3. **Hybrid RRF + Cloud Reranking:** All retrievals combine Qdrant semantic vectors with MongoDB keyword text matching, then reranked via Cohere.
4. **Resilient Startup & Safe Fallbacks:** Module imports handle missing keys gracefully without crashing container startup.
5. **Persistent Cloud Storage:** Vector embeddings and chunk text live permanently in Qdrant Cloud & MongoDB Atlas.

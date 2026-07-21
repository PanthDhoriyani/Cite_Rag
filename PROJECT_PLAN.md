# CiteRag — Project Overview

> Citation-Aware Hybrid RAG Platform  
> Built with LangChain · FastAPI · Qdrant Cloud · MongoDB Atlas · Groq

---

## What It Does

A trustworthy AI evidence-retrieval platform that:

- Accepts document uploads (PDF, DOCX, TXT)
- Ingests them through a LangChain pipeline: load → chunk → embed → store
- Retrieves relevant chunks via hybrid semantic + keyword search with cross-encoder reranking
- Generates cited answers using Groq LLM via LCEL chains
- Two answer modes: **Strict** (citation-mandatory, confidence-scored) and **Liberal** (educational)
- Highlights cited text on rendered PDF pages in the browser

---

## Final Tech Stack

| Layer | Technology |
|---|---|
| Web API | FastAPI (Python 3.12) |
| Frontend | Vanilla HTML / CSS / JS (single file, no build step) |
| RAG Framework | LangChain |
| PDF Loading | PyMuPDFLoader + Tesseract OCR fallback |
| DOCX Loading | Docx2txtLoader |
| Chunking | RecursiveCharacterTextSplitter (512 / 128 overlap) |
| Embeddings | HuggingFaceEmbeddings — `BAAI/bge-large-en-v1.5` (1024-dim) |
| Vector DB | QdrantVectorStore (Qdrant Cloud) |
| Keyword Search | MongoDB native `$text` index |
| Metadata DB | MongoDB Atlas (pymongo) |
| Hybrid Retrieval | EnsembleRetriever (Qdrant + custom MongoDBTextRetriever) via RRF |
| Reranking | ContextualCompressionRetriever + CrossEncoderReranker (`bge-reranker-large`) |
| LLM | ChatGroq — `llama-3.1-8b-instant` |
| Chain | LCEL — LangChain Expression Language |
| Observability | LangSmith (full pipeline tracing via `@traceable`) |
| PDF Rendering | PyMuPDF (fitz) — text search, highlight annotation, PNG export |
| Deployment | Docker → Railway (backend) + Netlify (frontend) |

---

## System Architecture

```
[User — Netlify Frontend]
        │  HTTPS
        ▼
[FastAPI Backend — Railway / Docker]
        │
        ├── POST /api/upload
        │       └─▶ pipeline.run() [BackgroundTask]
        │               ├─▶ load()   — PyMuPDF / Docx2txt / TextLoader
        │               ├─▶ split()  — RecursiveCharacterTextSplitter + metadata
        │               └─▶ store()  — QdrantVectorStore + mongo.save_chunks()
        │
        ├── POST /api/query
        │       ├─▶ retrieve_documents()
        │       │       ├─▶ Qdrant semantic search (top 20)
        │       │       ├─▶ MongoDB $text search   (top 20)
        │       │       ├─▶ EnsembleRetriever (RRF merge)
        │       │       └─▶ CrossEncoderReranker   (top 10)
        │       └─▶ generate_liberal_answer() | generate_strict_answer()
        │               └─▶ LCEL Chain: Prompt → ChatGroq → StrOutputParser
        │
        └── GET /api/chunks/{id}/highlight
                └─▶ PyMuPDF render page → highlight → base64 PNG

[Qdrant Cloud]          [MongoDB Atlas]
  Vectors (1024-dim)      Chunks + Metadata + Document status
```

---

## Completed Phases

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Document ingestion — LangChain pipeline (load → split → embed → store) | ✅ Complete |
| **Phase 2** | Hybrid retrieval + cross-encoder reranking | ✅ Complete |
| **Phase 3A** | Strict Mode — evidence-only, confidence scoring, claim verification | ✅ Complete |
| **Phase 3B** | Liberal Mode — document answer + AI explanation | ✅ Complete |
| **Phase 4** | Frontend — dark-mode SPA (HTML/CSS/JS) | ✅ Complete |
| **Phase 5** | Observability — LangSmith `@traceable` on all pipeline functions | ✅ Complete |
| **Phase 6** | PDF chunk highlighter — render + annotate PDF pages as base64 PNG | ✅ Complete |
| **Phase 7** | Production deployment — Docker, Railway, Netlify | ✅ Complete |

---

## Key Design Rules

1. **Never hallucinate in Strict Mode** — if `sigmoid(logit) < 0.30`, return rejection message
2. **Every Strict Mode answer must cite a source chunk** — citations are the core feature
3. **Always rerank** — EnsembleRetriever output always passes through CrossEncoderReranker
4. **Liberal Mode must label sections** — never silently blend document + AI content
5. **Metadata captured at ingestion** — `page_number` cannot be reconstructed after splitting
6. **Always overlap chunks** — 128-char overlap prevents context loss at boundaries
7. **Config in `.env` only** — `config.py` is the single import point for all settings
8. **Public verification is domain-specific** — PubMed for `healthcare`, arXiv for `research`
9. **Frontend is stateless** — backend URL stored in `localStorage`, no server-side sessions

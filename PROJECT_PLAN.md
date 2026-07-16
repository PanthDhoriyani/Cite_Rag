# CiteRag — Project Plan
> Citation-Aware RAG Platform
> Built with LangChain as the core RAG framework.

---

## What We Are Building

A trustworthy AI evidence-retrieval platform that:
- Accepts document uploads (PDF, DOCX, TXT)
- Stores them across Qdrant Cloud (vector embeddings) and MongoDB Atlas (full chunk text, metadata, and full-text keyword index)
- Retrieves relevant chunks using hybrid semantic (Qdrant) + keyword (MongoDB) search
- Reranks results with a cross-encoder
- Generates cited answers via the cloud-hosted Groq API
- Two answer modes: Strict (citation-mandatory) and Liberal (educational)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web API | FastAPI (Python) |
| RAG Framework | LangChain |
| PDF Loading | PyMuPDFLoader (LangChain community) |
| OCR | Tesseract + Pillow (scanned PDF fallback) |
| DOCX | Docx2txtLoader (LangChain community) |
| Chunking | RecursiveCharacterTextSplitter (LangChain) |
| Embeddings | HuggingFaceEmbeddings — BAAI/bge-large-en-v1.5 |
| Vector DB | QdrantVectorStore (langchain-qdrant, Cloud) |
| Keyword Search | MongoDB Full-Text ($text Search Index, Cloud) |
| Metadata DB | MongoDB (pymongo, Cloud) |
| Hybrid Retrieval | EnsembleRetriever (LangChain: Qdrant + Custom MongoDB Text Retriever) |
| Reranking | ContextualCompressionRetriever + CrossEncoderReranker |
| LLM | ChatGroq — llama-3.1-8b-instant (langchain-groq) |
| Chain | LCEL — LangChain Expression Language |
| Observability | LangSmith Dashboard (full pipeline tracing) |
| PDF Rendering | PyMuPDF (fitz) text-search highlight & PNG exporter |
| Frontend | Streamlit Web Dashboard (Python, Phase 4) |
| Deployment | Docker + Docker Compose (Phase 5) |

---

## System Architecture

```
[User Uploads Document]
        |
        v
[FastAPI Upload Endpoint]
  - validate format + size
  - save file to disk
  - create MongoDB record (status=processing)
  - trigger BackgroundTask -> pipeline.run()
        |
        v
[pipeline.py — Ingestion Pipeline]
  - PyMuPDFLoader (or OCR fallback)
  - RecursiveCharacterTextSplitter (512/128)
  - HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)
  - QdrantVectorStore.add_texts()     <- semantic vectors
  - mongo.save_chunks()               <- full text + native text index
  - mongo.update_status("ready")
        |
        +----------+----------+
     [Qdrant]              [MongoDB]
     Vectors         Full Text & Text Index
        |
        v
[User Asks Question]
        |
        v
[retrieval.py — Hybrid Retrieval]
  - EnsembleRetriever
      QdrantVectorStore.as_retriever() -> top 20 semantic
      MongoDBTextRetriever (BM25 search) -> top 20 keyword
      merged + deduplicated by RRF     -> ~40 chunks
  - ContextualCompressionRetriever
      CrossEncoderReranker (bge-reranker-large)
      -> top 10 chunks
        |
        v
[generation.py — LangChain LCEL Chain]
    /                    \
[STRICT MODE]        [LIBERAL MODE]
Evidence check       Doc answer first
Confidence score     Then AI explanation
Refuse if < 0.65     Label sections clearly
Strict LLM prompt    Liberal LLM prompt
ChatGroq            ChatGroq
    \                    /
        |
        v
[Structured Response]
  answer + citations + confidence (strict only)
```

---

## Phase 1 — Document Ingestion (LangChain)

**Goal:** Load files → chunk → embed → store in Qdrant Cloud + MongoDB Atlas

**File:** `backend/pipeline.py`

**Steps:**
1. `load()` — PyMuPDFLoader / Docx2txtLoader / TextLoader → Documents with page metadata
2. `split()` — RecursiveCharacterTextSplitter + inject chunk_id, document_id, domain, page_number
3. `store()` — QdrantVectorStore + MongoDB
4. `run()` — called as BackgroundTask, orchestrates 1→2→3

**Endpoints in `routers/upload.py`:**
- `POST /api/upload` → validate, save, trigger pipeline.run()
- `GET /api/documents` → list all docs with status
- `DELETE /api/documents/{id}` → remove from both databases

---

## Phase 2 — Hybrid Retrieval + Reranking (LangChain)

**Goal:** Question → best top-10 chunks via hybrid search + reranking

**File:** `backend/retrieval.py`

**Steps:**
1. `QdrantVectorStore.as_retriever(k=20)` → semantic search
2. `MongoDBTextRetriever` (custom retriever query `$text`) → keyword search
3. `EnsembleRetriever([qdrant, mongodb], weights=[0.5, 0.5])` → merge
4. `ContextualCompressionRetriever(CrossEncoderReranker, ensemble)` → rerank → top 10

**Function:** `retrieve_documents(question, filters) -> list[Document]`

---

## Phase 3B — Liberal Mode (LangChain LCEL)

**Goal:** Document answer + AI explanation, clearly labeled

**File:** `backend/generation.py`

**Chain:**
```
LIBERAL_PROMPT | ChatGroq | StrOutputParser
```

**Output format:**
```
DOCUMENT-BASED ANSWER: [from context]
ADDITIONAL EXPLANATION: [from AI knowledge]
```

---

## Phase 3A — Strict Mode (LangChain LCEL)

**Goal:** Evidence-only, citations required, confidence scored, refuses if weak

**File:** `backend/generation.py`

**Steps:**
1. Check top chunk score vs CONFIDENCE_THRESHOLD (0.65) → reject if below
2. Calculate confidence = average of top 3 chunk scores
3. STRICT_PROMPT | ChatGroq | StrOutputParser
4. Return answer + citations + confidence

**Optional:** `verifier.py` — calls PubMed / arXiv APIs to cross-verify claims based on document domain

---

## Phase 4 — Frontend (Streamlit)

**Goal:** Web UI for uploading docs, scoping searches, and asking questions.

**File:** `backend/frontend.py`

**Layout:**
- **Sidebar (Upload & Docs):** File drag-drop, domain picker, polling document list with status indicators and search scoping check boxes, deletion controls.
- **Main Workspace:** Mode selector radio toggle, chat inputs, formatted Strict Mode responses (progress confidence meter, references expander cards) and Liberal Mode responses (styled document evidence and AI explanation blocks).

---

## Phase 5 — Docker

**Goal:** `docker-compose up` starts everything

```
Services:
  backend        -> port 8000
  frontend       -> port 8501 (Streamlit)
  qdrant         -> port 6333
  mongodb        -> port 27017
  # No local LLM service required (uses cloud Groq API)
```

---

## Phase 6 — Testing & Tuning

- Upload test PDFs across all 7 domains
- Run queries in both modes
- Tune CHUNK_SIZE, CONFIDENCE_THRESHOLD
- Test public API verification (Phase 3A)
- Full frontend UX check

---

## Folder Structure

```
CiteRag/
  backend/
    main.py           <- FastAPI entry point
    config.py         <- all .env settings (including LangSmith)
    schemas.py        <- Pydantic models
    pipeline.py       <- LangChain ingestion (traced)
    retrieval.py      <- LangChain retrieval + reranking (traced)
    generation.py     <- LangChain LCEL chains (traced)
    verifier.py       <- Medical / research claim verification (traced)
    test_langsmith.py <- LangSmith diagnostics script
    frontend.py       <- Streamlit dashboard (Python client)
    routers/
      __init__.py
      upload.py       <- upload + chunk highlight endpoint
      query.py        <- query endpoint
    db/
      __init__.py
      mongo_client.py <- MongoDB client, text indexing & chunk lookup
    requirements.txt  <- dependencies (including langsmith)
  .env                <- secrets (Git ignored)
  .env.example        <- template
  .gitignore
  implementation_plan.md
  project_flow.md
  about.md
  PROJECT_PLAN.md
```

---

## Key Design Rules

1. **Never hallucinate in Strict Mode** — if confidence < 0.65, return rejection message
2. **Every Strict Mode answer must cite a chunk** — citation is the core feature
3. **Always rerank** — EnsembleRetriever output always passes through CrossEncoderReranker
4. **Liberal Mode must label sections** — never silently blend document + AI content
5. **Metadata captured at ingestion** — page_number cannot be reconstructed after splitting
6. **Always overlap chunks** — 128 char overlap, never zero
7. **Config in .env only** — config.py is the single import point
8. **Public verification is domain-specific** — PubMed for healthcare, arXiv for research

---

## Build Order

```
1  Setup: .env, requirements.txt, .gitignore
2  config.py
3  schemas.py
4  db/mongo_client.py (automatic full-text indexing & chunk lookup)
5  main.py
6  pipeline.py (LangChain ingestion Qdrant + Mongo)
7  routers/upload.py (FastAPI upload, status & highlight endpoints)
8  Install + test Phase 1 (upload PDF, check status=ready)
9  retrieval.py (LangChain retrieval Qdrant + MongoDBTextRetriever + reranking)
10 generation.py (LCEL liberal + strict chains)
11 routers/query.py
12 End-to-end test: upload -> query -> cited answer
13 Streamlit Frontend (Phase 4)
14 Observability & Tracing (Phase 5 - LangSmith Integration)
15 PDF Highlighting & Inline Viewer (Phase 6)
```

---

## Current Status

| Phase | Status |
|---|---|
| Phase 1 — Ingestion (LangChain) | Completed ✅ |
| Phase 2 — Retrieval + Reranking | Completed ✅ |
| Phase 3B — Liberal Mode | Completed ✅ |
| Phase 3A — Strict Mode | Completed ✅ |
| Phase 4 — Frontend (Streamlit) | Completed ✅ |
| Phase 5 — Observability (LangSmith) | Completed ✅ |
| Phase 6 — PDF Chunk Highlight | Completed ✅ |

---

*Last updated: Observability & PDF Highlight release — 2026-07-16*

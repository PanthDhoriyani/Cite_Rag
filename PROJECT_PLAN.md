# CiteRag — Project Plan
> Citation-Aware RAG Platform
> Built with LangChain as the core RAG framework.

---

## What We Are Building

A trustworthy AI evidence-retrieval platform that:
- Accepts document uploads (PDF, DOCX, TXT)
- Stores them across three databases via LangChain integrations
- Retrieves relevant chunks using hybrid BM25 + semantic search
- Reranks results with a cross-encoder
- Generates cited answers via a local LLM (Ollama)
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
| Vector DB | QdrantVectorStore (langchain-qdrant) |
| Keyword Search | ElasticsearchStore BM25 (langchain-elasticsearch) |
| Metadata DB | MongoDB (pymongo) |
| Hybrid Retrieval | EnsembleRetriever (LangChain) |
| Reranking | ContextualCompressionRetriever + CrossEncoderReranker |
| LLM | OllamaLLM — llama3:8b (langchain-ollama) |
| Chain | LCEL — LangChain Expression Language |
| Frontend | React + Tailwind CSS (Phase 4) |
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
[pipeline.py — LangChain Ingestion]
  - PyMuPDFLoader (or OCR fallback)
  - RecursiveCharacterTextSplitter (512/128)
  - HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)
  - QdrantVectorStore.add_texts()     <- semantic vectors
  - ElasticsearchStore.add_texts()    <- BM25 index
  - mongo.save_chunks()               <- full text for citations
  - mongo.update_status("ready")
        |
        +----------+----------+
     [Qdrant]  [Elasticsearch]  [MongoDB]
     Vectors      BM25 Index    Full Text
        |
        v
[User Asks Question]
        |
        v
[retrieval.py — LangChain Hybrid Retrieval]
  - EnsembleRetriever
      QdrantVectorStore.as_retriever() -> top 20 semantic
      ElasticsearchRetriever (BM25)    -> top 20 keyword
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
OllamaLLM            OllamaLLM
    \                    /
        |
        v
[Structured Response]
  answer + citations + confidence (strict only)
```

---

## Phase 1 — Document Ingestion (LangChain)

**Goal:** Load files → chunk → embed → store in 3 databases

**File:** `backend/pipeline.py`

**Steps:**
1. `load()` — PyMuPDFLoader / Docx2txtLoader / TextLoader → Documents with page metadata
2. `split()` — RecursiveCharacterTextSplitter + inject chunk_id, document_id, domain, page_number
3. `store()` — QdrantVectorStore + ElasticsearchStore + MongoDB
4. `run()` — called as BackgroundTask, orchestrates 1→2→3

**Endpoints in `routers/upload.py`:**
- `POST /api/upload` → validate, save, trigger pipeline.run()
- `GET /api/documents` → list all docs with status
- `DELETE /api/documents/{id}` → remove from all 3 databases

---

## Phase 2 — Hybrid Retrieval + Reranking (LangChain)

**Goal:** Question → best top-10 chunks via hybrid search + reranking

**File:** `backend/retrieval.py`

**Steps:**
1. `QdrantVectorStore.as_retriever(k=20)` → semantic search
2. `ElasticsearchRetriever` with BM25 body → keyword search
3. `EnsembleRetriever([qdrant, es], weights=[0.5, 0.5])` → merge
4. `ContextualCompressionRetriever(CrossEncoderReranker, ensemble)` → rerank → top 10

**Function:** `retrieve(question, filters) -> list[Document]`

---

## Phase 3B — Liberal Mode (LangChain LCEL)

**Goal:** Document answer + AI explanation, clearly labeled

**File:** `backend/generation.py`

**Chain:**
```
LIBERAL_PROMPT | OllamaLLM | StrOutputParser
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
3. STRICT_PROMPT | OllamaLLM | StrOutputParser
4. Return answer + citations + confidence

**Optional:** `verifier.py` — calls PubMed / arXiv / legal APIs to cross-verify claims

---

## Phase 4 — Frontend (React)

**Goal:** Web UI for uploading docs and asking questions

**Components:**
- `UploadZone.jsx` — drag-drop + domain selector + progress bar
- `ModeToggle.jsx` — Strict ↔ Liberal toggle
- `QueryInput.jsx` — question input box
- `StrictAnswerView.jsx` — answer + citation cards + confidence bar
- `LiberalAnswerView.jsx` — two-panel: document answer + AI explanation
- `DocumentManager.jsx` — list docs + delete

---

## Phase 5 — Docker

**Goal:** `docker-compose up` starts everything

```
Services:
  backend        -> port 8000
  frontend       -> port 3000
  qdrant         -> port 6333
  mongodb        -> port 27017
  elasticsearch  -> port 9200
  ollama         -> port 11434
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
    config.py         <- all .env settings
    schemas.py        <- Pydantic models
    pipeline.py       <- LangChain ingestion
    retrieval.py      <- LangChain retrieval + reranking
    generation.py     <- LangChain LCEL chains
    routers/
      __init__.py
      upload.py
      query.py
    db/
      __init__.py
      mongo_client.py <- MongoDB only
    requirements.txt
  frontend/           <- React (Phase 4)
  .env                <- secrets
  .env.example        <- template
  .gitignore
  docker-compose.yml  <- Phase 5
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
8. **Public verification is domain-specific** — PubMed for healthcare, not for legal

---

## Build Order

```
1  Setup: .env, requirements.txt, .gitignore
2  config.py
3  schemas.py
4  db/mongo_client.py
5  main.py
6  pipeline.py (LangChain ingestion)
7  routers/upload.py
8  Install + test Phase 1 (upload PDF, check status=ready)
9  retrieval.py (LangChain retrieval + reranking)
10 generation.py (LCEL liberal + strict chains)
11 routers/query.py
12 End-to-end test: upload -> query -> cited answer
13 Frontend (Phase 4)
14 Docker (Phase 5)
15 Testing & Tuning (Phase 6)
```

---

## Current Status

| Phase | Status |
|---|---|
| Phase 1 — Ingestion (LangChain) | Building |
| Phase 2 — Retrieval + Reranking | Next |
| Phase 3B — Liberal Mode | After Phase 2 |
| Phase 3A — Strict Mode | After Phase 3B |
| Phase 4 — Frontend | After Phase 3 |
| Phase 5 — Docker | After Phase 4 |
| Phase 6 — Testing | Last |

---

*Last updated: LangChain rewrite — 2026-07-14*

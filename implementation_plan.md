# CiteRag — Implementation Plan (LangChain-Based)
> Full plan for rebuilding CiteRag using LangChain as the core RAG framework.
> Read this before touching any code.

---

## What We Are Building

A **RAG system** with two answer modes:
- **Liberal Mode** — answers from the document + broader AI explanation
- **Strict Mode** — evidence-only answers, citations mandatory, confidence scored

**Core RAG flow:**
```
Upload file
  → LangChain Loader (PDF/DOCX/TXT)
  → LangChain Splitter (512 chunks, 128 overlap)
  → LangChain HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)
  → QdrantVectorStore (semantic vectors)
  → MongoDB (full text + status tracking + text search index)

Ask question
  → EnsembleRetriever (Qdrant 50% + MongoDB Text search 50%)
  → ContextualCompressionRetriever (CrossEncoder reranker)
  → LCEL Chain: context | prompt | ChatGroq | output
  → Return answer + citations
```

---

## Project Folder Structure

```
CiteRag/
  backend/
    main.py           <- FastAPI app, CORS, routes
    config.py         <- all settings from .env (one place)
    schemas.py        <- Pydantic request/response models
    pipeline.py       <- LangChain ingestion (load + split + store)
    retrieval.py      <- LangChain retrieval (Qdrant + ES + rerank)
    generation.py     <- LangChain LCEL chains (liberal + strict answers)
    routers/
      __init__.py
      upload.py       <- POST /api/upload, GET/DELETE /api/documents
      query.py        <- POST /api/query
    db/
      __init__.py
      mongo_client.py <- MongoDB (document status + chunk text for citations)
    requirements.txt
  .env                <- all secrets/keys (never commit this)
  .env.example        <- template (safe to commit)
  .gitignore
  implementation_plan.md   <- this file
  project_flow.md          <- step-by-step what code goes where
  about.md                 <- technologies explained
  PROJECT_PLAN.md          <- original project spec
```

---

## Technologies Used

| Layer | Tool | Why |
|---|---|---|
| Web API | FastAPI | Fast, async, auto-docs, BackgroundTasks |
| RAG Framework | LangChain | Loaders, splitters, retrievers, chains |
| PDF Loading | PyMuPDFLoader (LangChain) | Page-by-page text with metadata |
| OCR Fallback | pytesseract + Pillow | Scanned PDFs where text < 100 chars |
| DOCX Loading | Docx2txtLoader (LangChain) | Word document support |
| Chunking | RecursiveCharacterTextSplitter | 512 chars, 128 overlap |
| Embedding | HuggingFaceEmbeddings - BAAI/bge-large-en-v1.5 | 1024-dim, normalized |
| Vector DB | QdrantVectorStore (LangChain) | Semantic nearest-neighbour search |
| Keyword Search | MongoDB Full-Text ($text Search) | Exact keyword matching (no ES cost) |
| Metadata Store | MongoDB (pymongo) | Document status, chunk text for citations |
| Retriever Merge | EnsembleRetriever (LangChain) | Combines Qdrant + MongoDB 50/50 |
| Reranking | ContextualCompressionRetriever + CrossEncoderReranker | BAAI/bge-reranker-large |
| LLM | ChatGroq (LangChain) | Groq API (llama-3.1-8b-instant), free and fast |
| Chain | LCEL pipe operator | retriever | prompt | LLM | parser |

---

## Python Packages to Install

```txt
# LangChain Core
langchain
langchain-core
langchain-community
langchain-text-splitters

# LangChain Integrations
langchain-huggingface==0.1.2
# Qdrant: vector database store + retriever
langchain-qdrant==0.2.0
# Groq: cloud LLM API for answer generation (Phase 3)
langchain-groq==0.2.4

# ML Models
# Runs BAAI/bge-large-en-v1.5 (embedding) and bge-reranker-large (reranking)
sentence-transformers==3.4.1

# PDF + Doc Extraction
pymupdf
pytesseract
Pillow
docx2txt

# Databases
qdrant-client
pymongo

# FastAPI
fastapi
uvicorn[standard]
python-multipart
pydantic

# Utilities
python-dotenv
loguru
httpx
aiofiles
```

---

## .env Keys

```env
# Databases
MONGODB_URL=mongodb://localhost:27017
QDRANT_URL=http://localhost:6333
GROQ_API_KEY=your_groq_api_key_here

# Models
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama-3.1-8b-instant

# Pipeline
CHUNK_SIZE=512
CHUNK_OVERLAP=128
BM25_TOP_K=20
VECTOR_TOP_K=20
RERANKER_TOP_K=10
CONFIDENCE_THRESHOLD=0.65

# Upload
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=50
```

---

## File-by-File Plan

### config.py
Read all .env values. Every other file imports from here. No os.getenv() anywhere else.

### schemas.py
Pydantic models:
- Domain enum: legal, research, healthcare, technical, compliance, education, general
- UploadResponse: document_id, filename, status, message
- QueryRequest: question, mode, document_ids, domain
- QueryResponse: question, mode, answer, citations, confidence, status

### pipeline.py - LangChain Ingestion
Three functions called in order:

load(file_path, file_type)
  - PyMuPDFLoader for PDF -> returns Documents with page metadata
  - If total text < 100 chars -> Tesseract OCR fallback
  - Docx2txtLoader for DOCX
  - TextLoader for TXT

split(docs, doc_meta)
  - RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)
  - Injects: chunk_id, document_id, domain, page_number, chunk_index into each chunk metadata

store(chunks)
  - QdrantVectorStore.add_texts() -> vectors + metadata
  - mongo.save_chunks() -> full chunk text + metadata + native text index

run(document_id, file_path, filename, file_type, domain, upload_timestamp)
  - Called as FastAPI BackgroundTask
  - load -> split -> store -> mongo.update_status("ready")
  - On any error: mongo.update_status("failed")

### retrieval.py - LangChain Retrieval
get_qdrant_retriever(filters)
  - QdrantVectorStore.as_retriever(k=20)

get_mongodb_retriever()
  - Custom MongoDBTextRetriever wrapping MongoDB $text search operator

get_reranker()
  - HuggingFaceCrossEncoder(BAAI/bge-reranker-large)
  - CrossEncoderReranker(top_n=10)

retrieve(question, filters)
  - EnsembleRetriever([qdrant, mongodb_retriever], weights=[0.5, 0.5])
  - ContextualCompressionRetriever(reranker, ensemble)
  - Returns: top 10 Document objects with relevance scores

### generation.py - LangChain LCEL Chains
Liberal prompt: document answer first, then AI explanation labeled separately
Strict prompt: evidence only, refuse if confidence < 0.65

answer(question, mode, filters)
  - docs = retrieve(question, filters)
  - context = format_docs(docs)
  - if strict: check top score < CONFIDENCE_THRESHOLD -> return rejection
  - (prompt | ChatGroq | StrOutputParser()).invoke({context, question})
  - Return: {answer, citations, confidence}

### db/mongo_client.py
LangChain handles Qdrant and ES. MongoDB handles:
- save_document() - create record status="processing"
- update_status() - processing -> ready / failed
- save_chunks() - full chunk text for citation display
- get_chunks(ids) - fetch chunk text when needed
- all_documents() - list all for GET /api/documents
- remove_document() - delete on DELETE endpoint

### routers/upload.py
- POST /api/upload: validate, save file, save_document(), BackgroundTask(pipeline.run())
- GET /api/documents: mongo.all_documents()
- DELETE /api/documents/{id}: remove from Qdrant + Mongo in background

### routers/query.py
- POST /api/query: call generation.answer(question, mode, filters)
- Return QueryResponse with answer + citations + confidence

### main.py
- FastAPI app with lifespan
- CORSMiddleware (allow localhost:3000)
- Include upload + query routers
- GET /api/health

---

## Build Order (Follow This Exactly)

```
Step 1  Create: .env, .env.example, .gitignore, requirements.txt
Step 2  Create: backend/config.py
Step 3  Create: backend/schemas.py
Step 4  Create: backend/db/__init__.py + backend/db/mongo_client.py
Step 5  Create: backend/routers/__init__.py
Step 6  Create: backend/main.py
Step 7  Create: backend/pipeline.py (LangChain ingestion)
Step 8  Create: backend/routers/upload.py
Step 9  Install packages in venv, verify imports
Step 10 Create: backend/retrieval.py (LangChain retrievers + reranker)
Step 11 Create: backend/generation.py (LCEL chains, liberal + strict)
Step 12 Create: backend/routers/query.py (wire retrieval + generation)
Step 13 Verify all imports clean
Step 14 Git init + push to GitHub
```

---

## Key Rules

1. All DB keys in .env only, imported via config.py
2. Simple functions, no factory classes, no enterprise patterns
3. LangChain handles: loading, splitting, embedding, vector store, BM25, retrieval, reranking, LLM chains
4. MongoDB handles only: document status tracking + full chunk text for citations
5. Embeddings loaded once as module-level object in pipeline.py, reused in retrieval.py
6. Reranker loaded once as module-level singleton in retrieval.py
7. Strict Mode: confidence < 0.65 -> return "Insufficient evidence" - never generate
8. Liberal Mode: always label sections clearly (document vs AI)

---

Status: Completed up to Phase 4 (Streamlit Frontend UI). Next is Phase 5 (Docker).

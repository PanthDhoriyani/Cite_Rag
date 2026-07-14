# CiteRag — About: Technologies Used
> **Simple explanations of every tool, model, and database used in the project.**
> Written so anyone can understand what each piece does and why we chose it.

---

## What is CiteRag?

CiteRag is a **RAG system** — Retrieval-Augmented Generation.

That means: instead of asking an AI to answer from memory, we first **search our own uploaded documents**, find the most relevant pieces, and then let the AI answer **only using that evidence**.

This makes answers trustworthy because every statement can be traced back to a real source.

```
You upload a document
       ↓
You ask a question
       ↓
System finds the best matching paragraphs in your document
       ↓
AI reads those paragraphs and gives a cited, grounded answer
```

---

## 🏗️ Framework & Web Layer

### FastAPI
**What it is:** The web framework that powers the backend API.

**What it does in CiteRag:**
- Listens for HTTP requests (`/api/upload`, `/api/query`, `/api/health`, etc.)
- Validates incoming data automatically using Pydantic models
- Handles file uploads (PDF, DOCX, TXT)
- Runs background tasks (ingestion pipeline) without blocking the response

**Why we chose it:** FastAPI is the fastest Python web framework, has automatic API documentation, and has built-in `BackgroundTasks` so we can return a response to the user immediately while ingestion runs in the background.

---

### Uvicorn
**What it is:** The web server that runs FastAPI.

**What it does:** Starts the server, handles connections, and makes the API accessible at `http://localhost:8000`.

**Think of it like:** The engine that makes the car (FastAPI) actually drive.

---

### Pydantic
**What it is:** A data validation library for Python.

**What it does in CiteRag:**
- Defines the shape of every data object: `ChunkMetadata`, `DocumentInfo`, `UploadResponse`, etc.
- Automatically validates that all required fields are present and the right type
- Converts Python objects to/from JSON for API responses

**Why we chose it:** FastAPI is built on Pydantic, so they work together perfectly. No manual JSON parsing needed.

---

## 📄 Document Extraction

### PyMuPDF (fitz)
**What it is:** A fast PDF reading library.

**What it does in CiteRag:**
- Opens PDF files and extracts text from each page separately
- Runs first on every PDF because it's very fast and accurate for normal (digital) PDFs
- Also used to render PDF pages as images for Tesseract OCR

**Why we use PyMuPDF first:** Digital PDFs have their text embedded directly — PyMuPDF extracts it in milliseconds without needing to "read" the image.

---

### Tesseract OCR (via pytesseract + Pillow)
**What it is:** An Optical Character Recognition (OCR) engine that reads text from images.

**What it does in CiteRag:**
- Kicks in automatically when PyMuPDF returns less than 100 characters (which means the PDF is a scanned image, not a text-based PDF)
- Renders each PDF page as a high-resolution (300 DPI) PNG image
- Passes that image to Tesseract to "read" the text like a human would

**Why we use it as fallback:** Scanned PDFs are just pictures of text. PyMuPDF can't extract text from pictures — Tesseract can.

---

### python-docx
**What it is:** A library for reading Microsoft Word `.docx` files.

**What it does in CiteRag:**
- Opens DOCX files and reads all paragraphs
- Filters out empty lines, joins the rest into a single text block

---

## ✂️ Text Chunking

### LangChain — RecursiveCharacterTextSplitter
**Package:** `langchain_text_splitters`

**What it is:** A smart text splitter from the LangChain library.

**What it does in CiteRag:**
- Takes the extracted text from each page
- Splits it into smaller **chunks** of ~512 characters
- Each chunk overlaps with the next by ~128 characters (so context isn't lost at boundaries)
- Tries to split at natural breaks first: paragraph → line → word → character

**Why chunking is needed:** AI embedding models have a token limit. A 100-page PDF can't be sent as one block. We split it into small pieces so each piece can be embedded and searched individually.

**Why overlap matters:** If a sentence starts at the end of chunk 5 and finishes at the start of chunk 6, without overlap that sentence is split. With 128-token overlap, both chunks contain that sentence, so neither chunk loses the context.

```
Chunk 1: [----512 chars----]
Chunk 2:             [----512 chars----]
                  ↑ 128 chars overlap
```

---

## 🧠 Embedding Model

### BAAI/bge-large-en-v1.5
**What it is:** A state-of-the-art sentence embedding model made by the Beijing Academy of Artificial Intelligence (BAAI).

**What it does in CiteRag:**
- Takes a piece of text (a chunk or a user question) and converts it into a list of **1024 numbers** (called a vector or embedding)
- Two pieces of text that are **semantically similar** (same meaning, even different words) will have vectors that are **close together** in space

**Why 1024 numbers?** Think of it like placing the text in a 1024-dimensional map. Similar texts land near each other on this map.

**Example:**
- "Heart failure treatment" and "therapy for cardiac arrest" → vectors very close together
- "Heart failure treatment" and "tax law" → vectors far apart

**Why we normalize the embeddings:** BGE models work best with L2-normalized vectors. Normalizing makes the cosine similarity calculation accurate.

**Why it's a singleton (loaded once):** Loading the model takes 3–5 seconds. We load it once at first use and keep it in memory forever — every subsequent embedding is instant.

**Library used:** `sentence-transformers`

---

## 🗄️ Databases (Three Storage Backends)

CiteRag uses **three databases at the same time**, each serving a different purpose. This is called a hybrid retrieval architecture.

```
Every chunk is stored in all three simultaneously:
  ┌─────────────┬──────────────────────────────────┬───────────────────────┐
  │  Database   │  What it stores                  │  Used for             │
  ├─────────────┼──────────────────────────────────┼───────────────────────┤
  │  Qdrant     │  Embedding vectors               │  Semantic search      │
  │  MongoDB    │  Full chunk text + metadata      │  Storage & retrieval  │
  │  Elasticsearch│  Chunk text (keyword indexed) │  BM25 keyword search  │
  └─────────────┴──────────────────────────────────┴───────────────────────┘
```

---

### Qdrant
**What it is:** A vector database — a database built specifically for storing and searching embedding vectors.

**What it does in CiteRag:**
- Stores each chunk as a **point**: `{ id: chunk_id, vector: [1024 floats], payload: metadata }`
- When a user asks a question, we embed the question and ask Qdrant: "find me the 20 chunks whose vectors are closest to this question vector"
- This is called **semantic search** — it finds chunks with similar *meaning*, not just matching words

**Why Qdrant specifically:** It's purpose-built for vector search, much faster than doing vector similarity in a regular database, supports metadata filtering (e.g. filter by domain), and is open-source.

**Collection settings:**
- Name: `"documents"`
- Dimension: `1024` (matches BGE model output)
- Distance: `COSINE` (measures angle between vectors — best for normalized embeddings)

---

### MongoDB
**What it is:** A document database — stores data as flexible JSON-like documents.

**What it does in CiteRag:**
- **`chunks` collection:** Stores the full text + metadata of every chunk. This is the "source of truth" for chunk content.
- **`documents` collection:** Stores one record per uploaded file with status (`processing` / `ready` / `failed`) and `total_chunks`.

**Why MongoDB for chunk storage:** Qdrant and Elasticsearch store metadata, but not the full chunk text (that would be redundant). MongoDB holds the complete chunk text so we can retrieve it when needed (Phase 2: hydrating search results).

**Status tracking:** When a file is uploaded, a record is created immediately with `status: "processing"`. When ingestion finishes, it's updated to `"ready"`. If anything fails, it's `"failed"`. The client can poll `GET /api/documents` to check progress.

---

### Elasticsearch
**What it is:** A search engine and database optimized for text search.

**What it does in CiteRag:**
- Indexes every chunk's text using the **english analyzer** (handles stemming, stop-words)
- When a user asks a question, we run a **BM25 keyword search** across all chunk texts
- BM25 = Best Match 25 — the industry-standard algorithm for keyword relevance ranking

**Why use it alongside Qdrant?** Semantic search (Qdrant) is great for conceptual similarity. But keyword search (Elasticsearch) is great for exact terms — a rare drug name, a specific regulation code, a person's name. Using both together gives better results than either alone.

**English analyzer:** Automatically applies stemming (so "running" matches "run", "runs", "runner") and removes stop words (so "the", "is", "in" are ignored when matching).

---

## 🔄 Reranking (Phase 2 — Coming Next)

### BAAI/bge-reranker-large
**What it will do in Phase 2:**
- Takes the merged results from Qdrant (semantic) + Elasticsearch (keyword) — up to 40 chunks
- Re-scores each `(question, chunk)` pair using a **cross-encoder** — a model that reads both at the same time and gives a relevance score
- Selects the top 8–12 chunks for the LLM

**Why reranking?** Bi-encoder models (like the BGE embedder) are fast but approximate. Cross-encoder models are slower but much more accurate at judging relevance. We use bi-encoders to narrow from thousands to ~40, then the cross-encoder to nail the final top 10.

---

## 🤖 Language Model

### Ollama (llama3:8b / mistral / deepseek-r1)
**What it is:** A tool for running large language models locally on your own machine — no internet, no API key needed.

**What it does in CiteRag (Phase 3):**
- Receives the top reranked chunks as context
- In **Strict Mode:** answers *only* from the provided evidence, never speculates
- In **Liberal Mode:** answers from the document first, then adds broader explanation from its knowledge

**Why run locally with Ollama:** Privacy (documents never leave your machine), no API costs, works offline, and you control which model to use.

---

## 📦 Logging

### loguru
**What it is:** A modern Python logging library.

**Why we use it instead of Python's built-in `logging`:**
- One-line setup — no handlers, formatters, or config needed
- Colored, structured output in the terminal out of the box
- Works seamlessly with async code (FastAPI)
- `logger.exception()` automatically includes full stack traces

Every pipeline step logs what it's doing:
```
[Ingestion] ▶ START  document_id=abc123  file='paper.pdf'
[PyMuPDF] Extracted 12 pages from 'paper.pdf'
[Chunker] 'paper.pdf' → 84 chunks (size=512, overlap=128)
[Embedder] Generated 84 embeddings, shape=(1024,)
[Qdrant] Upserted 84 vectors into 'documents'
[MongoDB] Inserted 84 chunks
[Elasticsearch] Bulk indexed 84 chunks
[Ingestion] ✔ COMPLETE  84 chunks → Qdrant ✔  MongoDB ✔  Elasticsearch ✔
```

---

## 🌐 API Layer

### python-multipart
**What it is:** Enables FastAPI to accept file uploads via multipart form data.
**Why needed:** Without it, `UploadFile` in FastAPI doesn't work.

### python-dotenv
**What it is:** Reads the `.env` file and loads values into environment variables.
**Why needed:** Keeps all config (URLs, model names, thresholds) out of code and in `.env`.

### httpx
**What it is:** An async HTTP client for Python.
**Used for:** Making HTTP calls to the Ollama API (Phase 3) and public verification APIs like PubMed/arXiv (Phase 3A).

### aiofiles
**What it is:** Async file I/O for Python.
**Used for:** Reading/writing files without blocking the event loop in async FastAPI handlers.

---

## 📐 Full Data Flow (Everything Together)

```
User uploads paper.pdf
         │
         ▼
  POST /api/upload  (FastAPI + Uvicorn)
         │
         ├─ Validate: extension ∈ {pdf,docx,txt}, size < 50MB  (Pydantic)
         ├─ Save: uploads/{uuid}.pdf
         ├─ MongoDB insert: {document_id, status: "processing"}
         └─ BackgroundTask → run_ingestion()
                   │
                   ├─ PyMuPDF: extract text, page by page
                   │    └─ If < 100 chars → Tesseract OCR fallback
                   │
                   ├─ RecursiveCharacterTextSplitter
                   │    → 84 chunks × 512 chars, 128 overlap
                   │    → each chunk tagged: page, paragraph, line range, domain
                   │
                   ├─ BAAI/bge-large-en-v1.5
                   │    → 84 embedding vectors × 1024 floats
                   │
                   ├─ Qdrant: store 84 points (vector + metadata payload)
                   ├─ MongoDB: store 84 chunks (full text + metadata)
                   └─ Elasticsearch: index 84 docs (BM25 searchable)
                             │
                             ▼
                    MongoDB update: status → "ready"

── Phase 2 (coming) ──────────────────────────────────────

User asks: "What is the recommended dosage?"
         │
         ▼
  POST /api/query
         │
         ├─ BM25 search (Elasticsearch) → top 20 chunks by keyword
         ├─ Semantic search (Qdrant, embedded question) → top 20 chunks by meaning
         ├─ Merge + deduplicate → 25–40 unique chunks
         ├─ Hydrate with full text (MongoDB)
         └─ Cross-encoder rerank (BAAI/bge-reranker-large) → top 10 chunks

── Phase 3 (coming) ──────────────────────────────────────

         Top 10 chunks passed to Ollama (llama3:8b)
         │
         ├─ Liberal Mode: answer from doc + AI explanation
         └─ Strict Mode: answer ONLY from doc + citations + confidence score
```

---

## Summary Table

| Technology | Category | Role in CiteRag |
|---|---|---|
| **FastAPI** | Web Framework | REST API, file upload, background tasks |
| **Uvicorn** | Web Server | Runs the FastAPI app |
| **Pydantic** | Validation | Data models and API contracts |
| **PyMuPDF (fitz)** | Extraction | PDF text extraction (digital PDFs) |
| **Tesseract OCR** | Extraction | OCR fallback for scanned/image PDFs |
| **python-docx** | Extraction | DOCX paragraph extraction |
| **LangChain (RecursiveCharacterTextSplitter)** | Chunking | Splits text into 512/128 overlapping chunks |
| **BAAI/bge-large-en-v1.5** | Embedding Model | Converts text to 1024-dim semantic vectors |
| **sentence-transformers** | ML Library | Runs the BGE embedding model |
| **Qdrant** | Vector Database | Nearest-neighbour semantic search |
| **MongoDB** | Document Database | Stores full chunk text + document records |
| **Elasticsearch** | Search Engine | BM25 keyword search index |
| **BAAI/bge-reranker-large** | Reranker (Phase 2) | Cross-encoder relevance scoring |
| **Ollama** | LLM Runtime (Phase 3) | Local LLM for answer generation |
| **loguru** | Logging | Structured colored logs throughout pipeline |
| **python-dotenv** | Config | Loads `.env` into environment |
| **python-multipart** | Upload | Enables multipart file upload in FastAPI |
| **httpx** | HTTP Client | Calls Ollama + public APIs (Phase 3) |
| **aiofiles** | Async I/O | Non-blocking file operations |

---

*Reference: project_flow.md, explain.md, memory.md*
*Last updated: Phase 1 complete — 2026-07-14*

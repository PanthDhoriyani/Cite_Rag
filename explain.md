# CiteRag — Project Explanation (Phase by Phase)
> This document explains the codebase step-by-step as we build it.
> It details what folders and files are created in each phase and exactly what they do.

---

## Phase 1: Document Ingestion Pipeline (Completed)

**Goal:** Allow users to upload documents (PDF, DOCX, TXT), extract their text, split the text into chunks, convert the chunks into semantic vectors (embeddings), and store everything across three different databases for later retrieval.

### Folders and Files Created in Phase 1:

#### 1. Configuration & Setup
- **`.env` and `.env.example`**
  - **What it is:** Environment variables.
  - **What it contains:** Database connection URLs (MongoDB, Qdrant, Elasticsearch), local LLM URL (Ollama), and configuration thresholds (chunk size, chunk overlap).
- **`backend/requirements.txt`**
  - **What it is:** Python dependencies file.
  - **What it contains:** Pinned versions of `langchain`, `fastapi`, `pymongo`, `qdrant-client`, `elasticsearch`, `sentence-transformers`, etc.
- **`backend/config.py`**
  - **What it is:** Centralized configuration module.
  - **What it contains:** Reads the `.env` file using `python-dotenv` and exports variables like `MONGODB_URL`, `EMBEDDING_MODEL`, and `CHUNK_SIZE` for the rest of the app to use. (No `os.getenv()` is used anywhere else).

#### 2. API Models & Database Clients
- **`backend/schemas.py`**
  - **What it is:** Pydantic data models.
  - **What it contains:** Defines the structure of API requests and responses. For example, `UploadResponse` (what the user gets back after uploading) and the `Domain` enum (legal, research, etc.).
- **`backend/db/__init__.py` & `backend/db/mongo_client.py`**
  - **What it is:** The MongoDB database client.
  - **What it contains:** Functions to track document status (`save_document`, `update_status`) and store full chunk text (`save_chunks`). We only need a manual client for MongoDB because LangChain natively handles Qdrant and Elasticsearch.

#### 3. Core RAG Logic
- **`backend/pipeline.py`**
  - **What it is:** The LangChain Ingestion Pipeline (The Engine).
  - **What it contains:** 
    - `load()`: Uses LangChain's `PyMuPDFLoader`, `Docx2txtLoader`, and `TextLoader` to read files. Includes a Tesseract OCR fallback for scanned PDFs.
    - `split()`: Uses `RecursiveCharacterTextSplitter` to chop documents into overlapping 512-character chunks and injects metadata (page number, chunk ID).
    - `store()`: Uses `QdrantVectorStore` to save vector embeddings, `ElasticsearchStore` to create a BM25 keyword index, and our `mongo_client` to save the full text.
    - `run()`: The main orchestrator function that calls the above three steps.

#### 4. Web API (FastAPI)
- **`backend/main.py`**
  - **What it is:** The FastAPI entry point.
  - **What it contains:** Creates the `app` object, configures CORS (so a frontend on port 3000 can talk to it), and registers the routers (`upload.py` and `query.py`).
- **`backend/routers/__init__.py` & `backend/routers/upload.py`**
  - **What it is:** The document management endpoints.
  - **What it contains:** 
    - `POST /api/upload`: Validates the file, saves it to the `uploads/` folder, marks it as "processing" in MongoDB, and triggers `pipeline.run()` in the background (using FastAPI's `BackgroundTasks`).
    - `GET /api/documents`: Lists all uploaded files.
    - `DELETE /api/documents/{id}`: Removes a document from all three databases.
- **`backend/routers/query.py`**
  - **What it is:** The question-answering endpoint.
  - **What it contains:** Currently just a **stub** (placeholder) returning a message that Phase 2 is coming next.

---

## Phase 2: Hybrid Retrieval & Reranking (Completed)

**Goal:** Take a user's question and search the databases to find the most relevant chunks of text (evidence) to answer it, using a combination of meaning-based search, keyword search, and precision reranking.

### Folders and Files Created/Modified in Phase 2:

#### 1. Retrieval Logic
- **`backend/retrieval.py`**
  - **What it is:** The LangChain Hybrid Retrieval Pipeline.
  - **What it contains:**
    - **`QdrantVectorStore.as_retriever`:** Performs semantic search (finds chunks by meaning) and retrieves the top 20 matches.
    - **`ElasticsearchRetriever`:** Performs BM25 keyword search (finds chunks by exact words) and retrieves the top 20 matches.
    - **`EnsembleRetriever`:** Merges the results of Qdrant and Elasticsearch using Reciprocal Rank Fusion (RRF). This catches more relevant chunks than either database alone.
    - **`ContextualCompressionRetriever` with `CrossEncoderReranker`:** Takes the ~40 chunks from the Ensemble, reads the question and the chunks *together* using a powerful Cross-Encoder model (`BAAI/bge-reranker-large`), assigns a highly precise relevance score, and keeps only the Top 10 chunks.

## Phase 3: Answer Generation (Completed)

**Goal:** Feed the retrieved text chunks to a local LLM (Ollama) to generate a cited answer, supporting a "Liberal" (educational) mode and a "Strict" (evidence-only, validated) mode.

### Folders and Files Created/Modified in Phase 3:

#### 1. Generation Logic
- **`backend/generation.py`** (New)
  - **What it is:** The LangChain LCEL (LangChain Expression Language) Answer Generation chains.
  - **What it contains:**
    - **`OllamaLLM`:** Connects to the local Ollama LLM runtime running `llama3:8b`.
    - **`generate_liberal_answer()`:** Formats the 10 context chunks and runs a prompt requiring the model to provide a `DOCUMENT-BASED ANSWER` first, followed by an `ADDITIONAL EXPLANATION` based on its own training data.
    - **`generate_strict_answer()`:** Checks if the top chunk's relevance score is above the `CONFIDENCE_THRESHOLD` (0.65). If not, it refuses to answer. If it is, it generates an answer using a prompt that forbids speculation. It averages the top 3 scores to calculate confidence, and appends external API reference links.

#### 2. Public Claims Verification
- **`backend/verifier.py`** (New)
  - **What it is:** A domain-specific public API checker.
  - **What it contains:**
    - **`verify_pubmed()`:** Searches medical articles on the official PubMed database using search APIs and returns citation links.
    - **`verify_arxiv()`:** Searches the arXiv preprint database for scientific references.
    - **`verify_claim()`:** Automatically routes the search claim based on the document's domain (e.g. `healthcare` -> PubMed, `research` -> arXiv).

#### 3. Query Endpoint Update
- **`backend/routers/query.py`** (Modified)
  - **What changed:** Connected the retrieval output directly to the generation chains inside `generation.py`.
  - **What it does now:** Based on the requested mode (`liberal` or `strict`), it runs the corresponding LCEL generation chain and returns the generated answer text, confidence score, status, and citation items.

---

## Phase 4: Frontend UI (Coming Next)
*(This section will be updated when Phase 4 is completed.)*

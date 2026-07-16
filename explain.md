# CiteRag — Project Explanation (Phase by Phase)
> This document explains the codebase step-by-step as we build it.
> It details what folders and files are created in each phase and exactly what they do.

---

## Phase 1: Document Ingestion Pipeline (Completed)

**Goal:** Allow users to upload documents (PDF, DOCX, TXT), extract their text, split the text into chunks, convert the chunks into semantic vectors (embeddings), and store everything across two databases: Qdrant Cloud (for semantic search) and MongoDB Atlas (for keyword search, document status tracking, and full citation text).

### Folders and Files Created in Phase 1:

#### 1. Configuration & Setup
- **`.env` and `.env.example`**
  - **What it is:** Environment variables.
  - **What it contains:** Database connection URLs and credentials (MongoDB connection string, Qdrant cluster endpoint + API Key), LLM API credentials (Groq API Key), and configuration thresholds (chunk size, chunk overlap).
- **`backend/requirements.txt`**
  - **What it is:** Python dependencies file.
  - **What it contains:** Pinned versions of `langchain`, `fastapi`, `pymongo`, `qdrant-client` (updated to `1.18.0` for cloud compatibility), `sentence-transformers`, etc.
- **`backend/config.py`**
  - **What it is:** Centralized configuration module.
  - **What it contains:** Reads the `.env` file using `python-dotenv` and exports variables like `MONGODB_URL`, `QDRANT_API_KEY`, `EMBEDDING_MODEL`, and `CHUNK_SIZE` for the rest of the app to use. (No `os.getenv()` is used anywhere else).

#### 2. API Models & Database Clients
- **`backend/schemas.py`**
  - **What it is:** Pydantic data models.
  - **What it contains:** Defines the structure of API requests and responses. For example, `UploadResponse` (what the user gets back after uploading) and the `Domain` enum (legal, research, etc.).
- **`backend/db/__init__.py` & `backend/db/mongo_client.py`**
  - **What it is:** The MongoDB database client.
  - **What it contains:** Functions to track document status (`save_document`, `update_status`) and store full chunk text (`save_chunks`).
  - **Text Indexing:** Programmatically creates a text index on the `chunk_text` field (`chunks.create_index([("chunk_text", "text")])`) on startup to support keyword searches.

#### 3. Core RAG Logic
- **`backend/pipeline.py`**
  - **What it is:** The LangChain Ingestion Pipeline (The Engine).
  - **What it contains:** 
    - `load()`: Uses LangChain's `PyMuPDFLoader`, `Docx2txtLoader`, and `TextLoader` to read files. Includes a Tesseract OCR fallback for scanned PDFs.
    - `split()`: Uses `RecursiveCharacterTextSplitter` to chop documents into overlapping 512-character chunks and injects metadata (page number, chunk ID, document_id, domain).
    - `store()`: Uses `QdrantVectorStore` to save vector embeddings to Qdrant Cloud, and our `mongo_client` to save full text chunks to MongoDB.
    - `run()`: The main orchestrator function that calls the above three steps.

#### 4. Web API (FastAPI)
- **`backend/main.py`**
  - **What it is:** The FastAPI entry point.
  - **What it contains:** Creates the `app` object, configures CORS (so a frontend can talk to it), and registers the routers (`upload.py` and `query.py`).
- **`backend/routers/__init__.py` & `backend/routers/upload.py`**
  - **What it is:** The document management endpoints.
  - **What it contains:** 
    - `POST /api/upload`: Validates the file, saves it to the `uploads/` folder, marks it as "processing" in MongoDB, and triggers `pipeline.run()` in the background (using FastAPI's `BackgroundTasks`).
    - `GET /api/documents`: Lists all uploaded files.
    - `DELETE /api/documents/{id}`: Removes a document from Qdrant Cloud and MongoDB.
- **`backend/routers/query.py`**
  - **What it is:** The question-answering endpoint.
  - **What it contains:** Performs hybrid search and LCEL generation, returning answers with citations.

---

## Phase 2: Hybrid Retrieval & Reranking (Completed)

**Goal:** Take a user's question and search the databases to find the most relevant chunks of text (evidence) to answer it, using a combination of meaning-based search (Qdrant Cloud), native keyword search (MongoDB Atlas), and precision reranking.

### Folders and Files Created/Modified in Phase 2:

#### 1. Retrieval Logic
- **`backend/retrieval.py`**
  - **What it is:** The LangChain Hybrid Retrieval Pipeline.
  - **What it contains:**
    - **`QdrantVectorStore.as_retriever`:** Performs semantic search (finds chunks by meaning) and retrieves the top 20 matches.
    - **`MongoDBTextRetriever` (Custom):** A custom retriever wrapping MongoDB's native `$text` query matching, retrieving the top 20 exact-keyword matches.
    - **`EnsembleRetriever`:** Merges the results of Qdrant and MongoDB using Reciprocal Rank Fusion (RRF). This catches more relevant chunks than either database alone.
    - **`ContextualCompressionRetriever` with `CrossEncoderReranker`:** Takes the ~40 chunks from the Ensemble, reads the question and the chunks *together* using a powerful Cross-Encoder model (`BAAI/bge-reranker-large`), assigns a highly precise relevance score, and keeps only the Top 10 chunks.

---

## Phase 3: Answer Generation (Completed)

**Goal:** Feed the retrieved text chunks to a cloud LLM (Groq API) to generate a cited answer, supporting a "Liberal" (educational) mode and a "Strict" (evidence-only, validated) mode.

### Folders and Files Created/Modified in Phase 3:

#### 1. Generation Logic
- **`backend/generation.py`**
  - **What it is:** The LangChain LCEL (LangChain Expression Language) Answer Generation chains.
  - **What it contains:**
    - **`ChatGroq`:** Connects to the cloud-based Groq inference API running `llama-3.1-8b-instant`.
    - **`generate_liberal_answer()`:** Formats the 10 context chunks and runs a prompt requiring the model to provide a `DOCUMENT-BASED ANSWER` first, followed by an `ADDITIONAL EXPLANATION` based on its own training data.
    - **`generate_strict_answer()`:** Checks if the top chunk's relevance score is above the `CONFIDENCE_THRESHOLD` (0.65). If not, it refuses to answer. If it is, it generates an answer using a prompt that forbids speculation. It averages the top 3 scores to calculate confidence, and appends external API reference links.

#### 2. Public Claims Verification
- **`backend/verifier.py`**
  - **What it is:** A domain-specific public API checker.
  - **What it contains:**
    - **`verify_pubmed()`:** Searches medical articles on the official PubMed database using search APIs and returns citation links.
    - **`verify_arxiv()`:** Searches the arXiv preprint database for scientific references.
    - **`verify_claim()`:** Automatically routes the search claim based on the document's domain (e.g. `healthcare` -> PubMed, `research` -> arXiv).

#### 3. Query Endpoint Update
- **`backend/routers/query.py`**
  - **What changed:** Connected the retrieval output directly to the generation chains inside `generation.py`.
  - **What it does now:** Based on the requested mode (`liberal` or `strict`), it runs the corresponding LCEL generation chain and returns the generated answer text, confidence score, status, and citation items.

---

## Phase 4: Streamlit Frontend UI (Completed)

**Goal:** Build a pure-Python web interface to interact with the backend API, allowing users to upload files, manage documents, choose querying modes, and ask questions through a chat-like dashboard.

### Folders and Files Created/Modified in Phase 4:

#### 1. Streamlit Interface
- **`backend/frontend.py`**
  - **What it is:** The Streamlit dashboard client.
  - **What it contains:**
    - `fetch_documents()`, `upload_document()`, `delete_document()`, `query_rag()`: HTTP client functions using `requests` to talk to the FastAPI backend service.
    - **Sidebar Panel:** A file uploader, domain selector, document status checklist (processing files auto-refresh), and deletion trigger buttons.
    - **Answer workbench:** Mode switcher (radio button), chat input, and custom styled outputs for Liberal mode (splits document evidence vs AI explanation) and Strict mode (renders progress bar for confidence and expandable cards showing chunk citations).
    - **Custom CSS:** Custom scrollbars, glassmorphism containers, and borders injected programmatically.
- **`backend/requirements.txt`**
  - **What changed:** Added `streamlit==1.59.2` dependency to the list.

---

## Phase 5: Observability & Tracing (Completed)

**Goal:** Integrate full execution tracing to monitor pipeline performance, latency, tokens, and errors across the entire RAG pipeline using LangSmith.

### Folders and Files Created/Modified in Phase 5:
- **`backend/requirements.txt`**
  - **What changed:** Added `langsmith` dependency.
- **`backend/config.py` & `.env` / `.env.example`**
  - **What changed:** Configured standard LangChain variables (`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_ENDPOINT`).
- **`backend/main.py`**
  - **What changed:** Re-ordered imports to put `load_dotenv()` at the absolute top of the entry point, ensuring the environment is loaded before the LangSmith SDK initializes at import time.
- **`backend/test_langsmith.py` [NEW]**
  - **What it is:** Diagnostic test script to verify LangSmith client connectivity.
- **Tracing Annotations:**
  - Applied `@traceable` to:
    - Ingestion pipeline runs, document loaders, text splitters, and storage operations in `pipeline.py`.
    - Retrieval pipeline queries in `retrieval.py`.
    - Generation functions in `generation.py`.
    - Verification lookups in `verifier.py`.
    - Query and upload routes in `/routers`.
  - LCEL chains (Groq chains) are traced automatically via LangChain integrations.

---

## Phase 6: Inline PDF Chunk Highlighter (Completed)

**Goal:** Allow users to visually pinpoint where retrieved chunks originated by rendering the source PDF page inline with the cited passage highlighted in yellow.

### Folders and Files Created/Modified in Phase 6:
- **`backend/db/mongo_client.py`**
  - **What changed:** Added `get_chunk_by_id()` and `get_document_by_id()` helper methods to retrieve chunk text and source document paths from MongoDB.
- **`backend/routers/upload.py`**
  - **What changed:** Added the `GET /api/chunks/{chunk_id}/highlight` endpoint. It uses PyMuPDF (`fitz`) to open the local PDF, scan for the chunk's text (with a sliding length fallback for robustness), overlay a yellow annotation, and render the page to a 2× resolution base64 PNG.
- **`backend/frontend.py`**
  - **What changed:** 
    - Migrated backend query storage to `st.session_state` to keep results persisted during rerun events.
    - Added inline toggle buttons (**"📄 View" / "🔒 Close"** in Liberal mode and **"📄 View in PDF" / "🔒 Close PDF View"** in Strict mode) which fetch the highlighted page PNG and render it directly underneath the clicked citation.
    - Updated checkboxes to include `label_visibility="collapsed"` to resolve accessibility warnings.


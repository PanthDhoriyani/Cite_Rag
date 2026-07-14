# CiteRag — Project Memory & Progress Tracker
> Keeps track of what we have done, what works, and what's next.

---

## 🏗️ Architecture Status: LangChain Rewrite (Complete)
We have successfully refactored the entire project to use **LangChain** as the core RAG framework.
We removed the custom, overly-modular "enterprise" code and replaced it with a flat, readable structure.

### What was replaced:
- Custom PDF loading → `PyMuPDFLoader`
- Custom Chunking → `RecursiveCharacterTextSplitter`
- Custom Embedding → `HuggingFaceEmbeddings`
- Custom Qdrant inserts → `QdrantVectorStore`
- Custom Elasticsearch indexing → `ElasticsearchStore` (BM25 mode)

### What stays custom:
- `MongoDB` handles document status (`processing` vs `ready`) and stores the full chunk text for citations. LangChain does not natively handle asynchronous document ingestion statuses.

---

## 🟢 Current Phase: Phase 1 (Ingestion) Complete
All files for Phase 1 are written and documented:
1. `backend/config.py` — Centralized environment variables.
2. `backend/schemas.py` — Pydantic models (`QueryRequest`, `UploadResponse`, `Domain`).
3. `backend/db/mongo_client.py` — Module-level MongoDB connection for status tracking.
4. `backend/pipeline.py` — The LangChain ingestion pipeline (`load`, `split`, `store`, `run`).
5. `backend/routers/upload.py` — Upload endpoint with `BackgroundTask` ingestion.
6. `backend/routers/query.py` — Query endpoint (currently a stub for Phase 2).
7. `backend/main.py` — FastAPI app with CORS and router registration.

---

## 🔴 Known Issue: Python 3.14 Build Error
While attempting to install `requirements.txt` via `pip install`, the installation failed.

**The Cause:**
The system is running **Python 3.14.4**. Many native Python packages (like `zstandard`, `cffi`, etc.) do not yet have pre-compiled wheels for Python 3.14. Pip tries to compile them from source, which fails because the **Microsoft Visual C++ 14.0 Build Tools** are not installed on this machine.

**The Solution:**
To run this backend on this machine, we either need to:
1. Install Microsoft C++ Build Tools (https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2. Downgrade Python to **3.11 or 3.12**, where pre-compiled `.whl` files are readily available for all LangChain dependencies.

---

## 🔜 Next Steps (Phase 2)
Once the environment issue is resolved and packages are installed:
1. Move to **Phase 2: Hybrid Retrieval & Reranking**.
2. Create `backend/retrieval.py` using `EnsembleRetriever` (Qdrant + Elasticsearch) and `CrossEncoderReranker`.
3. Update `backend/routers/query.py` to use the new retrieval logic.

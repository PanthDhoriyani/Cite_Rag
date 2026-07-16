# CiteRag — Project Memory & Progress Tracker
> Keeps track of what we have done, what works, and what's next.

---

## 🏗️ Architecture Status: Cloud-Resilient, Simplified & Observed (Complete)
We have successfully refactored the entire project to run on **cloud-based databases (MongoDB Atlas + Qdrant Cloud)**, replacing Elasticsearch with MongoDB text index search, added **LangSmith observability**, and implemented a pure-Python **Streamlit frontend** with an **inline highlighted PDF viewer**.

### Component Setup:
- **Backend (FastAPI):** Exposes ingestion endpoints (`POST /api/upload`, `GET /api/documents`, `DELETE /api/documents/{id}`), retrieval/QA endpoints (`POST /api/query`), and rendering endpoints (`GET /api/chunks/{id}/highlight`). Fully traced via LangSmith.
- **Frontend (Streamlit):** Written in Python (`backend/frontend.py`), connects to FastAPI endpoints, manages state persistence via session state, and renders inline PDF page visual highlights.
- **Qdrant Cloud** (Free Tier): Handles semantic nearest-neighbour vector search.
- **MongoDB Atlas** (Free Tier): Handles document statuses, full-text chunks, **and BM25 keyword matching** (via native Text Indexing).

---

## 🟢 Current Phase: Phase 6 (PDF Chunk Highlight) Complete
All files for Phase 6 are written, documented, and verified:
1. `backend/routers/upload.py` — Added high-performance PDF page renderer and text locator endpoint.
2. `backend/db/mongo_client.py` — Added helper queries to retrieve chunk text and document paths.
3. `backend/frontend.py` — Added session state persistence and interactive inline image viewer toggles.
4. `requirements.txt` — Added `langsmith` package for tracing.

### How to Run:
You will need two terminal tabs running simultaneously in the virtual environment:
1. **Backend Uvicorn server:**
   ```bash
   cd backend
   venv\Scripts\python -m uvicorn main:app --reload --port 8000
   ```
2. **Frontend Streamlit server:**
   ```bash
   cd backend
   venv\Scripts\python -m streamlit run frontend.py
   ```

---

## 🔴 Known Issues
None.

---

## 🔜 Next Steps (Phase 7)
1. Move to **Phase 7: Docker & Containerization**.
2. Write `Dockerfile` for the backend.
3. Write `Dockerfile` for the frontend.
4. Construct `docker-compose.yml` to spin up both services and pass all environment variables safely.

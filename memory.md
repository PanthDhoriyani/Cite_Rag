# CiteRag — Project Memory & Progress Tracker
> Keeps track of what we have done, what works, and what's next.

---

## 🏗️ Architecture Status: Cloud-Resilient & simplified (Complete)
We have successfully refactored the entire project to run on **cloud-based databases (MongoDB Atlas + Qdrant Cloud)**, replacing Elasticsearch with MongoDB text index search, and implemented a pure-Python **Streamlit frontend**.

### Component Setup:
- **Backend (FastAPI):** Exposes ingestion endpoints (`POST /api/upload`, `GET /api/documents`, `DELETE /api/documents/{id}`) and retrieval endpoints (`POST /api/query`).
- **Frontend (Streamlit):** Written in Python (`backend/frontend.py`), connects to FastAPI endpoints, and renders file upload dropzones, file list checkboxes, select fields, and styled response panels.
- **Qdrant Cloud** (Free Tier): Handles semantic nearest-neighbour vector search.
- **MongoDB Atlas** (Free Tier): Handles document statuses, full-text chunks, **and BM25 keyword matching** (via native Text Indexing).

---

## 🟢 Current Phase: Phase 4 (Streamlit Frontend UI) Complete
All files for Phase 4 are written, documented, and verified:
1. `backend/frontend.py` — Streamlit dashboard (sidebar uploader/manager, main panel queries/answers, custom dark styling).
2. `backend/requirements.txt` — Added `streamlit==1.59.2` dependency.
3. Updated all project documents to reflect the Streamlit choice.

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
   venv\Scripts\streamlit run frontend.py
   ```

---

## 🔴 Known Issues
None.

---

## 🔜 Next Steps (Phase 5)
1. Move to **Phase 5: Docker & Containerization**.
2. Write `Dockerfile` for the backend.
3. Write `Dockerfile` for the frontend.
4. Construct `docker-compose.yml` to spin up both services and pass the `GROQ_API_KEY` environment variable.

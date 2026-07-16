# CiteRag — Frontend to Backend & Database Flow
This document maps out the end-to-end data flow of the CiteRag system. It describes what happens under the hood when a user clicks specific buttons on the Streamlit dashboard, tracing actions from the UI down to the FastAPI server, MongoDB Atlas, Qdrant Cloud, and the cloud-hosted Groq API.

---

## Architecture Overview
CiteRag operates as a decoupled architecture:
1. **Frontend (Streamlit):** A browser-based GUI running on port `8501`. It communicates with the backend via HTTP REST requests.
2. **Backend (FastAPI):** A high-performance Python web server running on port `8000`. It processes requests, manages database clients, and handles LLM pipelines.
3. **Databases:**
   - **Qdrant Cloud:** Vector store for nearest-neighbor semantic searches (stores 1024-dimension float vectors).
   - **MongoDB Atlas:** Metadata database for document statuses, full-text chunks, and exact-keyword search queries (using native text index search).
4. **Groq API:** Cloud-hosted LLM inference API running `llama-3.1-8b-instant` for running the LCEL chains.

```
[Streamlit Frontend] (8501)
         │
    (HTTP calls)
         ▼
  [FastAPI Backend] (8000)
    ┌────┴─────────────────────────────┐
    ▼                                  ▼
[Qdrant Cloud]                  [MongoDB Atlas]
(Vector/Semantic)             (Metadata/Keyword Search)
```

---

## Flow 1: Document Ingestion (Uploading a File)
When a user uploads a new document, the system registers the file and indexes it for search in the background.

```
[Upload File] ────► [FastAPI /upload] ────► [Create Status Record (Processing)]
                                                      │
                                                      ▼ (Background Task)
[Ready Badge] ◄──── [Update Status (Ready)] ◄── [Ingest to Qdrant & MongoDB]
```

### 1. User Actions on the Streamlit Sidebar
1. The user drags a file (`.pdf`, `.docx`, or `.txt`) into the **Uploader Zone**.
2. The user selects a domain from the **Document Domain** dropdown (e.g., *Healthcare & Medicine*, *Research / Preprint*).
3. The user clicks **Process Document**.

### 2. Frontend (Streamlit) Processing
- The browser reads the raw file bytes in memory.
- It maps the user's dropdown choice to the appropriate string key from the `Domain` enum (e.g. `"healthcare"`, `"research"`).
- It initiates a `multipart/form-data` POST request to the backend's `/api/upload` endpoint, sending the file object and the selected domain value.

### 3. Backend (FastAPI Router: `upload.py`) Processing
1. **Validation:** Checks that the file extension is supported (`.pdf`, `.docx`, `.txt`) and the file size is under `50MB`.
2. **Save File:** Saves the file onto disk in the `uploads/` directory, renaming it to a random UUID (e.g., `550e8400-e29b-41d4-a716-446655440000.pdf`) to avoid filename collisions.
3. **MongoDB Registration:** Inserts a document tracking record into the MongoDB `documents` collection:
   ```json
   {
       "document_id": "550e8400-e29b-41d4-a716-446655440000",
       "document_name": "clinical_guideline.pdf",
       "file_path": "uploads/550e8400-e29b-41d4-a716-446655440000.pdf",
       "file_type": "pdf",
       "domain": "healthcare",
       "upload_timestamp": "2026-07-15T19:35:10Z",
       "status": "processing",
       "total_chunks": 0
   }
   ```
4. **FastAPI BackgroundTask:** FastAPI launches `pipeline.run()` on a separate worker thread.
5. **Immediate Response:** FastAPI returns a `202 Accepted` status code to Streamlit immediately, containing the `document_id` and the status `"processing"`.

### 4. Background Ingestion Execution (`pipeline.py`)
1. **File Loading (`load`):**
   - *Digital PDF:* Extracted using `PyMuPDFLoader`, yielding one LangChain `Document` per page.
   - *Scanned PDF (OCR Fallback):* If under 100 characters are extracted, PyMuPDF opens the PDF, renders each page at 300 DPI as a PNG, and passes it to **Tesseract OCR** to pull the text.
   - *Word (.docx):* Extracted using `Docx2txtLoader`.
   - *Text (.txt):* Extracted using `TextLoader`.
2. **Text Splitting (`split`):**
   - The document is split into chunks of **512 characters** with an overlap of **128 characters** using the `RecursiveCharacterTextSplitter`.
   - Each chunk receives extensive metadata:
     - `chunk_id` (a unique UUID)
     - `page_number` (1-indexed page where the chunk came from)
     - `document_id` and `document_name`
     - `domain`
     - `chunk_index` (e.g. 5th chunk out of 100)
3. **Embedding Vectorization:**
   - The text contents of all chunks are passed to the `BAAI/bge-large-en-v1.5` model loaded locally by LangChain `HuggingFaceEmbeddings`.
   - The model converts each chunk into a **1024-dimensional float vector**.
4. **Database Storage (`store`):**
   - **Qdrant Cloud:** The 1024-dim vector, `chunk_id`, and all metadata fields are uploaded. Qdrant indexes the vectors using HNSW for rapid cosine similarity matching.
   - **MongoDB Atlas:** The chunk payload containing `chunk_id`, `document_id`, `page_number`, `document_name`, `domain`, and the full raw text (`chunk_text`) is bulk-inserted into the `chunks` collection. The native `$text` full-text search index indexes `chunk_text` on insert.
5. **Status Update:**
   - The parent document status in the `documents` collection is updated from `"processing"` to `"ready"`, and the `total_chunks` field is populated with the correct chunk count.
   - If any exception occurred during loading, splitting, embedding, or saving, the status is set to `"failed"`.

### 5. Frontend Polling & Update
- Streamlit's dashboard loop queries `GET /api/documents` periodically.
- While the document status is `"processing"`, the Streamlit frontend sleeps for 2 seconds and triggers `st.rerun()`.
- Once MongoDB reports `"ready"`, the file appears in the sidebar with a green **Ready (N chunks)** badge and a checkbox to scope search queries.

---

## Flow 2: Document Deletion
When a user purges a document, the databases and filesystem are cleaned up.

### 1. User Actions on the Streamlit Sidebar
1. The user clicks the **trash can (🗑️)** icon next to a ready document.

### 2. Frontend (Streamlit) Processing
- The browser triggers a DELETE request to `/api/documents/{document_id}`.

### 3. Backend (FastAPI Router: `upload.py` -> `_delete_from_all_stores`)
FastAPI schedules a background task to wipe out the data in the following order:
1. **Qdrant Cloud:** Deletes all points where the metadata key `document_id` matches the target ID.
2. **MongoDB Atlas:** 
   - Deletes all chunks matching the `document_id` from the `chunks` collection.
   - Deletes the document metadata record from the `documents` collection.
3. **Filesystem:** Deletes the physical file (e.g., `uploads/{uuid}.pdf`) from disk.
4. **Streamlit UI Rerun:** The frontend receives a `200 OK` response, displays a "Purged!" success message, waits 1 second, and calls `st.rerun()` to update the repository sidebar.

---

## Flow 3: Question Answering (Hybrid Retrieval & Reranking)
When a user asks a question, CiteRag searches both databases and narrows down the best evidence.

```
                  ┌──► Qdrant (Semantic Search) ────► Top 20 Chunks ──┐
                  │                                                   ▼
[User Question] ──┼                                              [Merge by RRF] ──► [Cross-Encoder Reranker] ──► Top 10 Chunks
                  │                                                   ▲
                  └──► MongoDB (Keyword Search) ────► Top 20 Chunks ──┘
```

### 1. User Action in the Main Panel
1. The user selects **Liberal** or **Strict** mode.
2. The user checks/unchecks document boxes to restrict the query scope (optional).
3. The user inputs their question (e.g., *"What is the recommended pediatric dosage?"*) into the chat bar and hits Enter.

### 2. Frontend (Streamlit) Processing
- The browser packages the question, selected mode (`"liberal"` or `"strict"`), and the selected `document_ids` (as a list, or `null` if querying globally) into a JSON payload.
- It sends a POST request to `/api/query`.

### 3. Backend Hybrid Retrieval (`retrieval.py`)
1. **Semantic Search (Qdrant):**
   - The question is embedded using the `BAAI/bge-large-en-v1.5` embeddings model.
   - A cosine similarity search is run against Qdrant Cloud to retrieve the **Top 20 most similar chunks** (`VECTOR_TOP_K`).
2. **Keyword Search (MongoDB):**
   - In parallel, a native MongoDB text query is executed using the `$text` operator:
     ```python
     collection.find({"$text": {"$search": query}})
     ```
   - Matches are ranked using `textScore` and limited to the **Top 20 exact matches** (`BM25_TOP_K`).
3. **Ensemble Merger (Reciprocal Rank Fusion):**
   - LangChain's `EnsembleRetriever` merges the Qdrant and MongoDB chunks.
   - It assigns a reciprocal rank fusion (RRF) score to each chunk, ensuring that chunks that scored high in both methods are ranked first, and filters out duplicates.
4. **Cross-Encoder Reranking:**
   - The merged candidate chunks (~40 items) are sent to the Cross-Encoder model (`BAAI/bge-reranker-large`).
   - The Cross-Encoder reads the question and each chunk text *together*, calculating an exact attention score from `0.0` (irrelevant) to `1.0` (highly relevant).
   - The pipeline keeps only the **Top 10 chunks** (`RERANKER_TOP_K`).

---

## Flow 4: Answer Generation (Mode Breakdown)
The generated response depends on the selected Mode.

### Mode A: Liberal Mode (Educational)
Designed to provide information even if the document context is sparse, clearly separating document facts from general LLM knowledge.

```
[Retrieve Top 10 Chunks] ────► [Format as Context] ────► [Liberal Prompt Template]
                                                                │
                                                                ▼
                                                          [ChatGroq LLM]
                                                                │
                                                                ▼
                                                   DOCUMENT-BASED ANSWER
                                                   ADDITIONAL EXPLANATION
```

1. **Format Chunks:** The 10 reranked chunks are formatted into a single context block:
   `--- Document Source [1]: Paper.pdf (Page 3) --- [chunk text content]`
2. **LCEL Invocation:** The context and question are sent to the `LIBERAL_PROMPT` chain:
   - The prompt instructs the model to answer the question using the Document Context under the header `DOCUMENT-BASED ANSWER:`, and then append a general explanation from its training data under `ADDITIONAL EXPLANATION:`.
3. **LLM Generation:** The Groq API generates the structured string response.
4. **FastAPI Return:** Returns the response object:
   ```json
   {
       "question": "What is diabetes?",
       "mode": "liberal",
       "answer": "DOCUMENT-BASED ANSWER:\n...\nADDITIONAL EXPLANATION:\n...",
       "citations": [ { "document_name": "paper.pdf", "page_number": 3, "chunk_text": "...", "chunk_id": "..." } ],
       "confidence": null,
       "status": "ok"
   }
   ```
5. **Streamlit UI Render:**
   - Streamlit checks for the headings in the response text.
   - It splits the text at `ADDITIONAL EXPLANATION:`.
   - It renders the document evidence inside a styled purple left-bordered card (`.doc-answer-card`).
   - It renders the general explanation inside a styled blue left-bordered card (`.ai-answer-card`).
   - It lists the inline citations in an expander panel labeled *"References & Chunks Cited"*.

---

### Mode B: Strict Mode (Evidence-Only)
Designed for critical environments where speculation is prohibited. All statements must be backed by the document.

```
[Retrieve Top 10 Chunks]
         │
         ▼
[Check Score of Top Chunk]
         ├───► (Score < 0.65) ──► [Refuse to Answer] ──► Status: "low_confidence"
         │
         └───► (Score >= 0.65)
                    │
                    ├─► [Compute Avg of Top 3 Chunks] ──► Confidence Score
                    ├─► [Strict Prompt Template] ────► [ChatGroq LLM]
                    │                                        │
                    │                                        ▼
                    │                                 [Check Domain]
                    │                                        │
                    ▼                                        ▼
            [healthcare -> PubMed] ◄────────────────── [research -> arXiv]
```

1. **Confidence Gate:**
   - The backend checks the Cross-Encoder score of the **#1 ranked chunk**.
   - **IF THE TOP SCORE IS < 0.65:**
     - The backend logs a warning: *"Top relevance score is below confidence threshold. Refusing to answer."*
     - It returns:
       ```json
       {
           "answer": "Insufficient evidence in the uploaded documents.",
           "status": "low_confidence",
           "confidence": 0.42,
           "citations": []
       }
       ```
     - **Streamlit Render:** Streamlit detects the `status == "low_confidence"` and renders a warning box: *"Low Retrieval Confidence: Insufficient evidence found..."*. No citation cards are shown.
   - **IF THE TOP SCORE IS >= 0.65:**
     - The pipeline proceeds to generation.
2. **Confidence Computation:**
   - The backend computes the average score of the **top 3 chunks** as the final confidence metric.
3. **LCEL Generation:**
   - Passes the formatted context chunks and question to the `STRICT_PROMPT` chain.
   - The prompt instructs the model to answer the question using **ONLY** the provided context, forbidding speculation. If there isn't enough information, it must respond with: *"Insufficient evidence in the uploaded documents."*
4. **Domain Routing & Public Verification (`verifier.py`):**
   - The backend inspects the `domain` metadata of the top retrieved chunk.
   - **Healthcare Domain:** Calls the **PubMed E-utilities search API** over HTTP using the question terms. If papers are found, it generates link URLs (e.g. `https://pubmed.ncbi.nlm.nih.gov/{pmid}/`).
   - **Research Domain:** Calls the **arXiv query API** over HTTP, parses the XML, and extracts matching preprint links.
   - **Other Domains (legal, general, technical):** Skips verification.
   - If verification returns reference links, they are appended to the answer text as `[Public Verification Source: PubMed/arXiv]`.
5. **FastAPI Return:** Returns the strict response payload.
6. **Streamlit UI Render:**
   - Detects `status == "ok"`.
   - Renders the assistant's answer text directly in the chat.
   - Renders a **Retrieval Confidence Score** text label and a visual progress bar (e.g., `87%` full).
   - Renders each source chunk used for the answer inside custom expandable dropdowns showing the page number, document name, and chunk text highlight.

---

## Flow 5: Pipeline Observability (LangSmith Tracing)
Every user action (uploading a file, checking progress, querying the RAG pipeline) is automatically instrumented and sent to LangSmith.

```
[User Request] ──► [FastAPI Router] ──► [LangSmith SDK (Decors / Auto-traced LCEL)]
                                                    │
                                                    ▼
                                          [LangSmith SaaS Dashboard]
```

1. **Initialization:** The backend initializes the LangSmith client at import time (with `.env` variables already loaded at the top of `main.py`).
2. **Execution Tracing:** As request flows through the routers, all decorators `@traceable` intercept the call:
   - For ingestion, a parent trace wraps `ingestion_pipeline`, containing child spans for `load_document`, `split_chunks`, and `store_chunks`.
   - For queries, `query_documents` forms the root trace, containing child spans for `retrieve_documents` (which records the exact ensemble RRF retrieval latency) and answer generation (`generate_liberal_answer` or `generate_strict_answer`).
   - LCEL prompts, models (ChatGroq), and output parsers are instrumented natively by LangChain and grouped under the same parent span.
3. **Transmission:** Traces are sent asynchronously to `api.smith.langchain.com` without blocking the API response.

---

## Flow 6: Inline PDF Highlight Viewer
Allows the user to pinpoint the precise location of the evidence chunk on the rendered PDF page.

```
[Click View in UI] ────► [POST /api/chunks/{id}/highlight] ────► [Find Chunk in DB]
                                                                        │
                                                                        ▼
[Render Inline PNG] ◄─── [Encode Base64 PNG] ◄── [Highlight PDF Page via fitz]
```

1. **User Action:** The user clicks the **"📄 View"** or **"📄 View in PDF"** button next to a citation chunk.
2. **Frontend UI State:** Streamlit updates `st.session_state` to store that this chunk's viewer is now toggled open.
3. **API Request:** Streamlit sends a GET request to `/api/chunks/{chunk_id}/highlight`.
4. **Backend Processing:**
   - Fetches chunk text, page number, and parent document ID from MongoDB `chunks`.
   - Looks up the source PDF's relative file path in MongoDB `documents`.
   - Opens the PDF using PyMuPDF (`fitz`).
   - Selects the target page (converting 1-indexed page number to 0-indexed page bounds).
   - Searches for the cited chunk text on that page using a robust substring match fallback (120, 80, 50 chars).
   - Draw a yellow highlight annotation on matching text coordinates.
   - Renders the highlighted page to a 2× resolution PNG in memory, base64 encodes it, and returns the string.
5. **Frontend Rendering:** Streamlit decodes the base64 image and displays the PDF page inline directly underneath the clicked citation inside the active result expander.

---

## Technical Summary of Events

| Click / Trigger in Streamlit | API Call | Backend Process | Databases Affected | LLM Used |
|---|---|---|---|---|
| **Process Document** (Ingest) | `POST /api/upload` | Validates file size/extension, saves to disk, starts background pipeline. Chunks, embeds (BGE-large), saves. Traced via LangSmith. | **MongoDB:** `documents` (status=processing -> ready), `chunks` (inserts text). <br>**Qdrant:** Inserts embeddings. | No |
| **🗑️ Trash Icon** (Delete) | `DELETE /api/documents/{id}` | Wipes vectors from Qdrant, deletes chunks and document status records from MongoDB in background. | **MongoDB:** Deletes status + chunks.<br>**Qdrant:** Deletes vector points. | No |
| **Ask Question** (Liberal) | `POST /api/query` | Qdrant semantic search + MongoDB text search -> RRF -> Cross-Encoder rerank -> LLM chain with Liberal template. Traced via LangSmith. | **Qdrant:** Semantic retrieval (read-only).<br>**MongoDB:** Text index search (read-only). | **ChatGroq** (`llama-3.1-8b-instant`) |
| **Ask Question** (Strict) | `POST /api/query` | Qdrant + MongoDB hybrid search -> RRF -> Cross-Encoder rerank. Checks score >= 0.65 -> LLM chain with Strict template -> Call PubMed/arXiv if domain matches. Traced via LangSmith. | **Qdrant:** Semantic retrieval (read-only).<br>**MongoDB:** Text index search (read-only). | **ChatGroq** (`llama-3.1-8b-instant`) |
| **View / View in PDF** (Highlight) | `GET /api/chunks/{id}/highlight` | Reads chunk/doc path from MongoDB, opens PDF with PyMuPDF, searches text, draws highlight, renders to PNG base64. | **MongoDB:** Reads chunk + document metadata (read-only). | No |

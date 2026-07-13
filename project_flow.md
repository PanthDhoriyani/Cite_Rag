# CiteRag — Project Flow
## Step-by-Step Build Roadmap (Phase by Phase)

> **Purpose:** This document translates `PROJECT_PLAN.md` into a concrete, sequential
> build flow — what to do, in what order, and what to validate at each step.
> Follow this file during active development.

---

## Quick Reference — Build Order

```
Phase 1  →  Document Ingestion Pipeline
Phase 2  →  Hybrid Retrieval & Reranking
Phase 3B →  Liberal Analysis Mode  (build before Strict — no external APIs needed)
Phase 3A →  Strict Analysis Mode   (citation grounding + public verification)
Phase 4  →  Frontend UI
Phase 5  →  Docker Deployment
Phase 6  →  Testing & Tuning
```

> **Why 3B before 3A?**
> Liberal Mode validates the full RAG loop (retrieval → generation → output)
> without needing external API integrations (PubMed, arXiv, IEEE).
> Once the pipeline is proven, layer on verification and confidence scoring for Strict Mode.

---

## Phase 1 — Document Ingestion Pipeline

**Goal:** Accept uploaded files, extract text, chunk them, embed them, and store across three databases.

---

### Step 1.1 — Project Scaffolding & Environment Setup

**What to do:**
- Create the root folder structure as defined in `PROJECT_PLAN.md § 11`
- Set up a Python virtual environment in `backend/`
- Create `backend/requirements.txt` with initial dependencies:
  - `fastapi`, `uvicorn`
  - `pymupdf`, `pdfplumber`, `pytesseract`, `python-docx`
  - `langchain`, `sentence-transformers`
  - `qdrant-client`, `pymongo`, `elasticsearch`
  - `python-multipart`, `pydantic`
- Create `.env` file with all environment variable keys (fill values after services are running)

**Files to create:**
```
backend/
  main.py
  requirements.txt
  routers/
  services/
  db/
  models/
.env
```

**Validation:**
- [ ] `uvicorn backend.main:app --reload` starts without errors
- [ ] `GET /api/health` returns `{ "status": "ok" }`

---

### Step 1.2 — File Upload Endpoint

**What to do:**
- Create `backend/routers/upload.py`
- Implement `POST /api/upload` endpoint:
  - Accept `PDF`, `DOCX`, `TXT` files via multipart form
  - Validate file type (whitelist extensions) and size (reject >50MB)
  - Save raw file to `uploads/` directory with a UUID-based filename
  - Generate and return a `document_id`
  - Trigger ingestion pipeline asynchronously (use `BackgroundTasks`)
- Register router in `backend/main.py`

**Files to create / modify:**
```
backend/routers/upload.py      ← NEW
backend/main.py                ← register router
```

**Validation:**
- [ ] Upload a PDF via `curl` or Postman → receive `{ document_id, status: "processing" }`
- [ ] File appears in `uploads/` directory
- [ ] Invalid file types are rejected with `422`

---

### Step 1.3 — Text Extraction Service

**What to do:**
- Create `backend/services/extractor.py`
- Implement extraction routing logic:
  - **PDF:** try `PyMuPDF` first → if output is empty/very short, fall back to `Tesseract OCR`
  - **PDF with tables/forms:** use `pdfplumber`
  - **DOCX:** use `python-docx`
  - **TXT:** plain `open().read()`
- Return raw extracted text with page-level boundaries preserved

**Files to create:**
```
backend/services/extractor.py  ← NEW
```

**Key logic:**
```python
# Extraction priority for PDFs
text = extract_with_pymupdf(file_path)
if len(text.strip()) < 100:
    text = extract_with_tesseract(file_path)  # OCR fallback
```

**Validation:**
- [ ] Standard PDF → PyMuPDF extracts full text
- [ ] Scanned/image PDF → Tesseract OCR extracts text
- [ ] DOCX file → text extracted correctly
- [ ] TXT file → text read correctly

---

### Step 1.4 — Metadata Extraction

**What to do:**
- Extend `extractor.py` or create a helper in `services/`
- For every chunk, capture:
  - `document_id`, `document_name`, `page_number`, `paragraph_number`
  - `line_start`, `line_end`, `upload_timestamp`
  - `domain` (legal / research / healthcare / technical / compliance / education)
  - `chunk_index`, `total_chunks`
- Create `backend/models/schemas.py` with Pydantic models for `ChunkMetadata`, `DocumentInfo`

**Files to create / modify:**
```
backend/models/schemas.py      ← NEW  (Pydantic models)
backend/services/extractor.py  ← MODIFY (add metadata capture)
```

**Validation:**
- [ ] Each extracted page/paragraph has all metadata fields populated
- [ ] `domain` field is set (either inferred or passed from upload request)
- [ ] No metadata field is null except optional ones

---

### Step 1.5 — Semantic Chunking

**What to do:**
- Create `backend/services/chunker.py`
- Use `LangChain RecursiveCharacterTextSplitter`:
  - Chunk size: **512 tokens**
  - Overlap: **128 tokens**
- Attach metadata to each chunk (link back to source page/paragraph)
- Return a list of `{ chunk_text, metadata }` objects

**Files to create:**
```
backend/services/chunker.py    ← NEW
```

**Key logic:**
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)
chunks = splitter.split_text(raw_text)
```

**Validation:**
- [ ] Long document splits into multiple overlapping chunks
- [ ] Metadata is preserved per chunk (not lost during splitting)
- [ ] Overlap is visible — adjacent chunks share ~128 tokens of text

---

### Step 1.6 — Embedding Generation

**What to do:**
- Create `backend/services/embedder.py`
- Load model `BAAI/bge-large-en-v1.5` via `sentence-transformers`
- For each chunk, generate a 1024-dimensional embedding vector
- Cache the model at startup (not per request) to avoid repeated loading

**Files to create:**
```
backend/services/embedder.py   ← NEW
```

**Key logic:**
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-large-en-v1.5")
embedding = model.encode(chunk_text)  # shape: (1024,)
```

**Validation:**
- [ ] Embedding vector has shape `(1024,)`
- [ ] Model loads once at startup, not per chunk
- [ ] Embedding generation completes in reasonable time per chunk

---

### Step 1.7 — Database Clients Setup

**What to do:**
- Start Qdrant, MongoDB, Elasticsearch locally (or via Docker)
- Create database client wrappers:
  - `backend/db/qdrant_client.py` — connect, create collection, upsert vectors
  - `backend/db/mongo_client.py` — connect, insert chunk docs, query by `document_id`
  - `backend/db/elastic_client.py` — connect, create index, index chunk text

**Files to create:**
```
backend/db/qdrant_client.py    ← NEW
backend/db/mongo_client.py     ← NEW
backend/db/elastic_client.py   ← NEW
```

**Qdrant collection setup:**
```python
# Collection: cosine similarity, 1024 dimensions
client.recreate_collection("documents", vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
```

**Validation:**
- [ ] Qdrant responds at `http://localhost:6333`
- [ ] MongoDB responds at `mongodb://localhost:27017`
- [ ] Elasticsearch responds at `http://localhost:9200`
- [ ] Each client can connect and perform a basic read/write

---

### Step 1.8 — Storage Pipeline (Wire Everything Together)

**What to do:**
- Create the full ingestion pipeline that calls all steps in sequence:
  1. Extract text from file
  2. Extract metadata
  3. Chunk text
  4. Generate embeddings
  5. Store in all three databases:
     - **Qdrant:** embedding vector + metadata payload
     - **MongoDB:** full chunk text + metadata
     - **Elasticsearch:** chunk text for BM25 indexing
- Wire this pipeline into the `BackgroundTasks` job triggered by the upload endpoint

**Files to modify:**
```
backend/routers/upload.py      ← MODIFY (trigger ingestion pipeline)
backend/services/             ← all services called here
```

**Validation:**
- [ ] Upload a PDF → all chunks appear in Qdrant, MongoDB, and Elasticsearch
- [ ] Qdrant: vectors stored with correct metadata payload
- [ ] MongoDB: full chunk text retrievable by `document_id`
- [ ] Elasticsearch: keyword search returns indexed chunks

---

### Phase 1 Complete Checklist
- [ ] File upload API endpoint working
- [ ] PyMuPDF extraction working on standard PDFs
- [ ] Tesseract OCR fallback working on scanned PDFs
- [ ] Metadata captured per chunk (all fields)
- [ ] Chunking with 512/128 overlap implemented
- [ ] BGE embeddings generated (1024-dim)
- [ ] Vectors stored in Qdrant
- [ ] Metadata + text stored in MongoDB
- [ ] BM25 index populated in Elasticsearch

---

## Phase 2 — Hybrid Retrieval & Reranking

**Goal:** Given a user question, retrieve the most relevant chunks from all three stores and rerank them.

---

### Step 2.1 — Query Input Endpoint

**What to do:**
- Create `backend/routers/query.py`
- Implement `POST /api/query` endpoint accepting:
  - `question` (string)
  - `document_ids` (list, optional filter)
  - `domain` (string, optional filter)
  - `mode` ("strict" | "liberal")
- Register router in `backend/main.py`
- Route to retrieval pipeline based on `mode`

**Files to create / modify:**
```
backend/routers/query.py       ← NEW
backend/main.py                ← register router
backend/models/schemas.py      ← add QueryRequest, QueryResponse models
```

**Validation:**
- [ ] `POST /api/query` with a question returns `200`
- [ ] Missing `question` field returns `422 Unprocessable Entity`

---

### Step 2.2 — BM25 Keyword Retrieval

**What to do:**
- Create `backend/services/retriever.py`
- Implement `bm25_retrieve(question, top_k=20)`:
  - Run a `multi_match` query on Elasticsearch across `chunk_text` and `document_name`
  - Return top-20 chunk IDs + BM25 scores
  - Apply optional `document_id` and `domain` filters

**Files to create:**
```
backend/services/retriever.py  ← NEW
```

**Elasticsearch query:**
```json
{
  "query": {
    "multi_match": {
      "query": "<user question>",
      "fields": ["chunk_text", "document_name"]
    }
  },
  "size": 20
}
```

**Validation:**
- [ ] Keyword query returns top-20 chunks from Elasticsearch
- [ ] Domain/document filter narrows results correctly
- [ ] Scores are included in results

---

### Step 2.3 — Vector Semantic Retrieval

**What to do:**
- Extend `retriever.py` with `vector_retrieve(question, top_k=20)`:
  - Embed the user question using BGE model
  - Run nearest-neighbor search in Qdrant by cosine similarity
  - Return top-20 chunk IDs + similarity scores
  - Apply optional filters

**Files to modify:**
```
backend/services/retriever.py  ← MODIFY (add vector retrieval)
```

**Validation:**
- [ ] Semantic query returns top-20 chunks from Qdrant
- [ ] Paraphrased queries return conceptually relevant chunks
- [ ] Results differ meaningfully from BM25 results (complementary)

---

### Step 2.4 — Result Merging & Deduplication

**What to do:**
- Extend `retriever.py` with `merge_results(bm25_results, vector_results)`:
  - Combine both result lists
  - Deduplicate by `chunk_id`
  - Expected: 25–40 unique chunks
- Fetch full chunk text from MongoDB for merged chunk IDs

**Files to modify:**
```
backend/services/retriever.py  ← MODIFY (add merge + dedup)
```

**Validation:**
- [ ] No duplicate chunks in merged list
- [ ] Full chunk text is attached to each result (fetched from MongoDB)
- [ ] Merged list has 25–40 unique items typically

---

### Step 2.5 — Cross-Encoder Reranking

**What to do:**
- Create `backend/services/reranker.py`
- Load `BAAI/bge-reranker-large`
- Implement `rerank(question, chunks, top_k=10)`:
  - Score each `(question, chunk_text)` pair
  - Sort by descending score
  - Return top-8 to top-12 chunks

**Files to create:**
```
backend/services/reranker.py   ← NEW
```

**Key logic:**
```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder("BAAI/bge-reranker-large")
scores = reranker.predict([(question, chunk.text) for chunk in chunks])
ranked = sorted(zip(scores, chunks), reverse=True)
top_chunks = [chunk for _, chunk in ranked[:10]]
```

**Validation:**
- [ ] Reranker assigns scores to all chunks
- [ ] Top-10 chunks are selected from merged 25–40
- [ ] Reranker score stored per chunk for downstream confidence scoring

---

### Phase 2 Complete Checklist
- [ ] BM25 retrieval from Elasticsearch working
- [ ] Vector retrieval from Qdrant working
- [ ] Result merging and deduplication working
- [ ] Cross-encoder reranking working
- [ ] Top-N chunks selected for generation with scores

---

## Phase 3B — Liberal Analysis Mode

**Goal:** Build the simpler, educational mode first to validate the full RAG loop end-to-end.
Build this before Strict Mode — no external API calls needed.

---

### Step 3B.1 — Liberal Mode Pipeline Service

**What to do:**
- Create `backend/services/liberal_mode.py`
- Pipeline sequence:
  1. Receive top reranked chunks
  2. Build document-based answer using LLM (chunks as primary context)
  3. Allow LLM to extend with broader knowledge
  4. Return structured output separating document vs AI content

**Files to create:**
```
backend/services/liberal_mode.py   ← NEW
```

---

### Step 3B.2 — Ollama LLM Integration

**What to do:**
- Ensure Ollama is running locally with model pulled (llama3:8b / mistral / deepseek-r1)
- Implement LLM call via Ollama REST API or LangChain Ollama wrapper
- Use the Liberal Mode system prompt:
  - "You are a helpful educational assistant."
  - "First, answer from the provided document evidence."
  - "Then, you may add broader explanation and context from your knowledge."
  - "Clearly separate what comes from the document and what is additional explanation."
  - "Use simple language where possible."

**Validation:**
- [ ] Ollama responds at `http://localhost:11434`
- [ ] LLM generates a response using the provided chunks as context
- [ ] Response contains both a document section and an AI section

---

### Step 3B.3 — Source Transparency Enforcement

**What to do:**
- Parse LLM output to enforce two-section structure:
  - `DOCUMENT-BASED ANSWER:` — sourced from chunks
  - `ADDITIONAL EXPLANATION:` — AI-added knowledge
- Attach soft citations per document answer (document name, page, paragraph)
- Return structured `QueryResponse` object

**Output structure:**
```
DOCUMENT-BASED ANSWER:
[Answer derived from uploaded document chunks]
Source: ResearchPaper.pdf, Page 4, Paragraph 2

---

ADDITIONAL EXPLANATION:
[Broader context, analogies, examples added by AI]
```

**Validation:**
- [ ] Output always has both sections (even if AI section is minimal)
- [ ] Document section always has at least one soft citation
- [ ] No blending of document and AI content without labels

---

### Step 3B.4 — Wire Liberal Mode to Query Endpoint

**What to do:**
- In `backend/routers/query.py`, route `mode: "liberal"` queries to `liberal_mode.py`
- Return the full structured `QueryResponse` via the API

**Files to modify:**
```
backend/routers/query.py       ← MODIFY (add liberal mode routing)
```

**Validation (end-to-end):**
- [ ] Upload a PDF → ask a question in liberal mode → receive structured response
- [ ] Response has document section with citation
- [ ] Response has AI explanation section

---

### Phase 3B Complete Checklist
- [ ] Document-first answer generation working
- [ ] LLM knowledge expansion layer working
- [ ] Output clearly separates document vs AI content
- [ ] Soft citations included (doc name, page, paragraph)
- [ ] Liberal mode system prompt implemented
- [ ] End-to-end flow: upload → query → liberal response PASS

---

## Phase 3A — Strict Analysis Mode

**Goal:** Enterprise-grade, hallucination-free, citation-mandatory, publicly verified answers.
Build after Phase 3B — same retrieval pipeline, more layers on top.

---

### Step 3A.1 — Citation Grounding Validation

**What to do:**
- Create `backend/services/strict_mode.py`
- Before calling the LLM, check:
  - Top reranked chunk score >= **0.65** (from reranker)
  - If score < 0.65 → return rejection message, do NOT call LLM
- Implement `validate_evidence(chunks, threshold=0.65) -> bool`

**Rejection message:**
```
"Insufficient evidence found in the uploaded documents to answer this question."
```

**Files to create:**
```
backend/services/strict_mode.py    ← NEW
```

**Validation:**
- [ ] Question with no relevant chunks → rejection message returned
- [ ] Question with strong relevant chunks (score > 0.65) → pipeline continues

---

### Step 3A.2 — Public Source Verification

**What to do:**
- Create `backend/services/verifier.py`
- Implement domain-specific API calls:
  - `healthcare` → PubMed API (https://eutils.ncbi.nlm.nih.gov/)
  - `research` → arXiv API (https://export.arxiv.org/api/)
  - `research` → Semantic Scholar API
  - `legal` → Government legal portals
  - `technical` → RFC databases, official docs
  - `compliance` → FDA, SEC regulatory sites
- For each domain:
  1. Extract key claims from top retrieved chunks
  2. Form a verification query string
  3. Call the relevant public API
  4. Return the retrieved public evidence paragraphs

**Files to create:**
```
backend/services/verifier.py   ← NEW
```

**Validation:**
- [ ] Healthcare query → PubMed returns relevant evidence
- [ ] Research query → arXiv returns relevant evidence
- [ ] Correct API is called based on document domain
- [ ] API errors are gracefully handled (return "no public evidence found")

---

### Step 3A.3 — Consistency Check

**What to do:**
- Extend `strict_mode.py` with `check_consistency(doc_claims, public_evidence)`:
  - Compare claims from uploaded document vs public source evidence
  - Return one of three statuses:
    - `Verified` — document claim matches public source
    - `Contradiction detected` — document claim conflicts with public source
    - `Insufficient public evidence` — no matching public evidence found

**Files to modify:**
```
backend/services/strict_mode.py    ← MODIFY (add consistency check)
```

**Validation:**
- [ ] Matching claims → `Verified` status
- [ ] Conflicting claims → `Contradiction detected` status
- [ ] No public evidence → `Insufficient public evidence` status

---

### Step 3A.4 — Confidence Scoring

**What to do:**
- Extend `strict_mode.py` with `calculate_confidence(...)`:
  - Inputs: reranker score, number of supporting chunks, consistency result, domain trust level
  - Output: float `0.0 – 1.0`
- Apply thresholds:
  - `< 0.5` → reject: "Low confidence — answer not generated"
  - `0.5 – 0.75` → generate with warning label
  - `> 0.75` → full answer with citations

**Files to modify:**
```
backend/services/strict_mode.py    ← MODIFY (add confidence scoring)
```

**Validation:**
- [ ] Score < 0.5 → answer rejected, rejection message returned
- [ ] Score 0.5–0.75 → answer with warning banner
- [ ] Score > 0.75 → full answer with citations

---

### Step 3A.5 — Grounded LLM Generation (Strict Prompt)

**What to do:**
- Call Ollama with the Strict Mode system prompt:
  - "You are a strict evidence-based assistant."
  - "Answer ONLY using the provided evidence chunks."
  - "Do NOT add any information not found in the evidence."
  - "Do NOT speculate or infer beyond what is written."
  - "Every sentence in your answer must be traceable to a provided chunk."
  - "If you cannot answer from the evidence alone, say so explicitly."
- Pass ONLY top reranked chunks as context — no additional knowledge

**Validation:**
- [ ] LLM answer contains only information traceable to provided chunks
- [ ] LLM does not speculate or add external knowledge

---

### Step 3A.6 — Strict Mode Output Assembly

**What to do:**
- Assemble the final structured output with:
  - Answer text
  - Uploaded document citation (doc name, page, paragraph, line range, chunk text)
  - Verified public source (source name, section, URL)
  - Consistency status
  - Confidence score
- Wire to `POST /api/query` for `mode: "strict"`

**Files to modify:**
```
backend/services/strict_mode.py    ← MODIFY (output assembly)
backend/routers/query.py           ← MODIFY (add strict mode routing)
```

**Validation (end-to-end):**
- [ ] Upload document → ask question in strict mode → receive full structured response
- [ ] Uploaded document citation is accurate (page/paragraph match)
- [ ] Public source URL is real and relevant
- [ ] Consistency status and confidence score present

---

### Phase 3A Complete Checklist
- [ ] Insufficient evidence detection working (threshold 0.65)
- [ ] Public source API queries working (PubMed / arXiv / IEEE)
- [ ] Consistency comparison logic working (3 statuses)
- [ ] Confidence scoring formula implemented (0.0–1.0)
- [ ] Strict LLM system prompt enforced
- [ ] Full structured output returned
- [ ] End-to-end flow: upload → query → strict response PASS

---

## Phase 4 — Output Layer & Frontend

**Goal:** Build the React + Tailwind UI for uploading documents, asking questions, and exploring citations.

---

### Step 4.1 — Project Setup (React + Tailwind)

**What to do:**
- Scaffold React app inside `frontend/`
- Install and configure Tailwind CSS
- Set up API base URL pointing to FastAPI backend (`http://localhost:8000`)
- Create base layout (sidebar + main content area)

**Files to create:**
```
frontend/src/App.jsx
frontend/src/index.js
frontend/package.json
frontend/tailwind.config.js
```

---

### Step 4.2 — Upload Zone Component

**What to do:**
- Build `frontend/src/components/UploadZone.jsx`
- Features:
  - Drag-and-drop or click-to-upload area
  - Accepts PDF, DOCX, TXT
  - Progress bar during upload
  - Status display: `Processing...` / `Ready`
  - Domain selector dropdown
  - Error display for rejected files
- Connect to `POST /api/upload`

---

### Step 4.3 — Mode Toggle Component

**What to do:**
- Build `frontend/src/components/ModeToggle.jsx`
- Prominent toggle: **Strict Mode** | **Liberal Mode**
- Brief description under each mode label
- Selected mode stored in app state, passed to query requests

---

### Step 4.4 — Query Input Component

**What to do:**
- Build `frontend/src/components/QueryInput.jsx`
- Features:
  - Text input for the user question
  - Domain filter dropdown (optional)
  - Document filter (select from uploaded documents, optional)
  - Submit button
  - Loading spinner during query processing
- Connect to `POST /api/query` with selected mode

---

### Step 4.5 — Strict Mode Answer Viewer

**What to do:**
- Build `frontend/src/components/StrictAnswerView.jsx`
- Layout:
  - Answer text panel
  - Expandable citation cards:
    - Document name, page, paragraph, line range
    - Chunk text preview (collapsible)
    - Public source link (clickable URL)
    - Consistency status badge (green / red / gray)
    - Confidence score progress bar (green / yellow / red)
  - Warning banner for low-confidence answers (0.5–0.75 range)

---

### Step 4.6 — Liberal Mode Answer Viewer

**What to do:**
- Build `frontend/src/components/LiberalAnswerView.jsx`
- Two-section layout:
  - **"From your document"** section with soft citation tags
  - **"Additional context"** section with AI badge label and distinct styling

---

### Step 4.7 — Document Manager Component

**What to do:**
- Build `frontend/src/components/DocumentManager.jsx`
- Features:
  - List all uploaded documents with domain tags and timestamps
  - Delete button → calls `DELETE /api/documents/{id}`
  - Re-index button → triggers re-ingestion
- Connect to `GET /api/documents`

---

### Step 4.8 — Remaining API Endpoints

**What to do:**
- Implement remaining backend endpoints:
  - `GET /api/documents` — list all uploaded documents
  - `DELETE /api/documents/{id}` — remove from all three stores
  - `GET /api/health` — health check for Qdrant, MongoDB, ES, Ollama

**Files to modify:**
```
backend/routers/upload.py      ← MODIFY (add GET + DELETE)
backend/main.py                ← register health check
```

---

### Phase 4 Complete Checklist
- [ ] Upload zone component built and working
- [ ] Mode toggle working and state propagated to queries
- [ ] Query input with domain/document filters built
- [ ] Strict mode answer viewer with citation cards built
- [ ] Liberal mode two-section answer viewer built
- [ ] Document manager (list, delete) built
- [ ] All API endpoints connected to frontend
- [ ] End-to-end UI test: upload → query → view answer PASS

---

## Phase 5 — Docker Deployment

**Goal:** Containerize every service so the entire stack launches with `docker-compose up`.

---

### Step 5.1 — Backend Dockerfile

**What to do:**
- Create `backend/Dockerfile`
- Base image: `python:3.11-slim`
- Install system dependencies (Tesseract, poppler, etc.)
- Install Python dependencies from `requirements.txt`
- Expose port `8000`
- Start: `uvicorn main:app --host 0.0.0.0 --port 8000`

---

### Step 5.2 — Frontend Dockerfile

**What to do:**
- Create `frontend/Dockerfile`
- Multi-stage build:
  - Stage 1: Node build (`npm run build`)
  - Stage 2: Nginx serve static files
- Expose port `3000` (or `80`)

---

### Step 5.3 — Docker Compose

**What to do:**
- Create `docker-compose.yml` with all 6 services:

| Service         | Image                      | Port  |
|-----------------|----------------------------|-------|
| `frontend`      | Custom Dockerfile          | 3000  |
| `backend`       | Custom Dockerfile          | 8000  |
| `qdrant`        | `qdrant/qdrant`            | 6333  |
| `mongodb`       | `mongo:7`                  | 27017 |
| `elasticsearch` | `elasticsearch:8.x`        | 9200  |
| `ollama`        | `ollama/ollama`            | 11434 |

- Add volume mounts for data persistence
- Add health checks for all services
- Configure `depends_on` between services
- Add Ollama model pre-pull on startup

---

### Step 5.4 — Environment Variables

**What to do:**
- Finalize `.env` file:

```env
MONGODB_URL=mongodb://mongodb:27017
QDRANT_URL=http://qdrant:6333
ELASTICSEARCH_URL=http://elasticsearch:9200
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama3:8b
CONFIDENCE_THRESHOLD=0.65
```

- Ensure backend reads from env vars (not hardcoded)

---

### Phase 5 Complete Checklist
- [ ] Dockerfile for FastAPI backend
- [ ] Dockerfile for React frontend
- [ ] `docker-compose.yml` with all 6 services
- [ ] `.env` file configured
- [ ] Volume mounts for data persistence
- [ ] Ollama model pre-pulled on startup
- [ ] Health checks for all services
- [ ] `docker-compose up` starts entire stack PASS

---

## Phase 6 — Testing & Tuning

**Goal:** Validate correctness, performance, and quality of the full pipeline.

---

### Step 6.1 — Pipeline Integration Tests

**What to do:**
- Upload 2–3 test documents across different domains (PDF, DOCX)
- Run queries in both modes
- Verify every stage produces expected output
- Test edge cases:
  - Empty document upload
  - Question with no relevant chunks → rejection
  - Scanned/image PDF → OCR fallback activates

---

### Step 6.2 — Chunk Size & Overlap Tuning

**What to do:**
- Test retrieval quality with different chunk configs:
  - Default: 512 tokens / 128 overlap
  - Alternative: 256 tokens / 64 overlap (more granular)
  - Alternative: 768 tokens / 192 overlap (more context)
- Measure: are the right passages being retrieved?

---

### Step 6.3 — Reranker Threshold Tuning

**What to do:**
- Adjust the confidence threshold (default `0.65`)
- Test lower (0.5) — are noisy answers being accepted?
- Test higher (0.75) — are too many valid answers rejected?
- Set final value in `.env` as `CONFIDENCE_THRESHOLD`

---

### Step 6.4 — Public Source Verification Accuracy

**What to do:**
- Test healthcare documents → verify PubMed returns relevant papers
- Test research papers → verify arXiv returns relevant abstracts
- Confirm domain routing is correct (no PubMed calls for legal documents)

---

### Step 6.5 — Frontend UX Review

**What to do:**
- Full end-to-end UI walkthrough
- Verify citation cards display all fields correctly
- Verify confidence score bar renders accurately
- Test upload, query, and document manager flows
- Check error handling for rejected answers and network errors

---

### Phase 6 Complete Checklist
- [ ] Integration tests pass for both modes
- [ ] Chunk size and overlap optimized
- [ ] Reranker threshold tuned and finalized
- [ ] Public source verification tested per domain
- [ ] Frontend UX reviewed and polished
- [ ] All design rules from `PROJECT_PLAN.md § 12` enforced PASS

---

## Key Design Rules (Always Enforce)

| Rule | Description |
|------|-------------|
| No hallucination | Strict Mode: insufficient evidence = rejection, never speculate |
| Citations mandatory | Every statement in Strict Mode must trace to a chunk |
| Reranking is required | Never skip — it is the quality gate before LLM |
| Transparency in Liberal | Always label document content vs AI content — never blend silently |
| Act on confidence scores | Low-confidence answers must be rejected, not just flagged |
| Metadata is sacred | Page/paragraph numbers captured at ingestion cannot be reconstructed later |
| Chunk overlap required | Never chunk without overlap — lost context at boundaries = retrieval failure |
| Domain-specific verification | Route each domain to the correct public source (PubMed is not for legal) |

---

## Summary Table

| Phase    | What Gets Built                                     | Key Output                          |
|----------|-----------------------------------------------------|-------------------------------------|
| Phase 1  | Ingestion pipeline (extract, chunk, embed, store)   | 3 populated databases               |
| Phase 2  | Hybrid retrieval + cross-encoder reranking          | Top-10 ranked chunks per query      |
| Phase 3B | Liberal mode (doc-first + AI expansion)             | Educational structured response     |
| Phase 3A | Strict mode (citation + verification + confidence)  | Verified, cited enterprise response |
| Phase 4  | React + Tailwind frontend                           | Full interactive UI                 |
| Phase 5  | Docker Compose deployment                           | One-command stack launch            |
| Phase 6  | Testing & parameter tuning                          | Production-ready system             |

---

*Reference: PROJECT_PLAN.md*
*Keep this file updated as phases are completed.*

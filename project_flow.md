# CiteRag — Project Flow
> What we are building, in what order, and exactly what code goes in each step.
> Simple coding style — RAG-focused, not enterprise-modular.

---

## What We Are Building

A **RAG system** that lets you upload documents and ask questions.
The system finds the most relevant chunks from the documents and uses a local AI to generate a cited answer.

Two answer modes:
- **Liberal Mode** — answers from the document + extra AI explanation
- **Strict Mode** — answers ONLY from the document, with citations and a confidence score

---

## File Structure (Final)

```
CiteRag/
  backend/
    main.py          ← FastAPI app, routes, CORS
    config.py        ← all keys, URLs, model names from .env
    schemas.py       ← Pydantic models for request/response
    pipeline.py      ← RAG ingestion: extract → chunk → embed → store
    retrieval.py     ← RAG retrieval: BM25 + vector search → merge → rerank
    generation.py    ← RAG generation: liberal mode + strict mode answers
    routers/
      upload.py      ← POST /api/upload, GET /api/documents, DELETE /api/documents/{id}
      query.py       ← POST /api/query
    db/
      qdrant_client.py   ← vector store (semantic search)
      mongo_client.py    ← text + metadata store
      elastic_client.py  ← BM25 keyword index
    requirements.txt
  frontend/          ← React app (Phase 4)
  .env               ← all secrets and settings
  docker-compose.yml ← Phase 5
```

---

## .env (All Keys in One Place)

```
# Databases
MONGODB_URL=mongodb://localhost:27017
QDRANT_URL=http://localhost:6333
ELASTICSEARCH_URL=http://localhost:9200
OLLAMA_URL=http://localhost:11434

# Models
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama3:8b

# Pipeline settings
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

## Phase 1 — Ingestion Pipeline ✅ DONE

**Goal:** Upload a file → read text → split into chunks → embed → save to 3 databases

### What happens when a file is uploaded:

```
POST /api/upload
  → validate: extension must be pdf/docx/txt, size < 50MB
  → save file as uploads/{uuid}.{ext}
  → save document record to MongoDB {status: "processing"}
  → run pipeline.run() in background
  → return {document_id, status: "processing"} immediately
```

### pipeline.py — 4 functions, called in order

**extract(file_path, file_type)**
- PDF: use PyMuPDF to get text page by page
- If PDF gives < 100 chars: PDF is scanned → use Tesseract OCR (render page as 300 DPI image)
- DOCX: use python-docx to read paragraphs
- TXT: just read the file
- Returns: `[{"page_number": 1, "text": "..."}, ...]`

**chunk(pages, doc_info)**
- Use LangChain `RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=128)`
- Split each page separately (so page_number stays accurate per chunk)
- Each chunk gets: chunk_id, chunk_text, page_number, paragraph_number, document_id, domain, etc.
- Returns: list of chunk dicts

**embed(texts)**
- Load `BAAI/bge-large-en-v1.5` once, reuse forever (singleton)
- Encode all chunk texts in one batch, normalize_embeddings=True
- Returns: list of 1024-float vectors

**store(chunks, vectors)**
- Qdrant: save vectors + metadata (for semantic search)
- MongoDB: save full chunk text + metadata (source of truth)
- Elasticsearch: index chunk text (for BM25 keyword search)

### run() — calls all 4 in order
```python
def run(document_id, file_path, filename, file_type, domain, upload_timestamp):
    qdrant.setup()
    elastic.setup()
    pages   = extract(file_path, file_type)
    chunks  = chunk(pages, {...})
    vectors = embed([c["chunk_text"] for c in chunks])
    store(chunks, vectors)
    mongo.update_status(document_id, "ready", len(chunks))
```

### DB clients (simple module-level connections)

**db/qdrant_client.py**
```python
client = QdrantClient(url=QDRANT_URL)
def setup()                            # create collection if not exists
def store_batch(ids, vectors, payloads)# save embeddings
def search(query_vector, top_k)        # semantic search
def delete_document(document_id)       # remove all vectors for a doc
```

**db/mongo_client.py**
```python
db     = MongoClient(MONGODB_URL)["citerag"]
chunks    = db["chunks"]
documents = db["documents"]
def save_chunks(chunk_list)            # bulk insert chunks
def get_chunks(chunk_ids)              # fetch by id list
def save_document(doc)                 # create document record
def update_status(doc_id, status, n)   # processing → ready / failed
def all_documents()                    # list all for GET /api/documents
def remove_document(doc_id)            # delete doc + its chunks
```

**db/elastic_client.py**
```python
client = Elasticsearch(ELASTICSEARCH_URL)
def setup()                            # create index if not exists
def index_chunks(chunk_list)           # bulk index for BM25
def search(query, top_k)               # BM25 keyword search
def delete_document(document_id)       # remove from index
```

---

## Phase 2 — Retrieval + Reranking (Next)

**Goal:** Take a user question → find the best chunks → rerank for precision

### What happens when a question is asked:

```
POST /api/query  {question, mode, document_ids, domain}
  → BM25 search (Elasticsearch) → top 20 chunks by keyword
  → Vector search (Qdrant)      → top 20 chunks by meaning
  → merge + dedup               → ~25-40 unique chunks
  → fetch full text (MongoDB)   → hydrate results
  → rerank (bge-reranker-large) → top 10 chunks
  → pass to generation (Phase 3)
```

### retrieval.py — 3 functions

**bm25_search(question, top_k, document_id, domain)**
```python
# Elasticsearch multi_match query
results = elastic.search(question, top_k, document_id, domain)
# Returns: [{"chunk_id": "...", "score": 0.9}, ...]
```

**vector_search(question, top_k, filters)**
```python
# Embed the question, then find nearest neighbours in Qdrant
query_vector = embed([question])[0]
results = qdrant.search(query_vector, top_k, filters)
# Returns: [{"chunk_id": "...", "score": 0.85, "metadata": {...}}, ...]
```

**merge_and_rerank(question, bm25_results, vector_results)**
```python
# 1. Merge both lists, dedup by chunk_id
all_ids = deduplicate(bm25_results + vector_results)

# 2. Fetch full text from MongoDB
chunks = mongo.get_chunks(all_ids)

# 3. Rerank with cross-encoder
from sentence_transformers import CrossEncoder
reranker = CrossEncoder(RERANKER_MODEL)   # loaded once
pairs    = [(question, c["chunk_text"]) for c in chunks]
scores   = reranker.predict(pairs)

# 4. Sort and return top 10
top_chunks = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)[:RERANKER_TOP_K]
# Returns: top chunks with scores attached
```

### Files to create:
- `backend/retrieval.py` — the 3 functions above
- Update `backend/routers/query.py` — wire in retrieval

---

## Phase 3B — Liberal Mode Answer (After Phase 2)

**Goal:** Generate an answer from the document, then add AI explanation

### Why 3B before 3A?
Liberal mode is simpler — it doesn't need to call PubMed / arXiv APIs. Build and test the full RAG loop (retrieve → generate → respond) here first.

### generation.py — liberal_answer(question, top_chunks)

```python
# Build context from top chunks
context = "\n\n".join([
    f"[Page {c['page_number']}, Para {c['paragraph_number']}]\n{c['chunk_text']}"
    for c in top_chunks
])

# System prompt — document first, then AI can add more
system_prompt = """
You are a helpful educational assistant.
First answer using ONLY the provided document chunks.
Then you may add broader explanation from your knowledge.
Clearly separate the two sections:
  DOCUMENT-BASED ANSWER:
  ADDITIONAL EXPLANATION:
"""

# Call Ollama (local LLM)
import httpx
response = httpx.post(f"{OLLAMA_URL}/api/generate", json={
    "model": LLM_MODEL,
    "system": system_prompt,
    "prompt": f"Context:\n{context}\n\nQuestion: {question}",
    "stream": False
})
answer_text = response.json()["response"]

# Parse into two sections
doc_part, ai_part = parse_liberal_output(answer_text)

return {
    "document_answer": doc_part,
    "ai_explanation":  ai_part,
    "citations":       build_citations(top_chunks),
    "mode": "liberal"
}
```

### Output format:
```json
{
  "mode": "liberal",
  "document_answer": "According to page 4, the recommended dosage is...",
  "ai_explanation": "In simpler terms, this means...",
  "citations": [
    {"document": "paper.pdf", "page": 4, "paragraph": 2, "text": "..."}
  ]
}
```

### Files to create:
- `backend/generation.py` — liberal_answer() function
- Update `backend/routers/query.py` — call generation after retrieval

---

## Phase 3A — Strict Mode Answer (After Phase 3B)

**Goal:** Zero-hallucination, citation-mandatory, publicly verified answers

### generation.py — strict_answer(question, top_chunks)

**Step 1 — Evidence threshold check**
```python
best_score = top_chunks[0]["reranker_score"]
if best_score < CONFIDENCE_THRESHOLD:   # 0.65
    return {"error": "Insufficient evidence to answer this question."}
```

**Step 2 — Confidence score**
```python
# Simple formula: weighted average of top chunk scores
confidence = sum(c["reranker_score"] for c in top_chunks[:3]) / 3
# 0.0–0.5: reject, 0.5–0.75: warn, 0.75+: full answer
```

**Step 3 — Public verification (by domain)**
```python
def verify(question, domain, top_chunks):
    claims = extract_key_claims(top_chunks)  # get key phrases
    if domain == "healthcare":
        return query_pubmed(claims)
    elif domain == "research":
        return query_arxiv(claims)
    elif domain == "legal":
        return query_legal_portal(claims)
    # etc.
```

PubMed API call (example):
```python
import httpx
r = httpx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={
    "db": "pubmed", "term": query_text, "retmode": "json", "retmax": 3
})
pmids = r.json()["esearchresult"]["idlist"]
# then fetch abstracts with efetch
```

**Step 4 — Consistency check**
```python
# Compare document claim against public source
# Returns: "Verified" / "Contradiction detected" / "Insufficient public evidence"
```

**Step 5 — LLM generation (strict prompt)**
```python
system_prompt = """
You are a strict evidence-based assistant.
Answer ONLY from the provided evidence chunks.
Do NOT add anything not in the evidence.
Every sentence must be traceable to a chunk.
If you cannot answer, say: "Insufficient evidence."
"""
```

**Step 6 — Structured output**
```json
{
  "mode": "strict",
  "answer": "The recommended dosage is 10mg twice daily...",
  "citations": [
    {
      "document": "ClinicalTrial.pdf",
      "page": 4, "paragraph": 2,
      "text": "...exact chunk text...",
      "reranker_score": 0.91
    }
  ],
  "public_source": {
    "source": "PubMed — PMID 123456",
    "url": "https://pubmed.ncbi.nlm.nih.gov/123456",
    "abstract": "..."
  },
  "consistency": "Verified",
  "confidence": 0.87
}
```

### Files to create:
- Add `strict_answer()` to `backend/generation.py`
- Add `verifier.py` for domain-specific public API calls
- Update `backend/routers/query.py` — route by mode

---

## Phase 4 — Frontend (After Phase 3)

**Goal:** React UI to upload files and ask questions

### Components to build:

| File | What it shows |
|---|---|
| `UploadZone.jsx` | Drag-drop file upload + domain selector + progress |
| `ModeToggle.jsx` | Switch: Strict Mode ↔ Liberal Mode |
| `QueryInput.jsx` | Question box + document filter + submit |
| `StrictAnswerView.jsx` | Answer + citation cards + confidence bar |
| `LiberalAnswerView.jsx` | Two sections: "From document" + "AI explanation" |
| `DocumentManager.jsx` | List of uploaded docs + delete button |

### API endpoints the frontend calls:
```
POST   /api/upload            → upload a file
GET    /api/documents         → get list of docs + status
DELETE /api/documents/{id}    → delete a document
POST   /api/query             → ask a question
GET    /api/health            → check if backend is running
```

---

## Phase 5 — Docker (After Frontend)

**Goal:** One command starts everything

```yaml
# docker-compose.yml
services:
  backend:       FastAPI on port 8000
  frontend:      React on port 3000
  qdrant:        Qdrant on port 6333
  mongodb:       MongoDB on port 27017
  elasticsearch: Elasticsearch on port 9200
  ollama:        Ollama on port 11434
```

```bash
docker-compose up   # starts all 6 services
```

---

## Phase 6 — Test + Tune (After Docker)

- Upload test PDFs across different domains
- Try questions in both modes
- Check citation accuracy
- Tune chunk_size (try 256 and 768)
- Tune confidence_threshold (try 0.5 and 0.75)
- Test public API verification per domain

---

## Current Status

| Phase | Status |
|---|---|
| Phase 1 — Ingestion Pipeline | ✅ Done |
| Phase 2 — Retrieval + Reranking | ⏳ Next |
| Phase 3B — Liberal Mode | ⏳ After Phase 2 |
| Phase 3A — Strict Mode | ⏳ After Phase 3B |
| Phase 4 — Frontend | ⏳ After Phase 3 |
| Phase 5 — Docker | ⏳ After Phase 4 |
| Phase 6 — Testing | ⏳ Last |

---

## Key Rules (Never Break These)

1. **Strict Mode never guesses** — if confidence < 0.65, return "Insufficient evidence"
2. **Every answer in Strict Mode must have a citation** — no sentence without a source chunk
3. **Always rerank** — don't skip it, noisy chunks = bad answers
4. **Liberal Mode must label sections** — never silently mix document + AI content
5. **Metadata captured at ingestion** — page/paragraph cannot be reconstructed later
6. **Always overlap chunks** — 128 chars overlap, never zero
7. **Route verification to the right API** — PubMed for healthcare, arXiv for research, not swapped
8. **All secrets in .env** — never hardcode URLs or model names in Python files

---

*Last updated: Phase 1 complete — 2026-07-14*

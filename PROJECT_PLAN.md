# Citation-Aware Multi-Source RAG Platform
## Complete Project Plan & Architecture Flow

> **Purpose:** Reference document for the full build plan of a production-grade,
> trustworthy AI evidence-retrieval and verification platform.
> Keep this file in the root of your project directory.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Phase 1 — Document Ingestion Pipeline](#4-phase-1--document-ingestion-pipeline)
5. [Phase 2 — Hybrid Retrieval & Reranking](#5-phase-2--hybrid-retrieval--reranking)
6. [Phase 3A — Strict Analysis Mode](#6-phase-3a--strict-analysis-mode)
7. [Phase 3B — Liberal Analysis Mode](#7-phase-3b--liberal-analysis-mode)
8. [Phase 4 — Output Layer & Frontend](#8-phase-4--output-layer--frontend)
9. [Phase 5 — Deployment & Docker](#9-phase-5--deployment--docker)
10. [Recommended Build Order](#10-recommended-build-order)
11. [Folder Structure](#11-folder-structure)
12. [Key Design Rules](#12-key-design-rules)

---

## 1. Project Overview

This is NOT a simple "chat with PDF" system.

It is a **trustworthy AI evidence-retrieval and verification platform** that combines:

- RAG architecture (Retrieval-Augmented Generation)
- Hybrid Retrieval (BM25 keyword + Vector semantic search)
- Cross-Encoder Re-ranking for precision
- Citation Grounding (every claim maps to a source chunk)
- Hallucination Prevention (reject if evidence is insufficient)
- Public Source Verification (PubMed, arXiv, IEEE, Gov sites)
- Explainable AI (transparent citations, confidence scores)
- Multi-source evidence validation
- Confidence-based answer rejection

### Supported Document Domains
- Legal documents
- Research papers
- Healthcare reports
- Technical documentation
- Compliance reports
- Educational PDFs

### Two Analysis Modes
| Mode    | Purpose                          | Audience      |
|---------|----------------------------------|---------------|
| Strict  | Factual, verified, cited answers | Enterprise    |
| Liberal | Explanatory, educational answers | Learners      |

---

## 2. Tech Stack

| Layer              | Technology                                      |
|--------------------|-------------------------------------------------|
| Frontend           | React + Tailwind CSS                            |
| Backend            | FastAPI (Python)                                |
| LLM Runtime        | Ollama (local)                                  |
| LLM Models         | Llama 3:8b / Mistral / DeepSeek-R1              |
| Embeddings         | BAAI/bge-large-en-v1.5 (HuggingFace)           |
| Vector Database    | Qdrant                                          |
| Keyword Search     | Elasticsearch (BM25)                            |
| Metadata Database  | MongoDB                                         |
| Reranker           | BAAI/bge-reranker-large / cross-encoder MiniLM  |
| PDF Extraction     | PyMuPDF + pdfplumber                            |
| OCR                | Tesseract OCR                                   |
| RAG Framework      | LangChain                                       |
| Deployment         | Docker + Docker Compose                         |

---

## 3. System Architecture Overview

```
[User Uploads Docs]
        |
        v
[Document Ingestion Pipeline]
   - Text Extraction (PyMuPDF / pdfplumber / Tesseract)
   - Metadata Extraction (page, para, domain, timestamp)
   - Semantic Chunking (overlapping windows)
   - BGE Embedding Generation
        |
        +--------+----------+
        |        |          |
     [Qdrant] [MongoDB] [Elasticsearch]
     Vectors  Metadata   BM25 Index
        |        |          |
        +--------+----------+
                 |
        [User Asks Question]
                 |
                 v
        [Hybrid Retrieval]
         BM25 + Vector Search
                 |
                 v
        [Cross-Encoder Reranking]
         Filter noisy chunks
                 |
                 v
        [Select Analysis Mode]
         /                  \
        /                    \
[STRICT MODE]          [LIBERAL MODE]
Citation grounding     Doc + LLM knowledge
Public verification    Simplified explanations
Contradiction check    Source transparency
Confidence scoring     Broader context
Grounded LLM gen       Flexible LLM gen
        \                    /
         \                  /
          [Structured Output]
          Answer + Citations
          + Verification Status
```

---

## 4. Phase 1 — Document Ingestion Pipeline

### Goal
Build the document processor: extract, chunk, embed, and store all uploaded documents.

---

### Step 1.1 — File Upload Endpoint (FastAPI)

- Accept file formats: PDF, DOCX, TXT
- Validate file type and size
- Store raw file in a local uploads directory or object storage
- Return a document_id for tracking

```
POST /api/upload
  -> validate format
  -> save to disk
  -> trigger ingestion job
  -> return { document_id, status }
```

---

### Step 1.2 — Text Extraction

Use different extractors based on file type and content:

| Condition              | Tool             |
|------------------------|------------------|
| Standard PDF           | PyMuPDF          |
| PDF with tables/forms  | pdfplumber       |
| Scanned/image PDF      | Tesseract OCR    |
| DOCX file              | python-docx      |
| TXT file               | plain read       |

Rules:
- Try PyMuPDF first for all PDFs
- If text output is empty or very short, fall back to Tesseract OCR
- Preserve paragraph boundaries as much as possible

---

### Step 1.3 — Metadata Extraction

For every chunk extracted, capture the following metadata:

```json
{
  "document_id": "uuid",
  "document_name": "ResearchPaper.pdf",
  "page_number": 4,
  "paragraph_number": 2,
  "line_start": 12,
  "line_end": 18,
  "upload_timestamp": "2025-01-01T10:00:00Z",
  "domain": "research",
  "chunk_index": 0,
  "total_chunks": 42
}
```

Domain values: legal | research | healthcare | technical | compliance | education

---

### Step 1.4 — Semantic Chunking

- Chunk size: 512 tokens
- Overlap: 128 tokens (preserves context across chunk boundaries)
- Use LangChain's RecursiveCharacterTextSplitter
- Maintain metadata linkage per chunk

Why overlapping chunks?
- Prevents losing context when a key answer spans a chunk boundary
- Improves retrieval recall for longer answers

---

### Step 1.5 — Embedding Generation

- Model: BAAI/bge-large-en-v1.5 (via HuggingFace sentence-transformers)
- Generate one embedding vector per chunk
- Dimension: 1024

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-large-en-v1.5")
embedding = model.encode(chunk_text)
```

---

### Step 1.6 — Storage (Three Stores)

**Qdrant (Vector Store)**
- Store: embedding vector + payload (metadata)
- Collection name per domain or per document
- Enable cosine similarity search

**MongoDB (Metadata + Raw Text)**
- Store: full chunk text, metadata, document info
- Index on: document_id, domain, page_number
- Used for: citation retrieval, audit trail

**Elasticsearch (BM25 Keyword Index)**
- Index: chunk text with standard analyzer
- Used for: exact keyword match retrieval
- Enable multi-field search (document_name, chunk_text)

---

### Phase 1 Checklist
- [ ] File upload API endpoint working
- [ ] PyMuPDF extraction working on standard PDFs
- [ ] Tesseract OCR fallback working on scanned PDFs
- [ ] Metadata captured per chunk
- [ ] Chunking with overlap implemented
- [ ] BGE embeddings generated
- [ ] Vectors stored in Qdrant
- [ ] Metadata stored in MongoDB
- [ ] BM25 index populated in Elasticsearch

---

## 5. Phase 2 — Hybrid Retrieval & Reranking

### Goal
When a user asks a question, retrieve the most relevant chunks from all three stores and rerank them for precision.

---

### Step 2.1 — Query Input (FastAPI)

```
POST /api/query
  body: {
    question: "What are the side effects of Drug X?",
    document_ids: ["uuid1", "uuid2"],   // optional filter
    domain: "healthcare",               // optional filter
    mode: "strict" | "liberal"
  }
```

---

### Step 2.2 — BM25 Keyword Retrieval (Elasticsearch)

- Encode the user question as-is
- Run a multi-match query on chunk_text field
- Retrieve top-20 chunks by BM25 score
- Captures: exact term matches, acronyms, names, codes

```json
{
  "query": {
    "multi_match": {
      "query": "side effects of Drug X",
      "fields": ["chunk_text", "document_name"]
    }
  },
  "size": 20
}
```

---

### Step 2.3 — Vector Semantic Retrieval (Qdrant)

- Encode the user question using BGE model
- Run nearest-neighbor search in Qdrant
- Retrieve top-20 chunks by cosine similarity
- Captures: paraphrases, conceptual matches, synonyms

---

### Step 2.4 — Merge Retrieved Results

- Combine BM25 results + Vector results
- Deduplicate by chunk_id
- Typically 25–40 unique chunks at this stage

---

### Step 2.5 — Cross-Encoder Reranking

- Model: BAAI/bge-reranker-large
  (alternative: cross-encoder/ms-marco-MiniLM-L-6-v2 for lighter compute)
- Input: (question, chunk_text) pairs
- Output: relevance score per chunk
- Keep top-8 to top-12 chunks after reranking

Purpose:
- Removes noisy or loosely related chunks
- Improves precision before LLM generation
- Critical for hallucination prevention

```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder("BAAI/bge-reranker-large")
scores = reranker.predict([(question, chunk) for chunk in merged_chunks])
ranked = sorted(zip(scores, merged_chunks), reverse=True)
top_chunks = [chunk for _, chunk in ranked[:10]]
```

---

### Phase 2 Checklist
- [ ] BM25 retrieval from Elasticsearch working
- [ ] Vector retrieval from Qdrant working
- [ ] Result merging and deduplication working
- [ ] Cross-encoder reranking working
- [ ] Top-N chunks selected for generation

---

## 6. Phase 3A — Strict Analysis Mode

### Goal
Enterprise-grade, hallucination-free, citation-mandatory, publicly verified answers.

---

### Step 3A.1 — Citation Grounding Validation

Before generating any answer:
- Check if retrieved chunks contain enough evidence
- Every planned statement must map to at least one chunk

**If insufficient evidence found:**
```
Return: "Insufficient evidence found in the uploaded documents
to answer this question."
```
Do NOT proceed to LLM generation.

Threshold rule: If top-ranked chunk score < 0.65 (from reranker), reject.

---

### Step 3A.2 — Trusted Public Source Verification

For domains that require factual verification:

| Domain       | Public Sources to Query                          |
|--------------|--------------------------------------------------|
| Healthcare   | PubMed API, WHO guidelines                       |
| Research     | arXiv API, IEEE Xplore, Semantic Scholar         |
| Legal        | Government legal portals, court databases        |
| Technical    | Official documentation sites, RFC databases      |
| Compliance   | Regulatory body websites (FDA, SEC, etc.)        |

Process:
1. Extract key claims from the top retrieved chunks
2. Form a verification query from those claims
3. Query the relevant public API
4. Retrieve public source evidence paragraphs

---

### Step 3A.3 — Consistency Check

Compare uploaded document claims vs public source evidence.

Possible outcomes:

| Status                     | Meaning                                              |
|----------------------------|------------------------------------------------------|
| Verified                   | Document claim matches public source                 |
| Contradiction detected     | Document claim conflicts with public source          |
| Insufficient public evidence | No matching public evidence found to compare with  |

Always include this status in the final output.

---

### Step 3A.4 — Confidence Scoring

Calculate a confidence score (0.0 to 1.0) based on:
- Reranker score of top chunk
- Number of supporting chunks
- Consistency verification result
- Source domain trust level

Rules:
- Score < 0.5: reject, return "Low confidence — answer not generated"
- Score 0.5–0.75: answer with warning label
- Score > 0.75: full answer with citations

---

### Step 3A.5 — Grounded LLM Generation

Use Ollama with a strict system prompt:

```
System prompt:
You are a strict evidence-based assistant.
Answer ONLY using the provided evidence chunks.
Do NOT add any information not found in the evidence.
Do NOT speculate or infer beyond what is written.
Every sentence in your answer must be traceable to a provided chunk.
If you cannot answer from the evidence alone, say so explicitly.
```

Models (via Ollama): llama3:8b | mistral | deepseek-r1

---

### Step 3A.6 — Strict Mode Output Structure

```
ANSWER:
[Generated answer text — grounded in evidence only]

UPLOADED DOCUMENT CITATION:
  Document : ResearchPaper.pdf
  Page     : 4
  Paragraph: 2
  Lines    : 12–18
  Chunk    : "[exact chunk text used as evidence]"

VERIFIED PUBLIC SOURCE:
  Source   : IEEE Xplore — "Title of Paper"
  Section  : Section 5, Paragraph 3
  URL      : https://ieeexplore.ieee.org/...

CONSISTENCY STATUS:
  Verified | Contradiction detected | Insufficient public evidence

CONFIDENCE SCORE:
  0.87 / 1.00
```

---

### Phase 3A Checklist
- [ ] Insufficient evidence detection working
- [ ] Public source API queries working (PubMed / arXiv / IEEE)
- [ ] Consistency comparison logic working
- [ ] Confidence scoring formula implemented
- [ ] Strict LLM system prompt enforced
- [ ] Full structured output returned

---

## 7. Phase 3B — Liberal Analysis Mode

### Goal
Educational, conversational, explanation-friendly answers that still prioritize document content but allow broader AI reasoning.

---

### Step 3B.1 — Document-Based Answer Generation

- Use top retrieved and reranked chunks as primary context
- Generate the document-based portion of the answer first
- Keep citations attached (soft citations — page and document reference)

---

### Step 3B.2 — LLM Knowledge Expansion

- After the document-based answer, allow the LLM to add:
  - Simplified explanations of technical terms
  - Background context not in the document
  - Analogies and examples to aid understanding
  - Related concepts that help comprehension

System prompt:
```
You are a helpful educational assistant.
First, answer from the provided document evidence.
Then, you may add broader explanation and context from your knowledge.
Clearly separate what comes from the document and what is additional explanation.
Use simple language where possible.
```

---

### Step 3B.3 — Source Transparency

The output must always clearly label:
- What came from the uploaded document
- What came from the AI's general knowledge

This prevents user confusion about document authenticity.

---

### Step 3B.4 — Liberal Mode Output Structure

```
DOCUMENT-BASED ANSWER:
[Answer derived directly from uploaded document chunks]

Source: ResearchPaper.pdf, Page 4, Paragraph 2

---

ADDITIONAL EXPLANATION:
[Broader context, simplified explanation, analogies, examples
added by the AI to aid understanding — not from the document]
```

---

### Phase 3B Checklist
- [ ] Document-first answer generation working
- [ ] LLM knowledge expansion layer working
- [ ] Output clearly separates document vs AI content
- [ ] Soft citations included
- [ ] Liberal mode system prompt implemented

---

## 8. Phase 4 — Output Layer & Frontend

### Goal
Build the React + Tailwind UI that presents both modes clearly and lets users upload documents, ask questions, and explore citations.

---

### Frontend Components

**Upload Zone**
- Drag-and-drop or click-to-upload
- Accepts PDF, DOCX, TXT
- Shows upload progress and processing status
- Lists uploaded documents with domain tag

**Mode Toggle**
- Prominent toggle: Strict Mode | Liberal Mode
- Show brief description of each mode under the toggle

**Query Input**
- Text input for the user question
- Optional: domain filter, document filter

**Answer Viewer (Strict Mode)**
- Answer text panel
- Expandable citation cards:
  - Document name, page, paragraph
  - Evidence chunk preview
  - Public source link
  - Consistency status badge (green / red / gray)
  - Confidence score bar

**Answer Viewer (Liberal Mode)**
- Two-section layout:
  - "From your document" section
  - "Additional context" section with AI label badge

**Document Manager**
- List of uploaded documents
- Delete document
- Re-index document

---

### API Endpoints Summary

| Method | Endpoint            | Purpose                        |
|--------|---------------------|--------------------------------|
| POST   | /api/upload         | Upload document                |
| GET    | /api/documents      | List all documents             |
| DELETE | /api/documents/{id} | Delete a document              |
| POST   | /api/query          | Ask a question                 |
| GET    | /api/health         | Health check for all services  |

---

### Phase 4 Checklist
- [ ] Upload zone component built
- [ ] Mode toggle working
- [ ] Query input with filters built
- [ ] Strict mode answer viewer with citation cards built
- [ ] Liberal mode two-section answer viewer built
- [ ] Document manager built
- [ ] API endpoints connected to frontend

---

## 9. Phase 5 — Deployment & Docker

### Goal
Wrap the entire stack into a Docker Compose setup so everything starts with one command.

---

### Services in docker-compose.yml

```
services:
  frontend       -> React app (port 3000)
  backend        -> FastAPI app (port 8000)
  qdrant         -> Qdrant vector DB (port 6333)
  mongodb        -> MongoDB (port 27017)
  elasticsearch  -> Elasticsearch (port 9200)
  ollama         -> Ollama LLM runtime (port 11434)
```

---

### Environment Variables (.env)

```
MONGODB_URL=mongodb://mongodb:27017
QDRANT_URL=http://qdrant:6333
ELASTICSEARCH_URL=http://elasticsearch:9200
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama3:8b
CONFIDENCE_THRESHOLD=0.65
```

---

### Phase 5 Checklist
- [ ] Dockerfile for FastAPI backend
- [ ] Dockerfile for React frontend
- [ ] docker-compose.yml with all 6 services
- [ ] .env file configured
- [ ] Volume mounts for Qdrant, MongoDB, Elasticsearch data persistence
- [ ] Ollama model pre-pull on startup
- [ ] Health checks for all services

---

## 10. Recommended Build Order

Follow this order to validate the core pipeline early before adding complexity:

```
Step 1  ->  Phase 1: Ingestion Pipeline
            (upload, extract, chunk, embed, store)

Step 2  ->  Phase 2: Hybrid Retrieval
            (BM25 + vector + reranking)

Step 3  ->  Phase 3B: Liberal Mode first
            (faster to test, no external API calls needed)

Step 4  ->  Phase 3A: Strict Mode
            (citation grounding + public verification + confidence)

Step 5  ->  Phase 4: Frontend
            (connect UI to working backend)

Step 6  ->  Phase 5: Docker
            (containerize and compose)

Step 7  ->  Testing & Tuning
            (chunk size, reranker threshold, confidence cutoff)
```

**Why Liberal Mode before Strict Mode?**
Liberal mode lets you validate the full RAG loop (retrieval → generation → output)
without needing external API integrations. Once that works, layer on the
verification, contradiction detection, and confidence scoring for Strict Mode.

---

## 11. Folder Structure

```
rag-platform/
│
├── PROJECT_PLAN.md               <- This file
│
├── backend/
│   ├── main.py                   <- FastAPI entry point
│   ├── routers/
│   │   ├── upload.py             <- Document upload endpoint
│   │   └── query.py              <- Query endpoint
│   ├── services/
│   │   ├── extractor.py          <- PyMuPDF / pdfplumber / OCR
│   │   ├── chunker.py            <- Semantic chunking
│   │   ├── embedder.py           <- BGE embedding generation
│   │   ├── retriever.py          <- BM25 + vector retrieval
│   │   ├── reranker.py           <- Cross-encoder reranking
│   │   ├── verifier.py           <- Public source verification
│   │   ├── strict_mode.py        <- Strict mode pipeline
│   │   └── liberal_mode.py       <- Liberal mode pipeline
│   ├── db/
│   │   ├── qdrant_client.py
│   │   ├── mongo_client.py
│   │   └── elastic_client.py
│   ├── models/
│   │   └── schemas.py            <- Pydantic models
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadZone.jsx
│   │   │   ├── ModeToggle.jsx
│   │   │   ├── QueryInput.jsx
│   │   │   ├── StrictAnswerView.jsx
│   │   │   ├── LiberalAnswerView.jsx
│   │   │   └── DocumentManager.jsx
│   │   ├── App.jsx
│   │   └── index.js
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml
├── .env
└── README.md
```

---

## 12. Key Design Rules

These rules must be respected throughout the entire build:

1. **Never hallucinate in Strict Mode.**
   If evidence is insufficient, return the rejection message.
   Do not generate a speculative answer.

2. **Every statement in Strict Mode must trace to a chunk.**
   Citation grounding is not optional — it is the core feature.

3. **Reranking is the quality gate.**
   Do not skip reranking to save compute.
   Sending noisy chunks to the LLM breaks the entire system.

4. **Liberal Mode must be transparent.**
   Always label what is from the document vs what is AI-added.
   Never blend them silently.

5. **Confidence scores must drive behavior.**
   Do not just display the score — act on it.
   Low-confidence answers in Strict Mode must be rejected.

6. **Metadata is sacred.**
   Page numbers and paragraph numbers must be captured accurately
   during ingestion — they cannot be reconstructed later.

7. **Chunk overlap is required.**
   Never chunk without overlap.
   Lost context at boundaries is a retrieval failure waiting to happen.

8. **Public source verification is domain-specific.**
   Do not call PubMed for legal documents.
   Always route verification to the correct trusted source for the domain.

---

*End of Project Plan*
*Keep this file at the root of your project directory.*
*Update the checklists as each phase is completed.*

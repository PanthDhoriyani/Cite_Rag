# CiteRag — Project Flow (LangChain Edition)
> What we are building, in what order, and exactly what code goes in each step.
> All RAG logic uses LangChain. Simple functions, no enterprise patterns.

---

## What We Are Building

A RAG system that:
1. Accepts uploaded documents (PDF, DOCX, TXT)
2. Extracts, chunks, embeds, and stores them using LangChain
3. Retrieves relevant chunks using hybrid search (BM25 + semantic) and reranks them
4. Generates cited answers using the Groq API via LangChain LCEL chains

Two modes:
- **Liberal** — document answer + AI explanation section
- **Strict** — evidence-only, citations mandatory, confidence scored, refuses if weak evidence

---

## File Structure

```
CiteRag/
  backend/
    main.py         <- FastAPI app
    config.py       <- all .env settings
    schemas.py      <- Pydantic models
    pipeline.py     <- LangChain ingestion: load + split + store
    retrieval.py    <- LangChain retrieval: Qdrant + ES + rerank
    generation.py   <- LangChain LCEL chains: liberal + strict answers
    routers/
      __init__.py
      upload.py     <- file upload endpoints
      query.py      <- question/answer endpoint
    db/
      __init__.py
      mongo_client.py  <- MongoDB (status tracking + chunk text)
    requirements.txt
  .env              <- all keys and settings
  .env.example      <- template
  .gitignore
  implementation_plan.md
  project_flow.md   <- this file
  about.md          <- technology explanations
  PROJECT_PLAN.md   <- original project spec
```

---

## .env (All Keys in One Place)

```env
MONGODB_URL=mongodb://localhost:27017
QDRANT_URL=http://localhost:6333
GROQ_API_KEY=your_groq_api_key_here

EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-large
LLM_MODEL=llama-3.1-8b-instant

CHUNK_SIZE=512
CHUNK_OVERLAP=128
BM25_TOP_K=20
VECTOR_TOP_K=20
RERANKER_TOP_K=10
CONFIDENCE_THRESHOLD=0.65

UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=50
```

---

## Phase 1 — Ingestion Pipeline

**Goal:** Upload a file → load → chunk → embed → store in Qdrant + MongoDB

### Upload Flow

```
POST /api/upload
  -> validate extension (pdf/docx/txt) and size (< 50MB)
  -> save file as uploads/{uuid}.{ext}
  -> MongoDB: insert {document_id, status="processing", ...}
  -> BackgroundTask: pipeline.run(...)
  -> return {document_id, status="processing"} immediately
```

### pipeline.py — 3 functions + run()

**load(file_path, file_type)**
```python
from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader

if file_type == "pdf":
    docs = PyMuPDFLoader(file_path).load()
    if sum(len(d.page_content) for d in docs) < 100:
        docs = _ocr_load(file_path)  # Tesseract OCR fallback
elif file_type == "docx":
    docs = Docx2txtLoader(file_path).load()
elif file_type == "txt":
    docs = TextLoader(file_path).load()
# Returns: [Document(page_content="...", metadata={page, source}), ...]
```

**split(docs, doc_meta)**
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,       # 512
    chunk_overlap=CHUNK_OVERLAP, # 128
    separators=["\n\n", "\n", " ", ""]
)
chunks = splitter.split_documents(docs)

# Inject our metadata into each chunk
for i, chunk in enumerate(chunks):
    chunk.metadata.update({
        "chunk_id":      str(uuid.uuid4()),
        "chunk_index":   i,
        "total_chunks":  len(chunks),
        "document_id":   doc_meta["document_id"],
        "document_name": doc_meta["document_name"],
        "domain":        doc_meta["domain"],
        "page_number":   chunk.metadata.get("page", 1),
    })
# Returns: [Document with updated metadata, ...]
```

**store(chunks)**
```python
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

# Embeddings singleton (loaded once on first call)
embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    encode_kwargs={"normalize_embeddings": True}
)

texts     = [c.page_content for c in chunks]
metadatas = [c.metadata for c in chunks]
ids       = [c.metadata["chunk_id"] for c in chunks]

# Qdrant — semantic vectors
qdrant_store = QdrantVectorStore.from_texts(
    texts=texts, metadatas=metadatas,
    embedding=embeddings,
    url=QDRANT_URL, collection_name="citerag_docs"
)

# MongoDB — full text + metadata for citations + text search index
mongo.save_chunks([{**m, "chunk_text": t} for t, m in zip(texts, metadatas)])
```

**run() — the BackgroundTask called on upload**
```python
def run(document_id, file_path, filename, file_type, domain, upload_timestamp):
    try:
        docs   = load(file_path, file_type)
        chunks = split(docs, {document_id, document_name, domain, ...})
        store(chunks)
        mongo.update_status(document_id, "ready", len(chunks))
    except Exception as e:
        mongo.update_status(document_id, "failed")
```

---

## Phase 2 — Hybrid Retrieval + Reranking

**Goal:** Take a question → find best chunks from both databases → rerank for precision

### retrieval.py — using LangChain retrievers

**Qdrant retriever (semantic search)**
```python
from langchain_qdrant import QdrantVectorStore

qdrant_store    = QdrantVectorStore(client=qdrant_client,
                    collection_name="citerag_docs", embedding=embeddings)
qdrant_retriever = qdrant_store.as_retriever(search_kwargs={"k": VECTOR_TOP_K})
```

**MongoDB retriever (BM25 keyword search fallback)**
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from pydantic import Field
from typing import Any

class MongoDBTextRetriever(BaseRetriever):
    collection: Any = Field(exclude=True)
    top_k: int = 20

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        cursor = self.collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}, "_id": 0}
        ).sort([("score", {"$meta": "textScore"})]).limit(self.top_k)
        
        results = []
        for doc in cursor:
            results.append(Document(
                page_content=doc.get("chunk_text", ""),
                metadata={
                    "chunk_id": doc.get("chunk_id"),
                    "page_number": doc.get("page_number"),
                    "document_name": doc.get("document_name"),
                    "domain": doc.get("domain"),
                }
            ))
        return results

mongodb_retriever = MongoDBTextRetriever(collection=mongo.chunks, top_k=BM25_TOP_K)

# Combine with EnsembleRetriever
from langchain.retrievers import EnsembleRetriever

ensemble = EnsembleRetriever(
    retrievers=[qdrant_retriever, mongodb_retriever],
    weights=[0.5, 0.5]  # 50% semantic + 50% keyword
)
```

**Rerank with cross-encoder**
```python
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.retrievers import ContextualCompressionRetriever

cross_encoder = HuggingFaceCrossEncoder(model_name=RERANKER_MODEL)
reranker      = CrossEncoderReranker(model=cross_encoder, top_n=RERANKER_TOP_K)

final_retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=ensemble
)

def retrieve(question, filters=None):
    return final_retriever.invoke(question)
    # Returns: top 10 Document objects
```

---

## Phase 3B — Liberal Mode Answer

**Goal:** Answer from document first, then allow AI to add broader explanation

### generation.py — liberal LCEL chain

```python
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatGroq(model=LLM_MODEL, groq_api_key=GROQ_API_KEY)

LIBERAL_PROMPT = PromptTemplate.from_template("""
You are a helpful educational assistant.

Answer the question using the document context below.
Then add broader explanation from your knowledge.
Always separate the two sections clearly.

Document Context:
{context}

Question: {question}

DOCUMENT-BASED ANSWER:
[answer from context only]

ADDITIONAL EXPLANATION:
[broader explanation, analogies, examples from your knowledge]
""")

def liberal_answer(question, docs):
    context = format_docs(docs)
    answer  = (LIBERAL_PROMPT | llm | StrOutputParser()).invoke(
        {"context": context, "question": question}
    )
    return {"answer": answer, "citations": build_citations(docs), "mode": "liberal"}
```

**Output structure:**
```json
{
  "mode": "liberal",
  "answer": "DOCUMENT-BASED ANSWER:\n...\n\nADDITIONAL EXPLANATION:\n...",
  "citations": [
    {"document_name": "paper.pdf", "page_number": 4, "chunk_text": "..."}
  ]
}
```

---

## Phase 3A — Strict Mode Answer

**Goal:** Evidence-only answer, citations mandatory, confidence scored, refuse if weak

### generation.py — strict LCEL chain

```python
STRICT_PROMPT = PromptTemplate.from_template("""
You are a strict evidence-based assistant.
Answer ONLY from the evidence context. Do NOT speculate.
Every sentence must be traceable to the context.
If the context lacks enough information, respond:
"Insufficient evidence in the uploaded documents."

Evidence Context:
{context}

Question: {question}

Answer:
""")

def strict_answer(question, docs):
    # Step 1: Check evidence quality
    best_score = docs[0].metadata.get("relevance_score", 0.0) if docs else 0.0
    if best_score < CONFIDENCE_THRESHOLD:
        return {
            "answer":     "Insufficient evidence — confidence below threshold.",
            "citations":  [],
            "confidence": round(best_score, 3),
            "mode":       "strict"
        }

    # Step 2: Generate from evidence only
    context = format_docs(docs)
    answer  = (STRICT_PROMPT | llm | StrOutputParser()).invoke(
        {"context": context, "question": question}
    )

    # Step 3: Confidence score = average of top 3 chunk scores
    confidence = round(
        sum(d.metadata.get("relevance_score", 0.8) for d in docs[:3]) / 3, 3
    )

    return {
        "answer":     answer,
        "citations":  build_citations(docs),
        "confidence": confidence,
        "mode":       "strict"
    }
```

**Output structure:**
```json
{
  "mode": "strict",
  "answer": "The recommended dosage is...",
  "citations": [
    {
      "document_name": "ClinicalTrial.pdf",
      "page_number": 4,
      "chunk_text": "...exact evidence text..."
    }
  ],
  "confidence": 0.87
}
```

---

## Phase 3A — Public Verification (verifier.py)

For Strict Mode, optionally verify claims against public sources:

| Domain | API |
|---|---|
| healthcare | PubMed API |
| research | arXiv API |
| legal | Government legal portals |
| technical | RFC databases |
| compliance | FDA, SEC sites |

```python
import httpx

def verify_pubmed(claim_text):
    r = httpx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={
        "db": "pubmed", "term": claim_text, "retmode": "json", "retmax": 3
    })
    pmids = r.json()["esearchresult"]["idlist"]
    # fetch abstracts and compare -> return Verified / Contradiction / Unknown
```

---

## Phase 4 — Frontend (Streamlit)

A pure-Python Streamlit app (`backend/frontend.py`) that acts as the user control panel.

### Layout Elements
- **Sidebar Panel:**
  - File uploader accepting PDF, DOCX, TXT documents.
  - Domain dropdown selection (legal, research, healthcare, general, etc.).
  - "Process Document" button to trigger background ingestion.
  - "Document Repository" list showing status badges, checkboxes for scoping searches, and delete buttons (🗑️).
- **Main Answer Workbench:**
  - Mode selector radio buttons ("Liberal" or "Strict").
  - Guidelines warning block based on the selected mode.
  - Chat input box for queries.
  - Formatted layouts:
    - **Strict Mode:** Displays progress bar for confidence, warning on low confidence, and citation chunks in expandable panels.
    - **Liberal Mode:** Displays "Document-Based Evidence" and "Broader AI Explanation" separately in stylized divs, followed by references.

API endpoints the frontend calls:
```
POST   /api/upload
GET    /api/documents
DELETE /api/documents/{id}
POST   /api/query
GET    /api/health
```

---

## Phase 5 — Docker

```yaml
services:
  backend:       FastAPI (port 8000)
  frontend:      Streamlit (port 8501)
  qdrant:        Qdrant Cloud / Local container
  mongodb:       MongoDB Atlas / Local container
  # No local LLM service required (uses cloud Groq API)
```

```bash
docker-compose up   # starts everything
```

---

## Phase 6 — Testing & Tuning

- Upload test PDFs across different domains
- Run queries in both modes
- Tune CHUNK_SIZE (try 256 and 768, compare retrieval quality)
- Tune CONFIDENCE_THRESHOLD (try 0.5 and 0.75)
- Test public API verification per domain

---

## Current Status

| Phase | Status |
|---|---|
| Phase 1 — Ingestion Pipeline (LangChain) | Completed ✅ |
| Phase 2 — Retrieval + Reranking (LangChain) | Completed ✅ |
| Phase 3B — Liberal Mode (LCEL chain) | Completed ✅ |
| Phase 3A — Strict Mode + Verification | Completed ✅ |
| Phase 4 — Frontend (Streamlit) | Completed ✅ |
| Phase 5 — Docker | ⏳ Next |
| Phase 6 — Testing | ⏳ Last |

---

## Key Rules

1. **All settings in .env** — imported via config.py, never os.getenv() elsewhere
2. **LangChain handles** — loading, chunking, embeddings, vector store, hybrid retrieval merging, reranking, LLM chains
3. **MongoDB handles** — document status tracking, full chunk text for citations, and native text indexing ($text search)
4. **Embeddings singleton** — HuggingFaceEmbeddings loaded once in pipeline.py, shared with retrieval.py
5. **Strict Mode refuses** — if confidence < 0.65, return rejection message, never generate
6. **Liberal Mode labels** — always separate "DOCUMENT-BASED ANSWER" from "ADDITIONAL EXPLANATION"
7. **Always rerank** — EnsembleRetriever output always passes through CrossEncoderReranker
8. **Chunk with overlap** — always 128 char overlap, never zero

---

*Last updated: LangChain rewrite — 2026-07-14*




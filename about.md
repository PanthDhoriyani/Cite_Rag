# CiteRag — Technologies Used (LangChain Edition)
> Simple explanations of every tool used in the project.
> Updated to reflect the LangChain-based RAG architecture with MongoDB text indexing and Streamlit frontend.

---

## What is CiteRag?

CiteRag is a **RAG system** — Retrieval-Augmented Generation.

Instead of asking an AI to answer from memory, we first **search our uploaded documents**, find the best matching pieces, and then let the AI answer **using only that evidence**.

Two answer modes:
- **Strict Mode** — answer ONLY from the document, citations required, confidence score given
- **Liberal Mode** — document answer first, then AI can add broader explanation

```
You upload a document
       ↓
You ask a question
       ↓
LangChain finds best matching paragraphs (BM25 via MongoDB + semantic via Qdrant + rerank)
       ↓
Ollama LLM reads those paragraphs and gives a cited answer
       ↓
You get: answer + page/paragraph citations + confidence score
```

---

## RAG Framework — LangChain

**What it is:** The main framework we use to build the entire RAG pipeline.

**What LangChain does in CiteRag:**
- Provides document loaders (PDF, DOCX, TXT)
- Provides text splitters
- Wraps HuggingFace embedding models
- Manages the Qdrant vector store
- Integrates retrievers (EnsembleRetriever)
- Applies reranking (ContextualCompressionRetriever)
- Builds answer chains using LCEL (LangChain Expression Language)

**Why LangChain:** Provides well-tested, composable building blocks for every part of the RAG pipeline. Instead of writing each piece from scratch, we use LangChain's integrations and wire them together with the `|` pipe operator.

---

## Web API — FastAPI

**What it is:** The web server that exposes the API endpoints.

**What it does:**
- `POST /api/upload` — accepts file uploads, triggers background ingestion
- `GET /api/documents` — lists uploaded documents + status
- `DELETE /api/documents/{id}` — removes a document
- `POST /api/query` — accepts a question, returns answer + citations
- `GET /api/health` — checks if backend is running

**BackgroundTasks:** When a file is uploaded, FastAPI returns a response immediately (status="processing") and runs the ingestion pipeline in the background. This prevents upload requests from timing out.

---

## Document Loading — LangChain Loaders

### PyMuPDFLoader
**Package:** `langchain-community`

**What it does:** Loads PDF files page by page. Each page becomes a LangChain `Document` object with `page_content` (text) and `metadata` (source, page number).

**Why this loader:** Fast, accurate for digital PDFs, preserves page numbers automatically.

### Tesseract OCR (fallback for scanned PDFs)
**Packages:** `pytesseract`, `Pillow`, `pymupdf`

**When it kicks in:** If PyMuPDFLoader extracts fewer than 100 characters total, the PDF is likely scanned (an image of text, not actual text). Tesseract renders each page as a 300 DPI image and reads the text from it.

### Docx2txtLoader
**Package:** `langchain-community`

**What it does:** Loads `.docx` Word files and extracts all paragraph text.

### TextLoader
**Package:** `langchain-community`

**What it does:** Reads plain `.txt` files as a single document.

---

## Text Splitting — RecursiveCharacterTextSplitter

**Package:** `langchain-text-splitters`

**What it does:**
- Splits extracted text into chunks of ~512 characters
- Each chunk overlaps the next by ~128 characters
- Tries to split at natural break points first: paragraph → line → word → character

**Why chunking:** Embedding models and LLMs have token limits. A 100-page PDF can't be processed as one block. We split into small searchable pieces.

**Why overlap:** If a key sentence starts at the end of chunk 5 and finishes at the start of chunk 6, without overlap that sentence is split between two chunks and may not be found. With 128-char overlap, both chunks contain that sentence.

```
Chunk 1: [----512 chars----]
Chunk 2:             [----512 chars----]
                  ↑ 128 chars overlap
```

---

## Embeddings — HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)

**Package:** `langchain-huggingface` (wraps `sentence-transformers`)

**What it does:**
- Converts each text chunk into a list of 1024 numbers (a vector/embedding)
- Texts with similar meaning produce vectors that are close together
- Used both during ingestion (to store chunk vectors) and at query time (to embed the question)

**normalize_embeddings=True:** Required for correct cosine similarity in Qdrant.

**Singleton pattern:** The model takes 3–5 seconds to load. It's created once as a module-level object in `pipeline.py` and reused everywhere (including `retrieval.py`).

**Example:**
- "cardiac arrest treatment" and "heart attack therapy" → vectors very close
- "cardiac arrest treatment" and "tax law" → vectors far apart

---

## Vector Database — QdrantVectorStore (LangChain)

**Package:** `langchain-qdrant`

**What it does:**
- `add_texts(texts, metadatas, ids)` — stores chunk embeddings + metadata
- `as_retriever(k=20)` — returns a LangChain retriever for semantic search
- When a user asks a question, the question is embedded and Qdrant finds the 20 most similar chunk vectors

**Collection settings:**
- Name: `citerag_docs`
- Dimension: 1024 (matches BGE model)
- Distance: COSINE

---

## Keyword Search — MongoDB Text Index Search (Standard Full-Text Index)

**Package:** `pymongo`

**What it does:**
- **Indexing:** On startup, MongoDB creates a text search index on the `chunk_text` field inside the `chunks` collection.
- **`MongoDBTextRetriever` (Custom):** A custom LangChain retriever we created that runs standard MongoDB `$text` search queries and matches exact words/phrases, returning the top 20 ranked text chunks.

**Why use MongoDB Search alongside Qdrant?**
- Qdrant is great for meaning: "cardiac therapy" finds "heart treatment"
- MongoDB Text search is great for exact terms: drug codes, regulation numbers, names, acronyms
- Together they catch more relevant chunks than either database alone, and because both are hosted on free tiers (MongoDB Atlas + Qdrant Cloud), we avoid the high costs of Elasticsearch.

---

## Metadata Store & Collections — MongoDB

**Package:** `pymongo`

**What it does:**
- `documents` collection — one record per uploaded file with `status` (processing/ready/failed) and `total_chunks`
- `chunks` collection — stores full chunk text, page numbers, domains, etc. (Acts as the source of truth for both keyword search queries and citation display).

---

## Hybrid Retrieval — EnsembleRetriever (LangChain)

**Package:** `langchain`

**What it does:**
- Takes multiple retrievers (Qdrant semantic retriever + custom MongoDB text retriever) and combines their results
- Applies Reciprocal Rank Fusion (RRF) to merge the ranked lists
- Default weights: 50% Qdrant + 50% MongoDB

```python
ensemble = EnsembleRetriever(
    retrievers=[qdrant_retriever, mongodb_retriever],
    weights=[0.5, 0.5]
)
```

---

## Reranking — ContextualCompressionRetriever + CrossEncoderReranker (LangChain)

**Packages:** `langchain`, `langchain-community`
**Model:** `BAAI/bge-reranker-large`

**What it does:**
- Takes the ~40 merged chunks from EnsembleRetriever
- Feeds each (question, chunk) pair to a cross-encoder model
- The cross-encoder reads both together and gives a precise relevance score
- Keeps the top 10 chunks by score

**Why rerank?** The bi-encoder (BGE embedder) is fast but approximate. The cross-encoder reads both question and chunk at the same time and is much more precise. We use bi-encoder to narrow from thousands to ~40, then cross-encoder to pick the final 10.

---

## LLM — OllamaLLM (LangChain)

**Package:** `langchain-ollama`
**Model:** `llama3:8b`

**What it does:**
- Receives the top 10 reranked chunks as context
- In **Liberal Mode:** answers from the document first, then adds AI explanation
- In **Strict Mode:** answers ONLY from the provided evidence, refuses to speculate

---

## LCEL Chains — LangChain Expression Language

**Package:** `langchain-core`

**What it does:** Composes the RAG pipeline using the `|` pipe operator:

```python
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

---

## Frontend — Streamlit (Python)

**Package:** `streamlit`

**What it does:**
- Provides a clean browser-based GUI.
- Uses `requests` to talk to the FastAPI backend API.
- Implements drag-and-drop file ingestion, document selection, query templates, confidence scoring progress bars, and citation viewer expandable cards.

---

## Full Data Flow (Everything Together)

```
User uploads paper.pdf
        |
Streamlit Uploader -> POST /api/upload (FastAPI)
        |
        +-- Validate: extension in {pdf,docx,txt}, size < 50MB
        +-- Save as uploads/{uuid}.pdf
        +-- MongoDB: save {document_id, status="processing"}
        +-- BackgroundTask -> pipeline.run()
                |
                +-- PyMuPDFLoader -> [Document(page_content, metadata), ...]
                |    If < 100 chars -> Tesseract OCR fallback
                |
                +-- RecursiveCharacterTextSplitter
                |    -> 84 chunks x 512 chars, 128 overlap
                |    -> each chunk: chunk_id, page_number, domain, ...
                |
                +-- HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)
                |    -> 84 vectors x 1024 floats
                |
                +-- QdrantVectorStore.add_texts()   -> vectors stored in Qdrant Cloud
                +-- MongoDB save_chunks()            -> full text and text index stored in MongoDB Atlas
                |
                +-- MongoDB: update status="ready"

User asks: "What is the recommended dosage?"
        |
Streamlit Chat -> POST /api/query {question, mode="liberal"}
        |
        +-- EnsembleRetriever
        |    +-- QdrantVectorStore retriever -> top 20 by meaning
        |    +-- MongoDBTextRetriever       -> top 20 by keyword
        |    -> merged ~40 unique chunks
        |
        +-- ContextualCompressionRetriever
        |    -> CrossEncoder scores each (question, chunk)
        |    -> keeps top 10
        |
        +-- LCEL Chain
             +-- format_docs(top_10) -> context string
             +-- PromptTemplate fills {context} + {question}
             +-- OllamaLLM generates answer
             +-- StrOutputParser -> clean text
             -> return {answer, citations, confidence}
```

---

## Summary Table

| Technology | Package | Role |
|---|---|---|
| FastAPI | fastapi | REST API + BackgroundTasks |
| LangChain | langchain + integrations | Full RAG framework |
| PyMuPDFLoader | langchain-community | PDF loading page-by-page |
| Tesseract OCR | pytesseract + Pillow | Scanned PDF fallback |
| Docx2txtLoader | langchain-community | DOCX loading |
| TextLoader | langchain-community | TXT loading |
| RecursiveCharacterTextSplitter | langchain-text-splitters | 512/128 chunking |
| HuggingFaceEmbeddings | langchain-huggingface | BAAI/bge-large-en-v1.5 wrapper |
| QdrantVectorStore | langchain-qdrant | Semantic vector search (Cloud) |
| MongoDB (pymongo) | pymongo | Document status + native full-text keyword search + chunk text (Cloud) |
| EnsembleRetriever | langchain | Hybrid retrieval (Qdrant 50% + MongoDB 50%) |
| CrossEncoderReranker | langchain-community | BAAI/bge-reranker-large reranking |
| OllamaLLM | langchain-ollama | Local LLM (llama3:8b) |
| LCEL (pipe operator) | langchain-core | Chain composition |
| Streamlit | streamlit | Pure Python frontend web application |
| python-dotenv | python-dotenv | .env loading |
| loguru | loguru | Colored logging |
| httpx | httpx | HTTP calls for public API verification (Phase 3A) |

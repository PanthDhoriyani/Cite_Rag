"""
pipeline.py — LangChain RAG Ingestion Pipeline
================================================
This is the heart of Phase 1. It takes an uploaded file and runs it through
the full ingestion pipeline using LangChain components:

  Step 1  load()   → LangChain document loaders (PDF / DOCX / TXT)
  Step 2  split()  → LangChain RecursiveCharacterTextSplitter
  Step 3  store()  → LangChain QdrantVectorStore + ElasticsearchStore + MongoDB

  run()   → orchestrates all 3 steps, called as a FastAPI BackgroundTask

Why LangChain for ingestion?
  - PyMuPDFLoader automatically extracts page numbers into metadata
  - RecursiveCharacterTextSplitter splits at natural boundaries (paragraph > line > word)
  - QdrantVectorStore handles embedding + upsert in one call
  - ElasticsearchStore (BM25 mode) handles BM25 indexing without needing embeddings
"""
import io
import uuid
from datetime import datetime
from pathlib import Path

# LangSmith tracing — @traceable turns any function into a named trace span
from langsmith import traceable

from loguru import logger

# LangChain document loaders — each handles a different file format
from langchain_community.document_loaders import (
    PyMuPDFLoader,   # PDF: fast digital text extraction, preserves page numbers
    Docx2txtLoader,  # DOCX: extracts all paragraph text from Word documents
    TextLoader,      # TXT: reads plain text files
)

# LangChain text splitter — splits long text into overlapping chunks
from langchain_text_splitters import RecursiveCharacterTextSplitter

# LangChain Qdrant integration — stores + searches vectors
from langchain_qdrant import QdrantVectorStore

# LangChain Cohere integration — cloud embeddings, no local model download needed
from langchain_cohere import CohereEmbeddings

# Qdrant client for collection setup (creating the collection before first insert)
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Our config (all from .env)
from config import (
    QDRANT_URL, QDRANT_API_KEY,
    COHERE_API_KEY,
    EMBEDDING_MODEL, EMBEDDING_DIM,
    CHUNK_SIZE, CHUNK_OVERLAP,
    QDRANT_COLLECTION
)

# Our MongoDB client for status tracking and chunk text storage
import db.mongo_client as mongo


# =============================================================================
# Embeddings — Cohere Cloud API (no local model download)
# =============================================================================
# CohereEmbeddings calls the Cohere API to embed text into 1024-dim vectors.
# No GPU, no disk space, no RAM for model weights — just an API call.
# The same object is imported by retrieval.py to keep a single client instance.

embeddings = CohereEmbeddings(
    model=EMBEDDING_MODEL,          # "embed-english-v3.0" — 1024-dim output
    cohere_api_key=COHERE_API_KEY,
)


# =============================================================================
# Step 1: Load — LangChain Document Loaders
# =============================================================================

@traceable(name="load_document", run_type="chain")
def load(file_path: str, file_type: str) -> list:
    """
    Load an uploaded file using the appropriate LangChain document loader.

    Returns a list of LangChain Document objects:
      Document(page_content="chunk text...", metadata={"source": path, "page": 0})

    PyMuPDFLoader gives us one Document per page with the page number in metadata.
    This is why we use it instead of a generic PDF loader — page numbers are
    critical metadata for building citations later.

    Scanned PDF fallback:
      If total extracted text is < 100 characters, the PDF is likely scanned
      (it's an image of text, not actual text). We fall back to Tesseract OCR.
    """
    path = str(file_path)

    if file_type == "pdf":
        logger.info(f"Loading PDF: {Path(path).name}")
        docs = PyMuPDFLoader(path).load()

        # Count total characters to detect scanned PDFs
        total_chars = sum(len(d.page_content.strip()) for d in docs)
        logger.info(f"Extracted {total_chars} characters from {len(docs)} pages")

        if total_chars < 100:
            # Very little text → scanned/image PDF → use OCR
            logger.warning(f"Only {total_chars} chars — switching to Tesseract OCR")
            docs = _ocr_load(path)

        return docs

    elif file_type == "docx":
        logger.info(f"Loading DOCX: {Path(path).name}")
        return Docx2txtLoader(path).load()

    elif file_type == "txt":
        logger.info(f"Loading TXT: {Path(path).name}")
        return TextLoader(path, encoding="utf-8").load()

    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _ocr_load(path: str) -> list:
    """
    Tesseract OCR fallback for scanned PDFs.

    Process:
      1. Open the PDF with PyMuPDF (fitz)
      2. Render each page as a 300 DPI PNG image (higher DPI = better OCR accuracy)
      3. Pass the image to Tesseract which reads the text like a human would
      4. Wrap the text in a LangChain Document object

    Why 300 DPI? Lower resolution images give poor OCR results.
    72 DPI (screen resolution) → terrible. 300 DPI (print resolution) → good.
    """
    import fitz           # PyMuPDF — for rendering PDF pages as images
    import pytesseract    # Python wrapper for Tesseract OCR
    from PIL import Image # For image processing
    from langchain_core.documents import Document

    doc    = fitz.open(path)
    matrix = fitz.Matrix(300 / 72, 300 / 72)  # scale factor for 300 DPI
    result = []

    for i, page in enumerate(doc):
        # Render page as a PNG image in memory
        pix  = page.get_pixmap(matrix=matrix)
        img  = Image.open(io.BytesIO(pix.tobytes("png")))

        # Run Tesseract OCR on the image
        text = pytesseract.image_to_string(img) or ""

        result.append(Document(
            page_content=text,
            metadata={"source": path, "page": i}  # 0-indexed page number
        ))

    doc.close()
    logger.info(f"OCR complete: {len(result)} pages processed")
    return result


# =============================================================================
# Step 2: Split — LangChain RecursiveCharacterTextSplitter
# =============================================================================

@traceable(name="split_chunks", run_type="chain")
def split(docs: list, doc_meta: dict) -> list:
    """
    Split the loaded Document objects into smaller overlapping chunks.

    RecursiveCharacterTextSplitter tries to split at:
      1. Double newlines (paragraph boundaries) — most preferred
      2. Single newlines (line boundaries)
      3. Spaces (word boundaries)
      4. Characters (last resort)

    This preserves semantic meaning within chunks as much as possible.

    After splitting, we inject our custom metadata into each chunk so we can
    build proper citations later:
      - chunk_id:       UUID for identifying this specific chunk in Qdrant + ES + Mongo
      - document_id:    Links chunk back to its parent document
      - document_name:  Human-readable file name (e.g. "ResearchPaper.pdf")
      - domain:         Domain category for verification routing in Phase 3A
      - page_number:    Page this chunk came from (from PyMuPDFLoader metadata)
      - chunk_index:    Position of this chunk within the document (0-based)
      - total_chunks:   Total number of chunks in this document

    Returns a list of LangChain Document objects with updated metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,       # 512 characters per chunk
        chunk_overlap=CHUNK_OVERLAP, # 128 characters shared with adjacent chunks
        separators=["\n\n", "\n", " ", ""]  # preferred split points
    )

    # Split all documents into chunks
    chunks = splitter.split_documents(docs)
    total  = len(chunks)

    # Inject our metadata into every chunk
    for i, chunk in enumerate(chunks):
        chunk.metadata.update({
            # Unique ID for this chunk (used as the record ID in Qdrant, ES, MongoDB)
            "chunk_id":         str(uuid.uuid4()),

            # Position within the document
            "chunk_index":      i,
            "total_chunks":     total,

            # Page number — comes from PyMuPDFLoader (0-indexed), we convert to 1-indexed
            "page_number":      chunk.metadata.get("page", 0) + 1,

            # Document-level metadata
            "document_id":      doc_meta["document_id"],
            "document_name":    doc_meta["document_name"],
            "domain":           doc_meta["domain"],
            "upload_timestamp": doc_meta["upload_timestamp"],
        })

    logger.info(
        f"Split '{doc_meta['document_name']}' → {total} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )
    return chunks


# =============================================================================
# Step 3: Store — LangChain Vector Stores + MongoDB
# =============================================================================

@traceable(name="store_chunks", run_type="chain")
def store(chunks: list):
    """
    Save all chunks to all three storage backends simultaneously:

      Qdrant (via LangChain QdrantVectorStore)
        → Embeds each chunk with HuggingFaceEmbeddings (BAAI/bge-large-en-v1.5)
        → Stores (chunk_id, 1024-dim vector, metadata) for semantic search
        → Used in Phase 2 for nearest-neighbour vector search

      Elasticsearch (via LangChain ElasticsearchStore, BM25 mode)
        → Indexes chunk text with the English analyzer (stemming + stop words)
        → No embedding needed — pure keyword matching
        → Used in Phase 2 for BM25 keyword search

      MongoDB (via our mongo_client)
        → Stores the full chunk text + all metadata
        → Source of truth for citation retrieval
        → Not handled by LangChain (LangChain doesn't track document status)
    """
    # Extract the pieces we need for each store
    texts     = [c.page_content for c in chunks]       # the actual text
    metadatas = [c.metadata for c in chunks]            # all metadata fields
    ids       = [c.metadata["chunk_id"] for c in chunks]  # unique IDs

    # -- Qdrant ----------------------------------------------------------------
    # QdrantVectorStore handles: embed texts → upsert (id, vector, payload)
    # We create the collection first if it doesn't exist yet.
    logger.info(f"Storing {len(chunks)} vectors in Qdrant...")
    qdrant_client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        timeout=30
    )
    _ensure_qdrant_collection(qdrant_client)

    qdrant_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=QDRANT_COLLECTION,
        embedding=embeddings,  # the singleton HuggingFaceEmbeddings
    )
    qdrant_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    # -- MongoDB ---------------------------------------------------------------
    # Save the full chunk text alongside all metadata.
    # We combine metadata dict with chunk_text for each record.
    logger.info(f"Saving {len(chunks)} chunks to MongoDB...")
    mongo.save_chunks([
        {**meta, "chunk_text": text}
        for text, meta in zip(texts, metadatas)
    ])
    logger.info("MongoDB: chunks saved")


def _ensure_qdrant_collection(client: QdrantClient):
    """
    Create the Qdrant collection if it doesn't already exist.
    Called before every store() to ensure the collection is ready.

    Settings:
      - size=EMBEDDING_DIM: 1024 for Cohere embed-english-v3.0
      - distance=COSINE: correct metric for cosine similarity search
    """
    existing_names = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing_names:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Qdrant: created collection '{QDRANT_COLLECTION}' (dim={EMBEDDING_DIM})")


# =============================================================================
# Full Pipeline — run()
# =============================================================================

@traceable(name="ingestion_pipeline", run_type="chain")
def run(
    document_id:      str,
    file_path:        str,
    filename:         str,
    file_type:        str,
    domain:           str,
    upload_timestamp: datetime,
):
    """
    Run the complete RAG ingestion pipeline for one uploaded document.

    Called as a FastAPI BackgroundTask — the upload endpoint returns a response
    to the user immediately while this function runs in the background.

    Flow:
      load() → split() → store() → update MongoDB status

    On success: MongoDB document status → "ready"
    On failure: MongoDB document status → "failed"

    The client polls GET /api/documents to check the status.
    """
    logger.info(f"[Pipeline] START  document='{filename}'  id={document_id}")

    try:
        # STEP 1: Load the file using the appropriate LangChain loader
        docs = load(file_path, file_type)

        # Sanity check: make sure we actually got text
        if not any(d.page_content.strip() for d in docs):
            raise ValueError("No text could be extracted from the file.")

        # STEP 2: Split into overlapping chunks with metadata injected
        chunks = split(docs, {
            "document_id":      document_id,
            "document_name":    filename,
            "domain":           domain,
            "upload_timestamp": upload_timestamp.isoformat(),
        })

        if not chunks:
            raise ValueError("Text splitter produced 0 chunks.")

        # STEP 3: Store in Qdrant + Elasticsearch + MongoDB
        store(chunks)

        # Mark the document as successfully ingested
        mongo.update_status(document_id, "ready", total_chunks=len(chunks))
        logger.info(f"[Pipeline] DONE  document='{filename}'  chunks={len(chunks)}")

    except Exception as e:
        # If anything fails at any step, mark the document as failed
        logger.error(f"[Pipeline] FAILED  document='{filename}'  error={e}")
        mongo.update_status(document_id, "failed", total_chunks=0)

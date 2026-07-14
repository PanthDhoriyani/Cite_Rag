"""
CiteRag — Semantic Chunking Service
Uses LangChain RecursiveCharacterTextSplitter:
  - Chunk size:    512 tokens  (configurable via CHUNK_SIZE env var)
  - Chunk overlap: 128 tokens  (configurable via CHUNK_OVERLAP env var)

Each chunk is annotated with full metadata including page/paragraph numbers
captured from the extractor output. These cannot be reconstructed later.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from models.schemas import Chunk, ChunkMetadata, Domain


# ── Config ────────────────────────────────────────────────────────────────────
# Read at module load time so values reflect .env settings
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "128"))

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", " ", ""],  # prefer paragraph → line → word breaks
)


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_pages(
    pages:            List[Dict[str, Any]],
    document_id:      str,
    document_name:    str,
    domain:           Domain,
    upload_timestamp: datetime,
) -> List[Chunk]:
    """
    Chunk each page's text and attach full metadata to every chunk.

    Strategy:
    - Iterate pages in order.
    - Split each page independently so page_number metadata stays accurate.
    - Paragraph number is the chunk's position within its page (1-indexed).
    - line_start / line_end are computed from the chunk's own line count.
    - global chunk_index is a running counter across all pages.
    - total_chunks is backfilled after processing all pages.

    Returns:
        Flat list of Chunk objects ready for embedding and storage.
    """
    all_chunks:         List[Chunk] = []
    global_chunk_index: int         = 0

    for page in pages:
        page_number: int = page["page_number"]
        page_text:   str = page["text"].strip()

        if not page_text:
            logger.debug(f"Skipping empty page {page_number} in '{document_name}'.")
            continue

        raw_chunks = _splitter.split_text(page_text)

        for para_num, chunk_text in enumerate(raw_chunks, start=1):
            lines      = chunk_text.splitlines()
            line_start = 1
            line_end   = max(1, len(lines))

            chunk = Chunk(
                chunk_text=chunk_text,
                metadata=ChunkMetadata(
                    document_id=document_id,
                    document_name=document_name,
                    chunk_id=str(uuid.uuid4()),
                    chunk_index=global_chunk_index,
                    total_chunks=0,           # backfilled below
                    page_number=page_number,
                    paragraph_number=para_num,
                    line_start=line_start,
                    line_end=line_end,
                    upload_timestamp=upload_timestamp,
                    domain=domain,
                ),
            )
            all_chunks.append(chunk)
            global_chunk_index += 1

    # Backfill total_chunks so every chunk knows the document size
    total = len(all_chunks)
    for c in all_chunks:
        c.metadata.total_chunks = total

    logger.info(
        f"[Chunker] '{document_name}' → {total} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})"
    )
    return all_chunks

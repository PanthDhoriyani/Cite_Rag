"""
CiteRag — Text Extraction Service
Handles three document types:
  - PDF  → PyMuPDF first; Tesseract OCR fallback for scanned/image PDFs
  - DOCX → python-docx paragraph extraction
  - TXT  → plain file read

Returns a list of page dicts: [{"page_number": int, "text": str}]
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger


# ── Public API ────────────────────────────────────────────────────────────────

def extract_text(file_path: str, file_type: str) -> List[Dict[str, Any]]:
    """
    Route extraction to the correct handler based on file extension.

    Args:
        file_path: Absolute path to the saved file.
        file_type: Extension without leading dot (e.g. 'pdf', 'docx', 'txt').

    Returns:
        List of dicts — one per page: {"page_number": int, "text": str}
    """
    path = Path(file_path)
    ext  = file_type.lower().lstrip(".")

    handlers = {
        "pdf":  _extract_pdf,
        "docx": _extract_docx,
        "txt":  _extract_txt,
    }

    if ext not in handlers:
        raise ValueError(f"Unsupported file type: '{ext}'")

    return handlers[ext](path)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> List[Dict[str, Any]]:
    """
    Try PyMuPDF first (fast, accurate for digital PDFs).
    If extracted text is too short (< 100 chars total), fall back to Tesseract OCR.
    """
    pages = _extract_with_pymupdf(path)
    total_text = " ".join(p["text"] for p in pages)

    if len(total_text.strip()) < 100:
        logger.warning(
            f"PyMuPDF returned only {len(total_text.strip())} chars for '{path.name}'. "
            "Falling back to Tesseract OCR (likely scanned PDF)."
        )
        pages = _extract_with_tesseract(path)

    return pages


def _extract_with_pymupdf(path: Path) -> List[Dict[str, Any]]:
    """Extract text page-by-page using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF

        doc   = fitz.open(str(path))
        pages = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            pages.append({"page_number": page_num, "text": text})
        doc.close()

        logger.info(f"[PyMuPDF] Extracted {len(pages)} pages from '{path.name}'.")
        return pages

    except Exception as exc:
        logger.error(f"[PyMuPDF] Failed on '{path.name}': {exc}")
        return [{"page_number": 1, "text": ""}]


def _extract_with_tesseract(path: Path) -> List[Dict[str, Any]]:
    """
    OCR fallback: render each PDF page as a 300-DPI PNG and run Tesseract.
    Requires Tesseract installed on the system and pytesseract + Pillow packages.
    """
    try:
        import fitz
        import pytesseract
        from PIL import Image

        doc   = fitz.open(str(path))
        pages = []
        # 300 DPI matrix for good OCR quality
        mat = fitz.Matrix(300 / 72, 300 / 72)

        for page_num, page in enumerate(doc, start=1):
            pix      = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image    = Image.open(io.BytesIO(img_data))
            text     = pytesseract.image_to_string(image) or ""
            pages.append({"page_number": page_num, "text": text})

        doc.close()
        logger.info(f"[Tesseract] OCR extracted {len(pages)} pages from '{path.name}'.")
        return pages

    except Exception as exc:
        logger.error(f"[Tesseract] OCR failed on '{path.name}': {exc}")
        return [{"page_number": 1, "text": ""}]


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _extract_docx(path: Path) -> List[Dict[str, Any]]:
    """
    Extract paragraphs from a DOCX file using python-docx.
    The whole document is treated as a single logical page.
    """
    try:
        from docx import Document

        doc        = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text  = "\n".join(paragraphs)

        logger.info(
            f"[python-docx] Extracted {len(paragraphs)} paragraphs from '{path.name}'."
        )
        return [{"page_number": 1, "text": full_text}]

    except Exception as exc:
        logger.error(f"[python-docx] Failed on '{path.name}': {exc}")
        return [{"page_number": 1, "text": ""}]


# ── TXT ───────────────────────────────────────────────────────────────────────

def _extract_txt(path: Path) -> List[Dict[str, Any]]:
    """Read a plain-text file with UTF-8 encoding (lossy replace on errors)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        logger.info(f"[TXT] Read {len(text):,} characters from '{path.name}'.")
        return [{"page_number": 1, "text": text}]

    except Exception as exc:
        logger.error(f"[TXT] Failed on '{path.name}': {exc}")
        return [{"page_number": 1, "text": ""}]

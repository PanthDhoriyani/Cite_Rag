# =============================================================================
# CiteRag — Dockerfile
# =============================================================================
# Runs both FastAPI (port 8000) and Streamlit (port 7860) inside one container
# using supervisord as the process manager.
#
# Port 7860 is the standard Hugging Face Spaces exposed port.
# Port 8000 is the internal FastAPI backend (Streamlit calls it via localhost).
#
# Build:  docker build -t citerag .
# Run:    docker run --env-file .env -p 7860:7860 citerag
# =============================================================================

FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# tesseract-ocr    → OCR fallback for scanned PDFs (pytesseract)
# libgl1           → OpenCV/PyMuPDF shared library dependency
# libglib2.0-0     → glib dependency for OpenCV
# supervisor       → process manager that runs FastAPI + Streamlit together
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Copy requirements first — Docker caches this layer separately from code.
# If only code changes (not deps), the pip install layer is reused → fast rebuilds.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download HuggingFace models at build time ────────────────────────────
# Downloads BAAI/bge-large-en-v1.5 (embedding) and BAAI/bge-reranker-large
# into the Docker image so the app starts instantly without downloading on boot.
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-large-en-v1.5'); \
CrossEncoder('BAAI/bge-reranker-large'); \
print('Models pre-downloaded successfully.')"

# ── Application code ──────────────────────────────────────────────────────────
COPY backend/ .

# Create the uploads directory (must exist even if volume-mounted)
RUN mkdir -p uploads

# ── Supervisor config ─────────────────────────────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/citerag.conf

# ── Expose ports ──────────────────────────────────────────────────────────────
# 7860 → Streamlit (Hugging Face Spaces public port)
# 8000 → FastAPI   (internal, called by Streamlit via localhost)
EXPOSE 7860 8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# ── Start both services via supervisord ───────────────────────────────────────
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/citerag.conf"]

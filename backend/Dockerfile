# ─────────────────────────────────────────────────────────────────────────────
# CiteRag Backend — Dockerfile
# Build:  docker build -t citerag-backend .
# Run:    docker run --env-file ../.env -p 8000:8000 citerag-backend
# ─────────────────────────────────────────────────────────────────────────────

# Base image
FROM python:3.12-slim

# OCI image labels (optional metadata)
LABEL org.opencontainers.image.title="CiteRag Backend"
LABEL org.opencontainers.image.description="Citation-Aware RAG API — FastAPI + LangChain"
LABEL org.opencontainers.image.version="0.1.0"

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system-level dependencies:
#   tesseract-ocr  — required by pytesseract for OCR fallback on scanned PDFs
#   libgl1         — required by PyMuPDF on headless servers
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security (avoids running as root inside container)
RUN adduser --disabled-password --gecos "" appuser

# Working directory
WORKDIR /app

# Copy requirements first — Docker caches this layer separately.
# Only rebuilds when requirements.txt actually changes.
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir keeps the image smaller by not saving pip's download cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Create the uploads directory and give ownership to appuser
RUN mkdir -p uploads && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health check — Docker will mark the container unhealthy if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"


# Start FastAPI.
# PORT env var is injected by Railway/Render/Fly — defaults to 8000 locally.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
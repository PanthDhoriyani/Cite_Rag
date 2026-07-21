# Base image
FROM python:3.12-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Print logs immediately
ENV PYTHONUNBUFFERED=1

# Install system-level dependencies:
#   tesseract-ocr  — required by pytesseract for OCR fallback on scanned PDFs
#   libgl1         — required by OpenCV/PyMuPDF on headless servers
#   curl           — used by Railway health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (cached layer — only rebuilds when requirements change)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Create uploads directory (Railway ephemeral disk — files lost on redeploy, use S3 for persistence)
RUN mkdir -p uploads

# Expose FastAPI port
EXPOSE 8000

# Health check (Railway uses this to verify the container is ready)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Start FastAPI with the PORT env var that Railway injects automatically
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
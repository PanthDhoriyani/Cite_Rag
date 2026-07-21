# Base image
FROM python:3.12-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Print logs immediately
ENV PYTHONUNBUFFERED=1

# Install system-level dependencies:
#   tesseract-ocr  — required by pytesseract for OCR fallback on scanned PDFs
#   libgl1         — required by PyMuPDF on headless servers
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
  && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .

# Install Python dependencies (no torch, no HuggingFace models — all API-based now)
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Create uploads directory (Railway ephemeral disk — files lost on redeploy)
RUN mkdir -p uploads

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI with the PORT env var that Railway injects automatically
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
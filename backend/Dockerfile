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

# Install CPU-only PyTorch first (saves ~1.6 GB by avoiding heavy CUDA binaries)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models into HF cache during build so startup is instant (~5s instead of ~3min)
RUN python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='BAAI/bge-large-en-v1.5'); from langchain_community.cross_encoders import HuggingFaceCrossEncoder; HuggingFaceCrossEncoder(model_name='BAAI/bge-reranker-large')"

# Copy backend source code
COPY . .

# Create uploads directory (Railway ephemeral disk — files lost on redeploy)
RUN mkdir -p uploads

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI with the PORT env var that Railway injects automatically
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
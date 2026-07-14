# Replaced by pipeline.py
# All ingestion logic (extract, chunk, embed, store) now lives in backend/pipeline.py
from pipeline import extract, chunk, embed, store, run

__all__ = ["extract", "chunk", "embed", "store", "run"]

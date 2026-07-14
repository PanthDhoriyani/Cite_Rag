# CiteRag — Project Memory & Progress Tracker
> Keeps track of what we have done, what works, and what's next.

---

## 🏗️ Architecture Status: LangChain Rewrite (Complete)
We have successfully refactored the entire project to use **LangChain** as the core RAG framework.
We removed the custom, overly-modular "enterprise" code and replaced it with a flat, readable structure.

### What was replaced:
- Custom PDF loading → `PyMuPDFLoader`
- Custom Chunking → `RecursiveCharacterTextSplitter`
- Custom Embedding → `HuggingFaceEmbeddings`
- Custom Qdrant inserts → `QdrantVectorStore`
- Custom Elasticsearch indexing → `ElasticsearchStore` (BM25 mode)

### What stays custom:
- `MongoDB` handles document status (`processing` vs `ready`) and stores the full chunk text for citations. LangChain does not natively handle asynchronous document ingestion statuses.

---

## 🟢 Current Phase: Phase 2 (Hybrid Retrieval & Reranking) Complete
All files for Phase 2 are written and documented:
1. `backend/retrieval.py` — The LangChain retrieval logic (`QdrantVectorStore` + `ElasticsearchRetriever` + `EnsembleRetriever` + `CrossEncoderReranker`).
2. `backend/routers/query.py` — Updated to execute the retrieval pipeline and return real top 10 chunks as Citations instead of just a stub.

### What is working right now:
- You can successfully upload a document (Phase 1).
- You can query a document and get back the **Top 10 most relevant text chunks** (Phase 2), combining semantic vector search and exact keyword match.
- The generation step (Phase 3) is still a stub, so it won't give you an LLM-generated answer yet.

---

## 🔴 Known Issues
None! The Python 3.14 build error was successfully resolved by switching to the Python 3.12 virtual environment, and all packages installed perfectly.

---

## 🔜 Next Steps (Phase 3)
1. Move to **Phase 3: Answer Generation**.
2. Create `backend/generation.py` to build the **LangChain Expression Language (LCEL)** chains.
3. Implement **Liberal Mode** (Answer from document + AI Explanation).
4. Implement **Strict Mode** (Answer ONLY from document, confidence threshold checks).
5. Update `backend/routers/query.py` to pass the chunks from `retrieval.py` into the LCEL chain in `generation.py`.

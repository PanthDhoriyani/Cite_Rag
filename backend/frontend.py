import streamlit as st
import requests
import time
from datetime import datetime

# =============================================================================
# Page Configuration & Styling
# =============================================================================
# Set page title, icon, and force wide layout for dashboard structure
st.set_page_config(
    page_title="CiteRag Workbench",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Base URL pointing to the FastAPI backend API service
API_BASE_URL = "http://localhost:8000/api"

# Inject custom CSS to construct a modern dark workspace design
# Includes custom card stylings, violet accent highlights, custom scrollbars, and buttons
st.markdown("""
    <style>
        /* General background and typography modifications */
        .stApp {
            background-color: #0d0e12;
            color: #e2e8f0;
        }
        
        /* Premium custom scrollbar styling */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0d0e12;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(147, 51, 234, 0.3);
            border-radius: 999px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(147, 51, 234, 0.6);
        }

        /* Glassmorphism custom panel */
        .glass-panel {
            background: rgba(22, 25, 37, 0.7);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }

        /* Highlighted Answer Card (Liberal - Document-Based) */
        .doc-answer-card {
            border-left: 4px solid #a855f7;
            background: rgba(168, 85, 247, 0.04);
            padding: 1.25rem;
            border-radius: 0 0.75rem 0.75rem 0;
            margin-bottom: 1rem;
        }

        /* Highlighted Answer Card (Liberal - AI Explanation) */
        .ai-answer-card {
            border-left: 4px solid #3b82f6;
            background: rgba(59, 130, 246, 0.04);
            padding: 1.25rem;
            border-radius: 0 0.75rem 0.75rem 0;
            margin-bottom: 1rem;
        }

        /* Citation highlight block */
        .citation-card {
            background: rgba(30, 41, 59, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 1rem;
            border-radius: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .citation-badge {
            background: rgba(168, 85, 247, 0.15);
            color: #d8b4fe;
            border: 1px solid rgba(168, 85, 247, 0.3);
            padding: 0.125rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }
    </style>
""", unsafe_allow_html=True)


# =============================================================================
# Helper Functions connecting to FastAPI Backend
# =============================================================================

def fetch_documents():
    """
    Fetch the list of ingested documents from the FastAPI server.
    Returns: List of document dicts.
    """
    try:
      response = requests.get(f"{API_BASE_URL}/documents", timeout=5)
      if response.status_code == 200:
          return response.json().get("documents", [])
    except Exception as e:
      st.sidebar.error(f"Cannot connect to backend: {e}")
    return []


def upload_document(uploaded_file, domain):
    """
    Upload a document file to the FastAPI backend.
    Parameters:
      - uploaded_file: Streamlit file object
      - domain: Domain string category
    """
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        data = {"domain": domain}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, data=data, timeout=10)
        return response.status_code == 202
    except Exception as e:
        st.error(f"Upload request failed: {e}")
        return False


def delete_document(document_id):
    """
    Delete a document and its database footprints via FastAPI.
    """
    try:
        response = requests.delete(f"{API_BASE_URL}/documents/{document_id}", timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Delete request failed: {e}")
        return False


def query_rag(question, mode, document_ids):
    """
    Post a user question to the RAG backend endpoint.
    Parameters:
      - question: Query string
      - mode: 'strict' or 'liberal'
      - document_ids: List of checked document_ids (empty list means query all)
    """
    try:
        payload = {
            "question": question,
            "mode": mode,
            "document_ids": document_ids if document_ids else None
        }
        response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Query execution request failed: {e}")
    return None


# =============================================================================
# Dashboard Workspace Layout
# =============================================================================

# Main Title & Subtitle Header
st.title("📚 CiteRag Answer Workbench")
st.markdown("##### Hybrid Semantic-BM25 Retrieval & Citation-Aware LLM Inference")

# ── SIDEBAR: UPLOADER & REPOSITORY MANAGER ──────────────────────────────────
st.sidebar.header("📁 Document Ingestion")

# Step 1: Upload Drop-zone
uploaded_file = st.sidebar.file_uploader(
    "Choose a PDF, DOCX, or TXT file", 
    type=["pdf", "docx", "txt"],
    help="Files larger than 50MB will be rejected."
)

# Step 2: Domain dropdown selection
domain_options = {
    "general": "General Content",
    "legal": "Legal / Regulatory",
    "research": "Research / Preprint",
    "healthcare": "Healthcare & Medicine",
    "technical": "Technical documentation",
    "compliance": "Compliance audit",
    "education": "Educational lecture"
}
selected_domain = st.sidebar.selectbox(
    "Select Document Domain",
    options=list(domain_options.keys()),
    format_func=lambda x: domain_options[x]
)

# Trigger Ingestion Pipeline
if st.sidebar.button("Process Document", disabled=not uploaded_file, use_container_width=True):
    with st.sidebar.spinner("Ingesting document..."):
        success = upload_document(uploaded_file, selected_domain)
        if success:
            st.sidebar.success(f"Successfully uploaded {uploaded_file.name}!")
            time.sleep(1)
            st.rerun()
        else:
            st.sidebar.error("Ingestion upload failed.")

st.sidebar.markdown("---")

# Step 3: Document Repository list & Selection
st.sidebar.header("📦 Document Repository")
docs = fetch_documents()

# Keep track of which document_ids are selected by the user to scope the query
selected_doc_ids = []

if not docs:
    st.sidebar.info("No documents ingested yet.")
else:
    for doc in docs:
        col_select, col_meta, col_delete = st.sidebar.columns([0.1, 0.75, 0.15])
        
        # Checkbox for search scoping
        is_ready = doc["status"] == "ready"
        with col_select:
            is_checked = st.checkbox(
                "", 
                value=False, 
                key=f"check_{doc['document_id']}", 
                disabled=not is_ready
            )
            if is_checked:
                selected_doc_ids.append(doc["document_id"])
        
        # Metadata display & Ingestion badges
        with col_meta:
            st.markdown(f"**{doc['document_name']}**")
            
            # Status Badge assignment
            if doc['status'] == 'ready':
                status_html = f"<span style='color:#34d399; font-size:11px;'>Ready ({doc['total_chunks']} chunks)</span>"
            elif doc['status'] == 'processing':
                status_html = "<span style='color:#fbbf24; font-size:11px;'>Processing... (refreshing)</span>"
            else:
                status_html = "<span style='color:#f87171; font-size:11px;'>Failed</span>"
                
            st.markdown(f"<div style='margin-top: -8px;'>{status_html}</div>", unsafe_allow_html=True)
            
        # Delete file action
        with col_delete:
            if st.button("🗑️", key=f"del_{doc['document_id']}", help="Delete from all databases"):
                with st.sidebar.spinner("Deleting..."):
                    if delete_document(doc["document_id"]):
                        st.sidebar.success("Purged!")
                        time.sleep(1)
                        st.rerun()

    # Informational footer on selections
    if selected_doc_ids:
        st.sidebar.caption(f"🔎 Querying scoped to {len(selected_doc_ids)} selected document(s).")
    else:
        st.sidebar.caption("🌍 Global Scope: Querying will search across all documents.")

    # Refresh page if documents are processing to simulate live status polling
    if any(doc["status"] == "processing" for doc in docs):
        time.sleep(2)
        st.rerun()


# ── MAIN COMPONENT: BENCHMARK & QUERYING ───────────────────────────────────

# Layout columns for setting modes
col_mode, col_info = st.columns([0.3, 0.7])

with col_mode:
    # Selector mapping mode configurations
    mode = st.radio(
        "Select Answer Mode",
        options=["Liberal", "Strict"],
        help="Strict mode enforces evidence matching and verifies sources; Liberal mode permits broader AI context."
    )

with col_info:
    # Display guidelines according to selected mode
    if mode == "Strict":
        st.info("🚨 **Strict Mode:** Confidence verification threshold is 0.65. Answers are derived strictly from text chunks. Medical and Research topics will execute PubMed/arXiv verifications.")
    else:
        st.success("🎓 **Liberal Mode:** Combines document facts with the LLM's broader knowledge base. Perfect for educational, brainstorming, or explanatory summaries.")

st.markdown("---")

# Query execution block using st.chat_input
user_question = st.chat_input("Ask a question against your document repository...")

if user_question:
    # Display the user's question
    st.chat_message("user").write(user_question)
    
    # Query FastAPI backend
    with st.spinner("Retrieving facts and generating answers..."):
        result = query_rag(user_question, mode.lower(), selected_doc_ids)
        
    if result:
        st.markdown("### Answer")
        
        # --- Strict Mode Layout Output ---
        if mode == "Strict":
            # Check if threshold failed
            if result.get("status") == "low_confidence":
                st.warning("⚠️ **Low Retrieval Confidence:** Insufficient evidence found in the uploaded documents to answer this question.")
            else:
                # Render answer content
                st.chat_message("assistant").write(result["answer"])
                
                # Confidence Progress visualization
                confidence = result.get("confidence", 0.0)
                st.markdown(f"**Retrieval Confidence Score:** `{confidence:.3f}`")
                st.progress(min(max(confidence, 0.0), 1.0))
                
                # Display Citations in styled expanders
                citations = result.get("citations", [])
                if citations:
                    st.markdown("#### Evidence Citations")
                    for i, cit in enumerate(citations):
                        with st.expander(f"[{i+1}] {cit['document_name']} — Page {cit['page_number'] or 'N/A'}"):
                            st.markdown(f"*{cit['chunk_text']}*")
                            st.markdown(f"<span class='citation-badge'>Source Chunk Index: {cit['chunk_id'][:8]}</span>", unsafe_allow_html=True)
                            
        # --- Liberal Mode Layout Output ---
        else:
            answer_text = result["answer"]
            
            # Split sections to style them separately (expected format from backend chain)
            if "DOCUMENT-BASED ANSWER:" in answer_text and "ADDITIONAL EXPLANATION:" in answer_text:
                parts = answer_text.split("ADDITIONAL EXPLANATION:")
                doc_part = parts[0].replace("DOCUMENT-BASED ANSWER:", "").strip()
                ai_part = parts[1].strip()
                
                st.markdown("**Document-Based Evidence:**")
                st.markdown(f"<div class='doc-answer-card'>{doc_part}</div>", unsafe_allow_html=True)
                
                st.markdown("**Broader AI Explanation:**")
                st.markdown(f"<div class='ai-answer-card'>{ai_part}</div>", unsafe_allow_html=True)
            else:
                # Fallback display if LLM did not structure headers cleanly
                st.chat_message("assistant").write(answer_text)
                
            # Display inline citations as footnotes
            citations = result.get("citations", [])
            if citations:
                with st.expander("References & Chunks Cited"):
                    for i, cit in enumerate(citations):
                        st.markdown(f"**[{i+1}] {cit['document_name']} (Page {cit['page_number'] or 'N/A'})**")
                        st.markdown(f"<p style='color:#9ca3af; font-size:13px; font-style:italic;'>{cit['chunk_text']}</p>", unsafe_allow_html=True)

import streamlit as st
import requests
import time
import os
import subprocess
import socket
from datetime import datetime

# =============================================================================
# FastAPI Background Launcher (Hugging Face Spaces — Streamlit SDK)
# =============================================================================
# When deployed on HF Spaces using the Streamlit SDK (no Docker), this block
# automatically starts the FastAPI backend in a background subprocess.
# A port-check prevents it from being re-launched on every Streamlit rerun.

def _is_fastapi_running(port: int = 8000) -> bool:
    """Return True if something is already listening on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

if not _is_fastapi_running(8000):
    # Start uvicorn as a detached background process.
    # stdout/stderr are suppressed here; logs go to HF Space build output.
    subprocess.Popen(
        ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give FastAPI ~3 seconds to boot before Streamlit starts making requests
    time.sleep(3)

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

# Base URL pointing to the FastAPI backend API service.
# On Hugging Face Spaces both services run in the same process group
# (localhost). Override via BACKEND_URL env var for other deployments.
API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api")


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


def rename_document(document_id, new_name):
    """
    Rename an ingested document via FastAPI.
    """
    try:
        response = requests.patch(
            f"{API_BASE_URL}/documents/{document_id}/rename",
            params={"new_name": new_name},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        st.error(f"Rename request failed: {e}")
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


def fetch_chunk_highlight(chunk_id: str):
    """
    Call the backend highlight endpoint to get a base64 PNG of the highlighted
    PDF page for a given chunk_id.
    Returns the full response dict or None on failure.
    """
    try:
        resp = requests.get(
            f"{API_BASE_URL}/chunks/{chunk_id}/highlight",
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()
        st.error(f"Highlight endpoint error {resp.status_code}: {resp.text[:120]}")
    except Exception as exc:
        st.error(f"PDF view request failed: {exc}")
    return None


def _render_pdf_highlight(data: dict):
    """
    Render the highlighted PDF page image returned by the highlight endpoint.
    Shows the full page; chunk text is highlighted in yellow if found.
    Falls back gracefully for non-PDF files or text-not-found cases.
    """
    if data.get("reason") == "not_pdf":
        st.info("📎 PDF highlight is not available for this file type.")
        return

    image_b64 = data.get("image_base64")
    if not image_b64:
        st.warning("⚠️ Could not render the PDF page.")
        return

    import base64 as _b64
    img_bytes = _b64.b64decode(image_b64)

    page_num  = data.get("page_number", "?")
    doc_name  = data.get("document_name", "")
    found     = data.get("found", False)
    note      = "🟡 Chunk highlighted in yellow" if found else "*(text not pinpointed — showing full page)*"

    st.markdown(
        f"<p style='font-size:12px; color:#9ca3af; margin-bottom:4px;'>"
        f"📄 <strong>{doc_name}</strong> — Page {page_num} &nbsp;•&nbsp; {note}</p>",
        unsafe_allow_html=True
    )
    st.image(img_bytes, use_container_width=True)


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
        col_select, col_meta, col_rename, col_delete = st.sidebar.columns([0.08, 0.62, 0.15, 0.15])
        
        # Checkbox for search scoping
        is_ready = doc["status"] == "ready"
        with col_select:
            is_checked = st.checkbox(
                "Select",
                value=False,
                key=f"check_{doc['document_id']}",
                disabled=not is_ready,
                label_visibility="collapsed"
            )
            if is_checked:
                selected_doc_ids.append(doc["document_id"])
        
        # Parse timestamp for display
        ts_str = doc.get("upload_timestamp", "")
        formatted_time = ""
        if ts_str:
            try:
                # Handle cases with Z or microseconds offsets
                clean_ts = ts_str.split(".")[0].replace("Z", "")
                dt = datetime.fromisoformat(clean_ts)
                formatted_time = dt.strftime("%b %d, %H:%M")
            except Exception:
                formatted_time = ts_str[:16].replace("T", " ")

        # Metadata display & Ingestion badges
        with col_meta:
            st.markdown(f"**{doc['document_name']}**")
            
            # Status Badge assignment
            time_part = f" • {formatted_time}" if formatted_time else ""
            if doc['status'] == 'ready':
                status_html = f"<span style='color:#34d399; font-size:11px;'>Ready ({doc['total_chunks']} chunks){time_part}</span>"
            elif doc['status'] == 'processing':
                status_html = f"<span style='color:#fbbf24; font-size:11px;'>Processing...{time_part}</span>"
            else:
                status_html = f"<span style='color:#f87171; font-size:11px;'>Failed{time_part}</span>"
                
            st.markdown(f"<div style='margin-top: -8px;'>{status_html}</div>", unsafe_allow_html=True)
            
        # Rename file action
        with col_rename:
            with st.popover("✏️", help="Rename document"):
                new_name = st.text_input("New Name", value=doc["document_name"], key=f"ren_input_{doc['document_id']}")
                if st.button("Save", key=f"ren_btn_{doc['document_id']}", use_container_width=True):
                    if new_name.strip() and new_name != doc["document_name"]:
                        with st.spinner("Renaming..."):
                            if rename_document(doc["document_id"], new_name.strip()):
                                st.success("Renamed!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Rename failed.")
                    else:
                        st.warning("Please enter a new name.")

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

# ── SESSION STATE INIT ───────────────────────────────────────────────────────
# Store last query result so it persists when PDF view buttons are clicked.
# (Every button click triggers a Streamlit rerun; without session_state the
# query result would be lost and the chat would disappear.)
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_question" not in st.session_state:
    st.session_state["last_question"] = None
if "last_mode" not in st.session_state:
    st.session_state["last_mode"] = None
if "pdf_views" not in st.session_state:
    st.session_state["pdf_views"] = {}   # chunk_key → API response dict

# Query execution block using st.chat_input
user_question = st.chat_input("Ask a question against your document repository...")

if user_question:
    # Display the user’s question
    st.chat_message("user").write(user_question)

    # Query FastAPI backend
    with st.spinner("Retrieving facts and generating answers..."):
        result = query_rag(user_question, mode.lower(), selected_doc_ids)

    if result:
        # Persist result so subsequent button-click reruns can still display it
        st.session_state["last_result"]   = result
        st.session_state["last_question"] = user_question
        st.session_state["last_mode"]     = mode
        st.session_state["pdf_views"]     = {}   # reset PDF viewers for new query

elif st.session_state["last_question"]:
    # Re-show the stored question on button-click reruns
    st.chat_message("user").write(st.session_state["last_question"])

# ── RENDER RESULT FROM SESSION STATE ─────────────────────────────────────────
result    = st.session_state.get("last_result")
mode_used = st.session_state.get("last_mode") or mode

if result:
    st.markdown("### Answer")

    # ── STRICT MODE ──────────────────────────────────────────────────────────
    if mode_used == "Strict":
        if result.get("status") == "low_confidence":
            st.warning("⚠️ **Low Retrieval Confidence:** Insufficient evidence found in the uploaded documents to answer this question.")
        else:
            st.chat_message("assistant").write(result["answer"])

            confidence = result.get("confidence", 0.0)
            st.markdown(f"**Retrieval Confidence Score:** `{confidence:.3f}`")
            st.progress(min(max(confidence, 0.0), 1.0))

            citations = result.get("citations", [])
            if citations:
                st.markdown("#### Evidence Citations")
                for i, cit in enumerate(citations):
                    chunk_key   = f"pdf_{cit['chunk_id']}"
                    is_pdf_open = chunk_key in st.session_state["pdf_views"]

                    # Keep the expander open while the PDF viewer is active
                    with st.expander(
                        f"[{i+1}] {cit['document_name']} — Page {cit['page_number'] or 'N/A'}",
                        expanded=is_pdf_open
                    ):
                        st.markdown(f"*{cit['chunk_text']}*")
                        st.markdown(
                            f"<span class='citation-badge'>Source Chunk: {cit['chunk_id'][:8]}</span>",
                            unsafe_allow_html=True
                        )

                        is_pdf = cit["document_name"].lower().endswith(".pdf")
                        if is_pdf:
                            btn_label = "🔒 Close PDF View" if is_pdf_open else "📄 View in PDF"
                            if st.button(btn_label, key=f"pdf_btn_strict_{i}_{cit['chunk_id']}"):
                                if is_pdf_open:
                                    del st.session_state["pdf_views"][chunk_key]
                                else:
                                    with st.spinner("Rendering PDF page…"):
                                        img_data = fetch_chunk_highlight(cit["chunk_id"])
                                        if img_data:
                                            st.session_state["pdf_views"][chunk_key] = img_data
                                st.rerun()

                            if is_pdf_open:
                                _render_pdf_highlight(st.session_state["pdf_views"][chunk_key])
                        else:
                            st.caption("📎 PDF highlight not available for this file type.")

    # ── LIBERAL MODE ─────────────────────────────────────────────────────────
    else:
        answer_text = result["answer"]

        if "DOCUMENT-BASED ANSWER:" in answer_text and "ADDITIONAL EXPLANATION:" in answer_text:
            parts    = answer_text.split("ADDITIONAL EXPLANATION:")
            doc_part = parts[0].replace("DOCUMENT-BASED ANSWER:", "").strip()
            ai_part  = parts[1].strip()

            st.markdown("**Document-Based Evidence:**")
            st.markdown(f"<div class='doc-answer-card'>{doc_part}</div>", unsafe_allow_html=True)

            st.markdown("**Broader AI Explanation:**")
            st.markdown(f"<div class='ai-answer-card'>{ai_part}</div>", unsafe_allow_html=True)
        else:
            st.chat_message("assistant").write(answer_text)

        citations = result.get("citations", [])
        if citations:
            # Keep the expander open while any PDF viewer inside it is active
            has_open_pdf = any(
                f"pdf_{c['chunk_id']}" in st.session_state["pdf_views"]
                for c in citations
            )
            with st.expander("References & Chunks Cited", expanded=has_open_pdf):
                for i, cit in enumerate(citations):
                    chunk_key   = f"pdf_{cit['chunk_id']}"
                    is_pdf_open = chunk_key in st.session_state["pdf_views"]
                    is_pdf      = cit["document_name"].lower().endswith(".pdf")

                    col_text, col_btn = st.columns([0.82, 0.18])

                    with col_text:
                        st.markdown(f"**[{i+1}] {cit['document_name']} (Page {cit['page_number'] or 'N/A'})**")
                        st.markdown(
                            f"<p style='color:#9ca3af; font-size:13px; font-style:italic;'>{cit['chunk_text']}</p>",
                            unsafe_allow_html=True
                        )

                    with col_btn:
                        if is_pdf:
                            btn_label = "🔒 Close" if is_pdf_open else "📄 View"
                            if st.button(
                                btn_label,
                                key=f"pdf_btn_lib_{i}_{cit['chunk_id']}",
                                use_container_width=True
                            ):
                                if is_pdf_open:
                                    del st.session_state["pdf_views"][chunk_key]
                                else:
                                    with st.spinner("Rendering…"):
                                        img_data = fetch_chunk_highlight(cit["chunk_id"])
                                        if img_data:
                                            st.session_state["pdf_views"][chunk_key] = img_data
                                st.rerun()
                        else:
                            st.caption("Non-PDF")

                    # Render the highlighted page inline below the citation row
                    if is_pdf_open:
                        _render_pdf_highlight(st.session_state["pdf_views"][chunk_key])

                    st.markdown(
                        "<hr style='border-color:rgba(255,255,255,0.06); margin:0.5rem 0;'>",
                        unsafe_allow_html=True
                    )

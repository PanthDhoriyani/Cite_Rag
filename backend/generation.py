"""
generation.py — LangChain RAG Answer Generation
=================================================
Phase 3: Takes retrieved document chunks and feeds them into the cloud LLM
(Groq API) to generate a cited answer.

Supports two distinct modes:
  1. Liberal Mode: Generates a document-based answer first, then appends broader
     general AI knowledge.
  2. Strict Mode: Generates evidence-only answers. Refuses to answer if the
     retrieval confidence is below threshold. Optionally cross-verifies with public APIs.
"""
import math
from loguru import logger

# LangSmith tracing
from langsmith import traceable

# LangChain LLM and LCEL tools
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Config settings
from config import GROQ_API_KEY, LLM_MODEL, CONFIDENCE_THRESHOLD

# Public verification module (PubMed, arXiv)
from verifier import verify_claim

# Initialize the Groq Chat LLM
# Safe fallback to dummy key if env var is missing to prevent module import crash on startup
llm = ChatGroq(
    model=LLM_MODEL,
    groq_api_key=GROQ_API_KEY if GROQ_API_KEY else "dummy_key_set_groq_api_key_in_env"
)



# =============================================================================
# Prompt Templates
# =============================================================================

# Liberal Mode: Educate and elaborate. Document content first, then general knowledge.
LIBERAL_PROMPT = PromptTemplate.from_template("""
You are a helpful educational assistant.

Answer the user's question using the provided Document Context below.
Then, add a broader explanation, examples, or analogies from your own general knowledge.
You MUST separate these two parts clearly using the section headers shown below.

Document Context:
{context}

Question: {question}

DOCUMENT-BASED ANSWER:
[Provide the answer derived strictly from the provided Document Context here]

ADDITIONAL EXPLANATION:
[Provide broader context, concepts, or details from your own training knowledge here]
""")


# Strict Mode: Evidence-only. Absolute accuracy, no speculation allowed.
STRICT_PROMPT = PromptTemplate.from_template("""
You are a strict evidence-based research assistant.

Answer the user's question using ONLY the provided Evidence Context below.
Every sentence you write MUST be directly traceable to the provided context.
Do NOT speculate, do NOT assume, and do NOT use your own knowledge.
If the Evidence Context does not contain enough information to answer, respond exactly with:
"Insufficient evidence in the uploaded documents."

Evidence Context:
{context}

Question: {question}

Answer:
""")


# =============================================================================
# Helper Functions
# =============================================================================

def _sigmoid(x: float) -> float:
    """
    NOTE: Kept for backward compatibility but no longer used.
    Cohere reranker (rerank-v3.5) returns relevance_score in 0.0–1.0 range directly.
    The old HuggingFace CrossEncoder returned raw logits (-10 to +10) that needed sigmoid.
    """
    return 1.0 / (1.0 + math.exp(-x))

def format_docs(docs: list) -> str:
    """
    Format a list of LangChain Document objects into a single string block
    to be injected into the prompt templates.
    """
    formatted = []
    for i, doc in enumerate(docs):
        doc_name = doc.metadata.get("document_name", "Unknown")
        page_num = doc.metadata.get("page_number", "N/A")
        text = doc.page_content.strip()
        formatted.append(f"--- Document Source [{i+1}]: {doc_name} (Page {page_num}) ---\n{text}")
    return "\n\n".join(formatted)


# =============================================================================
# Answer Generation Entrypoints
# =============================================================================

@traceable(name="generate_liberal_answer", run_type="llm")
def generate_liberal_answer(question: str, docs: list) -> dict:
    """
    Generate an answer in Liberal Mode.
    Connects: Context Formatting -> Prompt -> Groq LLM -> String Output
    """
    logger.info("Generating Liberal Mode answer...")
    context = format_docs(docs)

    # Construct the LangChain Expression Language (LCEL) chain
    chain = LIBERAL_PROMPT | llm | StrOutputParser()

    # Invoke the chain
    answer = chain.invoke({"context": context, "question": question})

    return {
        "answer": answer,
        "status": "ok"
    }


@traceable(name="generate_strict_answer", run_type="llm")
def generate_strict_answer(question: str, docs: list, domain: str) -> dict:
    """
    Generate an answer in Strict Mode.
    
    1. Validation: Ensures retrieval quality exceeds CONFIDENCE_THRESHOLD.
    2. Generation: Instructs Groq LLM to only write evidence-supported text.
    3. Verification: Runs domain-specific public API queries.
    """
    logger.info("Generating Strict Mode answer...")

    # Step 1: Check retrieval confidence threshold
    # Cohere Rerank API returns relevance_score in 0.0–1.0 range directly (no sigmoid needed).
    best_score = docs[0].metadata.get("relevance_score", 0.0) if docs else 0.0
    logger.info(
        f"Top reranker score: {best_score:.4f} "
        f"(Threshold: {CONFIDENCE_THRESHOLD})"
    )

    if best_score < CONFIDENCE_THRESHOLD:
        logger.warning("Top relevance score is below confidence threshold. Refusing to answer.")
        return {
            "answer": "Insufficient evidence in the uploaded documents.",
            "status": "low_confidence",
            "confidence": round(best_score, 3),
            "verification": {"status": "Skipped", "reason": "Low retrieval confidence"}
        }

    # Step 2: Calculate confidence score (direct average of top 3 Cohere scores)
    top_scores = [d.metadata.get("relevance_score", 0.0) for d in docs[:3]]
    avg_confidence = sum(top_scores) / len(top_scores) if top_scores else 0.0

    # Step 3: LCEL Generation Chain
    context = format_docs(docs)
    chain = STRICT_PROMPT | llm | StrOutputParser()
    answer = chain.invoke({"context": context, "question": question})

    # Step 4: Optional Domain-Specific Public Verification
    # Cross-verify the question/claims against public APIs
    verification = verify_claim(question, domain)

    # Append verification results to the answer text if verified
    modified_answer = answer
    if verification.get("status") == "Verified" and verification.get("references"):
        refs = "\n".join([f"- {ref}" for ref in verification["references"]])
        modified_answer += f"\n\n[Public Verification Source: {verification['source']}]\n{refs}"

    return {
        "answer": modified_answer,
        "status": "ok",
        "confidence": round(avg_confidence, 3)
    }

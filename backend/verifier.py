"""
verifier.py — Domain-Specific Public Verification
===================================================
Used in Strict Mode (Phase 3A) to cross-verify the generated answer
or its key terms against external public databases based on the document's domain.

Supported Domains & APIs:
  - healthcare → PubMed API
  - research   → arXiv API
  - general / others → Return default "No verification required"
"""
import httpx
from loguru import logger

# LangSmith tracing
from langsmith import traceable

# Connect timeout and read timeout for API calls
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@traceable(name="verify_pubmed", run_type="tool")
def verify_pubmed(query: str) -> dict:
    """
    Search PubMed database using Entrez E-utilities API.
    Checks if there are relevant articles matching the query/claims.
    """
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": 3
    }
    try:
        logger.info(f"Querying PubMed API for: '{query[:50]}...'")
        response = httpx.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if id_list:
                logger.info(f"PubMed: Found {len(id_list)} matching articles. IDs: {id_list}")
                # We could fetch summaries here, but for simple coding we return verification status
                return {
                    "status": "Verified",
                    "source": "PubMed",
                    "references": [f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" for pmid in id_list]
                }
            else:
                logger.info("PubMed: No matching articles found.")
                return {"status": "Unverified", "source": "PubMed", "references": []}
    except Exception as e:
        logger.error(f"PubMed API request failed: {e}")
    return {"status": "Error", "source": "PubMed", "message": "Failed to connect to PubMed"}


@traceable(name="verify_arxiv", run_type="tool")
def verify_arxiv(query: str) -> dict:
    """
    Search arXiv preprints database.
    Checks if scientific papers match the terms in the query/claims.
    """
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "max_results": 3
    }
    try:
        logger.info(f"Querying arXiv API for: '{query[:50]}...'")
        response = httpx.get(url, params=params, timeout=TIMEOUT)
        if response.status_code == 200:
            xml_data = response.text
            # Simple substring parser since we don't want to add xml parser dependencies
            if "<entry>" in xml_data:
                # Extract IDs using simple string splits
                papers = []
                parts = xml_data.split("<entry>")[1:]
                for part in parts:
                    if "<id>" in part:
                        paper_url = part.split("<id>")[1].split("</id>")[0].strip()
                        papers.append(paper_url)
                logger.info(f"arXiv: Found {len(papers)} matching articles.")
                return {
                    "status": "Verified",
                    "source": "arXiv",
                    "references": papers
                }
            else:
                logger.info("arXiv: No matching papers found.")
                return {"status": "Unverified", "source": "arXiv", "references": []}
    except Exception as e:
        logger.error(f"arXiv API request failed: {e}")
    return {"status": "Error", "source": "arXiv", "message": "Failed to connect to arXiv"}


@traceable(name="verify_claim", run_type="tool")
def verify_claim(claim: str, domain: str) -> dict:
    """
    Route the verification claim to the proper API based on the document's domain.
    """
    if not claim or len(claim.strip()) < 5:
        return {"status": "Skipped", "reason": "Claim too short"}

    # Route based on domain
    if domain == "healthcare":
        return verify_pubmed(claim)
    elif domain == "research":
        return verify_arxiv(claim)
    else:
        # Other domains (legal, technical, compliance, education, general)
        # for a simple project return skipped / mock successful status
        logger.info(f"Verification skipped: No public API configured for domain '{domain}'")
        return {"status": "Not Required", "reason": f"No external API mapped for domain '{domain}'"}

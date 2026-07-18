from dotenv import load_dotenv
# Load environment variables
load_dotenv(dotenv_path="../.env")

from retrieval import retrieve_documents

print("Running retrieve_documents test query...")
results = retrieve_documents("attention")
print(f"Total results: {len(results)}")
for i, doc in enumerate(results[:3]):
    print(f"\nResult {i+1}:")
    print(f"Document: {doc.metadata.get('document_name')}")
    print(f"Page: {doc.metadata.get('page_number')}")
    print(f"Relevance Score: {doc.metadata.get('relevance_score')}")
    print(f"Metadata keys: {list(doc.metadata.keys())}")
    print(f"Text snippet: {doc.page_content[:150]}...")

import os
from dotenv import load_dotenv
from langsmith import Client

# Load environment variables from the parent directory
# Since we are in backend/, we load from ../.env
load_dotenv(dotenv_path="../.env")

print("--- Environment Variables ---")
print(f"LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2')}")
print(f"LANGCHAIN_API_KEY: {os.getenv('LANGCHAIN_API_KEY')[:15] if os.getenv('LANGCHAIN_API_KEY') else None}...")
print(f"LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT')}")
print(f"LANGCHAIN_ENDPOINT: {os.getenv('LANGCHAIN_ENDPOINT')}")

print("\n--- Initializing LangSmith Client ---")
try:
    client = Client()
    # Test connection by listing projects
    projects = list(client.list_projects())
    print("Successfully connected to LangSmith!")
    print("Your projects:")
    for proj in projects:
        print(f" - {proj.name}")
except Exception as e:
    print("ERROR connecting to LangSmith:")
    import traceback
    traceback.print_exc()

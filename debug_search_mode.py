import os
from dotenv import load_dotenv
from search_manager import AzureSearchManager

# Load environment variables
load_dotenv()

def test_search_mode():
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")

    if not all([endpoint, key, index_name]):
        print("Error: Missing environment variables.")
        return

    search_manager = AzureSearchManager(endpoint, key, index_name)
    query = "foundation loading data"

    print(f"--- Testing Search Mode: ALL (AND) with query '{query}' ---")
    results_all = search_manager.search(query, search_mode="all", top=5)
    print(f"Found {len(results_all)} documents.")
    for res in results_all:
        print(f"- {res.get('metadata_storage_name')}")

    print(f"\n--- Testing Search Mode: ANY (OR) with query '{query}' ---")
    results_any = search_manager.search(query, search_mode="any", top=5)
    print(f"Found {len(results_any)} documents.")
    for res in results_any:
        print(f"- {res.get('metadata_storage_name')}")

if __name__ == "__main__":
    test_search_mode()

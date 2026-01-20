import os
from search_manager import AzureSearchManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_secret(key):
    return os.environ.get(key)

# Configuration
SEARCH_ENDPOINT = get_secret("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = get_secret("AZURE_SEARCH_KEY")
SEARCH_INDEX_NAME = get_secret("AZURE_SEARCH_INDEX_NAME") or "pdf-search-index"

def test_fetch(filename):
    print(f"Testing fetch for: {filename}")
    manager = AzureSearchManager(SEARCH_ENDPOINT, SEARCH_KEY, SEARCH_INDEX_NAME)
    
    # Method 1: Current implementation (startswith)
    print("--- Method 1: Current Implementation ---")
    docs = manager.get_document_json(filename)
    print(f"Found {len(docs)} documents.")
    if len(docs) == 0:
        print("FAILURE: No documents found.")
    else:
        print(f"SUCCESS: Found {len(docs)} pages.")
        print(f"Sample ID: {docs[0]['id']}")
        print(f"Sample Name: {docs[0]['metadata_storage_name']}")

    # Method 2: Alternative implementation (search.ismatch)
    print("\n--- Method 2: Alternative Implementation (search.ismatch) ---")
    try:
        # Escape for search query
        safe_filename = filename.replace('"', '\\"')
        
        results = manager.search_client.search(
            search_text="*",
            filter=f"project eq 'drawings_analysis' and search.ismatch('\"{safe_filename}\"', 'metadata_storage_name')",
            select=["id", "metadata_storage_name"],
            top=10
        )
        docs2 = list(results)
        print(f"Found {len(docs2)} documents.")
    except Exception as e:
        print(f"Error in Method 2: {e}")

if __name__ == "__main__":
    # Test with the problematic filename from the screenshot
    # "PH20-810-EC115-00540_REV.A_PH20 TCA COOLER FOUNDATION PLAN & SECTION 1.pdf"
    target_file = "PH20-810-EC115-00540_REV.A_PH20 TCA COOLER FOUNDATION PLAN & SECTION 1.pdf"
    test_fetch(target_file)

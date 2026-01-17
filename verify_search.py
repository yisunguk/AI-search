import os
from dotenv import load_dotenv
from search_manager import AzureSearchManager

# Load environment variables
load_dotenv()

def verify_search_config():
    service_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    service_key = os.environ.get("AZURE_SEARCH_KEY")
    
    if not service_endpoint or not service_key:
        print("Error: Azure Search credentials not found in environment variables.")
        return

    manager = AzureSearchManager(service_endpoint, service_key)
    
    print(f"Checking Index: {manager.index_name}")
    
    try:
        index = manager.index_client.get_index(manager.index_name)
        print("Index exists.")
        
        # Verify Analyzer on metadata_storage_name
        name_field = next((f for f in index.fields if f.name == "metadata_storage_name"), None)
        if name_field:
            print(f"Field 'metadata_storage_name' Analyzer: {name_field.analyzer_name}")
            if name_field.analyzer_name == "tag_analyzer":
                print("SUCCESS: Custom Analyzer 'tag_analyzer' is applied to 'metadata_storage_name'.")
            else:
                print(f"WARNING: Expected 'tag_analyzer', found '{name_field.analyzer_name}'.")
        else:
            print("Error: Field 'metadata_storage_name' not found.")

        # Verify content_exact field
        exact_field = next((f for f in index.fields if f.name == "content_exact"), None)
        if exact_field:
            print(f"Field 'content_exact' exists. Analyzer: {exact_field.analyzer_name}")
        else:
            print("WARNING: Field 'content_exact' not found.")

        # Test Search
        query = "10-P-101A"
        print(f"\nTesting Search for '{query}'...")
        results = manager.search(query)
        print(f"Found {len(results)} results.")
        for res in results:
            print(f" - {res.get('metadata_storage_name')}")
            if '@search.highlights' in res:
                print(f"   Highlights: {res['@search.highlights']}")

    except Exception as e:
        print(f"Error verifying index: {e}")

if __name__ == "__main__":
    verify_search_config()

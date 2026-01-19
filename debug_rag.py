import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

service_endpoint = os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT")
index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME")
key = os.environ.get("AZURE_SEARCH_ADMIN_KEY")

if not all([service_endpoint, index_name, key]):
    print("Missing environment variables. Please check .env file.")
    exit(1)

credential = AzureKeyCredential(key)
client = SearchClient(endpoint=service_endpoint,
                      index_name=index_name,
                      credential=credential)

def check_index_stats():
    print(f"--- Checking Index: {index_name} ---")
    count = client.get_document_count()
    print(f"Total Documents: {count}")

def list_drawings_documents():
    print("\n--- Listing Documents with project='drawings_analysis' ---")
    results = client.search(search_text="*", filter="project eq 'drawings_analysis'", select=["id", "metadata_storage_name", "project"])
    count = 0
    for doc in results:
        print(f"Found: {doc['metadata_storage_name']} (ID: {doc['id']})")
        count += 1
    print(f"Total 'drawings_analysis' documents found: {count}")

def test_search(query):
    print(f"\n--- Testing Search: '{query}' ---")
    results = client.search(search_text=query, filter="project eq 'drawings_analysis'", top=5, select=["metadata_storage_name", "content"])
    count = 0
    for doc in results:
        print(f"Match: {doc['metadata_storage_name']}")
        print(f"Content Snippet: {doc['content'][:100]}...")
        count += 1
    print(f"Total matches: {count}")

if __name__ == "__main__":
    check_index_stats()
    list_drawings_documents()
    test_search("foundation loading data")
    test_search("*")

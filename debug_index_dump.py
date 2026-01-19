import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

service_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
service_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
index_name = "pdf-search-index"

credential = AzureKeyCredential(service_key)
client = SearchClient(endpoint=service_endpoint, index_name=index_name, credential=credential)

print(f"Querying index: {index_name}")

results = client.search(search_text="*", select=["metadata_storage_name"], top=50)

print("-" * 50)
for result in results:
    name = result['metadata_storage_name']
    print(f"Name: {name}")
    print(f"Repr: {repr(name)}")
    # Print hex for first few chars to check encoding
    print(f"Hex:  {' '.join(hex(ord(c)) for c in name[:20])}...")
    print("-" * 50)

import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import unicodedata

# Load secrets from .streamlit/secrets.toml if possible, or use environment variables
# For this debug script, we'll assume they are available or we can hardcode for a quick check
# But better to read from the environment if set.

endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
key = os.environ.get("AZURE_SEARCH_KEY")
index_name = "pdf-search-index"

if not endpoint or not key:
    print("Error: AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_KEY not set in environment.")
    # Try to read from streamlit secrets if running locally
    try:
        import toml
        secrets = toml.load(".streamlit/secrets.toml")
        endpoint = secrets.get("AZURE_SEARCH_ENDPOINT")
        key = secrets.get("AZURE_SEARCH_KEY")
    except:
        pass

if not endpoint or not key:
    print("Still no credentials. Please set them.")
    exit(1)

client = SearchClient(endpoint=endpoint, index_name=index_name, credential=AzureKeyCredential(key))

print(f"--- Index Content Check ---")
target_filename = "Fuel Gas Coalescing Filter for Gas Turbine(filter).pdf"
import re
# Escape for Lucene
escaped_filename = re.sub(r'([+\-&|!(){}\[\]^"~*?:\\])', r'\\\1', target_filename)

# Use search.ismatch in filter
filter_expr = f"search.ismatch('\"{escaped_filename}\"', 'metadata_storage_name')"
print(f"Searching with filter: {filter_expr}")
results = client.search(search_text="*", filter=filter_expr, select=["metadata_storage_name", "project", "metadata_storage_path"], top=100)

print(f"Found {results.get_count() if hasattr(results, 'get_count') else 'some'} documents.")
for doc in results:
    name = doc.get('metadata_storage_name', 'N/A')
    project = doc.get('project', 'N/A')
    path = doc.get('metadata_storage_path', 'N/A')
    
    # Check normalization
    is_nfc = unicodedata.is_normalized('NFC', name)
    
    print(f"Name: {name} (NFC: {is_nfc})")
    print(f"  Project: {project}")
    print(f"  Path: {path}")
    print("-" * 20)

print(f"--- End of Check ---")

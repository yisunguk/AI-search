import os
import re
import urllib3
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

def get_secret_from_file(key):
    try:
        with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(f'{key} = "(.*)"', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error reading secrets file: {e}")
    return None

def main():
    endpoint = get_secret_from_file("AZURE_SEARCH_ENDPOINT")
    key = get_secret_from_file("AZURE_SEARCH_KEY")
    index_name = get_secret_from_file("AZURE_SEARCH_INDEX_NAME") or "pdf-search-index"
    
    if not endpoint or not key:
        print("Error: Search credentials not found.")
        return

    credential = AzureKeyCredential(key)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential, connection_verify=False)
    
    print(f"Checking index: {index_name}")
    
    # Filter for gulflng folder
    # Note: We are using client-side filtering to be safe, or we can try OData if we think it works.
    # Let's use search with broad query and count.
    
    try:
        results = client.search(search_text="*", top=1000)
        gulflng_docs = []
        for res in results:
            path = res.get('metadata_storage_path', '')
            if '/gulflng/' in path:
                gulflng_docs.append(res)
        
        print(f"Total documents in index: {sum(1 for _ in client.search(search_text='*', select='id'))}")
        print(f"Documents found for 'gulflng': {len(gulflng_docs)}")
        
        if gulflng_docs:
            print("\nSample documents:")
            for doc in gulflng_docs[:5]:
                print(f"- {doc.get('metadata_storage_name')}")
                
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    main()

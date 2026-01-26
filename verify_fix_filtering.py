import os
import sys
from chat_manager_v2 import AzureOpenAIChatManager
from search_manager import AzureSearchManager
import streamlit as st

# Mock streamlit secrets
if not os.path.exists(".streamlit/secrets.toml"):
    print("Secrets file not found")
    sys.exit(1)

import toml
# Helper function to get secrets (matching app.py logic)
def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.environ.get(key)

try:
    print("Loaded secrets keys:", list(st.secrets.keys()))
except:
    pass

# Setup
endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
api_key = get_secret("AZURE_OPENAI_KEY") # Fixed key name
deployment = get_secret("AZURE_OPENAI_DEPLOYMENT") or get_secret("AZURE_OPENAI_DEPLOYMENT_NAME") # Fixed key name
api_version = get_secret("AZURE_OPENAI_API_VERSION")
search_endpoint = get_secret("AZURE_SEARCH_ENDPOINT")
search_key = get_secret("AZURE_SEARCH_KEY")
storage_conn = get_secret("AZURE_STORAGE_CONNECTION_STRING")
container = get_secret("AZURE_BLOB_CONTAINER_NAME")

search_manager = AzureSearchManager(search_endpoint, search_key)
chat_manager = AzureOpenAIChatManager(endpoint, api_key, deployment, api_version, search_manager, storage_conn, container)

def test_filtering(user_folder, query="List"):
    print(f"\nTesting with user_folder='{user_folder}' and query='{query}'...")
    try:
        # We need to mock the search_manager.search to return mixed results if we want to test the filter logic in isolation,
        # OR we can rely on the actual index having mixed data (which it seems to have).
        # Let's rely on actual index.
        
        response, citations, context, filter_expr, results = chat_manager.get_chat_response(
            query,
            conversation_history=[],
            user_folder=user_folder
        )
        
        print(f"Results count: {len(results)}")
        for i, res in enumerate(results[:5]):
            path = res.get('metadata_storage_path', '')
            print(f"{i+1}. {res.get('metadata_storage_name')} - Path: {path}")
            
            # Verification
            if user_folder and user_folder not in path:
                print(f"❌ FAILURE: Found document NOT belonging to {user_folder}")
            else:
                print(f"✅ OK")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test 1: gulflng (Should only see gulflng docs)
    test_filtering("gulflng")
    
    # Test 2: 이근배 (Should only see 이근배 docs, if any)
    test_filtering("이근배")

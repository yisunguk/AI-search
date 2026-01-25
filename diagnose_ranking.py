from search_manager import AzureSearchManager
import streamlit as st
import re

# Mock secrets for script execution
AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]

def diagnose():
    sm = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)
    query = "냉각수펌프 전기실"
    
    # Sanitize like Chat Manager
    sanitized_query = re.sub(r'\bAND\b', ' ', query, flags=re.IGNORECASE)
    sanitized_query = re.sub(r'[&+\-|!(){}\[\]^"~*?:\\]', ' ', sanitized_query)
    sanitized_query = " ".join(sanitized_query.split())
    
    print(f"Query: {sanitized_query}")
    
    results = sm.search(
        sanitized_query,
        search_mode="all",
        top=10,
        use_semantic_ranker=False
    )
    
    print(f"Found {len(results)} results.")
    for i, res in enumerate(results, 1):
        name = res.get('metadata_storage_name', 'Unknown')
        content = res.get('content', '')[:200].replace('\n', ' ')
        print(f"{i}. {name}")
        print(f"   Content: {content}...")
        
        if "p.17" in name:
            print("   [SUSPECT] This is the page the LLM used.")
        if "p.82" in name:
            print("   [TARGET] This is the page the user wants.")

if __name__ == "__main__":
    diagnose()

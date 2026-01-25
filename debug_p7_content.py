import os
from search_manager import AzureSearchManager
import streamlit as st

# Mock secrets for local execution if needed, or rely on env vars
# Assuming running in environment where secrets are available or can be loaded
try:
    AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
    AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]
except:
    # Fallback for local testing if secrets not in streamlit config
    AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT")
    AZURE_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY")

if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
    print("Error: Azure Search credentials not found.")
    exit(1)

search_manager = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)

filename = "제4권 도면(청주).pdf"
print(f"Searching for Page 7 of {filename}...")

# 1. Fetch Page 7 specifically
results = search_manager.search(
    "*",
    filter_expr=f"search.ismatch('{filename}', 'metadata_storage_name')",
    top=200
)

page_7_doc = None
for doc in results:
    if "(p.7)" in doc['metadata_storage_name']:
        page_7_doc = doc
        break

if page_7_doc:
    print(f"\n✅ Found Page 7: {page_7_doc['metadata_storage_name']}")
    print("-" * 50)
    print(f"CONTENT PREVIEW (First 500 chars):\n")
    print(page_7_doc['content'][:500])
    print("-" * 50)
    
    # Check for keywords
    content = page_7_doc['content'].upper()
    keywords = ["PIPING", "INSTRUMENT", "DIAGRAM", "LIST", "FOR", "INDEX"]
    print("\nKeyword Check:")
    for kw in keywords:
        if kw in content:
            print(f"  ✅ {kw}")
        else:
            print(f"  ❌ {kw}")
            
    # Check exact phrases
    phrases = [
        "PIPING AND INSTRUMENT DIAGRAM LIST",
        "PIPING AND INSTRUMENT DIAGRAM FOR LIST",
        "PIPING & INSTRUMENT DIAGRAM"
    ]
    print("\nPhrase Check:")
    for phrase in phrases:
        if phrase in content:
            print(f"  ✅ '{phrase}'")
        else:
            print(f"  ❌ '{phrase}'")

else:
    print("❌ Page 7 NOT FOUND in index.")

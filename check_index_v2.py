import os
import streamlit as st
from search_manager import AzureSearchManager
from dotenv import load_dotenv

load_dotenv()

# Mock st.secrets if needed
try:
    AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
    AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]
    AZURE_SEARCH_INDEX_NAME = st.secrets.get("AZURE_SEARCH_INDEX_NAME", "pdf-search-index")
except:
    AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
    AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
    AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "pdf-search-index")

if not AZURE_SEARCH_ENDPOINT:
    print("Failed to get credentials.")
    exit(1)

search_manager = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX_NAME)

target_files = ['제4권 도면(청주).pdf', '제4권 도면_2018.10.22.pdf']

print(f"Checking index for: {target_files}")

for filename in target_files:
    # Escape for filter
    safe_name = filename.replace("'", "''")
    results = search_manager.search(
        "*",
        filter_expr=f"startswith(metadata_storage_name, '{safe_name}')",
        select=["metadata_storage_name"]
    )
    print(f"File '{filename}': Found {len(results)} chunks.")

print("-" * 30)
print("Listing top 10 filenames in index:")
results = search_manager.search("*", select=["metadata_storage_name"], top=10)
seen = set()
for res in results:
    name = res['metadata_storage_name']
    # Extract base name
    base = name.split(' (p.')[0]
    if base not in seen:
        print(f" - {name}")
        seen.add(base)

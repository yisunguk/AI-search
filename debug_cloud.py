import streamlit as st
from search_manager import AzureSearchManager

st.set_page_config(page_title="Search Debug Tool", page_icon="🔍", layout="wide")

st.title("🔍 Search Debug Tool (Cloud)")

# Secrets
AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]

search_manager = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)

filename = "제4권 도면(청주).pdf"

st.markdown("---")

# Test 1: Check if page 7 exists
st.header("📋 Test 1: Verify Page 7 is Indexed")

with st.spinner("Fetching all pages..."):
    all_pages = search_manager.search(
        "*",
        filter_expr=f"startswith(metadata_storage_name, '{filename}')",
        top=200
    )

page_7_doc = None
all_page_names = []
for doc in all_pages:
    name = doc['metadata_storage_name']
    all_page_names.append(name)
    if "(p.7)" in name:
        page_7_doc = doc

if page_7_doc:
    st.success(f"✅ **Page 7 EXISTS in index:** `{page_7_doc['metadata_storage_name']}`")
    with st.expander("📄 View Page 7 Content (first 1000 chars)"):
        st.code(page_7_doc['content'][:1000], language=None)
        
        # Check for keywords
        content_upper = page_7_doc['content'].upper()
        keywords = ["PIPING AND INSTRUMENT DIAGRAM", "P&I DIAGRAM", "LIST", "INDEX", "DRAWING"]
        st.write("**Keywords found in content:**")
        for kw in keywords:
            if kw in content_upper:
                st.write(f"  ✅ `{kw}`")
            else:
                st.write(f"  ❌ `{kw}` (NOT FOUND)")
else:
    st.error("❌ **Page 7 NOT FOUND in index!**")
    st.write(f"Total pages found: {len(all_pages)}")
    with st.expander("All indexed pages"):
        for name in all_page_names[:50]:
            st.write(f"- {name}")
    st.stop()

st.markdown("---")

# Test 2: Search queries
st.header("🔎 Test 2: Search Query Analysis")

test_queries = [
    ("P&ID 리스트 비교", "Original user query"),
    ("PIPING AND INSTRUMENT DIAGRAM LIST", "Expanded query"),
    ("P&ID DIAGRAM LIST INDEX TABLE", "Full expansion"),
    ("PIPING INSTRUMENT", "Keywords only"),
    ("LIST", "Single keyword"),
    ("*", "Wildcard")
]

results_data = []

for query, description in test_queries:
    with st.spinner(f"Testing query: {query}..."):
        results = search_manager.search(
            query,
            filter_expr=f"startswith(metadata_storage_name, '{filename}')",
            search_mode="any",
            top=50
        )
    
    page_7_rank = None
    top_page = None
    for rank, doc in enumerate(results):
        if rank == 0:
            top_page = doc['metadata_storage_name']
        if "(p.7)" in doc['metadata_storage_name']:
            page_7_rank = rank + 1
            break
    
    results_data.append({
        "Query": query,
        "Description": description,
        "Page 7 Rank": f"✅ Rank {page_7_rank}" if page_7_rank else "❌ Not in top 50",
        "Top Result": top_page if top_page else "No results"
    })

import pandas as pd
df = pd.DataFrame(results_data)
st.dataframe(df, use_container_width=True)

st.markdown("---")

# Test 3: With filters
st.header("🔧 Test 3: Filter Analysis")

filter_tests = [
    (None, "No filter"),
    (f"startswith(metadata_storage_name, '{filename}')", "File filter only"),
    (f"project eq 'drawings_analysis'", "Project filter only"),
    (f"project eq 'drawings_analysis' and startswith(metadata_storage_name, '{filename}')", "Both filters")
]

filter_results = []

for filter_expr, description in filter_tests:
    with st.spinner(f"Testing filter: {description}..."):
        results = search_manager.search(
            "PIPING INSTRUMENT DIAGRAM LIST",
            filter_expr=filter_expr,
            search_mode="any",
            top=50
        )
    
    page_7_rank = None
    total_results = len(results)
    for rank, doc in enumerate(results):
        if "(p.7)" in doc.get('metadata_storage_name', ''):
            page_7_rank = rank + 1
            break
    
    filter_results.append({
        "Filter": description,
        "Total Results": total_results,
        "Page 7 Status": f"✅ Rank {page_7_rank}/{total_results}" if page_7_rank else f"❌ Not found (out of {total_results})"
    })

df_filter = pd.DataFrame(filter_results)
st.dataframe(df_filter, use_container_width=True)

st.markdown("---")

# Conclusion
st.header("💡 Diagnostic Summary")

if all(row["Page 7 Rank"].startswith("❌") for row in results_data):
    st.error("""
    **Root Cause Identified:**
    Page 7 is indexed but NEVER returned by keyword searches.
    
    **Possible reasons:**
    1. OCR text quality issue (text not searchable)
    2. Tokenization problem (keywords split incorrectly)
    3. Indexing configuration (analyzer issue)
    
    **Recommended fix:**
    Re-index the document with better OCR or different analyzer.
    """)
elif any(row["Page 7 Rank"].startswith("✅") for row in results_data[:3]):
    st.success("""
    **Status:** Page 7 CAN be found with some queries.
    
    **Next step:** Verify chat_manager uses the correct query expansion.
    """)
else:
    st.warning("""
    **Status:** Page 7 only found with wildcard/basic queries.
    
    **Issue:** Keyword matching is not working properly.
    """)

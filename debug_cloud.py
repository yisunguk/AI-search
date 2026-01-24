import streamlit as st
from search_manager import AzureSearchManager

st.set_page_config(page_title="Search Debug Tool", page_icon="🔍", layout="wide")

st.title("🔍 Search Debug Tool (Cloud)")

# Secrets
AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]

search_manager = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)

# ========================================
# 사용자 정의 검색 입력
# ========================================
st.header("📝 사용자 지정 검색")

col1, col2 = st.columns([2, 1])

with col1:
    custom_query = st.text_input(
        "검색할 키워드 입력",
        value="piping and instrument diagram list",
        help="검색하고 싶은 키워드를 입력하세요"
    )

with col2:
    custom_top = st.number_input(
        "검색 결과 수",
        min_value=1,
        max_value=200,
        value=50,
        step=10
    )

filename = st.text_input(
    "대상 파일명 (선택사항)",
    value="제4권 도면(청주).pdf",
    help="특정 파일만 검색하려면 입력하세요. 비워두면 전체 인덱스를 검색합니다."
)

if st.button("🔍 검색 실행", type="primary", use_container_width=True):
    st.markdown("---")
    st.subheader(f"🔎 검색 결과: '{custom_query}'")
    
    with st.spinner("검색 중..."):
        # Build filter
        filter_expr = None
        if filename and filename.strip():
            filter_expr = f"search.ismatch('{filename}', 'metadata_storage_name')"
        
        # Execute search
        results = search_manager.search(
            custom_query,
            filter_expr=filter_expr,
            search_mode="any",
            top=custom_top
        )
        
        st.success(f"✅ **{len(results)}개 결과 발견**")
        
        if len(results) == 0:
            st.warning("검색 결과가 없습니다. 다른 키워드를 시도해보세요.")
        else:
            # Display results
            for i, doc in enumerate(results, 1):
                doc_name = doc.get('metadata_storage_name', 'Unknown')
                content = doc.get('content', '')
                title = doc.get('title', 'No title')
                
                with st.expander(f"**{i}. {doc_name}**", expanded=(i <= 3)):
                    st.markdown(f"**Title**: {title}")
                    
                    # Highlight if query keywords are in content
                    content_upper = content.upper()
                    query_upper = custom_query.upper()
                    
                    # Check for keyword presence
                    keywords_found = []
                    for word in query_upper.split():
                        if word in content_upper:
                            keywords_found.append(word)
                    
                    if keywords_found:
                        st.success(f"✅ 키워드 매칭: {', '.join(keywords_found)}")
                    
                    # Content preview
                    st.markdown("**Content Preview (처음 500자):**")
                    st.text_area("", content[:500], height=150, key=f"custom_result_{i}", disabled=True)
                    
                    # Full content
                    with st.expander("전체 내용 보기"):
                        st.text_area("", content, height=400, key=f"custom_full_{i}", disabled=True)

st.markdown("---")
st.markdown("---")
st.header("🔬 자동 테스트 (기본 디버깅)")

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

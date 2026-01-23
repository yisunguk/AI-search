import streamlit as st
from search_manager import AzureSearchManager

def debug_p7():
    st.title("Debug Page 7 Content")
    
    # Load secrets
    try:
        AZURE_SEARCH_ENDPOINT = st.secrets["AZURE_SEARCH_ENDPOINT"]
        AZURE_SEARCH_KEY = st.secrets["AZURE_SEARCH_KEY"]
    except Exception as e:
        st.error(f"Secrets load failed: {e}")
        return

    search_manager = AzureSearchManager(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_KEY)
    
    # Target file and page
    filename = "제4권 도면(청주).pdf"
    page_suffix = "(p.7)"
    
    st.write(f"Searching for {filename} {page_suffix}...")
    print(f"Searching for {filename} {page_suffix}...")
    
    results = search_manager.search(
        "*",
        filter_expr=f"startswith(metadata_storage_name, '{filename}')",
        top=50
    )
    
    found = False
    for doc in results:
        name = doc['metadata_storage_name']
        if page_suffix in name:
            st.success(f"[FOUND] {name}")
            print(f"[FOUND] {name}")
            st.text_area("Content", doc['content'], height=400)
            print("-" * 40)
            print(doc['content'])
            print("-" * 40)
            found = True
            break
            
    if not found:
        st.error(f"[NOT FOUND] Page 7 not found in top 50 results for '{filename}'.")
        print(f"[NOT FOUND] Page 7 not found in top 50 results for '{filename}'.")
        st.write("Found pages:")
        print("Found pages:")
        for doc in results:
            st.write(f"- {doc['metadata_storage_name']}")
            print(f"- {doc['metadata_storage_name']}")

if __name__ == "__main__":
    debug_p7()

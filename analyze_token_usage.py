import streamlit as st
from search_manager import AzureSearchManager
import os

def main():
    st.title("Token Usage Analyzer")
    
    target_file = "PH20-810-EC115-00540_REV.A_PH20 TCA COOLER FOUNDATION PLAN & SECTION 1.pdf"
    
    st.write(f"Analyzing: `{target_file}`")
    
    # Get secrets
    try:
        endpoint = st.secrets["AZURE_SEARCH_ENDPOINT"]
        key = st.secrets["AZURE_SEARCH_KEY"]
        index_name = st.secrets["AZURE_SEARCH_INDEX_NAME"]
    except Exception as e:
        st.error(f"Secrets load failed: {e}")
        return

    search_manager = AzureSearchManager(endpoint, key, index_name)
    
    # Search
    # Note: We use search.ismatch to match the filename in metadata_storage_name
    # We select specific fields to minimize payload
    try:
        results = search_manager.search_client.search(
            search_text="*",
            filter=f"search.ismatch('{target_file}', 'metadata_storage_name')",
            select=["metadata_storage_name", "content", "metadata_storage_path"]
        )
        # Convert iterator to list
        results = list(results)
    except Exception as e:
        st.error(f"Search failed: {e}")
        return
    
    st.success(f"Found {len(results)} chunks.")
    print(f"DEBUG: Found {len(results)} chunks.")
    
    total_chars = 0
    for i, doc in enumerate(results):
        content = doc.get('content', '')
        char_count = len(content)
        total_chars += char_count
        
        print(f"DEBUG: Chunk {i+1} ({char_count} chars): {content[:500]}...")
        
        with st.expander(f"Chunk {i+1}: {doc.get('metadata_storage_name')} ({char_count} chars)"):
            st.code(content[:2000]) # Show first 2000 chars
            if len(content) > 2000:
                st.caption("... (content truncated)")
    
    st.divider()
    st.metric("Total Characters", total_chars)
    st.metric("Estimated Tokens", int(total_chars / 4))
    print(f"DEBUG: Total Characters: {total_chars}")
    print(f"DEBUG: Estimated Tokens: {int(total_chars / 4)}")
    
    if total_chars > 30000:
        st.warning("⚠️ Total content is very large! This explains the token limit error.")
    else:
        st.info("✅ Content size seems reasonable.")

if __name__ == "__main__":
    main()

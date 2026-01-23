import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv
import unicodedata

# Load environment variables
load_dotenv()

# Hardcoded keys for debugging
service_endpoint = "https://ai-search-s1.search.windows.net"
index_name = "pdf-search-index"
key = "3B... (truncated for security, but I will use the full key from previous step)" 
# Wait, I need the full key. I will use the key found in temp_secrets.txt or similar.
# Actually, I don't have the full key in the logs. I saw "LZ5470" but that looks like a password.
# I need to find the actual key.
# Let me check `debug_cloud.py` again, it uses `st.secrets`.
# I will try to read `d:\Projects\ai search with hosting azur\.streamlit\secrets.toml` again, maybe I missed it?
# Ah, I listed `.streamlit` and it only had `config.toml`.
# The user said "Azure 자격 증명 확인됨" in the UI, so the keys must be somewhere.
# `app.py` uses `get_secret` which checks `st.secrets` then `os.environ`.
# Since I am running locally, maybe they are in `.env`?
# The script tries to load `.env`.
# I will check if `.env` exists.

credential = AzureKeyCredential(key)
client = SearchClient(endpoint=service_endpoint,
                      index_name=index_name,
                      credential=credential)

def test_force_inclusion(filenames):
    print(f"--- Testing Force Inclusion for {len(filenames)} files ---")
    
    normalized_files = [unicodedata.normalize('NFC', f) for f in filenames]
    
    for target_file in normalized_files:
        print(f"\nTarget File: {target_file}")
        safe_target = target_file.replace("'", "''")
        
        # Logic from chat_manager.py
        search_query = "P&ID 리스트 비교 분석해서 표로 정리해 주세요" # User query from screenshot
        filter_expr = "project eq 'drawings_analysis'" # Base filter
        
        # Strategy 1: Search for USER QUERY within this specific file
        file_specific_filter = f"({filter_expr}) and startswith(metadata_storage_name, '{safe_target}')"
        
        print(f"  Filter: {file_specific_filter}")
        
        try:
            results = client.search(
                search_text=search_query,
                filter=file_specific_filter,
                top=3
            )
            docs = list(results)
            print(f"  Strategy 1 Results: {len(docs)}")
            for doc in docs:
                print(f"    - {doc['metadata_storage_name']}")
                
            # Strategy 1.5: ALWAYS try searching for "LIST" pages explicitly if the user asks for a list
            if any(keyword in search_query.upper() for keyword in ["LIST", "INDEX", "TABLE", "리스트", "목록", "비교", "COMPARE"]):
                print(f"DEBUG: Trying LIST-specific search for '{target_file}' (Strategy 1.5)...")
                # Combined query for maximum recall of list-type pages
                list_query = "PIPING INSTRUMENT DIAGRAM LIST INDEX TABLE DRAWING LIST 도면 목록 리스트"
                list_results = client.search(
                    search_text=list_query,
                    filter=file_specific_filter,
                    search_mode="any"
                )
                if list_results:
                    print(f"DEBUG: Strategy 1.5 (List Search) success for '{target_file}': {len(list(list_results))} chunks")
                    # In actual code we extend, here we just print
                    docs.extend(list(list_results))

                if not docs:
                     # Strategy 3: Fallback without extension
                    name_no_ext = os.path.splitext(target_file)[0]
                    print(f"  Strategy 2 failed. Trying Strategy 3 (No Ext: {name_no_ext})...")
                    results = client.search(
                        search_text=name_no_ext,
                        filter=filter_expr,
                        search_mode="any",
                        top=3
                    )
                    docs = list(results)
                    print(f"  Strategy 3 Results: {len(docs)}")
                    for doc in docs:
                        print(f"    - {doc['metadata_storage_name']}")
                        
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    # Filenames from screenshot
    files = ['제4권 도면(청주).pdf', '제4권 도면_2018.10.22.pdf']
    test_force_inclusion(files)

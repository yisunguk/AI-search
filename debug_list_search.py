"""
Debug script to test P&ID LIST search in Azure AI Search
"""
import os
from dotenv import load_dotenv
from search_manager import SearchManager

load_dotenv()

# Initialize search manager
search_manager = SearchManager(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    key=os.getenv("AZURE_SEARCH_KEY"),
    index_name=os.getenv("AZURE_SEARCH_INDEX", "drawing-index")
)

target_file = "제4권 도면(청주).pdf"

print("=" * 80)
print(f"Testing P&ID LIST search for: {target_file}")
print("=" * 80)

# Test 1: Search with exact phrase from page 7
print("\n[TEST 1] Exact phrase search: 'PIPING INSTRUMENT DIAGRAM LIST'")
print("-" * 80)
results = search_manager.search(
    "PIPING INSTRUMENT DIAGRAM LIST",
    filter_expr=f"search.ismatch('{target_file}', 'metadata_storage_name')",
    top=50,
    search_mode="any"
)
print(f"Found {len(results)} results")
for i, result in enumerate(results[:10], 1):
    title = result.get('title', 'No title')
    content_preview = result.get('content', '')[:200].replace('\n', ' ')
    print(f"{i}. {title}")
    print(f"   Preview: {content_preview}...")
    print()

# Test 2: Current list_query from chat_manager_v2.py
print("\n[TEST 2] Current list_query from chat_manager_v2.py")
print("-" * 80)
list_query = "PIPING INSTRUMENT DIAGRAM LIST INDEX TABLE DRAWING LIST 도면 목록 리스트 목차 FOR LIST"
results2 = search_manager.search(
    list_query,
    filter_expr=f"search.ismatch('{target_file}', 'metadata_storage_name')",
    top=50,
    search_mode="any"
)
print(f"Found {len(results2)} results")
for i, result in enumerate(results2[:10], 1):
    title = result.get('title', 'No title')
    content_preview = result.get('content', '')[:200].replace('\n', ' ')
    print(f"{i}. {title}")
    print(f"   Preview: {content_preview}...")
    print()

# Test 3: Search for page 7 specifically
print("\n[TEST 3] Does page 7 exist in the index?")
print("-" * 80)
results3 = search_manager.search(
    "*",
    filter_expr=f"search.ismatch('{target_file}', 'metadata_storage_name')",
    top=200,
    search_mode="all"
)
print(f"Total pages indexed for this file: {len(results3)}")
page_7_found = False
for result in results3:
    title = result.get('title', '')
    if 'p.7)' in title or '#page=7' in result.get('metadata_storage_path', ''):
        page_7_found = True
        print(f"\n✓ Page 7 FOUND in index!")
        print(f"  Title: {title}")
        print(f"  Path: {result.get('metadata_storage_path', '')}")
        content = result.get('content', '')
        print(f"  Content length: {len(content)} characters")
        print(f"  Content preview (first 500 chars):")
        print(f"  {content[:500]}")
        print()
        print(f"  Does content contain 'PIPING INSTRUMENT DIAGRAM LIST'? {('PIPING INSTRUMENT DIAGRAM LIST' in content.upper())}")
        print()

if not page_7_found:
    print("\n✗ Page 7 NOT found in index!")
    print("Available pages:")
    for result in results3[:20]:
        print(f"  - {result.get('title', 'Unknown')}")

print("\n" + "=" * 80)

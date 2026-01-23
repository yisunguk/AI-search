import os
import unicodedata
from unittest.mock import MagicMock

# Mock Search Manager
class MockSearchManager:
    def __init__(self):
        self.index_name = "test-index"
    
    def search(self, query, filter_expr=None, **kwargs):
        print(f"MOCK SEARCH: query='{query}', filter='{filter_expr}'")
        
        # Simple logic to simulate filtering by filename in the mock
        def matches_filter(name, expr):
            if not expr: return True
            import re
            # Extract the filename from startswith(metadata_storage_name, '...')
            match = re.search(r"startswith\(metadata_storage_name, '([^']+)'\)", expr)
            if match:
                target = match.group(1)
                return name.startswith(target)
            return True

        # Simulate finding page 39 for the user query
        if query == "필터 엘리먼트 재료 알려 주세요":
            # This query usually returns nothing in our mock unless we force it
            return []
            
        # Simulate finding page 7 for the list query
        if "LIST" in query or "리스트" in query:
            name = "제4권 도면(청주).pdf (p.7)"
            if matches_filter(name, filter_expr):
                return [{"metadata_storage_name": name, "content": "P&ID LIST DATA...", "metadata_storage_path": "path/to/p7"}]
            return []

        # Simulate finding first 10 pages
        if query == "*":
            results = []
            # Mock data for both files
            all_mock_docs = [
                {"metadata_storage_name": f"제4권 도면(청주).pdf (p.{i})", "content": f"Page {i} content", "metadata_storage_path": f"path/to/p{i}"}
                for i in range(1, 11)
            ] + [
                {"metadata_storage_name": f"10-24000-OM-171-200_GENERAL ASSEMBLY DRAWING FOR LAST CHANCE FILTER AB WITH FOUNDATION LOADING (FUEL GAS)_REV.A.pdf (p.{i})", "content": f"GA Page {i} content", "metadata_storage_path": f"path/to/ga{i}"}
                for i in range(1, 11)
            ]
            
            for doc in all_mock_docs:
                if matches_filter(doc['metadata_storage_name'], filter_expr):
                    results.append(doc)
            return results
        return []

# Mock Chat Manager to test retrieval logic
from chat_manager import AzureOpenAIChatManager

def test_retrieval():
    mock_search = MockSearchManager()
    chat_manager = AzureOpenAIChatManager(
        endpoint="http://mock",
        api_key="mock",
        deployment_name="mock",
        api_version="mock",
        search_manager=mock_search,
        storage_connection_string="mock",
        container_name="mock"
    )
    
    # Mock the LLM call to avoid actual API request
    chat_manager.client.chat.completions.create = MagicMock()
    
    user_message = "필터 엘리먼트 재료 알려 주세요"
    # Select only one specific file
    available_files = ["10-24000-OM-171-200_GENERAL ASSEMBLY DRAWING FOR LAST CHANCE FILTER AB WITH FOUNDATION LOADING (FUEL GAS)_REV.A.pdf"]
    
    print(f"\n--- Running Scope Filter Test (Selected: {available_files}) ---")
    response, citations, context = chat_manager.get_chat_response(
        user_message, 
        available_files=available_files,
        filter_expr="project eq 'drawings_analysis'"
    )
    
    print("\n--- Context Summary ---")
    pages_found = []
    for line in context.split('\n'):
        if "[Document:" in line:
            pages_found.append(line)
    
    for p in pages_found:
        print(p)
        
    # Verify ONLY the selected file is in the context
    unselected_found = any("제4권 도면" in p for p in pages_found)
    selected_found = any(available_files[0] in p for p in pages_found)
    
    if selected_found and not unselected_found:
        print("\nSUCCESS: Only selected files were included in the context!")
    elif unselected_found:
        print("\nFAILURE: Unselected files were found in the context!")
    else:
        print("\nFAILURE: Selected file was NOT found in the context.")

if __name__ == "__main__":
    test_retrieval()

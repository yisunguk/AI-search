import os
import unicodedata
from unittest.mock import MagicMock

# Mock Search Manager
class MockSearchManager:
    def __init__(self):
        self.index_name = "test-index"
    
    def search(self, query, filter_expr=None, **kwargs):
        print(f"MOCK SEARCH: query='{query}', filter='{filter_expr}'")
        # Simulate finding page 39 for the user query
        if query == "P&ID 리스트 보여 주세요":
            return [
                {"metadata_storage_name": "제4권 도면(청주).pdf (p.39)", "content": "P&I DIAGRAM (FOR ENV.)", "metadata_storage_path": "path/to/p39"}
            ]
        # Simulate finding page 7 for the list query
        if "LIST" in query or "리스트" in query:
            return [
                {"metadata_storage_name": "제4권 도면(청주).pdf (p.7)", "content": "P&ID LIST DATA...", "metadata_storage_path": "path/to/p7"}
            ]
        # Simulate finding first 10 pages
        if query == "*":
            return [
                {"metadata_storage_name": f"제4권 도면(청주).pdf (p.{i})", "content": f"Page {i} content", "metadata_storage_path": f"path/to/p{i}"}
                for i in range(1, 11)
            ]
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
    
    user_message = "P&ID 리스트 보여 주세요"
    available_files = ["제4권 도면(청주).pdf"]
    
    print("\n--- Running Retrieval Test ---")
    response, citations, context = chat_manager.get_chat_response(
        user_message, 
        available_files=available_files
    )
    
    print("\n--- Context Summary ---")
    pages_found = []
    import re
    for line in context.split('\n'):
        if "[Document:" in line:
            pages_found.append(line)
    
    for p in pages_found:
        print(p)
        
    # Verify page 7 is in the context
    has_p7 = any("Page: 7" in p for p in pages_found)
    if has_p7:
        print("\nSUCCESS: Page 7 was found and included in the context!")
    else:
        print("\nFAILURE: Page 7 was NOT found in the context.")

if __name__ == "__main__":
    test_retrieval()

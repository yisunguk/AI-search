import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

class DocumentIntelligenceManager:
    def __init__(self, endpoint, key):
        self.endpoint = endpoint
        self.key = key
        self.credential = AzureKeyCredential(key)
        self.client = DocumentAnalysisClient(endpoint=endpoint, credential=self.credential)

    def analyze_document(self, document_url):
        """
        Analyze a document from a URL using the prebuilt-layout model.
        Returns the markdown content (if supported) or constructs it.
        """
        try:
            # Use prebuilt-layout to extract text and tables
            poller = self.client.begin_analyze_document_from_url(
                "prebuilt-layout", document_url
            )
            result = poller.result()

            # Construct Markdown-like content
            # Note: Newer versions of API support output_content_format="markdown", 
            # but for compatibility we can construct it or check if 'content' is sufficient.
            # The 'content' field in result is the raw text.
            # We want to preserve table structure.
            
            output = []
            
            # Iterate through pages to reconstruct content with tables
            # This is a simplified reconstruction. For better markdown, we might need more logic
            # or use the markdown output feature if available in the SDK version.
            # Checking if the result has 'content' is basic.
            # Let's try to use the tables to enhance the text.
            
            # Actually, simply appending tables to the end or replacing them might be complex.
            # A robust way is to just append the tables in Markdown format at the end of the text,
            # or rely on the fact that 'content' usually contains the text in reading order.
            # However, 'content' often flattens tables.
            
            # Let's try to build a representation.
            
            # For this implementation, we will return the full 'content' 
            # AND append a markdown representation of tables for better LLM understanding.
            
            full_text = result.content
            
            tables_markdown = []
            for table in result.tables:
                # Build Markdown Table
                # 1. Header
                # We don't strictly know which row is header, but usually the first one.
                # Let's assume row 0 is header if we have to, or just dump the grid.
                
                row_limit = table.row_count
                col_limit = table.column_count
                
                grid = [["" for _ in range(col_limit)] for _ in range(row_limit)]
                
                for cell in table.cells:
                    grid[cell.row_index][cell.column_index] = cell.content
                
                # Convert grid to markdown
                md_table = "\n\n"
                # Header
                md_table += "| " + " | ".join(grid[0]) + " |\n"
                md_table += "| " + " | ".join(["---"] * col_limit) + " |\n"
                # Body
                for row in grid[1:]:
                    md_table += "| " + " | ".join(row) + " |\n"
                
                tables_markdown.append(md_table)
            
            # Combine text and tables (or just append tables if they are not well represented in content)
            # The 'content' usually has the table text line by line. 
            # Appending structured tables helps the LLM.
            
            final_content = full_text + "\n\n" + "\n".join(tables_markdown)
            
            return final_content

        except Exception as e:
            print(f"Error analyzing document: {e}")
            raise e

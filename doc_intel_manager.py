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
        Returns a list of page chunks with metadata.
        
        Returns:
            List of dicts with keys: 'content', 'page_number', 'tables'
        """
        try:
            # Use prebuilt-layout to extract text and tables
            # Explicitly request pages 1-2000 to ensure all pages are processed
            # (Requires Azure Form Recognizer Standard Tier for >2 pages)
            poller = self.client.begin_analyze_document_from_url(
                "prebuilt-layout", document_url, pages="1-2000"
            )
            result = poller.result()

            # Process each page separately
            page_chunks = []
            
            print(f"DEBUG: Document Intelligence found {len(result.pages)} pages.")
            
            for page in result.pages:
                page_num = page.page_number
                
                # Extract text from this page
                # We'll collect all lines on this page
                page_text_lines = []
                if hasattr(page, 'lines'):
                    for line in page.lines:
                        page_text_lines.append(line.content)
                
                page_text = "\n".join(page_text_lines)
                
                # Find tables on this page
                page_tables = []
                for table in result.tables:
                    # Check if table is on this page
                    # Tables have bounding_regions that indicate which page they're on
                    if table.bounding_regions and table.bounding_regions[0].page_number == page_num:
                        # Build Markdown Table
                        row_limit = table.row_count
                        col_limit = table.column_count
                        
                        grid = [["" for _ in range(col_limit)] for _ in range(row_limit)]
                        
                        for cell in table.cells:
                            grid[cell.row_index][cell.column_index] = cell.content
                        
                        # Convert grid to markdown
                        md_table = "\n\n**Table:**\n"
                        # Header
                        if len(grid) > 0:
                            md_table += "| " + " | ".join(grid[0]) + " |\n"
                            md_table += "| " + " | ".join(["---"] * col_limit) + " |\n"
                            # Body
                            for row in grid[1:]:
                                md_table += "| " + " | ".join(row) + " |\n"
                        
                        page_tables.append(md_table)
                
                # Combine page text and tables
                full_page_content = page_text
                if page_tables:
                    full_page_content += "\n\n" + "\n".join(page_tables)
                
                page_chunks.append({
                    'content': full_page_content,
                    'page_number': page_num,
                    'tables_count': len(page_tables)
                })
            
            return page_chunks

        except Exception as e:
            print(f"Error analyzing document: {e}")
            raise e


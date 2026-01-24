import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

class DocumentIntelligenceManager:
    def __init__(self, endpoint, key):
        self.endpoint = endpoint
        self.key = key
        self.credential = AzureKeyCredential(key)
        # Use the latest API version for v4.0 features
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint, 
            credential=self.credential,
            api_version="2024-07-31-preview"
        )

    def analyze_document(self, document_url, page_range=None, high_res=False):
        """
        Analyze a document from a URL using the prebuilt-layout model.
        Returns a list of page chunks with metadata.
        
        Args:
            document_url (str): SAS URL of the document.
            page_range (str): Optional page range (e.g., "1-50").
            high_res (bool): Whether to use highResolution feature.
            
        Returns:
            List of dicts with keys: 'content', 'page_number', 'tables_count'
        """
        try:
            features = []
            if high_res:
                features.append("highResolution")
            
            print(f"DEBUG: Starting DI analysis for {document_url} (Range: {page_range}, HighRes: {high_res})")
            
            # Use dictionary for body to avoid ImportError with AnalyzeDocumentRequest
            # Pass as positional argument to avoid TypeError
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                {"urlSource": document_url},
                pages=page_range,
                output_content_format="markdown",
                features=features
            )
            
            # Set a generous timeout (30 minutes) for large documents/chunks
            result = poller.result(timeout=1800)

            # Process each page separately
            page_chunks = []
            
            # In the new SDK, result.pages is a list of DocumentPage
            print(f"DEBUG: Document Intelligence found {len(result.pages)} pages in this range.")
            
            # Extract global metadata (Key-Value Pairs) - First pass
            # This is useful if the title/drawing no is detected as a global KV pair
            global_title = ""
            global_drawing_no = ""
            
            if result.key_value_pairs:
                for kvp in result.key_value_pairs:
                    if kvp.key and kvp.value:
                        key_text = kvp.key.content.lower()
                        value_text = kvp.value.content
                        
                        # Heuristic for Title
                        if "title" in key_text or "도면명" in key_text:
                            global_title = value_text
                        
                        # Heuristic for Drawing No
                        if "dwg" in key_text or "drawing no" in key_text or "도면번호" in key_text:
                            global_drawing_no = value_text

            for page in result.pages:
                page_num = page.page_number
                
                # Extract text from this page
                page_content = ""
                if page.spans:
                    for span in page.spans:
                        page_content += result.content[span.offset : span.offset + span.length]
                
                # Find tables on this page
                page_tables_count = 0
                page_title = global_title
                page_drawing_no = global_drawing_no
                
                if result.tables:
                    for table in result.tables:
                        if table.bounding_regions and table.bounding_regions[0].page_number == page_num:
                            page_tables_count += 1
                            
                            # Try to extract metadata from tables (Title Block) if not found in KV pairs
                            # or if we want page-specific metadata
                            if not page_title or not page_drawing_no:
                                cells = table.cells
                                for i, cell in enumerate(cells):
                                    content = cell.content.lower()
                                    # Check next cell for value (simple heuristic for horizontal or vertical adjacency)
                                    # This is a simplified approach. A more robust one would check row/col indices.
                                    if i + 1 < len(cells):
                                        next_cell = cells[i+1]
                                        
                                        if not page_title and ("title" in content or "도면명" in content):
                                            page_title = next_cell.content
                                        
                                        if not page_drawing_no and ("dwg" in content or "drawing no" in content or "도면번호" in content):
                                            page_drawing_no = next_cell.content
                
                page_chunks.append({
                    'content': page_content,
                    'page_number': page_num,
                    'tables_count': page_tables_count,
                    '도면명(TITLE)': page_title,       # Key expected by app.py
                    '도면번호(DWG. NO.)': page_drawing_no # Key expected by app.py
                })
            
            return page_chunks

        except Exception as e:
            print(f"Error analyzing document: {e}")
            raise e


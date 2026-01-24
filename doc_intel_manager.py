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
            
            for page in result.pages:
                page_num = page.page_number
                
                # Extract text from this page
                # In markdown mode, result.content contains the full markdown.
                # We might want to slice result.content by page spans if we want per-page markdown.
                # However, for simplicity and better RAG, we can use the page-specific text if available
                # or slice the global content.
                
                # The new SDK provides 'spans' for each page in result.content
                page_content = ""
                if page.spans:
                    for span in page.spans:
                        page_content += result.content[span.offset : span.offset + span.length]
                
                # Find tables on this page
                page_tables_count = 0
                if result.tables:
                    for table in result.tables:
                        if table.bounding_regions and table.bounding_regions[0].page_number == page_num:
                            page_tables_count += 1
                
                page_chunks.append({
                    'content': page_content,
                    'page_number': page_num,
                    'tables_count': page_tables_count
                })
            
            return page_chunks

        except Exception as e:
            print(f"Error analyzing document: {e}")
            raise e


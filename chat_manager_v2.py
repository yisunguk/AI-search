import os
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import urllib.parse

class AzureOpenAIChatManager:
    def __init__(self, endpoint, api_key, deployment_name, api_version, 
                 search_manager, storage_connection_string, container_name):
        """
        Azure OpenAI Chat Manager with Client-Side RAG
        """
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        print("DEBUG: chat_manager_v2.py loaded (Version: V2 Rename Fix)")
        self.deployment_name = deployment_name
        self.search_manager = search_manager
        self.storage_connection_string = storage_connection_string
        self.container_name = container_name
        
        # System prompt optimized for technical accuracy and table interpretation
        self.system_prompt = """You are an expert EPC (Engineering, Procurement, and Construction) project assistant with deep knowledge in interpreting technical drawings and documents.
Use the provided CONTEXT to answer the user's question.

### 1. EPC DRAWING INTERPRETATION RULES
You must interpret the provided text as if you are looking at an engineering diagram. Even if the text is fragmented due to OCR, use the following logic:

- **Single Line Diagram (SLD)**:
    - Look for electrical loads: Motors (M), Heaters (H), Feeders.
    - Identify ratings: kW, HP, A (Amperes), V (Voltage), PH (Phase).
    - Identify Tag Numbers: e.g., 10-P-101M, K-1101M1.
    - **Load List Extraction**: If asked for a "Load List" or "전기부하리스트", scan for these patterns and compile a table with columns: [Tag No, Description, Rating (kW/HP), Voltage, Source/Location].

- **P&ID (Piping & Instrument Diagram)**:
    - Identify Equipment: Pumps (P), Vessels (V/T), Heat Exchangers (E), Compressors (K).
    - Identify Lines: Format like "Size-Service-Number-Spec" (e.g., 6"-FG-001-1A).
    - Identify Valves and Instruments (PT, TT, FT).
    - **Equipment/Line List**: Compile tables based on these identified tags and their nearby specifications.

- **GA (General Arrangement) & Layout**:
    - Interpret dimensions (numbers followed by mm), coordinates (EL, N, E), and spatial relationships.
    - Identify equipment names and their relative positions.

- **BOM/MTO (Bill of Materials)**:
    - Extract material descriptions, quantities, sizes, and weights from tabular text data.

- **Bill of Quantities (BOQ) / 내역서 (CRITICAL)**:
    - These pages contain detailed lists of equipment, materials, and labor costs.
    - Look for sections like "4-2. 내역서", "공종", "명칭", "규격", "수량".
    - **Extraction**: If asked for "내역서 내용", extract the items, their specifications (규격), and quantities.
    - Even if an item doesn't have a Tag No, it is a valid entry if it appears in the BOQ.

- **Drawing List / Index / Table of Contents**:
    - If the user asks for a "List of Drawings", "P&ID List", or "Index", check if there is a dedicated "DRAWING LIST" or "INDEX" page.
    - **PRIORITY**: Use the Master List for the overall structure, but **ALWAYS** cross-reference with individual content pages (like BOQ or SLD) for specific details.
    - Do not ignore detailed content pages just because a Master List exists.

### 2. CRITICAL ANSWER STRATEGY
1. **Answer Strategy**:
    - PRIMARY: Use information from the provided context documents.
    - SECONDARY: Use your general engineering knowledge to bridge gaps (e.g., explaining what a component does or interpreting fragmented specs).
    - ALWAYS clearly distinguish between document-based facts and general knowledge.
    - **IMPORTANT**: Even if specific information is not found, you MUST provide a helpful response. Never leave it empty.

2. **Information Source Labeling**:
    - For facts from documents: Cite with (문서명: p.페이지번호)
    - For general knowledge: Clearly state "일반적인 엔지니어링 지식에 따르면..." or "문서에는 명시되지 않았으나, 일반적으로..."

3. **Table/Data Interpretation**: 
    - Engineering documents often contain tables where keys and values might be visually separated.
    - Look for patterns like "Item: Value" or columns in a table row.
    - Even if the text is fragmented, try to reconstruct the specification from nearby words.

4. **Machine Identifiers**: For Tag Nos like "10-P-101A", copy them EXACTLY.

5. **Numeric Values**: Quote exact numbers with units.

6. **Citations with Page Numbers**: 
    - ALWAYS cite the source document name AND page number.
    - Use the format: (문서명: p.페이지번호)

7. **Multi-Document Comparison (CRITICAL)**:
    - If the context contains multiple documents, you MUST check all of them for the requested information.
    - **Conflicting Info**: If Document A says "Material X" and Document B says "Material Y", you MUST report BOTH.
      - Example: "문서 A에 따르면 재질은 X이나, 문서 B에는 Y로 명시되어 있습니다."
    - **Complementary Info**: Combine information from all documents to provide a complete answer.
    - Do NOT just pick the first answer you find. Compare and contrast.

8. **Formatting**:
    - **Tables**: When the user asks for a list, summary, or comparison, YOU MUST USE MARKDOWN TABLE SYNTAX.
    - Do not use bullet points for structured data if a table is requested.

9. **Language**: Respond in Korean unless asked otherwise.
"""

    def generate_sas_url(self, blob_name):
        """
        Generate a SAS URL for a specific blob
        """
        try:
            blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
            sas_token = generate_blob_sas(
                account_name=blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            return f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{urllib.parse.quote(blob_name)}?{sas_token}"
        except Exception as e:
            print(f"Error generating SAS URL: {e}")
            return "#"

    def _extract_filename_filter(self, user_message, available_files):
        """
        Detect if user mentioned a specific file and return OData filter
        """
        if not available_files:
            return None
            
        # Normalize message
        msg_lower = user_message.lower()
        
        # Check for exact or partial matches
        matched_file = None
        
        # Sort files by length (descending) to match longest filename first
        # e.g. "Drawing_RevA.pdf" vs "Drawing.pdf"
        sorted_files = sorted(available_files, key=len, reverse=True)
        
        for filename in sorted_files:
            # Remove extension for matching if user didn't say it
            name_no_ext = os.path.splitext(filename)[0].lower()
            filename_lower = filename.lower()
            
            if filename_lower in msg_lower or name_no_ext in msg_lower:
                matched_file = filename
                break
        
        if matched_file:
            print(f"DEBUG: Detected filename in query: {matched_file}")
            import unicodedata
            # Ensure NFC normalization for consistent matching with indexed data
            matched_file = unicodedata.normalize('NFC', matched_file)
            # Escape single quotes for OData
            safe_filename = matched_file.replace("'", "''")
            # Escape special characters for Lucene/Simple query syntax
            # Special chars: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
            import re
            escaped_filename = re.sub(r'([+\-&|!(){}\[\]^"~*?:\\])', r'\\\1', safe_filename)
            
            import re
            escaped_filename = re.sub(r'([+\-&|!(){}\[\]^"~*?:\\])', r'\\\1', safe_filename)
            # Use search.ismatch for exact filename matching (more reliable for SearchableFields)
            # We match the phrase because the indexed name might be "filename (p.N)"
            return f"search.ismatch('\"{escaped_filename}\"', 'metadata_storage_name')"
            
        return None

    def _rewrite_query(self, user_message):
        """
        Rewrite user query to be search-friendly using LLM
        """
        import re
        
        # Skip rewriting for page-specific queries (preserve exact page number)
        if re.search(r'(\d+)\s*페이지|p\.?\s*\d+|page\s*\d+', user_message, re.IGNORECASE):
            print("DEBUG: Skipping query rewriting (page-specific query)")
            return user_message
        
        # Skip rewriting for structural/title queries (preserve exact keywords)
        structural_keywords = ['LIST', 'INDEX', 'TABLE', 'DIAGRAM', '목록', '리스트', '다이어그램', '도면']
        if any(kw in user_message.upper() for kw in structural_keywords):
            print("DEBUG: Skipping query rewriting (structural/title query)")
            return user_message
        
        # Otherwise, proceed with LLM-based query rewriting
        try:
            # Simple rule-based first for speed
            # If it's a "Load List" request, add specific keywords
            if "전기부하리스트" in user_message or "Load List" in user_message:
                return f"{user_message} Electrical Load List Motor Heater kW HP Tag No Rating"
            
            # Rule for P&ID List
            if any(x in user_message.upper() for x in ["P&ID", "PID", "피앤아이디"]) and any(x in user_message for x in ["리스트", "목록", "LIST", "INDEX", "비교"]):
                # Expanded to include exact title from user screenshot
                expanded = f"{user_message} PIPING AND INSTRUMENT DIAGRAM LIST DRAWING INDEX TABLE PIPING AND INSTRUMENT DIAGRAM FOR LIST"
                print(f"DEBUG: Query expansion triggered for P&ID List: '{user_message}' -> '{expanded}'")
                return expanded
            
            # Use LLM for complex rewriting
            system_prompt = """You are a search query optimizer for technical documents.
Convert the user's natural language question into a keyword-based search query.
- Remove conversational filler (e.g., "Please find", "Can you tell me").
- Add relevant technical synonyms (e.g., "Load List" -> "Load List Motor Heater kW").
- Keep specific Tag Numbers (e.g., 10-P-101).
- Output ONLY the search query.
"""
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=100,
                temperature=0.1
            )
            rewritten = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"DEBUG: Query rewriting failed: {e}")
            return user_message

    def _clean_content(self, text):
        """
        Clean indexed content by removing XML tags and OCR noise
        """
        if not text:
            return ""
            
        import re
        
        # 1. Remove XML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # 2. Mark intended line breaks (Row/Block endings)
        # We use a placeholder to protect these breaks from the newline stripping step
        LINE_BREAK = "___LB___"
        
        text = re.sub(r'</tr>', LINE_BREAK, text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', LINE_BREAK, text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', LINE_BREAK, text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', LINE_BREAK, text, flags=re.IGNORECASE)
        
        # 3. Replace cell endings with pipe
        text = re.sub(r'</td>', ' | ', text, flags=re.IGNORECASE)
        text = re.sub(r'</th>', ' | ', text, flags=re.IGNORECASE)
        
        # 4. Remove all original newlines (to prevent vertical splitting of cells)
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # 5. Remove remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # 6. Restore intended line breaks
        text = text.replace(LINE_BREAK, '\n')
        
        # 7. Remove specific OCR noise
        text = text.replace("AutoCAD SHX Text", "")
        text = text.replace("%%C", "Ø")
        
        # 8. Collapse whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()

    def _get_direct_context_from_json(self, filename, user_folder=None):
        """
        Fetch analysis JSON directly from Blob Storage to bypass AI Search
        """
        try:
            blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
            container_client = blob_service_client.get_container_client(self.container_name)
            
            # Construct JSON path
            # We assume the JSON is stored in 'json/' folder with the same name + .json
            # Or if it's in a subfolder (user_folder), we check there.
            
            json_blob_name = f"json/{filename}.json"
            if user_folder:
                # Try with user_folder prefix if provided
                json_blob_name = f"{user_folder.strip('/')}/json/{filename}.json"
            
            print(f"DEBUG: Attempting direct JSON fetch: {json_blob_name}")
            blob_client = container_client.get_blob_client(json_blob_name)
            
            if not blob_client.exists():
                # Try fallback without user_folder if it failed
                json_blob_name = f"json/{filename}.json"
                blob_client = container_client.get_blob_client(json_blob_name)
                if not blob_client.exists():
                    print(f"DEBUG: Direct JSON fetch failed - blob not found: {json_blob_name}")
                    return []

            import json
            data = json.loads(blob_client.download_blob().readall())
            
            # Convert JSON chunks to search-result-like objects
            results = []
            for chunk in data:
                # Construct a path that preserves the folder structure for citation
                # If user_folder is provided, use it. Otherwise assume root or handle gracefully.
                # NOTE: Files are stored in 'drawings/' subdirectory
                folder_prefix = f"{user_folder}/drawings/" if user_folder else "drawings/"
                
                results.append({
                    'metadata_storage_name': f"{filename} (p.{chunk.get('page_number', 1)})",
                    'content': chunk.get('content', ''),
                    'title': chunk.get('도면명(TITLE)', ''),  # Extract title for search matching
                    # Use a custom scheme to pass the full path info
                    'metadata_storage_path': f"https://direct_fetch/{folder_prefix}{filename}#page={chunk.get('page_number', 1)}",
                    'project': 'drawings_analysis'
                })
            
            print(f"DEBUG: Direct JSON fetch success: {len(results)} pages for {filename}")
            return results
        except Exception as e:
            print(f"DEBUG: Direct JSON fetch error for {filename}: {e}")
            return []

    def get_chat_response(self, user_message, conversation_history=None, search_mode="any", use_semantic_ranker=False, filter_expr=None, available_files=None, user_folder=None):
        """
        Get chat response with client-side RAG
        """
        try:
            # 0. Extract explicit page number from query
            # This allows users to request specific pages like "7페이지", "p.10", "page 7"
            import re
            explicit_page = None
            page_patterns = [
                r'(\d+)\s*페이지',  # "7페이지"
                r'p\.?\s*(\d+)',  # "p.7" or "p7" or "p. 7"
                r'page\s*(\d+)',  # "page 7"
            ]
            for pattern in page_patterns:
                match = re.search(pattern, user_message, re.IGNORECASE)
                if match:
                    explicit_page = int(match.group(1))
                    print(f"DEBUG: Detected explicit page request: {explicit_page}")
                    break
            
            # 1. Intent Detection & Filtering
            
            # 0. Construct Scope Filter from available_files (if provided, treat as selected files)
            # This ensures we ONLY search within the files the user has selected in the UI
            scope_filter = None
            import unicodedata
            
            if available_files:
                 # Normalize filenames to NFC to match index
                 normalized_files = [unicodedata.normalize('NFC', f) for f in available_files]
                 
                 # Use startswith for exact filename matching (more reliable than search.ismatch for filenames with special chars)
                 # We match the prefix because the indexed name might be "filename (p.N)"
                 conditions = []
                 for f in normalized_files:
                     # Escape single quotes for OData filter
                     safe_f = f.replace("'", "''")
                     import re
                     escaped_f = re.sub(r'([+\-&|!(){}\[\]^"~*?:\\])', r'\\\1', safe_f)
                     # Use search.ismatch for exact filename matching (more reliable for SearchableFields)
                     # CRITICAL FIX: Restore double quotes for exact phrase match (like Debug Tool)
                     conditions.append(f"search.ismatch('\"{escaped_f}\"', 'metadata_storage_name')")
                 
                 if conditions:
                    scope_filter = f"({' or '.join(conditions)})"
                    print(f"DEBUG: Scope filter (Selected files): {len(normalized_files)} files")
                    # print(f"DEBUG: Scope filter string: {scope_filter}")
            else:
                print("DEBUG: No available_files passed (or empty list)")

            # Check if user specified a file (Intent Detection)
            # We still pass available_files to help detection, but the scope_filter enforces the selection
            specific_file_filter = self._extract_filename_filter(user_message, available_files)
            
            # 2. Construct OData Filter
            # Combine base filter, scope filter (selected files), and specific file filter
            filters = []
            if filter_expr:
                filters.append(f"({filter_expr})")
            
            if scope_filter:
                filters.append(f"{scope_filter}")
                
            if specific_file_filter:
                filters.append(f"({specific_file_filter})")
            
            final_filter = " and ".join(filters) if filters else None
            
            print(f"DEBUG: Final OData Filter: {final_filter}")

            # 1.5 DIRECT CONTEXT RETRIEVAL (Bypass Search for Selected Files)
            direct_results = []
            if available_files:
                print(f"DEBUG: Using Direct Context Retrieval for {len(available_files)} files")
                for f in available_files:
                    f_results = self._get_direct_context_from_json(f, user_folder)
                    if f_results:
                        direct_results.extend(f_results)
            
            # If we have direct results, we can either skip search or combine them.
            # For "도면/스펙 비교" tab, we usually want EXACTLY these files.
            # But let's combine to allow for keyword-based ranking within the files.
            
            # 2. TWO-STAGE SEARCH STRATEGY for better precision
            # Stage 1: Exact phrase search (high precision)
            # Stage 2: Expanded query (high recall, only if needed)
            
            print(f"DEBUG: ===== TWO-STAGE SEARCH STARTING =====")
            print(f"DEBUG: User query: '{user_message}'")
            
            search_results = []
            exact_match_count = 0
            
            # Stage 1: Search with user's EXACT query (no expansion)
            # CRITICAL FIX: Disable Semantic Ranker for Stage 1
            # The Debug Tool finds Page 7 as #1 using standard BM25.
            # Semantic Ranker might be down-ranking it due to noise or slight phrasing differences.
            
            # SANITIZE QUERY: Remove "AND", "&", and special chars to avoid syntax issues
            # We want to match "PIPING", "INSTRUMENT", "DIAGRAM", "LIST" regardless of "AND" or "&"
            import re
            
            # CRITICAL: Match app.py logic exactly (No stopword removal)
            # The Debug Tool uses the raw query (sanitized), so we should too.
            sanitized_query = re.sub(r'\bAND\b', ' ', user_message, flags=re.IGNORECASE)
            sanitized_query = re.sub(r'[&+\-|!(){}\[\]^"~*?:\\]', ' ', sanitized_query)
            sanitized_query = " ".join(sanitized_query.split()) # Normalize whitespace
            
            print(f"DEBUG: [Stage 1] Exact phrase search (Semantic Ranker: OFF)...")
            print(f"DEBUG: [Stage 1] Original Query: '{user_message}'")
            print(f"DEBUG: [Stage 1] Sanitized Query: '{sanitized_query}'")
            print(f"DEBUG: [Stage 1] Filter: {final_filter}")
            
            exact_results = self.search_manager.search(
                sanitized_query,  # Use sanitized query
                filter_expr=final_filter,
                use_semantic_ranker=False,  # FORCE FALSE for exact match stage
                search_mode="all",  # FORCE ALL (AND logic) - all terms must be present
                top=50  # Get enough to find exact matches
            )
            
            if exact_results:
                exact_match_count = len(exact_results)
                search_results.extend(exact_results)
                print(f"DEBUG: [Stage 1] Found {exact_match_count} exact match results")
                print(f"DEBUG: [Stage 1] Top 5 results:")
                for i, res in enumerate(exact_results[:5], 1):
                    print(f"  {i}. {res.get('metadata_storage_name', 'Unknown')}")
            else:
                print(f"DEBUG: [Stage 1] No exact matches found")
            
            # Stage 2: Query expansion (only if Stage 1 didn't find enough)
            # CRITICAL: Lower threshold to 3. If we found 3+ exact matches, that's usually enough context.
            # We don't want to dilute high-quality exact matches with loose semantic matches.
            EXACT_MATCH_THRESHOLD = 3
            
            if exact_match_count < EXACT_MATCH_THRESHOLD:
                print(f"DEBUG: [Stage 2] Expanding query (only {exact_match_count} exact matches)...")
                search_query = self._rewrite_query(user_message)
                print(f"DEBUG: [Stage 2] Expanded query: '{search_query}'")
                
                expanded_results = self.search_manager.search(
                    search_query,
                    filter_expr=final_filter,
                    use_semantic_ranker=use_semantic_ranker,
                    search_mode=search_mode
                )
                
                if expanded_results:
                    print(f"DEBUG: [Stage 2] Found {len(expanded_results)} additional results")
                    search_results.extend(expanded_results)
                else:
                    print(f"DEBUG: [Stage 2] No additional results from expansion")
            else:
                print(f"DEBUG: [Stage 2] SKIPPED - exact search found {exact_match_count} results (>= {EXACT_MATCH_THRESHOLD})")
            
            # Deduplication (preserve order = exact matches stay at top)
            seen_ids = set()
            deduped_results = []
            for result in search_results:
                # Create unique ID from name + content snippet
                result_id = (
                    result.get('metadata_storage_name', '') + 
                    str(result.get('content', '')[:50])
                )
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    deduped_results.append(result)
            
            search_results = deduped_results
            print(f"DEBUG: After deduplication: {len(search_results)} unique results")
            print(f"DEBUG: ===== TWO-STAGE SEARCH COMPLETE =====\n")
            
            # Combine with direct results (avoid duplicates)
            if direct_results:
                # Add direct results that aren't already in search_results
                existing_paths = {res.get('metadata_storage_path') for res in search_results}
                added_count = 0
                for res in direct_results:
                    if res.get('metadata_storage_path') not in existing_paths:
                        search_results.append(res)
                        added_count += 1
                print(f"DEBUG: Combined search results with {added_count} direct results. Total: {len(search_results)}")
            
            # Filter by user_folder (Python-side enforcement)
            if user_folder and search_results:
                from urllib.parse import unquote
                original_count = len(search_results)
                filtered_results = [
                    doc for doc in search_results 
                    if user_folder in unquote(doc.get('metadata_storage_path', ''))
                ]
                if filtered_results:
                    search_results = filtered_results
                    print(f"DEBUG: User folder filter: {original_count} -> {len(search_results)}")
                else:
                    print(f"DEBUG: User folder filter would remove all {original_count} results, SKIPPING filter")
            
            # Debug: Check search results
            print(f"DEBUG: Search query='{search_query}', Results count={len(search_results) if search_results else 0}")
            if search_results:
                print(f"DEBUG: Top 10 search results pages:")
                for i, res in enumerate(search_results[:10]):
                    print(f"  {i+1}. {res.get('metadata_storage_name', 'Unknown')}")
            
            # Fallback 1: REMOVED
            # If specific file search fails, we do NOT retry globally.
            pass

            # Fallback 2: REMOVED
            # If search fails, do NOT fetch the whole file. It confuses the LLM.
            pass
                


            # 4. Force Inclusion of Selected Files - REMOVED
            # We rely purely on the search engine ranking.
            pass

            # 5. Page-Aware Context Grouping
            # Group chunks by (Filename, Page)
            grouped_context = {} # Key: (filename, page), Value: list of chunks
            citations_map = {} # Key: (filename, page), Value: citation info
            page_ranks = {} # Key: (filename, page), Value: min_rank (lower is better)
            
            for rank, result in enumerate(search_results):
                filename = result.get('metadata_storage_name', 'Unknown')
                path = result.get('metadata_storage_path', '')
                content = result.get('content', '')
                page_title = result.get('title', '')  # Extract title if available
                
                # Extract page number
                page = None
                import re
                from urllib.parse import unquote
                
                filename = unquote(filename)
                
                # Try to get page from path first
                if path:
                    page_match = re.search(r'#page=(\d+)', path)
                    if page_match:
                        page = int(page_match.group(1))
                
                # If not in path, try to extract from filename (e.g. "file.pdf (p.7)")
                if page is None:
                    page_match = re.search(r'\(p\.(\d+)\)', filename)
                    if page_match:
                        page = int(page_match.group(1))
                        # Clean filename by removing the suffix
                        filename = filename.split(' (p.')[0]
                
                # CRITICAL: If page is still None, this is a "rogue" document (whole file indexed without page splitting).
                # We default to Page 1 to ensure we don't miss data.
                # CRITICAL: If page is still None, this is a "rogue" document (whole file indexed without page splitting).
                # We default to Page 1 to ensure we don't miss data.
                if page is None:
                    print(f"DEBUG: Rogue document found (no page number), defaulting to Page 1: {filename}")
                    page = 1
                
                key = (filename, page)
                
                # Boosting Logic - REMOVED
                # We rely purely on the search engine ranking.
                boost = 0
                
                adjusted_rank = rank + boost
                if key not in page_ranks:
                    page_ranks[key] = adjusted_rank
                else:
                    page_ranks[key] = min(page_ranks[key], adjusted_rank)
                
                if key not in grouped_context:
                    grouped_context[key] = []
                    
                    # Clean up path for citation
                    # Default fallback with correct folder structure
                    if user_folder:
                        blob_path = f"{user_folder}/drawings/{filename}"
                    else:
                        blob_path = f"drawings/{filename}"
                    
                    # Debug path extraction
                    # print(f"DEBUG: Extracting blob path from: {path} (Container: {self.container_name})")
                    
                    if path:
                        # Case 1: Direct Fetch (Custom Scheme)
                        if path.startswith("https://direct_fetch/"):
                            # Format: https://direct_fetch/{user_folder}/{filename}#page=...
                            try:
                                path_without_scheme = path.replace("https://direct_fetch/", "")
                                path_clean = path_without_scheme.split('#')[0]
                                blob_path = unquote(path_clean)
                            except Exception as e:
                                print(f"DEBUG: Error parsing direct fetch path: {e}")
                        
                        # Case 2: Azure Blob URL
                        elif self.container_name in path:
                            try:
                                parts = path.split(f"/{self.container_name}/")
                                if len(parts) > 1:
                                    blob_path = parts[1].split('#')[0]
                                    blob_path = unquote(blob_path)
                            except Exception as e:
                                print(f"DEBUG: Error parsing blob path: {e}")
                        
                        # Case 3: Path is already relative (rare but possible)
                        elif not path.startswith("http"):
                             blob_path = path
                        
                        # CRITICAL FIX: Strip " (p.N)" suffix if present in the path
                        # This happens if the indexer appended it to the path
                        import re
                        blob_path = re.sub(r'\s*\(p\.\d+\)$', '', blob_path)
                        
                    citations_map[key] = {
                        'filepath': blob_path,
                        'url': '',
                        'path': path,
                        'title': page_title,  # Store actual page title, not filename
                        'page': page
                    }
                
                # Avoid duplicate chunks for the same page
                if content not in grouped_context[key]:
                    grouped_context[key].append(content)

            # 5. Construct Context String
            context_parts = []
            citations = []
            
            # Strategy: Simple sort by Rank
            # We rely strictly on the search engine's ranking.
            sorted_keys = sorted(grouped_context.keys(), key=lambda k: page_ranks[k])
            print(f"DEBUG: Context construction - Sorted {len(sorted_keys)} pages by rank")
            
            # Limit total pages
            # Increased to 20 to allow for more context when comparing multiple documents
            # Limit total pages
            # Reduced to 10 to prevent token overflow (finish_reason='length')
            # Limit total pages
            # Increased to 25 to ensure we capture lists/tables that might be ranked lower
            context_limit = 25
            
            # CRITICAL: If user asked for a specific page, prioritize it
            if explicit_page:
                explicit_keys = [k for k in sorted_keys if k[1] == explicit_page]
                other_keys = [k for k in sorted_keys if k[1] != explicit_page]
                sorted_keys = explicit_keys + other_keys
                if explicit_keys:
                    print(f"DEBUG: Prioritized explicit page {explicit_page}, found {len(explicit_keys)} matching pages")
            
            # LIST-related query logic - REMOVED
            # We rely purely on the search engine ranking.
            pass

            
            # DEBUG: Log top 30 pages with their ranks to see if page 7 is included
            print(f"\n{'='*60}")
            print(f"DEBUG: Page Ranking (showing top 30 out of {len(sorted_keys)} total pages)")
            print(f"{'='*60}")
            for idx, key in enumerate(sorted_keys[:30], 1):
                filename, page = key
                rank = page_ranks[key]
                title = citations_map[key].get('title', 'No title')[:60]
                content_preview = grouped_context[key][0][:100].replace('\n', ' ') if grouped_context[key] else ''
                
                # Check if this is a list page
                is_list = False
                for chunk in grouped_context[key]:
                    if any(kw in chunk.upper() for kw in ["DRAWING LIST", "PIPING INSTRUMENT DIAGRAM LIST", "도면 목록"]):
                        is_list = True
                        break
                
                list_marker = "🎯 [LIST PAGE] " if is_list else ""
                selected_marker = "✅ SELECTED " if idx <= context_limit else "❌ SKIPPED  "
                
                print(f"{selected_marker}{idx:2d}. {list_marker}Rank:{rank:4d} | {filename} p.{page} | {title}")
            print(f"{'='*60}\n")
            
            for key in sorted_keys[:context_limit]:
                filename, page = key
                chunks = grouped_context[key]
                # Join chunks for the same page
                page_content = "\n...\n".join(chunks)
                
                # Clean content
                page_content = self._clean_content(page_content)
                
                # Increased limit to 8000 to allow for more context per page
                if len(page_content) > 8000: page_content = page_content[:8000] + "..."
                
                # Include title in context if available
                title = citations_map[key].get('title', '')
                if title:
                    context_parts.append(f"[Document: {filename}, Page: {page}, Title: {title}]\n{page_content}\n")
                else:
                    context_parts.append(f"[Document: {filename}, Page: {page}]\n{page_content}\n")
                citations.append(citations_map[key])
            
            if not context_parts and not conversation_history:
                debug_msg = ""
                if scope_filter:
                    debug_msg = f"\n\n(Debug: Filter applied: {scope_filter})"
                return f"검색된 문서가 없습니다. 다른 검색어를 시도해 보세요.{debug_msg}", [], "", final_filter, []

            context = "\n" + "="*50 + "\n".join(context_parts) if context_parts else "(No new documents found. Use conversation history.)"
            print(f"DEBUG: Context length: {len(context)} chars")
            print(f"DEBUG: Context snippet: {context[:500]}...")
            
            # 6. Build Prompt
            full_prompt = f"""{self.system_prompt}

CONTEXT:
{context}

USER QUESTION:
{user_message}"""
            
            messages = []
            if conversation_history:
                history = [msg for msg in conversation_history if msg['role'] != 'system']
                messages.extend(history)
            messages.append({"role": "user", "content": full_prompt})
            
            # 7. Call LLM
            try:
                print("DEBUG: Calling Azure OpenAI...")
                # Check model name to decide parameter
                # o1 models and gpt-5 preview use max_completion_tokens
                deployment_lower = self.deployment_name.lower()
                
                # Check for high-capacity models (o1, gpt-5, 5.2, etc.)
                if any(x in deployment_lower for x in ["o1", "gpt-5", "5.2"]):
                    print(f"DEBUG: Using high-capacity model: {self.deployment_name}")
                    response = self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=messages,
                        max_completion_tokens=32000, # Increased limit for Pro models
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=messages,
                        max_tokens=4096, # Increased standard limit
                        temperature=0.3
                    )
                
                response_text = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                if finish_reason == "content_filter":
                    print("DEBUG: Content filter triggered")
                    response_text = "⚠️ Azure OpenAI 콘텐츠 정책에 의해 답변이 차단되었습니다. (Content Filter Triggered)\n\n질문을 변경하거나 문서에 민감한 내용이 있는지 확인해주세요."
                
                elif finish_reason == "length":
                    print("DEBUG: Token limit reached (length)")
                    # CRITICAL FIX: Do not hide the partial response!
                    if response_text:
                        response_text += "\n\n---\n⚠️ **답변이 길어서 중단되었습니다.** (Token Limit Reached)\n모델의 출력 한도에 도달했습니다. 이어서 답변을 원하시면 '계속'이라고 입력해주세요."
                    else:
                        response_text = "⚠️ 답변을 생성하는 도중 한도에 도달했으나, 생성된 텍스트가 없습니다."

                elif not response_text or not response_text.strip():
                    print(f"DEBUG: Empty response. Finish reason: {finish_reason}")
                    response_text = f"죄송합니다. 답변을 생성하지 못했습니다. (응답 없음, 사유: {finish_reason})"
            except Exception as e:
                print(f"DEBUG: LLM call failed: {e}")
                return f"LLM 호출 중 오류가 발생했습니다: {str(e)}\n\n(컨텍스트 길이: {len(context)} 자)", citations, context, final_filter, search_results

            # DEBUG: Log citations to see what the LLM actually used
            print(f"\n{'='*60}")
            print(f"DEBUG: LLM Citations Analysis")
            print(f"{'='*60}")
            cited_pages = []
            import re
            # Find patterns like (Filename: p.N)
            matches = re.findall(r'\(([^):]+):\s*p\.\s*(\d+)\)', response_text)
            for fname, pnum in matches:
                cited_pages.append(int(pnum))
            
            print(f"DEBUG: LLM cited pages: {cited_pages}")
            
            # Check if Page 82 was in context but NOT cited
            context_pages = [k[1] for k in sorted_keys[:context_limit]]
            for p in context_pages:
                if p == 82 and 82 not in cited_pages:
                    print(f"DEBUG: ⚠️ WARNING: Page 82 was in CONTEXT but NOT CITED by LLM.")
                elif p == 82 and 82 in cited_pages:
                    print(f"DEBUG: ✅ SUCCESS: Page 82 was in CONTEXT and CITED by LLM.")
            print(f"{'='*60}\n")

            # 8. Post-process: Linkify Citations in Text
            response_text = self._linkify_citations(response_text, citations)

            # DEBUG: Add context visualization to the answer (hidden in expander)
            # This helps users/admins verify if the correct pages were used
            debug_info = "\n\n<details><summary>🛠️ <b>Debug: Selected Context Pages</b></summary>\n\n"
            debug_info += "| Rank | Page | Score/Priority | Source |\n"
            debug_info += "|---|---|---|---|\n"
            
            for idx, key in enumerate(sorted_keys[:context_limit], 1):
                filename, page = key
                rank = page_ranks.get(key, 999)
                
                # Check if it was a list page
                is_list = False
                if key in grouped_context:
                    for chunk in grouped_context[key]:
                        if any(kw in chunk.upper() for kw in ["DRAWING LIST", "PIPING INSTRUMENT DIAGRAM LIST", "도면 목록"]):
                            is_list = True
                            break
                
                marker = "🎯 LIST" if is_list else ""
                if idx == 1: marker += " (Top)"
                
                debug_info += f"| {idx} | {filename} (p.{page}) | {rank} {marker} | Context |\n"
            
            debug_info += "\n</details>"
            
            return response_text + debug_info, citations, context, final_filter, search_results

        except Exception as e:
            print(f"Error in get_chat_response: {e}")
            return f"오류가 발생했습니다: {str(e)}", [], "", None, []

    def _linkify_citations(self, text, citations):
        """
        Convert text citations like '(Filename: p.1)' into Markdown links.
        """
        if not text or not citations:
            return text
            
        import re
        
        # Helper to find citation
        def find_citation(fname_text, page_text):
            try:
                page_num = int(page_text)
                fname_text_lower = fname_text.lower().strip()
                
                for cit in citations:
                    # Check page match first
                    if cit.get('page') != page_num:
                        continue
                        
                    # Check filename match
                    # cit['filepath'] is usually "drawings/filename.pdf" or "filename.pdf"
                    filepath = cit.get('filepath', '')
                    basename = filepath.split('/')[-1].lower()
                    
                    # 1. Exact basename match
                    if fname_text_lower == basename:
                        return cit
                    
                    # 2. Match without extension
                    if fname_text_lower == os.path.splitext(basename)[0]:
                        return cit
                        
                    # 3. Prefix match (for truncated text like "Fuel Gas Coalescing...")
                    # Remove "..." and "…" if present
                    clean_fname = fname_text_lower.replace("...", "").replace("…", "").strip()
                    if len(clean_fname) > 5 and basename.startswith(clean_fname):
                        return cit
                        
                    # 4. Title match (if LLM used title)
                    title = cit.get('title', '').lower()
                    if title and (fname_text_lower in title or title in fname_text_lower):
                        return cit
                        
            except:
                pass
            return None

        # Regex to find patterns like (Filename: p.1)
        # We look for: ( [anything not )] : p. [digits] )
        # Added handling for spaces after p. and unicode ellipsis
        pattern = r'\(([^):]+):\s*p\.\s*(\d+)\)'
        
        def replace_match(match):
            full_match = match.group(0)
            fname_text = match.group(1)
            page_text = match.group(2)
            
            cit = find_citation(fname_text, page_text)
            if cit:
                # Generate SAS URL
                filepath = cit.get('filepath')
                if filepath:
                    url = self.generate_blob_sas(filepath)
                    if url:
                        # Append page fragment
                        url += f"#page={page_text}"
                        # Use a shorter link text to prevent table layout breakage
                        # Instead of replacing the whole (Filename: p.1), we just link the "p.1" part or similar?
                        # User wants the citation to be clickable.
                        # Let's keep the full text but ensure the URL is valid so Markdown renders it.
                        # If Markdown fails to render, it shows the raw URL which is huge.
                        # The issue in the screenshot was likely the URL not being quoted properly, breaking the Markdown syntax if it contained spaces or parens.
                        return f"[{full_match}]({url})"
            
            return full_match

        return re.sub(pattern, replace_match, text)

    def generate_blob_sas(self, blob_name):
        """
        Generate SAS URL for blob document
        """
        try:
            blob_service_client = BlobServiceClient.from_connection_string(
                self.storage_connection_string
            )
            
            sas_token = generate_blob_sas(
                account_name=blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1),
                content_disposition="inline",
                content_type="application/pdf"
            )
            
            # CRITICAL FIX: URL encode the blob name to handle Korean characters and spaces
            # The blob_name passed to generate_blob_sas must be the raw name.
            # The blob_name in the URL must be encoded.
            encoded_blob_name = urllib.parse.quote(blob_name)
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{encoded_blob_name}?{sas_token}"
            return blob_url
        except Exception as e:
            print(f"Error generating SAS URL: {e}")
            return None

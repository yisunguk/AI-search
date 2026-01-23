import os
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

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
        print("DEBUG: chat_manager.py loaded (Version: Startswith Fix v2)")
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
        try:
            # Simple rule-based first for speed
            # If it's a "Load List" request, add specific keywords
            if "전기부하리스트" in user_message or "Load List" in user_message:
                return f"{user_message} Electrical Load List Motor Heater kW HP Tag No Rating"
            
            # Rule for P&ID List
            if any(x in user_message.upper() for x in ["P&ID", "PID", "피앤아이디"]) and any(x in user_message for x in ["리스트", "목록", "LIST", "INDEX", "비교"]):
                expanded = f"{user_message} PIPING AND INSTRUMENT DIAGRAM LIST DRAWING INDEX TABLE"
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
            print(f"DEBUG: Rewritten query: '{user_message}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            print(f"DEBUG: Query rewriting failed: {e}")
            return user_message

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
                results.append({
                    'metadata_storage_name': f"{filename} (p.{chunk.get('page_number', 1)})",
                    'content': chunk.get('content', ''),
                    'metadata_storage_path': f"https://direct_fetch/{filename}#page={chunk.get('page_number', 1)}",
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
            
            # 2. Query Rewriting
            search_query = self._rewrite_query(user_message)
            
            # 3. Search
            search_results = self.search_manager.search(
                search_query, 
                filter_expr=final_filter,
                use_semantic_ranker=use_semantic_ranker,
                search_mode=search_mode
            )
            
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
            
            # Fallback: If specific file search failed, try without file filter (maybe user got name wrong)
            if not search_results and specific_file_filter:
                print("DEBUG: Specific file search failed, retrying globally...")
                # Only retry if scope_filter allows it (i.e., search within selected files but ignore specific mention)
                # If scope_filter is set, we must respect it.
                retry_filter = filter_expr
                if scope_filter:
                    if retry_filter:
                        retry_filter = f"({retry_filter}) and {scope_filter}"
                    else:
                        retry_filter = scope_filter
                
                search_results = self.search_manager.search(
                    search_query, 
                    filter_expr=retry_filter, 
                    use_semantic_ranker=use_semantic_ranker,
                    search_mode=search_mode
                )
                
                # Filter by user_folder
                if user_folder and search_results:
                    from urllib.parse import unquote
                    original_count = len(search_results)
                    filtered_results = [
                        doc for doc in search_results 
                        if user_folder in unquote(doc.get('metadata_storage_path', ''))
                    ]
                    if filtered_results:
                        search_results = filtered_results
                        print(f"DEBUG: User folder filter (fallback 1): {original_count} -> {len(search_results)}")
                    else:
                        print(f"DEBUG: User folder filter would remove all {original_count} results, SKIPPING filter")

            # Fallback 2: If user selected files (scope_filter) but keywords didn't match,
            # fetch the content of the selected files directly.
            if not search_results and scope_filter:
                print("DEBUG: No results with query but files selected. Retrying with '*'...")
                
                # Reconstruct filter to ensure we only search within scope
                fallback_filter = filter_expr
                if fallback_filter:
                    fallback_filter = f"({fallback_filter}) and {scope_filter}"
                else:
                    fallback_filter = scope_filter
                    
                search_results = self.search_manager.search(
                    "*", 
                    filter_expr=fallback_filter, 
                    use_semantic_ranker=use_semantic_ranker,
                    search_mode=search_mode
                )
                
                # Filter by user_folder
                if user_folder and search_results:
                    from urllib.parse import unquote
                    original_count = len(search_results)
                    filtered_results = [
                        doc for doc in search_results 
                        if user_folder in unquote(doc.get('metadata_storage_path', ''))
                    ]
                    if filtered_results:
                        search_results = filtered_results
                        print(f"DEBUG: User folder filter (fallback 2): {original_count} -> {len(search_results)}")
                    else:
                        print(f"DEBUG: User folder filter would remove all {original_count} results, SKIPPING filter")

            # 4. Force Inclusion of Selected Files (CRITICAL for Comparison)
            # If user selected files but they didn't appear in the top results, force fetch them.
            if available_files:
                # Normalize available_files again just to be safe (though we did it above, let's use the local var)
                normalized_files = [unicodedata.normalize('NFC', f) for f in available_files]
                
                # Get set of filenames already in results
                found_filenames = set()
                for res in search_results:
                    fname = res.get('metadata_storage_name', '')
                    # Normalize found filenames too
                    found_filenames.add(unicodedata.normalize('NFC', fname))
                
                # Check for missing files
                for target_file in normalized_files:
                    # We check if the target file is "represented" in the results
                    is_found = False
                    for found in found_filenames:
                        if found.startswith(target_file):
                            is_found = True
                            break
                    
                    # CRITICAL: Even if found, we ALWAYS fetch the first few pages (Index/Summary) 
                    # and specifically search for LIST pages if the query suggests it.
                    # This ensures we don't miss the P&ID List just because the title page was found.
                    print(f"DEBUG: Essential context fetch for '{target_file}' (is_found={is_found})")
                    safe_target = target_file.replace("'", "''")
                    
                    import re
                    escaped_target = re.sub(r'([+\-&|!(){}\[\]^"~*?:\\])', r'\\\1', safe_target)
                    # Use search.ismatch for exact filename matching (more reliable for SearchableFields)
                    file_specific_filter = f"search.ismatch('\"{escaped_target}\"', 'metadata_storage_name')"
                    if final_filter:
                        file_specific_filter = f"({final_filter}) and ({file_specific_filter})"
                    
                    # 1. Fetch first 10 pages (likely to contain Index/TOC)
                    print(f"DEBUG: Fetching first 10 pages for '{target_file}'...")
                    index_pages = self.search_manager.search(
                        "*",
                        filter_expr=file_specific_filter,
                        top=10,
                        search_mode="all"
                    )
                    if index_pages:
                        search_results.extend(index_pages)
                        print(f"DEBUG: Added {len(index_pages)} initial pages for '{target_file}'")

                    # 2. If query is list-related, specifically search for LIST pages
                    if any(keyword in search_query.upper() for keyword in ["LIST", "INDEX", "TABLE", "리스트", "목록", "비교", "COMPARE"]):
                        print(f"DEBUG: List-specific search for '{target_file}'...")
                        list_query = "PIPING INSTRUMENT DIAGRAM LIST INDEX TABLE DRAWING LIST 도면 목록 리스트"
                        list_results = self.search_manager.search(
                            list_query,
                            filter_expr=file_specific_filter,
                            top=10,
                            search_mode="any"
                        )
                        if list_results:
                            search_results.extend(list_results)
                            print(f"DEBUG: Added {len(list_results)} list-specific pages for '{target_file}'")

            # 5. Page-Aware Context Grouping
            # Group chunks by (Filename, Page)
            grouped_context = {} # Key: (filename, page), Value: list of chunks
            citations_map = {} # Key: (filename, page), Value: citation info
            page_ranks = {} # Key: (filename, page), Value: min_rank (lower is better)
            
            for rank, result in enumerate(search_results):
                filename = result.get('metadata_storage_name', 'Unknown')
                path = result.get('metadata_storage_path', '')
                content = result.get('content', '')
                
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
                if page is None:
                    print(f"DEBUG: Rogue document found (no page number), defaulting to Page 1: {filename}")
                    page = 1
                
                key = (filename, page)
                
                # Track the best rank for this page
                # BOOST ranking for pages with "LIST", "INDEX", "TABLE" keywords
                boost = 0
                content_upper = content.upper()
                if any(keyword in content_upper for keyword in ["PIPING AND INSTRUMENT DIAGRAM", "P&I DIAGRAM", "P & I DIAGRAM"]):
                    if any(list_keyword in content_upper for list_keyword in ["LIST", "INDEX", "TABLE OF CONTENTS"]):
                        boost = -100  # Strong boost for list pages
                        print(f"DEBUG: BOOSTING page {key} (contains LIST/INDEX)")
                
                adjusted_rank = rank + boost
                if key not in page_ranks:
                    page_ranks[key] = adjusted_rank
                else:
                    page_ranks[key] = min(page_ranks[key], adjusted_rank)
                
                if key not in grouped_context:
                    grouped_context[key] = []
                    
                    # Clean up path for citation
                    blob_path = filename
                    if path and self.container_name in path:
                        try:
                            parts = path.split(f"/{self.container_name}/")
                            if len(parts) > 1:
                                blob_path = parts[1].split('#')[0]
                                blob_path = unquote(blob_path)
                        except: pass
                        
                    citations_map[key] = {
                        'filepath': blob_path,
                        'url': '',
                        'path': path,
                        'title': filename,
                        'page': page
                    }
                
                # Avoid duplicate chunks for the same page
                if content not in grouped_context[key]:
                    grouped_context[key].append(content)

            # 5. Construct Context String
            context_parts = []
            citations = []
            
            # Strategy: Round Robin selection by Document to ensure diversity
            # We want to avoid filling the context with just one document if multiple are relevant
            
            # Group keys by filename
            docs_map = {}
            for key in grouped_context:
                fname = key[0]
                if fname not in docs_map:
                    docs_map[fname] = []
                docs_map[fname].append(key)
            
            # Sort pages within each doc by RELEVANCE (min_rank) instead of page number
            # This ensures we pick the most relevant pages first
            for fname in docs_map:
                docs_map[fname].sort(key=lambda x: page_ranks[x])
            
            # Interleave keys: Doc1_BestPage, Doc2_BestPage, Doc3_BestPage, Doc1_2ndBest, ...
            sorted_keys = []
            max_pages_per_doc = max(len(p) for p in docs_map.values()) if docs_map else 0
            
            sorted_filenames = sorted(docs_map.keys())
            print(f"DEBUG: Context construction - {len(sorted_filenames)} documents, max {max_pages_per_doc} pages each")
            
            for i in range(max_pages_per_doc):
                for fname in sorted_filenames:
                    if i < len(docs_map[fname]):
                        sorted_keys.append(docs_map[fname][i])
            
            # Limit total pages
            # Increased to 20 to allow for more context when comparing multiple documents
            # Limit total pages
            # Reduced to 10 to prevent token overflow (finish_reason='length')
            # Limit total pages
            # Increased to 25 to ensure we capture lists/tables that might be ranked lower
            context_limit = 25
            
            for key in sorted_keys[:context_limit]:
                filename, page = key
                chunks = grouped_context[key]
                # Join chunks for the same page
                page_content = "\n...\n".join(chunks)
                
                # Clean content
                page_content = page_content.replace("AutoCAD SHX Text", "").replace("%%C", "Ø")
                # Increased limit to 8000 to allow for more context per page
                if len(page_content) > 8000: page_content = page_content[:8000] + "..."
                
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

            return response_text, citations, context, final_filter, search_results

        except Exception as e:
            print(f"Error in get_chat_response: {e}")
            return f"오류가 발생했습니다: {str(e)}", [], "", None, []
    
    def generate_sas_url(self, blob_name):
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
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
            return blob_url
        except Exception as e:
            print(f"Error generating SAS URL: {e}")
            return None

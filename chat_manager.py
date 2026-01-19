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
            # Escape single quotes for OData
            safe_filename = matched_file.replace("'", "''")
            # Filter by metadata_storage_name using startswith because indexed name has (p.N) suffix
            return f"startswith(metadata_storage_name, '{safe_filename}')"
            
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

    def get_chat_response(self, user_message, conversation_history=None, search_mode="any", use_semantic_ranker=False, filter_expr=None, available_files=None):
        """
        Get chat response with client-side RAG
        """
        try:
            # 1. Intent Detection & Filtering
            
            # 0. Construct Scope Filter from available_files (if provided, treat as selected files)
            # This ensures we ONLY search within the files the user has selected in the UI
            scope_filter = None
            if available_files:
                 # Use search.ismatch for more robust matching (handles tokenization and minor differences)
                 # We use a phrase search ("...") to ensure the filename sequence matches
                 # search.ismatch('"{filename}"', 'metadata_storage_name')
                 conditions = []
                 for f in available_files:
                     # Escape double quotes for the search query
                     safe_f = f.replace('"', '\\"')
                     conditions.append(f"search.ismatch('\"{safe_f}\"', 'metadata_storage_name')")
                 
                 if conditions:
                    scope_filter = f"({' or '.join(conditions)})"
                    print(f"DEBUG: Scope filter (Selected files): {len(available_files)} files")
                    print(f"DEBUG: Scope filter string: {scope_filter}")
            else:
                print("DEBUG: No available_files passed (or empty list)")

            # Check if user specified a file (Intent Detection)
            # We still pass available_files to help detection, but the scope_filter enforces the selection
            specific_file_filter = self._extract_filename_filter(user_message, available_files)
            
            final_filter = filter_expr
            
            # Apply Scope Filter (Selected Documents)
            if scope_filter:
                if final_filter:
                    final_filter = f"({final_filter}) and {scope_filter}"
                else:
                    final_filter = scope_filter
            
            # Apply Specific File Filter (User Mentioned)
            if specific_file_filter:
                if final_filter:
                    final_filter = f"({final_filter}) and ({specific_file_filter})"
                else:
                    final_filter = specific_file_filter
                print(f"DEBUG: Applied specific file filter: {specific_file_filter}")
            
            print(f"DEBUG: Final OData Filter: {final_filter}")

            # 2. Query Rewriting
            search_query = self._rewrite_query(user_message)
            
            # 3. Search
            search_results = self.search_manager.search(
                search_query, 
                filter_expr=final_filter,
                use_semantic_ranker=use_semantic_ranker,
                search_mode=search_mode
            )
            
            # Debug: Check search results
            print(f"DEBUG: Search query='{search_query}', Results count={len(search_results) if search_results else 0}")
            
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

            # 4. Page-Aware Context Grouping
            # Group chunks by (Filename, Page)
            grouped_context = {} # Key: (filename, page), Value: list of chunks
            citations_map = {} # Key: (filename, page), Value: citation info
            page_ranks = {} # Key: (filename, page), Value: min_rank (lower is better)
            
            for rank, result in enumerate(search_results):
                filename = result.get('metadata_storage_name', 'Unknown')
                path = result.get('metadata_storage_path', '')
                content = result.get('content', '')
                
                # Extract page number
                page = 1
                import re
                from urllib.parse import unquote
                
                filename = unquote(filename)
                
                # Try to get page from path
                if path:
                    page_match = re.search(r'#page=(\d+)', path)
                    if page_match:
                        page = int(page_match.group(1))
                
                key = (filename, page)
                
                # Track the best rank for this page
                if key not in page_ranks:
                    page_ranks[key] = rank
                else:
                    page_ranks[key] = min(page_ranks[key], rank)
                
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
            
            for i in range(max_pages_per_doc):
                for fname in sorted_filenames:
                    if i < len(docs_map[fname]):
                        sorted_keys.append(docs_map[fname][i])
            
            # Limit total pages
            # Increased to 20 to allow for more context when comparing multiple documents
            context_limit = 20
            
            for key in sorted_keys[:context_limit]:
                filename, page = key
                chunks = grouped_context[key]
                # Join chunks for the same page
                page_content = "\n...\n".join(chunks)
                
                # Clean content
                page_content = page_content.replace("AutoCAD SHX Text", "").replace("%%C", "Ø")
                if len(page_content) > 3000: page_content = page_content[:3000] + "..."
                
                context_parts.append(f"[Document: {filename}, Page: {page}]\n{page_content}\n")
                citations.append(citations_map[key])
            
            if not context_parts and not conversation_history:
                debug_msg = ""
                if scope_filter:
                    debug_msg = f"\n\n(Debug: Filter applied: {scope_filter})"
                return f"검색된 문서가 없습니다. 다른 검색어를 시도해 보세요.{debug_msg}", []

            context = "\n" + "="*50 + "\n".join(context_parts) if context_parts else "(No new documents found. Use conversation history.)"
            
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
                if "o1" in deployment_lower or "gpt-5" in deployment_lower:
                    response = self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=messages,
                        max_completion_tokens=5000, # o1/gpt-5 models support larger output
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=messages,
                        max_tokens=2500,
                        temperature=0.3
                    )
                response_text = response.choices[0].message.content
            except Exception as e:
                print(f"DEBUG: LLM call failed: {e}")
                # Return the actual error to the user for debugging
                return f"LLM 호출 중 오류가 발생했습니다: {str(e)}\n\n(컨텍스트 길이: {len(context)} 자)", citations

            if not response_text or not response_text.strip():
                response_text = "죄송합니다. 문서 내용을 분석했지만 답변을 생성하지 못했습니다. (응답 없음)"

            return response_text, citations

        except Exception as e:
            print(f"Error in get_chat_response: {e}")
            return f"오류가 발생했습니다: {str(e)}", []
    
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

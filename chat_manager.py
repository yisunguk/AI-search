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
        self.system_prompt = """You are a technical document assistant for EPC engineering projects.
Use the provided CONTEXT to answer the user's question.

CRITICAL RULES:
1. **Answer Strategy**:
   - PRIMARY: Use information from the provided context documents when available.
   - SECONDARY: If the question requires comparison, analysis, or general engineering knowledge not fully covered in the documents, you MAY use your general knowledge.
   - ALWAYS clearly distinguish between document-based facts and general knowledge.
   - **IMPORTANT**: Even if specific information is not found in the documents, you MUST provide a helpful response. For example:
     * "제공된 문서에서 foundation loading data에 대한 정보를 찾을 수 없습니다."
     * "REV.A 문서에는 foundation loading data가 있지만, 다른 문서에는 해당 정보가 없습니다."
   - NEVER leave the response empty. Always provide context about what you found or didn't find.

2. **Information Source Labeling**:
   - For facts from documents: Cite with (문서명: p.페이지번호)
   - For general knowledge: Clearly state "일반적인 엔지니어링 지식에 따르면..." or "문서에는 명시되지 않았으나, 일반적으로..."
   - Example: "REV.A와 REV.B를 비교하면... (문서 기반 차이점). 일반적으로 이러한 변경은 성능 개선을 위한 것입니다 (일반 지식)."

3. **Table/Data Interpretation**: 
   - Engineering documents often contain tables where keys and values might be visually separated.
   - Look for patterns like "Item: Value" or columns in a table row.
   - If you see "FILTER ELEMENT" and "POLYESTER" near each other or aligned, infer the relationship.
   - Even if the text is fragmented, try to reconstruct the specification from nearby words.

4. **Machine Identifiers**: For Tag Nos like "10-P-101A", copy them EXACTLY.

5. **Numeric Values**: Quote exact numbers with units.

6. **Citations with Page Numbers**: 
   - ALWAYS cite the source document name AND page number when providing specific facts from documents.
   - Use the format: (문서명: p.페이지번호)
   - Example: "FILTER ELEMENT는 POLYESTER입니다. (Fuel Gas Coalescing Filter for Gas Turbine(filter).pdf: p.3)"
   - Each document in the context includes its page number - use it in your citation.

7. **Comparison and Analysis**:
   - When asked to compare documents (e.g., REV.A vs REV.B), extract specific differences from the documents.
   - You can provide engineering insights or interpretations using general knowledge, but label them clearly.
   - Example: "REV.A에서는 X였으나 REV.B에서는 Y로 변경되었습니다 (문서 기반). 이는 일반적으로 Z를 개선하기 위한 것입니다 (일반 지식)."

8. **Language**: Respond in Korean unless asked otherwise.
"""

    def get_chat_response(self, user_message, conversation_history=None, search_mode="any", use_semantic_ranker=False, filter_expr=None):
        """
        Get chat response with client-side RAG
        
        Args:
            filter_expr: OData filter expression (e.g., "project eq 'drawings_analysis'")
        
        Returns:
            response_text: AI response
            citations: List of citation objects with file info
        """
        try:
            # 1. Extract keywords from user question for better search
            # Remove common question words that don't help with search
            import re
            
            # Remove question patterns
            search_query = user_message
            question_patterns = [
                r'는\s*두\s*문서간?\s*차이점?이?\s*있나요?\?*',
                r'를?\s*비교해?\s*주세요\.?',
                r'를?\s*검토해?\s*주세요\.?',
                r'이?\s*뭐?야?\?*',
                r'이?\s*무엇인가요?\?*',
                r'에\s*대해\s*질문하세요\.?',
                r'에\s*대해\s*알려주세요\.?',
                r'차이점?을?\s*알려주세요\.?'
            ]
            
            for pattern in question_patterns:
                search_query = re.sub(pattern, '', search_query, flags=re.IGNORECASE)
            
            # Clean up extra spaces
            search_query = ' '.join(search_query.split()).strip()
            
            # If the query is too short after cleaning, use original
            if len(search_query) < 3:
                search_query = user_message
            
            # 2. Search for relevant documents using Azure AI Search
            # Use cleaned search query
            search_results = self.search_manager.search(
                search_query, 
                filter_expr=filter_expr,
                use_semantic_ranker=use_semantic_ranker,
                search_mode=search_mode
            )
            
            # Debug: Check search results
            print(f"DEBUG: Search query='{search_query}', Results count={len(search_results) if search_results else 0}")
            
            # 2. Construct context from search results
            context_parts = []
            citations = []
            
            # Detect if this is a comparison/analysis question
            comparison_keywords = ['비교', '검토', '차이', '다른', '변경', 'compare', 'review', 'difference', 'change', 'vs', 'versus']
            is_comparison = any(keyword in user_message.lower() for keyword in comparison_keywords)
            
            # For comparison questions, if no good search results, try broader search
            # This ensures we get both revision documents even if the keyword is only in one
            if is_comparison and (not search_results or len(search_results) < 2):
                # Try a wildcard search on drawings to get all documents
                search_results = self.search_manager.search(
                    "*",  # Wildcard to get all documents
                    filter_expr=filter_expr,
                    use_semantic_ranker=False,
                    search_mode="any"
                )
            
            # Increase context limit for comparison questions to capture multiple documents/revisions
            context_limit = 20 if is_comparison else 10
            
            for i, result in enumerate(search_results, 1):
                if i > context_limit: break
                
                filename = result.get('metadata_storage_name', 'Unknown')
                content = result.get('content', '')
                path = result.get('metadata_storage_path', '') # Full URL
                
                # Decode filename as well
                from urllib.parse import unquote
                filename = unquote(filename)
                
                # Extract relative path from URL (handle folders)
                # Format: https://account.blob.core.windows.net/container/folder/file.pdf#page=N
                blob_path = filename # Default fallback
                if path and self.container_name in path:
                    try:
                        # Split by container name and take the part after it
                        parts = path.split(f"/{self.container_name}/")
                        if len(parts) > 1:
                            blob_path = parts[1]
                            # Remove #page fragment if present
                            if '#page=' in blob_path:
                                blob_path = blob_path.split('#page=')[0]
                            # Decode URL encoding if needed (e.g. %20 -> space)
                            blob_path = unquote(blob_path)
                    except:
                        pass

                # Clean OCR noise (AutoCAD artifacts)
                content = content.replace("AutoCAD SHX Text", "")
                content = content.replace("%%C", "Ø") # CAD diameter symbol
                
                # Skip documents with no content
                if not content or len(content.strip()) == 0:
                    print(f"Warning: Skipping document {filename} - no content")
                    continue
                
                # Truncate content to fit context window (increased for o1 models)
                # Drawings might have scattered text, so we need more context
                if len(content) > 15000:
                    content = content[:15000] + "..."
                
                context_parts.append(f"[Document {i}: {filename}]\n{content}\n")
                
                # Add to citations
                citations.append({
                    'filepath': blob_path, # Use full blob path including folders
                    'url': '',
                    'path': path,
                    'title': filename
                })
            
            if not context_parts:
                return "검색된 문서가 없습니다. 다른 검색어를 시도해 보세요.", []
            
            context = "\n" + "="*50 + "\n".join(context_parts)
            
            # 3. Build messages with context
            # For o1 models, it's safer to include context in the user message
            # rather than using 'system' role which might be restricted
            
            full_prompt = f"""{self.system_prompt}

CONTEXT:
{context}

USER QUESTION:
{user_message}"""
            
            messages = []
            
            if conversation_history:
                # Add history but ensure we don't duplicate system messages
                # Filter out any system messages from history if they exist
                history = [msg for msg in conversation_history if msg['role'] != 'system']
                messages.extend(history)
            
            messages.append({"role": "user", "content": full_prompt})
            
            # 4. Call Azure OpenAI with standard API
            # Now we can use max_completion_tokens for GPT-5
            # Note: o1 models do not support temperature (must be 1)
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=2000,
                timeout=300  # Increase timeout for o1 models (5 minutes)
            )
            
            # Extract response
            response_text = response.choices[0].message.content
            
            # Extract page numbers from metadata_storage_path (which contains #page=N)
            import re
            
            for citation in citations:
                # Check if the path contains #page=N
                path = citation.get('path', '')
                page_match = re.search(r'#page=(\d+)', path)
                if page_match:
                    citation['page'] = int(page_match.group(1))
                else:
                    citation['page'] = None
            
            return response_text, citations
            
        except Exception as e:
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

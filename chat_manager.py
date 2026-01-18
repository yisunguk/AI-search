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
1. **Fact-Based Answers**: Answer strictly based on the provided context. If the information is not in the context, state "문서에서 정보를 찾을 수 없습니다."

2. **Table/Data Interpretation**: 
   - Engineering documents often contain tables where keys and values might be visually separated.
   - Look for patterns like "Item: Value" or columns in a table row.
   - If you see "FILTER ELEMENT" and "POLYESTER" near each other or aligned, infer the relationship.
   - Even if the text is fragmented, try to reconstruct the specification from nearby words.

3. **Machine Identifiers**: For Tag Nos like "10-P-101A", copy them EXACTLY.

4. **Numeric Values**: Quote exact numbers with units.

5. **Citations**: Always cite the document name when providing specific facts.

6. **Language**: Respond in Korean unless asked otherwise.
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
            # 1. Search for relevant documents using Azure AI Search
            # Use provided search parameters
            search_results = self.search_manager.search(
                user_message, 
                filter_expr=filter_expr,
                use_semantic_ranker=use_semantic_ranker,
                search_mode=search_mode
            )
            
            # 2. Construct context from search results
            context_parts = []
            citations = []
            
            # Increase context limit to 10 documents
            for i, result in enumerate(search_results, 1):
                if i > 10: break
                
                filename = result.get('metadata_storage_name', 'Unknown')
                content = result.get('content', '')
                path = result.get('metadata_storage_path', '') # Full URL
                
                # Decode filename as well
                from urllib.parse import unquote
                filename = unquote(filename)
                
                # Extract relative path from URL (handle folders)
                # Format: https://account.blob.core.windows.net/container/folder/file.pdf
                blob_path = filename # Default fallback
                if path and self.container_name in path:
                    try:
                        # Split by container name and take the part after it
                        parts = path.split(f"/{self.container_name}/")
                        if len(parts) > 1:
                            blob_path = parts[1]
                            # Decode URL encoding if needed (e.g. %20 -> space)
                            blob_path = unquote(blob_path)
                    except:
                        pass

                # Clean OCR noise (AutoCAD artifacts)
                content = content.replace("AutoCAD SHX Text", "")
                content = content.replace("%%C", "Ø") # CAD diameter symbol
                
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

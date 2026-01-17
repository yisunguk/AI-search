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
        
        # System prompt optimized for technical accuracy
        self.system_prompt = """You are a technical document assistant for EPC engineering projects.
Use the provided CONTEXT to answer the user's question.

CRITICAL RULES:
1. For machine identifiers (Tag No.) like "P-101", "10-P-101A":
   - Copy the EXACT identifier from the source document
   - Do NOT modify hyphens, numbers, or letters
   - Example: If source says "10-P-101A", write exactly "10-P-101A"

2. For design specifications and numeric values:
   - Quote exact numbers from the document
   - Include units (e.g., "25 bar", "100°C")
   - If uncertain, say "문서에 따르면"

3. Always cite your sources:
   - Reference specific document names
   - Mention which document number provided the information

4. If information is not in the CONTEXT, clearly state:
   "이 정보는 제공된 문서에서 찾을 수 없습니다."

5. Respond in Korean unless asked otherwise.
"""

    def get_chat_response(self, user_message, conversation_history=None):
        """
        Get chat response with client-side RAG
        
        Returns:
            response_text: AI response
            citations: List of citation objects with file info
        """
        try:
            # 1. Search for relevant documents using Azure AI Search
            search_results = self.search_manager.search(
                user_message, 
                top=5, 
                use_semantic_ranker=True
            )
            
            # 2. Construct context from search results
            context_parts = []
            citations = []
            
            for i, result in enumerate(search_results, 1):
                filename = result.get('metadata_storage_name', 'Unknown')
                content = result.get('content', '')
                path = result.get('metadata_storage_path', '')
                
                # Truncate very long content to fit context window
                if len(content) > 2000:
                    content = content[:2000] + "..."
                
                context_parts.append(f"[Document {i}: {filename}]\n{content}\n")
                
                # Add to citations
                citations.append({
                    'filepath': filename,
                    'url': '',
                    'path': path,
                    'title': filename
                })
            
            if not context_parts:
                return "검색된 문서가 없습니다. 다른 검색어를 시도해 보세요.", []
            
            context = "\n" + "="*50 + "\n".join(context_parts)
            
            # 3. Build messages with context
            system_message = f"{self.system_prompt}\n\n{context}"
            
            messages = [{"role": "system", "content": system_message}]
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": user_message})
            
            # 4. Call Azure OpenAI with standard API
            # Now we can use max_completion_tokens for GPT-5
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=2000,
                temperature=0.3
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

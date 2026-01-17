import os
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

class AzureOpenAIChatManager:
    def __init__(self, endpoint, api_key, deployment_name, api_version, 
                 search_endpoint, search_key, search_index_name,
                 storage_connection_string, container_name):
        """
        Azure OpenAI Chat Manager with Search Grounding
        """
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        self.search_endpoint = search_endpoint
        self.search_key = search_key
        self.search_index_name = search_index_name
        self.storage_connection_string = storage_connection_string
        self.container_name = container_name
        
        # System prompt optimized for technical accuracy
        self.system_prompt = """You are a technical document assistant for EPC engineering projects.

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
   - Include page numbers when available

4. If information is not in the documents, clearly state:
   "이 정보는 제공된 문서에서 찾을 수 없습니다."

5. Respond in Korean unless asked otherwise.
"""

    def get_chat_response(self, user_message, conversation_history=None):
        """
        Get chat response with search grounding
        
        Args:
            user_message: User's question
            conversation_history: List of {"role": "user"/"assistant", "content": "..."}
            
        Returns:
            response_text: AI response
            citations: List of citation objects with file info
        """
        try:
            # Build messages
            messages = [{"role": "system", "content": self.system_prompt}]
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": user_message})
            
            # Call Azure OpenAI with search grounding
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                extra_body={
                    "data_sources": [
                        {
                            "type": "azure_search",
                            "parameters": {
                                "endpoint": self.search_endpoint,
                                "index_name": self.search_index_name,
                                "authentication": {
                                    "type": "api_key",
                                    "key": self.search_key
                                },
                                "query_type": "semantic",
                                "semantic_configuration": "my-semantic-config",
                                "top_n_documents": 5,
                                "in_scope": True,
                                "strictness": 3
                            }
                        }
                    ]
                }
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Extract citations
            citations = []
            if hasattr(response.choices[0].message, 'context') and response.choices[0].message.context:
                if 'citations' in response.choices[0].message.context:
                    for citation in response.choices[0].message.context['citations']:
                        citations.append({
                            'filepath': citation.get('filepath', 'Unknown'),
                            'url': citation.get('url', ''),
                            'chunk_id': citation.get('chunk_id', ''),
                            'title': citation.get('title', 'Document')
                        })
            
            return response_text, citations
            
        except Exception as e:
            return f"오류가 발생했습니다: {str(e)}", []
    
    def generate_sas_url(self, blob_name):
        """
        Generate SAS URL for blob document
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
            
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
            return blob_url
        except Exception as e:
            print(f"Error generating SAS URL: {e}")
            return None

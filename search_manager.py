import os
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SimpleField,
    SearchFieldDataType,
    SearchableField,
    CorsOptions,
    IndexingSchedule,
    SemanticSearch,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile
)
from azure.search.documents.models import VectorizedQuery
import streamlit as st

class AzureSearchManager:
    def __init__(self, service_endpoint, service_key, index_name="pdf-search-index"):
        self.service_endpoint = service_endpoint
        self.service_key = service_key
        self.index_name = index_name
        self.credential = AzureKeyCredential(service_key)
        
        self.index_client = SearchIndexClient(endpoint=service_endpoint, credential=self.credential)
        self.indexer_client = SearchIndexerClient(endpoint=service_endpoint, credential=self.credential)
        self.search_client = SearchClient(endpoint=service_endpoint, index_name=index_name, credential=self.credential)

    def create_data_source(self, name, connection_string, container_name):
        """
        Azure Blob Storage를 데이터 소스로 등록
        """
        try:
            container = SearchIndexerDataContainer(name=container_name)
            data_source_connection = SearchIndexerDataSourceConnection(
                name=name,
                type="azureblob",
                connection_string=connection_string,
                container=container
            )
            result = self.indexer_client.create_or_update_data_source_connection(data_source_connection)
            return True, f"Data Source '{name}' created/updated."
        except Exception as e:
            return False, str(e)

    def create_index(self):
        """
        인덱스 스키마 정의 및 생성
        """
        try:
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="ko.microsoft"),
                SimpleField(name="metadata_storage_name", type=SearchFieldDataType.String, filterable=True, sortable=True),
                SimpleField(name="metadata_storage_path", type=SearchFieldDataType.String),
                SimpleField(name="metadata_storage_last_modified", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
                SimpleField(name="metadata_storage_size", type=SearchFieldDataType.Int64),
                SimpleField(name="metadata_storage_content_type", type=SearchFieldDataType.String, filterable=True),
                # 추가 메타데이터 필드
                SearchableField(name="project", type=SearchFieldDataType.String, filterable=True, sortable=True),
            ]

            cors_options = CorsOptions(allowed_origins=["*"], max_age_in_seconds=60)
            
            index = SearchIndex(
                name=self.index_name,
                fields=fields,
                cors_options=cors_options,
                semantic_search=SemanticSearch(
                    configurations=[
                        SemanticConfiguration(
                            name="my-semantic-config",
                            prioritized_fields=SemanticPrioritizedFields(
                                content_fields=[SemanticField(field_name="content")],
                                keywords_fields=[SemanticField(field_name="metadata_storage_name")]
                            )
                        )
                    ]
                )
            )
            
            result = self.index_client.create_or_update_index(index)
            return True, f"Index '{self.index_name}' created/updated."
        except Exception as e:
            return False, str(e)

    def delete_index(self):
        """
        인덱스 삭제 (Analyzer 변경 시 필수)
        """
        try:
            self.index_client.delete_index(self.index_name)
            return True, f"Index '{self.index_name}' deleted."
        except Exception as e:
            # 인덱스가 없으면 성공으로 간주
            return True, "Index did not exist or deleted."

    def create_indexer(self, indexer_name, data_source_name):
        """
        인덱서 생성 (Blob -> Index 매핑)
        """
        try:
            # 기본 매핑: content -> content
            # Azure Blob Indexer는 기본적으로 'content' 필드에 텍스트를 추출해 넣음 (metadata_storage_content_type이 텍스트/PDF인 경우)
            # id는 metadata_storage_path를 base64 인코딩하여 자동 생성됨 (설정 필요 없음, 기본 동작)
            
            indexer = SearchIndexer(
                name=indexer_name,
                data_source_name=data_source_name,
                target_index_name=self.index_name,
                schedule=IndexingSchedule(interval="PT1H") # 1시간마다 실행
            )
            
            result = self.indexer_client.create_or_update_indexer(indexer)
            return True, f"Indexer '{indexer_name}' created/updated."
        except Exception as e:
            return False, str(e)

    def run_indexer(self, indexer_name):
        """
        인덱서 수동 실행
        """
        try:
            self.indexer_client.run_indexer(indexer_name)
            return True, "Indexer run triggered."
        except Exception as e:
            return False, str(e)

    def get_indexer_status(self, indexer_name):
        try:
            status = self.indexer_client.get_indexer_status(indexer_name)
            return status.last_result.status, status.last_result.error_message
        except Exception as e:
            return "Unknown", str(e)

    def search(self, query, filter_expr=None, use_semantic_ranker=False, search_mode="all"):
        """
        문서 검색
        """
        try:
            # 기본 검색 파라미터
            search_params = {
                "search_text": query,
                "filter": filter_expr,
                "include_total_count": True,
                "select": ["metadata_storage_name", "content", "metadata_storage_path", "metadata_storage_last_modified"],
                "highlight_fields": "content",
                "highlight_pre_tag": "**",
                "highlight_post_tag": "**",
                "top": 10,
                "search_mode": search_mode  # 'all' (AND) or 'any' (OR)
            }

            # 시맨틱 랭커 적용
            if use_semantic_ranker:
                search_params.update({
                    "query_type": "semantic",
                    "semantic_configuration_name": "my-semantic-config",
                    "query_answer": "extractive",
                    "query_caption": "extractive",
                    "query_language": "ko-kr"
                })

            results = self.search_client.search(**search_params)
            return list(results)
        except Exception as e:
            print(f"Search error: {e}")
            return []

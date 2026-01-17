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
    VectorSearchProfile,
    LexicalAnalyzerName,
    CustomAnalyzer,
    PatternTokenizer,
    TokenFilterName,
    FieldMapping
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

    def create_data_source(self, name, connection_string, container_name, query=None):
        """
        Azure Blob Storage를 데이터 소스로 등록
        query: 특정 폴더만 인덱싱할 경우 폴더명 (예: 'GULFLNG')
        """
        try:
            container = SearchIndexerDataContainer(name=container_name, query=query)
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
            # Custom Analyzer 정의: Tag No 등 특수문자 포함 식별자 보존
            # 1. PatternTokenizer: 구분자(공백, 쉼표 등)로만 토큰 분리. 하이픈(-), 점(.) 등은 유지.
            # 정규식 패턴: [^\s,]+ (공백이나 쉼표가 아닌 문자열 덩어리를 하나의 토큰으로 취급)
            tag_analyzer_name = "tag_analyzer"
            tag_analyzer = CustomAnalyzer(
                name=tag_analyzer_name,
                tokenizer_name="tag_tokenizer",
                token_filters=[TokenFilterName.LOWERCASE] # 대소문자 구분 없이 검색
            )
            
            # Tokenizer 정의 (CustomAnalyzer에서 참조)
            # 여기서는 API 제약상 CustomAnalyzer 내부에 tokenizer를 직접 정의하기보다,
            # 별도의 Tokenizer 정의가 필요할 수 있으나, Python SDK에서는 CustomAnalyzer 생성 시
            # tokenizer_name에 미리 정의된 tokenizer나 'keyword' 등을 쓸 수 있음.
            # 'keyword' tokenizer는 입력 전체를 하나의 토큰으로 만듦.
            # 'whitespace' tokenizer는 공백 기준으로만 나눔. -> Tag No에 적합 (10-P-101A)
            
            # 더 정교한 제어를 위해 PatternTokenizer 사용 시도
            # (SDK 버전에 따라 지원 여부가 다를 수 있으므로 안전하게 whitespace 사용 후 필요시 변경)
            # 여기서는 'whitespace'를 사용하여 공백 기준으로만 분리하고, lowercase 필터 적용.
            
            # 수정: CustomAnalyzer 객체 생성 시 tokenizer_name에 표준 토크나이저 이름 사용 가능
            tag_analyzer = CustomAnalyzer(
                name=tag_analyzer_name,
                tokenizer_name=LexicalAnalyzerName.WHITESPACE,
                token_filters=[TokenFilterName.LOWERCASE]
            )

            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                # 일반 본문 검색 (한국어 분석기)
                SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="ko.microsoft"),
                # 정확한 매칭을 위한 본문 필드 (Custom Analyzer)
                SearchableField(name="content_exact", type=SearchFieldDataType.String, analyzer_name=tag_analyzer_name),
                
                # 파일명도 검색 가능하도록 (Custom Analyzer 적용하여 정확도 향상)
                SearchableField(name="metadata_storage_name", type=SearchFieldDataType.String, analyzer_name=tag_analyzer_name, filterable=True, sortable=True),
                
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
                analyzers=[tag_analyzer], # Analyzer 등록
                cors_options=cors_options,
                semantic_search=SemanticSearch(
                    configurations=[
                        SemanticConfiguration(
                            name="my-semantic-config",
                            prioritized_fields=SemanticPrioritizedFields(
                                content_fields=[
                                    SemanticField(field_name="content"),
                                    SemanticField(field_name="content_exact")
                                ],
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

    def delete_indexer(self, indexer_name):
        """
        인덱서 삭제 (상태 초기화용)
        """
        try:
            self.indexer_client.delete_indexer(indexer_name)
            return True, f"Indexer '{indexer_name}' deleted."
        except Exception as e:
            return True, "Indexer did not exist or deleted."

    def create_indexer(self, indexer_name, data_source_name):
        """
        인덱서 생성 (Blob -> Index 매핑)
        """
        try:
            # 필드 매핑: Blob의 content를 content 필드와 content_exact 필드 모두에 매핑
            # Azure Blob Indexer는 기본적으로 'content'라는 이름의 소스 필드를 제공하지 않을 수 있음 (문서 추출 시)
            # 보통 '/document/content' 경로를 사용.
            
            field_mappings = [
                # 메타데이터 매핑은 자동 (이름이 같으면)
            ]
            
            # 출력 필드 매핑 (Skillset이 없는 경우에도 텍스트 추출 결과 매핑 가능)
            # Blob Indexer는 텍스트 파일/PDF의 내용을 'content'라는 필드에 자동으로 넣으려 시도함.
            # 명시적으로 매핑해주는 것이 안전.
            # content_exact에도 동일한 내용을 넣어야 함.
            
            # 주의: Blob Indexer에서 소스 필드 이름은 보통 'content'임.
            # 하나의 소스 필드를 여러 타겟 필드에 매핑하려면 FieldMapping을 여러 개 쓰면 됨.
            
            # 하지만 create_or_update_indexer의 field_mappings 인자는 'source_field_name' -> 'target_field_name' 1:1 매핑임.
            # 동일한 소스를 여러 타겟으로 보내려면... 
            # 공식적으로는 Skillset을 써서 복제하거나, Indexer의 outputFieldMappings를 써야 하는데,
            # 간단한 방법은 FieldMapping을 두 번 정의하는 것인데, source_field_name이 중복되어도 되는지 확인 필요.
            # 보통은 안됨.
            
            # 대안: Indexer 정의 시 parameters configuration에 "indexedFileNameExtensions" 등을 설정.
            # 여기서는 content_exact를 채우기 위해 Skillset 없이 하려면...
            # 사실 content 필드는 기본적으로 채워짐. content_exact는 비워질 수 있음.
            # 가장 확실한 방법: Skillset을 정의하지 않고, Indexer의 fieldMappings에
            # source_field_name="content", target_field_name="content" (기본)
            # source_field_name="content", target_field_name="content_exact" (추가)
            # 이렇게 리스트에 추가하면 됨.
            
            mappings = [
                FieldMapping(source_field_name="content", target_field_name="content"),
                FieldMapping(source_field_name="content", target_field_name="content_exact")
            ]
            
            indexer = SearchIndexer(
                name=indexer_name,
                data_source_name=data_source_name,
                target_index_name=self.index_name,
                schedule=IndexingSchedule(interval="PT1H"), # 1시간마다 실행
                field_mappings=mappings
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
            last_result = status.last_result
            
            if last_result:
                # 에러 및 경고 상세 정보 추출
                errors = [e.message for e in last_result.errors] if last_result.errors else []
                warnings = [w.message for w in last_result.warnings] if last_result.warnings else []
                
                return {
                    "status": last_result.status,
                    "item_count": last_result.item_count,
                    "failed_item_count": last_result.failed_item_count,
                    "error_message": last_result.error_message,
                    "errors": errors,
                    "warnings": warnings
                }
            else:
                return {
                    "status": "Never Run",
                    "item_count": 0,
                    "failed_item_count": 0,
                    "error_message": "No execution history found.",
                    "errors": [],
                    "warnings": []
                }
        except Exception as e:
            return {
                "status": "Unknown",
                "item_count": 0,
                "failed_item_count": 0,
                "error_message": str(e),
                "errors": [],
                "warnings": []
            }

    def get_source_blob_count(self, connection_string, container_name, folder_path=None):
        """
        소스 컨테이너(또는 폴더)의 총 Blob 개수 계산 (진행률 표시용)
        """
        try:
            from azure.storage.blob import BlobServiceClient
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            container_client = blob_service_client.get_container_client(container_name)
            
            prefix = folder_path if folder_path else None
            blobs = container_client.list_blobs(name_starts_with=prefix)
            
            count = 0
            for _ in blobs:
                count += 1
            return count
        except Exception as e:
            print(f"Error counting blobs: {e}")
            return 0

    def get_document_count(self):
        """
        인덱스에 저장된 문서 개수 확인
        """
        try:
            return self.search_client.get_document_count()
        except Exception as e:
            print(f"Error getting doc count: {e}")
            return -1

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
                "select": ["metadata_storage_name", "content", "metadata_storage_path", "metadata_storage_last_modified", "metadata_storage_content_type"],
                # 하이라이트 요청
                "highlight_fields": "content,content_exact",
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

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
    FieldMapping,
    SearchIndexerSkillset,
    OcrSkill,
    MergeSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    CognitiveServicesAccountKey
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

    def create_data_source(self, name, connection_string, container_name, query=None, folder_name=None):
        """
        Azure Blob Storage를 데이터 소스로 등록 (폴더별)
        query: 특정 폴더만 인덱싱할 경우 폴더명 (예: 'GULFLNG')
        folder_name: 데이터소스 이름 생성용 폴더명
        """
        try:
            # 폴더 이름 기반으로 데이터소스 이름 생성
            if folder_name:
                datasource_name = f"datasource-{folder_name}"
            else:
                datasource_name = name  # 기존 호환성 유지
            
            container = SearchIndexerDataContainer(name=container_name, query=query)
            data_source_connection = SearchIndexerDataSourceConnection(
                name=datasource_name,
                type="azureblob",
                connection_string=connection_string,
                container=container
            )
            result = self.indexer_client.create_or_update_data_source_connection(data_source_connection)
            return True, f"Data Source '{datasource_name}' created/updated.", datasource_name
        except Exception as e:
            return False, str(e), None

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
                
                SimpleField(name="metadata_storage_path", type=SearchFieldDataType.String, filterable=True),
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

    def delete_indexer(self, folder_name):
        """
        인덱서 삭제 (폴더별)
        """
        try:
            indexer_name = f"indexer-{folder_name}" if folder_name else "indexer-all"
            return True, f"Indexer '{indexer_name}' deleted."
        except Exception as e:
            return True, "Indexer did not exist or deleted."

    def create_skillset(self, skillset_name, cognitive_services_key):
        """
        Create a Skillset for OCR (Optical Character Recognition)
        """
        try:
            # 1. OCR Skill: Extract text from images
            ocr_skill = OcrSkill(
                name="ocr-skill",
                description="Extract text from images",
                context="/document/normalized_images/*",
                default_language_code="ko", # Default to Korean/English
                should_detect_orientation=True,
                inputs=[
                    InputFieldMappingEntry(name="image", source="/document/normalized_images/*")
                ],
                outputs=[
                    OutputFieldMappingEntry(name="text", target_name="text")
                ]
            )
            
            # 2. Merge Skill: Merge extracted text with content
            merge_skill = MergeSkill(
                name="merge-skill",
                description="Merge OCR text with content",
                context="/document",
                insert_pre_tag=" ",
                insert_post_tag=" ",
                inputs=[
                    InputFieldMappingEntry(name="text", source="/document/content"),
                    InputFieldMappingEntry(name="itemsToInsert", source="/document/normalized_images/*/text"),
                    InputFieldMappingEntry(name="offsets", source="/document/normalized_images/*/contentOffset")
                ],
                outputs=[
                    OutputFieldMappingEntry(name="mergedText", target_name="merged_content")
                ]
            )
            
            # Cognitive Services Key
            cog_services = CognitiveServicesAccountKey(key=cognitive_services_key) if cognitive_services_key else None
            
            skillset = SearchIndexerSkillset(
                name=skillset_name,
                description="OCR Skillset for PDF Drawings",
                skills=[ocr_skill, merge_skill],
                cognitive_services_account=cog_services
            )
            
            self.indexer_client.create_or_update_skillset(skillset)
            return True, f"Skillset '{skillset_name}' created/updated."
        except Exception as e:
            return False, f"Failed to create skillset: {str(e)}"

    def create_indexer(self, folder_name, datasource_name, skillset_name=None):
        """
        인덱서 생성 (폴더별)
        """
        try:
            # 필드 매핑
            mappings = [
                FieldMapping(source_field_name="content", target_field_name="content"),
                FieldMapping(source_field_name="content", target_field_name="content_exact")
            ]
            
            # If using skillset (OCR), map 'merged_content' to 'content' instead of original content
            if skillset_name:
                # When using MergeSkill, the output 'merged_content' contains both text and OCR text.
                # We map this to the index 'content' field.
                mappings = [
                    FieldMapping(source_field_name="merged_content", target_field_name="content"),
                    FieldMapping(source_field_name="merged_content", target_field_name="content_exact")
                ]
            
            # 인덱서 설정
            config = {
                "indexStorageMetadataOnlyForOversizedDocuments": True,
                "failOnUnsupportedContentType": False,
                "failOnUnprocessableDocument": False
            }
            
            # If using skillset, enable image extraction
            if skillset_name:
                config["imageAction"] = "generateNormalizedImages"
                config["dataToExtract"] = "contentAndMetadata"
                config["normalizedImageMaxWidth"] = 2000
                config["normalizedImageMaxHeight"] = 2000

            indexer_parameters = {"configuration": config}
            
            # 폴더 이름 기반으로 인덱서 이름 생성
            indexer_name = f"indexer-{folder_name}" if folder_name else "indexer-all"
            
            indexer = SearchIndexer(
                name=indexer_name,
                data_source_name=datasource_name,
                target_index_name=self.index_name,
                skillset_name=skillset_name, # Attach Skillset
                schedule=IndexingSchedule(interval="PT1H"),
                field_mappings=mappings,
                parameters=indexer_parameters
            )
            
            result = self.indexer_client.create_or_update_indexer(indexer)
            return True, f"Indexer '{indexer_name}' created/updated.", indexer_name
        except Exception as e:
            return False, str(e), None

    def run_indexer(self, folder_name):
        """
        인덱서 수동 실행 (폴더별)
        """
        try:
            indexer_name = f"indexer-{folder_name}" if folder_name else "indexer-all"
            self.indexer_client.run_indexer(indexer_name)
            return True, f"Indexer '{indexer_name}' started."
        except Exception as e:
            return False, str(e)

    def get_indexer_status(self, folder_name):
        try:
            indexer_name = f"indexer-{folder_name}" if folder_name else "indexer-all"
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

    def get_document_content(self, filename):
        """
        특정 파일의 인덱싱된 내용 조회 (디버깅용)
        """
        try:
            # 확장자 체크 및 자동 추가
            if not filename.lower().endswith('.pdf'):
                filename += ".pdf"

            # metadata_storage_name은 SimpleField이므로 search_text가 아닌 filter로 찾아야 함
            results = self.search_client.search(
                search_text="*",
                filter=f"metadata_storage_name eq '{filename}'",
                select=["metadata_storage_name", "content"]
            )
            
            for result in results:
                return result.get("content", "내용 없음")
            
            return f"문서를 찾을 수 없습니다. (검색된 파일명: {filename})"
        except Exception as e:
            return f"조회 실패: {str(e)}"

    def get_document_count(self):
        """
        인덱스에 저장된 문서 개수 확인
        """
        try:
            return self.search_client.get_document_count()
        except Exception as e:
            print(f"Error getting doc count: {e}")
            return -1

    def search(self, query, filter_expr=None, use_semantic_ranker=False, search_mode="all", **kwargs):
        """
        문서 검색
        """
        try:
            # Force AND logic if search_mode is 'all'
            # Azure AI Search 'search_mode' parameter sometimes behaves unexpectedly with certain analyzers
            # So we manually enforce AND by prepending + to each term in Simple Query Syntax
            if search_mode == "all" and query and not any(char in query for char in ['+', '|', '"', '*']):
                # Split by whitespace and prepend +
                terms = query.split()
                if len(terms) > 1:
                    # Only apply if multiple terms
                    query = " ".join([f"+{term}" for term in terms])
                    print(f"DEBUG: Transformed query for ALL mode: '{query}'")

            # 기본 검색 파라미터
            search_params = {
                "search_text": query,
                "filter": filter_expr,
                "include_total_count": True,
                "select": ["metadata_storage_name", "content", "metadata_storage_path", "metadata_storage_last_modified", "metadata_storage_content_type"],
                "highlight_fields": "content,content_exact",
                "highlight_pre_tag": "<mark style='background-color: #ffd700; color: black; font-weight: bold;'>",
                "highlight_post_tag": "</mark>",
                "top": 50,
                "search_mode": search_mode
            }
            
            # Update with any additional parameters (e.g. select, top)
            search_params.update(kwargs)

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
    def upload_documents(self, documents):
        """
        문서 직접 업로드 (Push API)
        documents: list of dict
        """
        try:
            results = self.search_client.upload_documents(documents=documents)
            
            failed_docs = []
            for res in results:
                if not res.succeeded:
                    failed_docs.append(f"Key: {res.key}, Error: {res.error_message}")
            
            if failed_docs:
                return False, f"Partial upload failure: {'; '.join(failed_docs)}"
                
            return True, f"Successfully uploaded {len(documents)} documents."
        except Exception as e:
            return False, f"Upload failed: {str(e)}"

    def get_document_json(self, filename):
        """
        특정 파일의 모든 페이지/청크를 JSON 형태로 가져오기
        """
        try:
            # Use search.ismatch for searchable fields (startswith is for non-searchable filterable fields)
            safe_filename = filename.replace("'", "''")
            
            # Try with project filter first
            results = self.search_client.search(
                search_text="*",
                filter=f"project eq 'drawings_analysis' and search.ismatch('\"{safe_filename}*\"', 'metadata_storage_name')",
                select=["id", "metadata_storage_name", "content", "metadata_storage_path", "metadata_storage_last_modified"],
                top=1000
            )
            documents = list(results)
            
            # Fallback: If no results with project tag, try searching by name and filter path in Python
            if not documents:
                print(f"DEBUG: No docs found with project tag for {filename}. Retrying with name-only filter...")
                results = self.search_client.search(
                    search_text="*",
                    filter=f"search.ismatch('\"{safe_filename}*\"', 'metadata_storage_name')",
                    select=["id", "metadata_storage_name", "content", "metadata_storage_path", "metadata_storage_last_modified"],
                    top=1000
                )
                # Filter by path in Python
                documents = [
                    doc for doc in results 
                    if '/drawings/' in doc.get('metadata_storage_path', '')
                ]
            
            # Sort by page number if possible, or just name
            documents.sort(key=lambda x: x.get('metadata_storage_name', ''))
            
            return documents
        except Exception as e:
            print(f"Error fetching document JSON: {e}")
            return []

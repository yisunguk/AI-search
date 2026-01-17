import streamlit as st
import os
import time
import uuid
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, generate_container_sas, ContainerSasPermissions
from azure.ai.translation.document import DocumentTranslationClient, DocumentTranslationInput, TranslationTarget
from azure.core.credentials import AzureKeyCredential
import urllib.parse
import requests

# Search Manager Import
from search_manager import AzureSearchManager

# Chat Manager Import  
from chat_manager import AzureOpenAIChatManager

# -----------------------------
# 설정 및 비밀 관리
# -----------------------------
st.set_page_config(page_title="Azure 문서 번역기 & 검색", page_icon="🌏", layout="centered")

def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.environ.get(key)

# 필수 자격 증명
# 1. Storage
STORAGE_CONN_STR = get_secret("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = get_secret("AZURE_BLOB_CONTAINER_NAME") or "blob-leesunguk"

# 2. Translator
TRANSLATOR_KEY = get_secret("AZURE_TRANSLATOR_KEY")
TRANSLATOR_ENDPOINT = get_secret("AZURE_TRANSLATOR_ENDPOINT")

# 3. Search
SEARCH_ENDPOINT = get_secret("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = get_secret("AZURE_SEARCH_KEY")
SEARCH_INDEX_NAME = "pdf-search-index"
SEARCH_INDEXER_NAME = "pdf-indexer"
SEARCH_DATASOURCE_NAME = "blob-datasource"

# 4. Azure OpenAI
AZURE_OPENAI_ENDPOINT = get_secret("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = get_secret("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = get_secret("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = get_secret("AZURE_OPENAI_API_VERSION")

# -----------------------------
# Azure 클라이언트 헬퍼
# -----------------------------
def get_blob_service_client():
    if not STORAGE_CONN_STR:
        st.error("Azure Storage Connection String이 설정되지 않았습니다.")
        st.stop()
    return BlobServiceClient.from_connection_string(STORAGE_CONN_STR)

def get_translation_client():
    if not TRANSLATOR_KEY or not TRANSLATOR_ENDPOINT:
        st.error("Azure Translator Key 또는 Endpoint가 설정되지 않았습니다.")
        st.stop()
    return DocumentTranslationClient(TRANSLATOR_ENDPOINT, AzureKeyCredential(TRANSLATOR_KEY))

def get_search_manager():
    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        st.error("Azure Search Endpoint 또는 Key가 설정되지 않았습니다.")
        st.stop()
    return AzureSearchManager(SEARCH_ENDPOINT, SEARCH_KEY, SEARCH_INDEX_NAME)

def get_chat_manager():
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
        st.error("Azure OpenAI Endpoint 또는 Key가 설정되지 않았습니다.")
        st.stop()
    return AzureOpenAIChatManager(
        endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        deployment_name=AZURE_OPENAI_DEPLOYMENT,
        api_version=AZURE_OPENAI_API_VERSION,
        search_endpoint=SEARCH_ENDPOINT,
        search_key=SEARCH_KEY,
        search_index_name=SEARCH_INDEX_NAME,
        storage_connection_string=STORAGE_CONN_STR,
        container_name=CONTAINER_NAME
    )

def generate_sas_url(blob_service_client, container_name, blob_name=None, permission="r", expiry_hours=1):
    """
    Blob 또는 Container에 대한 SAS URL 생성
    blob_name이 있으면 Blob SAS, 없으면 Container SAS (Write용)
    """
    import urllib.parse
    
    account_name = blob_service_client.account_name
    
    # Connection String으로 생성된 경우 credential은 dict일 수 있음
    if hasattr(blob_service_client.credential, 'account_key'):
        account_key = blob_service_client.credential.account_key
    else:
        account_key = blob_service_client.credential['account_key']
    
    # 시계 오차(Clock Skew) 방지를 위해 시작 시간을 15분 전으로 설정
    start = datetime.utcnow() - timedelta(minutes=15)
    expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
    
    # 항상 Container SAS를 사용 (Source/Target 모두 더 안정적)
    # Source의 경우 Read/List, Target의 경우 Write/List/Read 필요
    # 편의상 모든 권한을 부여한 Container SAS 하나로 통일하거나, 구분 가능
    # 여기서는 구분 없이 Container 수준의 강력한 SAS를 발급하여 오류 가능성 차단
    
    sas_token = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        account_key=account_key,
        permission=ContainerSasPermissions(write=True, list=True, read=True, delete=True),
        start=start,
        expiry=expiry
    )
    
    base_url = f"https://{account_name}.blob.core.windows.net/{container_name}"
    
    if blob_name:
        # Blob 경로가 있는 경우 URL에 추가 (SAS는 컨테이너 레벨이라 서명 불일치 없음)
        encoded_blob_name = urllib.parse.quote(blob_name, safe='/')
        return f"{base_url}/{encoded_blob_name}?{sas_token}"
    else:
        # 컨테이너 루트 URL
        return f"{base_url}?{sas_token}"

# -----------------------------
# UI 구성
# -----------------------------
st.title("🌏 Azure 문서 번역기 & 검색")
st.caption("Azure Document Translation & Blob Storage & AI Search 기반")

# 지원 언어 목록 가져오기 (API)
@st.cache_data
def get_supported_languages():
    try:
        url = "https://api.cognitive.microsofttranslator.com/languages?api-version=3.0&scope=translation"
        # Accept-Language 헤더를 'ko'로 설정하여 언어 이름을 한국어로 받음
        headers = {"Accept-Language": "ko"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        languages = {}
        for code, info in data['translation'].items():
            # "한국어 이름 (원어 이름)" 형식으로 표시 (예: 영어 (English))
            label = f"{info['name']} ({info['nativeName']})"
            languages[label] = code
        return languages
    except Exception as e:
        st.error(f"언어 목록을 가져오는데 실패했습니다: {e}")
        # 실패 시 기본 언어 제공
        return {"한국어 (Korean)": "ko", "영어 (English)": "en"}

LANGUAGES = get_supported_languages()

# 언어 코드별 파일 접미사 매핑 (기본적으로 대문자 코드를 사용하되, 일부 커스텀 가능)
# 여기서는 자동 생성 로직을 사용하므로 별도 딕셔너리 불필요, 
# 다만 중국어 등 특수 케이스를 위해 남겨둘 수 있음.
LANG_SUFFIX_OVERRIDE = {
    "zh-Hans": "CN",
    "zh-Hant": "TW",
}

with st.sidebar:
    st.header("메뉴")
    menu = st.radio("이동", ["번역하기", "파일 보관함", "검색 & AI", "관리자 설정"])
    
    st.divider()
    
    if menu == "번역하기":
        st.header("설정")
        # 한국어를 기본값으로 찾기
        default_index = 0
        lang_labels = list(LANGUAGES.keys())
        for i, label in enumerate(lang_labels):
            if "Korean" in label or "한국어" in label:
                default_index = i
                break
                
        target_lang_label = st.selectbox("목표 언어 선택", lang_labels, index=default_index)
        target_lang_code = LANGUAGES[target_lang_label]
        st.info(f"선택된 목표 언어: {target_lang_code}")

    # 자격 증명 상태 확인
    if STORAGE_CONN_STR and TRANSLATOR_KEY and SEARCH_KEY:
        st.success("✅ Azure 자격 증명 확인됨")
    else:
        st.warning("⚠️ 일부 Azure 자격 증명이 누락되었습니다.")

if menu == "번역하기":
    uploaded_file = st.file_uploader("번역할 문서 업로드 (PPTX, PDF, DOCX, XLSX 등)", type=["pptx", "pdf", "docx", "xlsx"])

    if st.button("번역 시작", type="primary", disabled=not uploaded_file):
        if not uploaded_file:
            st.error("파일을 업로드해주세요.")
        else:
            with st.spinner("Azure Blob에 파일 업로드 중..."):
                try:
                    blob_service_client = get_blob_service_client()
                    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                    
                    # 컨테이너 접근 권한 확인
                    try:
                        if not container_client.exists():
                            container_client.create_container()
                    except Exception as e:
                        if "AuthenticationFailed" in str(e):
                            st.error("🚨 인증 실패: Azure Storage Key가 올바르지 않습니다. Secrets 설정을 확인해주세요.")
                            st.stop()
                        else:
                            raise e

                    # 파일명 유니크하게 처리
                    file_uuid = str(uuid.uuid4())[:8]
                    original_filename = uploaded_file.name
                    input_blob_name = f"input/{file_uuid}/{original_filename}"
                    
                    # 업로드
                    blob_client = container_client.get_blob_client(input_blob_name)
                    blob_client.upload_blob(uploaded_file, overwrite=True)
                    
                    st.success("업로드 완료! 번역 요청 중...")
                    
                    # SAS 생성
                    source_url = generate_sas_url(blob_service_client, CONTAINER_NAME, input_blob_name)
                    
                    # Target URL 설정
                    target_base_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}"
                    # Target URL은 컨테이너 또는 폴더 경로여야 함 (파일 경로 불가)
                    # 파일명 보존을 위해 폴더 경로 끝에 '/'를 반드시 붙여야 함
                    target_output_url = f"{target_base_url}/output/{file_uuid}/?{generate_sas_url(blob_service_client, CONTAINER_NAME).split('?')[1]}"
                    
                except Exception as e:
                    st.error(f"업로드/SAS 생성 실패: {e}")
                    st.stop()

            with st.spinner("번역 작업 요청 및 대기 중..."):
                try:
                    client = get_translation_client()
                    
                    poller = client.begin_translation(
                        inputs=[
                            DocumentTranslationInput(
                                source_url=source_url,
                                storage_type="File",
                                targets=[
                                    TranslationTarget(
                                        target_url=target_output_url,
                                        language=target_lang_code
                                    )
                                ]
                            )
                        ]
                    )
                    
                    result = poller.result()
                    
                    for doc in result:
                        if doc.status == "Succeeded":
                            st.success(f"번역 완료! (상태: {doc.status})")
                        else:
                            st.error(f"문서 번역 실패! (상태: {doc.status})")
                            if doc.error:
                                st.error(f"에러 코드: {doc.error.code}, 메시지: {doc.error.message}")
                    
                    # 결과 파일 찾기
                    time.sleep(2)
                    output_prefix_search = f"output/{file_uuid}"
                    output_blobs = list(container_client.list_blobs(name_starts_with=output_prefix_search))
                    
                    if not output_blobs:
                        all_output = list(container_client.list_blobs(name_starts_with="output/"))
                        debug_msg = "\n".join([b.name for b in all_output[:10]])
                        st.error(f"결과 파일을 찾을 수 없습니다. (검색 경로: {output_prefix_search})\n현재 output 폴더 파일 목록:\n{debug_msg}")
                    else:
                        st.subheader("다운로드")
                        for blob in output_blobs:
                            blob_name = blob.name
                            file_name = blob_name.split("/")[-1]
                            
                            # 파일명에 언어 접미사 추가 (Rename)
                            suffix = LANG_SUFFIX_OVERRIDE.get(target_lang_code, target_lang_code.upper())
                            name_part, ext_part = os.path.splitext(file_name)
                            
                            # 이미 접미사가 있는지 확인 (혹시 모를 중복 방지)
                            if not name_part.endswith(f"_{suffix}"):
                                new_file_name = f"{name_part}_{suffix}{ext_part}"
                                new_blob_name = f"output/{file_uuid}/{new_file_name}"
                                
                                try:
                                    # Rename: Copy to new name -> Delete old
                                    source_blob = container_client.get_blob_client(blob_name)
                                    dest_blob = container_client.get_blob_client(new_blob_name)
                                    
                                    source_sas = generate_sas_url(blob_service_client, CONTAINER_NAME, blob_name)
                                    dest_blob.start_copy_from_url(source_sas)
                                    
                                    # Wait for copy
                                    for _ in range(10):
                                        props = dest_blob.get_blob_properties()
                                        if props.copy.status == "success":
                                            break
                                        time.sleep(0.2)
                                        
                                    source_blob.delete_blob()
                                    
                                    # Update variables for download link
                                    blob_name = new_blob_name
                                    file_name = new_file_name
                                    st.toast(f"파일명 변경됨: {file_name}")
                                    
                                except Exception as e:
                                    st.warning(f"파일명 변경 실패 (기본 이름으로 유지): {e}")

                            # PPTX 폰트 변경 (Times New Roman)
                            if file_name.lower().endswith(".pptx"):
                                try:
                                    from pptx import Presentation
                                    
                                    # 임시 파일로 다운로드
                                    temp_pptx = f"temp_{file_uuid}.pptx"
                                    blob_client_temp = container_client.get_blob_client(blob_name)
                                    with open(temp_pptx, "wb") as f:
                                        data = blob_client_temp.download_blob().readall()
                                        f.write(data)
                                    
                                    # 폰트 변경 로직
                                    prs = Presentation(temp_pptx)
                                    font_name = "Times New Roman"
                                    
                                    def change_font(shapes):
                                        for shape in shapes:
                                            if shape.has_text_frame:
                                                for paragraph in shape.text_frame.paragraphs:
                                                    for run in paragraph.runs:
                                                        run.font.name = font_name
                                            
                                            if shape.has_table:
                                                for row in shape.table.rows:
                                                    for cell in row.cells:
                                                        if cell.text_frame:
                                                            for paragraph in cell.text_frame.paragraphs:
                                                                for run in paragraph.runs:
                                                                    run.font.name = font_name
                                            
                                            if shape.shape_type == 6: # Group
                                                change_font(shape.shapes)

                                    for slide in prs.slides:
                                        change_font(slide.shapes)
                                    
                                    prs.save(temp_pptx)
                                    
                                    # 다시 업로드 (덮어쓰기)
                                    with open(temp_pptx, "rb") as f:
                                        blob_client_temp.upload_blob(f, overwrite=True)
                                    
                                    os.remove(temp_pptx)
                                    st.toast("PPTX 폰트 변경 완료 (Times New Roman)")
                                    
                                except Exception as e:
                                    st.warning(f"PPTX 폰트 변경 실패: {e}")

                            download_sas = generate_sas_url(blob_service_client, CONTAINER_NAME, blob_name)
                            st.markdown(f"[{file_name} 다운로드]({download_sas})", unsafe_allow_html=True)
                            
                except Exception as e:
                    st.error(f"번역 요청 중 오류 발생: {e}")

elif menu == "파일 보관함":
    st.subheader("📂 클라우드 파일 보관함")
    
    # -----------------------------
    # 1. 파일 직접 업로드 (Save)
    # -----------------------------
    with st.expander("📤 파일 직접 업로드 (번역 없이 저장)", expanded=False):
        upload_archive = st.file_uploader("보관함에 저장할 파일 선택", key="archive_upload")
        if st.button("저장하기", disabled=not upload_archive):
            try:
                blob_service_client = get_blob_service_client()
                container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                
                file_uuid = str(uuid.uuid4())[:8]
                blob_name = f"input/{file_uuid}/{upload_archive.name}"
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(upload_archive, overwrite=True)
                st.success(f"'{upload_archive.name}' 업로드 완료!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"업로드 실패: {e}")

    st.divider()
    
    if st.button("🔄 목록 새로고침"):
        st.rerun()
        
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # 탭으로 Input/Output 구분
        tab1, tab2 = st.tabs(["원본 문서 (Input)", "번역된 문서 (Output)"])
        
        def render_file_list(prefix, tab_name):
            blobs = list(container_client.list_blobs(name_starts_with=prefix))
            blobs.sort(key=lambda x: x.creation_time, reverse=True)
            
            if not blobs:
                st.info(f"{tab_name}에 파일이 없습니다.")
                return

            for i, blob in enumerate(blobs):
                file_name = blob.name.split("/")[-1]
                creation_time = blob.creation_time.strftime('%Y-%m-%d %H:%M')
                
                with st.container():
                    col1, col2, col3 = st.columns([6, 2, 2])
                    
                    with col1:
                        sas_url = generate_sas_url(blob_service_client, CONTAINER_NAME, blob.name)
                        st.markdown(f"**[{file_name}]({sas_url})**")
                        st.caption(f"📅 {creation_time} | 📦 {blob.size / 1024:.1f} KB")
                    
                    with col2:
                        # 수정 (이름 변경)
                        with st.popover("수정"):
                            new_name = st.text_input("새 파일명", value=file_name, key=f"rename_{prefix}_{i}")
                            if st.button("이름 변경", key=f"btn_rename_{prefix}_{i}"):
                                try:
                                    # 새 경로 생성 (UUID 폴더 구조 유지)
                                    path_parts = blob.name.split("/")
                                    # path_parts = ['input', 'uuid', 'filename']
                                    if len(path_parts) >= 3:
                                        new_blob_name = f"{path_parts[0]}/{path_parts[1]}/{new_name}"
                                    else:
                                        # 폴더 구조가 다를 경우 그냥 같은 폴더에
                                        folder = "/".join(path_parts[:-1])
                                        new_blob_name = f"{folder}/{new_name}"
                                    
                                    # 복사 (Rename은 Copy + Delete)
                                    source_blob = container_client.get_blob_client(blob.name)
                                    dest_blob = container_client.get_blob_client(new_blob_name)
                                    
                                    # SAS URL for Copy Source
                                    source_sas = generate_sas_url(blob_service_client, CONTAINER_NAME, blob.name)
                                    
                                    dest_blob.start_copy_from_url(source_sas)
                                    
                                    # 복사 완료 대기 (간단한 폴링)
                                    for _ in range(10):
                                        props = dest_blob.get_blob_properties()
                                        if props.copy.status == "success":
                                            break
                                        time.sleep(0.5)
                                    
                                    # 원본 삭제
                                    source_blob.delete_blob()
                                    st.success("이름 변경 완료!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"이름 변경 실패: {e}")

                    with col3:
                        # 삭제
                        if st.button("삭제", key=f"del_{prefix}_{i}", type="secondary"):
                            try:
                                container_client.delete_blob(blob.name)
                                st.success("삭제되었습니다.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
                    
                    st.divider()

        with tab1:
            render_file_list("input/", "원본 문서")
            
        with tab2:
            render_file_list("output/", "번역된 문서")
                
    except Exception as e:
        st.error(f"파일 목록을 불러오는 중 오류 발생: {e}")

elif menu == "검색 & AI":
    # Tabs for Search and Chat to preserve state
    tab1, tab2 = st.tabs(["🔍 문서 검색", "🤖 AI 채팅"])
    
    with tab1:
    st.subheader("🔍 PDF 문서 검색")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input("검색어 입력", placeholder="검색할 키워드를 입력하세요...")
    with col2:
        use_semantic = st.checkbox("시맨틱 랭커", value=False, help="의미 기반 검색 (Standard Tier 이상)")
    with col3:
        search_mode_opt = st.radio("검색 모드", ["all (AND)", "any (OR)"], index=0, horizontal=True, help="all: 모든 단어 포함, any: 하나라도 포함")
        search_mode = "all" if "all" in search_mode_opt else "any"
    
    
    if query:
        with st.spinner("검색 중..."):
            search_manager = get_search_manager()
            results = search_manager.search(query, use_semantic_ranker=use_semantic, search_mode=search_mode)
            
            if not results:
                st.info("검색 결과가 없습니다.")
            else:
                st.success(f"총 {len(results)}개의 문서를 찾았습니다.")
                for result in results:
                    with st.container():
                        file_name = result.get('metadata_storage_name', 'Unknown File')
                        path = result.get('metadata_storage_path', '')
                        
                        # 하이라이트 처리
                        highlights = result.get('@search.highlights')
                        if highlights:
                            # content 또는 content_exact에서 하이라이트 추출
                            # 여러 개의 하이라이트가 있을 수 있으므로 합쳐서 보여줌
                            snippets = []
                            if 'content' in highlights:
                                snippets.extend(highlights['content'])
                            if 'content_exact' in highlights:
                                snippets.extend(highlights['content_exact'])
                            
                            # 중복 제거 및 길이 제한
                            unique_snippets = list(set(snippets))[:3]
                            content_snippet = " ... ".join(unique_snippets)
                        else:
                            # 하이라이트 없으면 기본 스니펫
                            content_snippet = result.get('content', '')[:300] + "..."
                        
                        blob_path = ""
                        try:
                            if CONTAINER_NAME in path:
                                blob_path = path.split(f"/{CONTAINER_NAME}/")[-1]
                                blob_path = urllib.parse.unquote(blob_path)
                        except:
                            pass
                            
                        st.markdown(f"### 📄 {file_name}")
                        st.markdown(f"> {content_snippet}", unsafe_allow_html=True) # HTML 태그(bold) 허용
                        
                        if blob_path:
                            try:
                                blob_service_client = get_blob_service_client()
                                
                                # Content-Type 결정 (확장자 우선 적용)
                                # 메타데이터가 application/octet-stream인 경우가 많아 확장자로 강제 설정
                                if file_name.lower().endswith('.pdf'):
                                    content_type = "application/pdf"
                                else:
                                    content_type = result.get('metadata_storage_content_type')
                                    if not content_type or content_type == "application/octet-stream":
                                        import mimetypes
                                        content_type, _ = mimetypes.guess_type(file_name)
                                
                                # Blob SAS 생성 (Content-Disposition: inline 설정 + Content-Type 강제)
                                sas_token = generate_blob_sas(
                                    account_name=blob_service_client.account_name,
                                    container_name=CONTAINER_NAME,
                                    blob_name=blob_path,
                                    account_key=blob_service_client.credential.account_key,
                                    permission=BlobSasPermissions(read=True),
                                    expiry=datetime.utcnow() + timedelta(hours=1),
                                    content_disposition="inline", # 브라우저에서 열기 강제
                                    content_type=content_type # 올바른 MIME 타입 설정
                                )
                                
                                sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{urllib.parse.quote(blob_path)}?{sas_token}"
                                
                                # 새 탭에서 열기 (target="_blank")
                                st.markdown(f'<a href="{sas_url}" target="_blank">📄 문서 열기 (새 탭)</a>', unsafe_allow_html=True)
                            except Exception as e:
                                st.caption(f"문서 링크 생성 실패: {e}")
                        
                        st.divider()
    
    with tab2:
        st.subheader("🤖 AI 문서 도우미")
        st.caption("Azure OpenAI와 문서 검색을 활용한 정확한 답변 제공")
        
        # Initialize chat history in session state
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        
        # Display chat messages
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Display citations if present
                if "citations" in message and message["citations"]:
                    st.markdown("---")
                    st.caption("📚 **참조 문서:**")
                    for i, citation in enumerate(message["citations"], 1):
                        filepath = citation.get('filepath', 'Unknown')
                        url = citation.get('url', '')
                        
                        # Generate SAS URL if we have blob path
                        if url:
                            display_url = url
                        else:
                            # Try to generate SAS URL from filepath
                            blob_service_client = get_blob_service_client()
                            display_url = generate_sas_url(blob_service_client, CONTAINER_NAME, filepath)
                        
                        st.markdown(f"{i}. [{filepath}]({display_url})")
        
        # Chat input
        if prompt := st.chat_input("질문을 입력하세요 (예: 10-P-101A의 사양은 무엇인가요?)"):
            # Add user message to chat history
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("답변 생성 중..."):
                    try:
                        chat_manager = get_chat_manager()
                        
                        # Prepare conversation history (exclude citations from history)
                        conversation_history = [
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in st.session_state.chat_messages[:-1]  # Exclude the just-added user message
                        ]
                        
                        response_text, citations = chat_manager.get_chat_response(prompt, conversation_history)
                        
                        # Display response
                        st.markdown(response_text)
                        
                        # Display citations
                        if citations:
                            st.markdown("---")
                            st.caption("📚 **참조 문서:**")
                            for i, citation in enumerate(citations, 1):
                                filepath = citation.get('filepath', 'Unknown')
                                url = citation.get('url', '')
                                
                                # Generate SAS URL if we have blob path
                                if url:
                                    display_url = url
                                else:
                                    # Try to generate SAS URL from filepath
                                    blob_service_client = get_blob_service_client()
                                    display_url = generate_sas_url(blob_service_client, CONTAINER_NAME, filepath)
                                
                                st.markdown(f"{i}. [{filepath}]({display_url})")
                        
                        # Add assistant response to chat history
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": response_text,
                            "citations": citations
                        })
                        
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {str(e)}")
        
        # Clear chat button
        if st.session_state.chat_messages:
            if st.button("🗑️ 대화 초기화"):
                st.session_state.chat_messages = []
                st.rerun()

elif menu == "관리자 설정":
    st.subheader("⚙️ 관리자 설정")
    st.info("Azure AI Search 리소스를 초기화하거나 상태를 확인합니다.")
    
    # 인덱싱 대상 폴더 설정
    # 폴더 목록 가져오기
    folder_options = ["(전체)"]
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        # walk_blobs를 사용하여 최상위 폴더만 조회
        for blob in container_client.walk_blobs(delimiter='/'):
            if blob.name.endswith('/'):
                folder_options.append(blob.name.strip('/'))
    except Exception as e:
        st.warning(f"폴더 목록을 가져오지 못했습니다: {e}")
        folder_options.append("GULFLNG") # Fallback

    # 기본값 설정 (GULFLNG가 있으면 그걸로, 없으면 전체)
    default_idx = 0
    if "GULFLNG" in folder_options:
        default_idx = folder_options.index("GULFLNG")

    selected_folder = st.selectbox(
        "인덱싱 대상 폴더 선택", 
        folder_options, 
        index=default_idx,
        help="인덱싱할 프로젝트 폴더를 선택하세요."
    )
    
    
    # '(전체)' 선택 시 None으로 처리
    target_folder = None if selected_folder == "(전체)" else selected_folder
    
    st.info("💡 **폴더별 인덱싱**: 각 폴더는 독립적으로 인덱싱됩니다. 다른 폴더의 데이터에 영향을 주지 않습니다.")
    
    confirm_reset = st.checkbox("위 폴더를 인덱싱 대상으로 설정하고 싶습니다.", key="confirm_reset")
    
    if st.button("🚀 폴더 인덱싱 설정 (Data Source, Indexer)", disabled=not confirm_reset):
        with st.spinner("리소스 생성 중..."):
            manager = get_search_manager()
            
            # 1. Index 확인/생성 (한번만 필요)
            st.write("1. Index 확인 중...")
            success, msg = manager.create_index()
            if success:
                st.success(msg)
            else:
                st.error(msg)
                
            # 2. Data Source (폴더별)
            st.write(f"2. Data Source 생성 중... (폴더: {selected_folder})")
            success, msg, datasource_name = manager.create_data_source(
                SEARCH_DATASOURCE_NAME, 
                STORAGE_CONN_STR, 
                CONTAINER_NAME, 
                query=target_folder,
                folder_name=target_folder
            )
            if success:
                st.success(msg)
            else:
                st.error(msg)
                st.stop()  # Stop execution if datasource creation fails
                
                
            # 3. Indexer (폴더별)
            st.write(f"3. Indexer 생성 중... (폴더: {selected_folder})")
            # 기존 인덱서 삭제 (같은 폴더의 이전 설정 제거)
            manager.delete_indexer(target_folder)
            success, msg, indexer_name = manager.create_indexer(target_folder, datasource_name)
            if success:
                st.success(msg)
                st.info(f"✅ '{selected_folder}' 폴더에 대한 인덱싱 설정이 완료되었습니다. 아래 '인덱서 수동 실행'을 눌러 인덱싱을 시작하세요.")
            else:
                st.error(msg)
                
                
    st.divider()
    
    # 수동 실행 안내 및 확인
    st.info(f"📂 **현재 선택된 폴더**: {selected_folder}")
    st.markdown("수동 인덱서 실행은 선택한 폴더의 새 파일 또는 변경된 파일을 검색 엔진에 반영합니다.")
    
    confirm_run = st.checkbox("위 폴더를 인덱싱하는 것을 확인했으며, 진행하고 싶습니다.", key="confirm_run")
    
    if st.button("▶️ 인덱서 수동 실행", disabled=not confirm_run):
        manager = get_search_manager()
        success, msg = manager.run_indexer(target_folder)
        if success:
            st.success(msg)
            st.info("인덱싱이 시작되었습니다. 아래 '상태 확인' 버튼을 눌러 진행 상황을 모니터링하세요.")
        else:
            st.error(msg)
            
    st.divider()
    
    col_status, col_refresh = st.columns([3, 1])
    with col_status:
        st.markdown("### 📊 인덱싱 현황 모니터링")
    with col_refresh:
        auto_refresh = st.checkbox("자동 새로고침 (5초)", value=False)

    # 상태 확인 로직 (버튼 클릭 또는 자동 새로고침)
    if st.button("상태 및 진행률 확인") or auto_refresh:
        manager = get_search_manager()
        
        # 1. 소스 파일 개수 확인 (진행률 계산용)
        with st.spinner("소스 파일 개수 계산 중..."):
            total_blobs = manager.get_source_blob_count(STORAGE_CONN_STR, CONTAINER_NAME, folder_path=target_folder)
        
        # 2. 인덱서 상태 확인
        status_info = manager.get_indexer_status(target_folder)
        
        # 상태 언팩
        status = status_info.get("status")
        item_count = status_info.get("item_count", 0)
        failed_count = status_info.get("failed_item_count", 0)
        error_msg = status_info.get("error_message")
        errors = status_info.get("errors", [])
        warnings = status_info.get("warnings", [])
        
        # 3. 인덱스 문서 개수
        doc_count = manager.get_document_count()
        
        # UI 표시
        st.metric(label="총 소스 파일 수", value=f"{total_blobs}개")
        
        # 진행률 계산 (실제 인덱스된 문서 수 기준)
        if total_blobs > 0:
            progress = min(doc_count / total_blobs, 1.0)
        else:
            progress = 0.0
            
        st.progress(progress, text=f"인덱싱 진행률: {int(progress * 100)}% ({doc_count}/{total_blobs})")
        
        # 상태 메시지
        if status == "inProgress":
            st.info(f"⏳ 인덱싱 진행 중... (처리된 문서: {item_count}, 실패: {failed_count})")
            if auto_refresh:
                time.sleep(5)
                st.rerun()
        elif status == "success":
            st.success(f"✅ 인덱싱 완료! (총 인덱스 문서: {doc_count}개)")
        elif status == "error":
            st.error(f"❌ 인덱싱 오류 발생: {error_msg}")
        elif status == "transientFailure":
            st.warning("⚠️ 일시적 오류 발생 (재시도 중...)")
        else:
            st.write(f"상태: {status}")

        # 오류 상세 표시
        if failed_count > 0 or errors:
            st.error(f"❌ 실패한 문서: {failed_count}개")
            with st.expander("🚨 오류 상세 로그 확인", expanded=True):
                for err in errors:
                    st.write(f"- {err}")
        
        if warnings:
            with st.expander("⚠️ 경고 로그 확인"):
                for warn in warnings:
                    st.warning(f"- {warn}")






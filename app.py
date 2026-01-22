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
from doc_intel_manager import DocumentIntelligenceManager
import excel_manager

# Authentication imports
from utils.auth_manager import AuthManager
from modules.login_page import render_login_page

# -----------------------------
# 설정 및 비밀 관리
# -----------------------------
st.set_page_config(page_title="인텔리전트 다큐먼트", page_icon="🏗️", layout="centered")

# Custom CSS for larger tab labels
st.markdown("""
<style>
    /* Increase font size for tab labels */
    button[data-baseweb="tab"] {
        font-size: 20px !important;
    }
    button[data-baseweb="tab"] p {
        font-size: 20px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

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
SEARCH_INDEX_NAME = get_secret("AZURE_SEARCH_INDEX_NAME") or "pdf-search-index"
SEARCH_INDEXER_NAME = "pdf-indexer"
SEARCH_DATASOURCE_NAME = "blob-datasource"

# 4. Azure OpenAI
AZURE_OPENAI_ENDPOINT = get_secret("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = get_secret("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = get_secret("AZURE_OPENAI_DEPLOYMENT") or get_secret("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = get_secret("AZURE_OPENAI_API_VERSION")

# 5. Document Intelligence
AZURE_DOC_INTEL_ENDPOINT = get_secret("AZURE_DOC_INTEL_ENDPOINT")
AZURE_DOC_INTEL_KEY = get_secret("AZURE_DOC_INTEL_KEY")

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
    
    # Get search manager for Client-Side RAG
    search_manager = get_search_manager()
    
    return AzureOpenAIChatManager(
        endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        deployment_name=AZURE_OPENAI_DEPLOYMENT,
        api_version=AZURE_OPENAI_API_VERSION,
        search_manager=search_manager,
        storage_connection_string=STORAGE_CONN_STR,
        container_name=CONTAINER_NAME
    )

def get_doc_intel_manager():
    if not AZURE_DOC_INTEL_ENDPOINT or not AZURE_DOC_INTEL_KEY:
        st.error("Azure Document Intelligence Endpoint 또는 Key가 설정되지 않았습니다.")
        st.stop()
    return DocumentIntelligenceManager(AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY)

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
    
    if blob_name:
        # Blob SAS 사용 (파일 직접 열기 지원을 위해 content_disposition 설정)
        import mimetypes
        content_type, _ = mimetypes.guess_type(blob_name)
        if not content_type:
            content_type = "application/octet-stream"
            
        # PDF는 inline, 나머지는 attachment (또는 브라우저 기본 동작)
        # 엑셀 등은 브라우저가 알아서 다운로드 처리함
        content_disposition = "inline" if content_type == "application/pdf" else "attachment"

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            start=start,
            expiry=expiry,
            content_disposition=content_disposition, 
            content_type=content_type
        )
        
        base_url = f"https://{account_name}.blob.core.windows.net/{container_name}"
        encoded_blob_name = urllib.parse.quote(blob_name, safe='/')
        return f"{base_url}/{encoded_blob_name}?{sas_token}"
        
    else:
        # Container SAS 사용 (폴더 작업용)
        sas_token = generate_container_sas(
            account_name=account_name,
            container_name=container_name,
            account_key=account_key,
            permission=ContainerSasPermissions(write=True, list=True, read=True, delete=True),
            start=start,
            expiry=expiry
        )
        
        base_url = f"https://{account_name}.blob.core.windows.net/{container_name}"
        return f"{base_url}?{sas_token}"

# -----------------------------
# UI 구성
# -----------------------------


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

# Initialize session state for page navigation
if "page" not in st.session_state:
    st.session_state.page = "홈"

def change_page(page_name):
    st.session_state.page = page_name

# Initialize AuthManager
auth_manager = AuthManager(STORAGE_CONN_STR)

# Initialize login state
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

# Define role-based menu permissions (Fallback / Admin)
ALL_MENUS = ["홈", "번역하기", "파일 보관함", "검색 & AI 채팅", "도면/스펙 분석", "엑셀데이터 자동추출", "사진대지 자동작성", "작업계획 및 투입비 자동작성", "관리자 설정", "사용자 설정"]
GUEST_MENUS = ["홈", "사용자 설정"]

# Check if user is logged in
if not st.session_state.is_logged_in:
    render_login_page(auth_manager)
    st.stop()

# User is logged in - get their info
user_info = st.session_state.get('user_info', {})
user_role = user_info.get('role', 'guest')
user_perms = user_info.get('permissions', [])

def get_user_folder_name(user_info):
    """Get sanitized user folder name"""
    if not user_info:
        return "guest"
    # Use name but fallback to ID if empty
    name = user_info.get('name', user_info.get('id', 'guest'))
    return name.strip()

user_folder = get_user_folder_name(user_info)

if user_role == 'admin':
    available_menus = ALL_MENUS
else:
    # Use assigned permissions, ensuring mandatory menus are present
    available_menus = user_perms if user_perms else GUEST_MENUS
    # Ensure "홈" and "사용자 설정" are always available
    if "홈" not in available_menus:
        available_menus.insert(0, "홈")
    if "사용자 설정" not in available_menus:
        available_menus.append("사용자 설정")
    
    # Remove "관리자 설정" if somehow present for non-admins
    if "관리자 설정" in available_menus:
        available_menus.remove("관리자 설정")

with st.sidebar:
    # User profile
    st.markdown(f"### 👤 {user_info.get('name', 'User')}")
    st.caption(f"**{user_info.get('email', '')}**")
    st.caption(f"권한: {user_role.upper()}")
    
    if st.button("🚪 로그아웃", key="logout_btn", use_container_width=True):
        st.session_state.is_logged_in = False
        st.session_state.user_info = None
        st.rerun()
    
    st.divider()
    
    st.header("메뉴")
    # Filter menu based on user role
    menu = st.radio("이동", available_menus, key="page")
    
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

# Common Header for non-Home pages
if menu != "홈":
    st.title(menu)


if menu == "홈":
    # Use the new home_chat module with function calling support
    from home_chat import render_home_chat
    chat_manager = get_chat_manager()
    render_home_chat(chat_manager)
    
if menu == "번역하기":
    if "translate_uploader_key" not in st.session_state:
        st.session_state.translate_uploader_key = 0

    uploaded_file = st.file_uploader("번역할 문서 업로드 (PPTX, PDF, DOCX, XLSX 등)", type=["pptx", "pdf", "docx", "xlsx"], key=f"translate_{st.session_state.translate_uploader_key}")

    # 이전 번역 결과가 있으면 표시
    if "last_translation_result" in st.session_state:
        result = st.session_state.last_translation_result
        st.success("✅ 번역이 완료되었습니다!")
        st.markdown(f"[{result['file_name']} 다운로드]({result['url']})", unsafe_allow_html=True)
        
        # 결과를 지우고 싶을 수 있으므로 닫기 버튼 제공 (선택 사항)
        if st.button("결과 닫기"):
            del st.session_state.last_translation_result
            st.rerun()

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

                    # 파일명 유니크하게 처리 (UUID 제거, 덮어쓰기 허용)
                    # file_uuid = str(uuid.uuid4())[:8] 
                    original_filename = uploaded_file.name
                    input_blob_name = f"{user_folder}/documents/{original_filename}"
                    
                    # 업로드
                    blob_client = container_client.get_blob_client(input_blob_name)
                    blob_client.upload_blob(uploaded_file, overwrite=True)
                    
                    st.success("업로드 완료! 번역 요청 중...")
                    
                    # SAS 생성
                    source_url = generate_sas_url(blob_service_client, CONTAINER_NAME, input_blob_name)
                    
                    # Target URL 설정
                    target_base_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}"
                    # Target URL은 컨테이너 또는 폴더 경로여야 함 (파일 경로 불가)
                    # 사용자별 translated 폴더로 설정
                    # URL 인코딩 필요
                    encoded_user_folder = urllib.parse.quote(user_folder)
                    target_output_url = f"{target_base_url}/{encoded_user_folder}/translated/?{generate_sas_url(blob_service_client, CONTAINER_NAME).split('?')[1]}"
                    
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
                    # UUID 폴더가 없으므로 translated 폴더 전체에서 해당 파일명 검색
                    output_prefix_search = f"{user_folder}/translated/"
                    output_blobs = list(container_client.list_blobs(name_starts_with=output_prefix_search))
                    
                    # 방금 번역된 파일 찾기 (파일명 매칭)
                    # Azure 번역은 원본 파일명을 유지하거나 언어 코드를 붙임
                    target_blobs = []
                    for blob in output_blobs:
                        if original_filename in blob.name:
                            target_blobs.append(blob)
                    
                    if not target_blobs:
                        st.warning(f"결과 파일을 찾는 중입니다... (경로: {output_prefix_search})")
                        # Fallback: list all to debug
                        # all_output = list(container_client.list_blobs(name_starts_with=output_prefix_search))
                        # debug_msg = "\n".join([b.name for b in all_output[:10]])
                        # st.error(f"결과 파일을 찾을 수 없습니다.\n현재 폴더 파일 목록:\n{debug_msg}")
                    else:
                        st.subheader("다운로드")
                        for blob in target_blobs:
                            blob_name = blob.name
                            file_name = blob_name.split("/")[-1]
                            
                            # 파일명에 언어 접미사 추가 (Rename)
                            suffix = LANG_SUFFIX_OVERRIDE.get(target_lang_code, target_lang_code.upper())
                            name_part, ext_part = os.path.splitext(file_name)
                            
                            # 이미 접미사가 있는지 확인 (혹시 모를 중복 방지)
                            if not name_part.endswith(f"_{suffix}"):
                                new_file_name = f"{name_part}_{suffix}{ext_part}"
                                new_blob_name = f"{user_folder}/translated/{new_file_name}"
                                
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
                                    temp_pptx = f"temp_{original_filename}"
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
                            
                            # 결과 세션에 저장
                            st.session_state.last_translation_result = {
                                "file_name": file_name,
                                "url": download_sas
                            }
                            
                    # 성공적으로 완료되면 업로더 초기화 (키 변경)
                    st.session_state.translate_uploader_key += 1
                    time.sleep(1) # 잠시 대기
                    st.rerun()
                            
                except Exception as e:
                    st.error(f"번역 요청 중 오류 발생: {e}")

elif menu == "파일 보관함":
    # st.subheader("📂 클라우드 파일 보관함") - Removed to avoid duplication
    
    # -----------------------------
    # 1. 파일 직접 업로드 (Save)
    # -----------------------------
    with st.expander("📤 파일 직접 업로드 (번역 없이 저장)", expanded=False):
        upload_archive = st.file_uploader("보관함에 저장할 파일 선택", key="archive_upload")
        if st.button("저장하기", disabled=not upload_archive):
            try:
                blob_service_client = get_blob_service_client()
                container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                
                # file_uuid = str(uuid.uuid4())[:8]
                # Upload to {user_folder}/documents/ (Flat structure)
                blob_name = f"{user_folder}/documents/{upload_archive.name}"
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
                                    # 새 경로 생성 (기존 폴더 구조 유지)
                                    path_parts = blob.name.split("/")
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
            render_file_list(f"{user_folder}/documents/", "내 문서 (Documents)")
            
        with tab2:
            render_file_list(f"{user_folder}/translated/", "번역된 문서")
                
    except Exception as e:
        st.error(f"파일 목록을 불러오는 중 오류 발생: {e}")

elif menu == "검색 & AI 채팅":
    # Tabs for Search and Chat to preserve state
    tab1, tab2 = st.tabs(["🔍 문서 검색", "🤖 AI 채팅"])
    
    with tab1:

        st.subheader("🔍 PDF 문서 검색")
        
        # File Uploader for Document Search
        with st.expander("📤 문서 업로드 (내 문서)", expanded=False):
            doc_upload = st.file_uploader("검색할 문서 업로드", type=['pdf', 'docx', 'txt', 'pptx'], key="doc_search_upload")
            if doc_upload and st.button("업로드", key="btn_doc_upload"):
                try:
                    blob_service_client = get_blob_service_client()
                    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                    
                    # file_uuid = str(uuid.uuid4())[:8]
                    # Upload to {user_folder}/documents/ (Flat structure)
                    blob_name = f"{user_folder}/documents/{doc_upload.name}"
                    blob_client = container_client.get_blob_client(blob_name)
                    blob_client.upload_blob(doc_upload, overwrite=True)
                    st.success(f"'{doc_upload.name}' 업로드 완료! (인덱싱에 시간이 걸릴 수 있습니다)")
                except Exception as e:
                    st.error(f"업로드 실패: {e}")
        
        # Search Input
        query = st.text_input("검색어 입력", placeholder="검색할 키워드를 입력하세요...")
        
        # Search Options (Expander)
        with st.expander("⚙️ 검색 옵션 설정", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                use_semantic = st.checkbox("시맨틱 랭커", value=False, help="의미 기반 검색 (Standard Tier 이상)")
            with c2:
                search_mode_opt = st.radio("검색 모드", ["all (AND)", "any (OR)"], index=0, horizontal=True, help="all: 모든 단어 포함, any: 하나라도 포함")
                search_mode = "all" if "all" in search_mode_opt else "any"
        
        
        if query:
            with st.spinner("검색 중..."):
                search_manager = get_search_manager()
                
                # Filter by user folder
                # Construct prefix URL: https://{account}.blob.core.windows.net/{container}/{user_folder}/
                account_name = get_blob_service_client().account_name
                # Need to handle spaces in user_folder for URL
                encoded_user_folder = urllib.parse.quote(user_folder)
                prefix_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{encoded_user_folder}/"
                
                # OData filter: startswith(metadata_storage_path, 'prefix_url')
                # Also allow 'all' access for admin if needed, but user requested isolation.
                # Assuming strict isolation.
                filter_expr = f"search.ismatch('{encoded_user_folder}/*', 'metadata_storage_path') or startswith(metadata_storage_path, '{prefix_url}')"
                # Note: search.ismatch might not work on SimpleField. startswith is safer for path.
                filter_expr = f"startswith(metadata_storage_path, '{prefix_url}')"
                
                results = search_manager.search(query, filter_expr=filter_expr, use_semantic_ranker=use_semantic, search_mode=search_mode)
                
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
        st.subheader("🤖 AI 문서 도우미 (GPT-5.2)")
        st.caption("Azure OpenAI(GPT-5.2)와 문서 검색을 활용한 정확한 답변 제공")
        
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
                            try:
                                blob_service_client = get_blob_service_client()
                                display_url = generate_sas_url(blob_service_client, CONTAINER_NAME, filepath)
                            except:
                                display_url = "#"
                        
                        st.markdown(f"{i}. [{filepath}]({display_url})")
        
        # -----------------------------
        # 검색 옵션 (Chat Tab) - Bottom of chat area
        # -----------------------------
        st.write("")
        with st.expander("⚙️ 고급 검색 옵션 (RAG 설정)", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                chat_use_semantic = st.checkbox("시맨틱 랭커 사용", value=False, key="chat_use_semantic", help="의미 기반 검색을 사용하여 정확도를 높입니다.")
            with c2:
                chat_search_mode_opt = st.radio("검색 모드", ["all (AND)", "any (OR)"], index=1, horizontal=True, key="chat_search_mode", help="any: 키워드 중 하나라도 포함되면 검색 (추천)")
                chat_search_mode = "all" if "all" in chat_search_mode_opt else "any"

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
                        
                        # Pass the selected search options to the chat manager
                        response_text, citations, context = chat_manager.get_chat_response(
                            prompt, 
                            conversation_history, 
                            search_mode=chat_search_mode, 
                            use_semantic_ranker=chat_use_semantic
                        )
                        
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
        # Clear chat button
        if st.session_state.chat_messages:
            if st.button("🗑️ 대화 초기화"):
                st.session_state.chat_messages = []
                st.rerun()

elif menu == "도면/스펙 분석":
    # st.subheader("🏗️ 도면/스펙 정밀 분석 (RAG)") - Removed to avoid duplication
    st.caption("Azure Document Intelligence를 활용한 고정밀 문서 분석 및 질의응답")
    
    with st.expander("ℹ️ Document Intelligence가 왜 더 좋은가요?", expanded=False):
        st.markdown("""
        **건설 EPC 설계 담당자님께 이 서비스가 필요한 이유는 크게 3가지입니다.**

        1. **표(Table) 추출의 정확도**: 일반 OCR은 표 안의 데이터를 읽을 때 줄이 밀리거나 텍스트가 섞이기 쉽습니다. 하지만 Document Intelligence는 행과 열의 구조를 완벽히 파악하여 엑셀처럼 정교하게 데이터를 추출합니다.
        2. **레이아웃 분석**: 제목, 본문, 각주, 페이지 번호 등을 구분하여 텍스트의 우선순위를 정할 수 있습니다.
        3. **체크박스 및 서명 인식**: 설계 검토서나 승인 문서에 포함된 체크 표시나 서명 여부까지 인식할 수 있습니다.
        """)

    tab1, tab2 = st.tabs(["📤 문서 업로드 및 분석", "💬 분석 문서 채팅"])
    
    with tab1:
        st.markdown(f"### 1. 분석할 문서 업로드 ({user_folder}/drawings 폴더)")
        
        if "drawing_uploader_key" not in st.session_state:
            st.session_state.drawing_uploader_key = 0
            
        uploaded_files = st.file_uploader("PDF 도면, 스펙, 사양서 등을 업로드하세요", accept_multiple_files=True, type=['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'], key=f"drawing_{st.session_state.drawing_uploader_key}")
        
        if uploaded_files:
            if st.button("업로드 및 분석 시작"):
                blob_service_client = get_blob_service_client()
                container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                doc_intel_manager = get_doc_intel_manager()
                search_manager = get_search_manager()
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_files = len(uploaded_files)
                
                for idx, file in enumerate(uploaded_files):
                    try:
                        # Normalize filename to NFC (to match search query logic)
                        import unicodedata
                        safe_filename = unicodedata.normalize('NFC', file.name)
                        
                        status_text.text(f"처리 중 ({idx+1}/{total_files}): {safe_filename}")
                        
                        blob_path = f"{user_folder}/drawings/{safe_filename}"
                        # 2. Upload to Azure Blob Storage
                        status_text.text(f"업로드 중 ({idx+1}/{total_files}): {file.name}...")
                        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_path)
                        
                        # CRITICAL: Reset file pointer to ensure full upload
                        file.seek(0)
                        blob_client.upload_blob(file, overwrite=True)
                        
                        # Verify upload size
                        props = blob_client.get_blob_properties()
                        if props.size != file.size:
                            st.error(f"⚠️ 파일 업로드 크기 불일치! (원본: {file.size}, 업로드됨: {props.size})")
                        else:
                            print(f"DEBUG: Upload verified. Size: {props.size} bytes")

                        # Generate SAS Token for Document Intelligence access
                        sas_token = generate_blob_sas(
                            account_name=blob_service_client.account_name,
                            container_name=CONTAINER_NAME,
                            blob_name=blob_path,
                            account_key=blob_service_client.credential.account_key,
                            permission=BlobSasPermissions(read=True),
                            expiry=datetime.utcnow() + timedelta(hours=1)
                        )
                        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{urllib.parse.quote(blob_path)}?{sas_token}"
                        
                        # 3. Analyze with Document Intelligence
                        status_text.text(f"분석 중 ({idx+1}/{total_files}): {file.name} - Document Intelligence Layout 모델 실행...")
                        page_chunks = doc_intel_manager.analyze_document(blob_url)
                        
                        # 4. Indexing (Push to Search) - One document per page
                        # 4. Indexing (Push to Search) - One document per page
                        detected_pages = [chunk['page_number'] for chunk in page_chunks]
                        status_text.text(f"인덱싱 중 ({idx+1}/{total_files}): {safe_filename} - {len(page_chunks)} 페이지 발견 (Pages: {detected_pages})")
                        
                        if len(page_chunks) == 0:
                            st.warning(f"⚠️ 경고: '{file.name}'에서 페이지를 찾을 수 없습니다.")
                        
                        documents_to_index = []
                        for page_chunk in page_chunks:
                            # Create document object for each page
                            # ID must be unique and URL safe. Include page number in ID.
                            import base64
                            page_id_str = f"{blob_path}_page_{page_chunk['page_number']}"
                            doc_id = base64.urlsafe_b64encode(page_id_str.encode('utf-8')).decode('utf-8')
                            
                            document = {
                                "id": doc_id,
                                "content": page_chunk['content'],
                                "content_exact": page_chunk['content'],
                                "metadata_storage_name": f"{safe_filename} (p.{page_chunk['page_number']})",
                                "metadata_storage_path": f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_path}#page={page_chunk['page_number']}",
                                "metadata_storage_last_modified": datetime.utcnow().isoformat() + "Z",
                                "metadata_storage_size": file.size,
                                "metadata_storage_content_type": file.type,
                                "project": "drawings_analysis"  # Tag for filtering
                            }
                            documents_to_index.append(document)
                        
                        # Batch upload all pages
                        if documents_to_index:
                            success, msg = search_manager.upload_documents(documents_to_index)
                            if not success:
                                st.error(f"인덱싱 실패 ({file.name}): {msg}")
                        
                        progress_bar.progress((idx + 1) / total_files)
                        
                    except Exception as e:
                        st.error(f"오류 발생 ({file.name}): {str(e)}")
                
                status_text.text("모든 작업이 완료되었습니다!")
                st.success("업로드, 분석 및 인덱싱이 완료되었습니다.")
                
                # 성공적으로 완료되면 업로더 초기화
                st.session_state.drawing_uploader_key += 1
                time.sleep(2)
                st.rerun()

    with tab2:
        st.markdown("### 💬 도면/스펙 전문 채팅 (GPT-5.2)")
        
        # Display analyzed documents
        st.markdown("#### 📋 분석된 문서 목록")
        try:
            blob_service_client = get_blob_service_client()
            container_client = blob_service_client.get_container_client(CONTAINER_NAME)
            
            # List files in user's drawings folder
            prefix = f"{user_folder}/drawings/"
            blobs = container_client.list_blobs(name_starts_with=prefix)
            blob_list = []
            available_filenames = []
            for blob in blobs:
                if not blob.name.endswith('/'):  # Skip folder markers
                    filename = blob.name.replace(prefix, '')
                    blob_list.append({
                        'name': filename,
                        'size': blob.size,
                        'modified': blob.last_modified
                    })
                    available_filenames.append(filename)
            
            # Sort by modified date (most recent first)
            blob_list.sort(key=lambda x: x['modified'], reverse=True)
            
            selected_filenames = []
            
            if blob_list:
                st.info(f"총 {len(blob_list)}개의 문서가 분석되어 있습니다. 분석할 문서를 선택하세요.")
                
                # Add "Select All" checkbox
                def toggle_all():
                    new_state = st.session_state.select_all_files
                    for key in st.session_state.keys():
                        if key.startswith("chk_"):
                            st.session_state[key] = new_state

                select_all = st.checkbox("전체 선택", value=True, key="select_all_files", on_change=toggle_all)
                
                # Display as expandable list
                with st.expander("📄 문서 목록 및 선택", expanded=True):
                    for idx, blob_info in enumerate(blob_list, 1):
                        col0, col1, col2, col3 = st.columns([0.5, 4, 1.2, 1])
                        with col0:
                            # Checkbox for selection
                            is_selected = st.checkbox(f"select_{idx}", value=select_all, key=f"chk_{blob_info['name']}", label_visibility="collapsed")
                            if is_selected:
                                selected_filenames.append(blob_info['name'])
                        
                        with col1:
                            size_mb = blob_info['size'] / (1024 * 1024)
                            modified_str = blob_info['modified'].strftime('%Y-%m-%d %H:%M')
                            st.markdown(f"**{blob_info['name']}** ({size_mb:.2f} MB)")
                        
                        with col2:
                            # JSON Download Logic
                            json_key = f"json_data_{blob_info['name']}"
                            
                            if json_key not in st.session_state:
                                if st.button("JSON 생성", key=f"gen_json_{blob_info['name']}"):
                                    with st.spinner("데이터 가져오는 중..."):
                                        search_manager = get_search_manager()
                                        docs = search_manager.get_document_json(blob_info['name'])
                                        if docs:
                                            import json
                                            json_str = json.dumps(docs, ensure_ascii=False, indent=2)
                                            st.session_state[json_key] = json_str
                                            st.rerun()
                                        else:
                                            st.error("데이터가 없습니다.")
                            else:
                                # Show download button
                                json_data = st.session_state[json_key]
                                st.download_button(
                                    label="💾 다운로드",
                                    data=json_data,
                                    file_name=f"{blob_info['name']}.json",
                                    mime="application/json",
                                    key=f"dl_json_{blob_info['name']}"
                                )

                        with col3:
                            if st.button("🗑️ 삭제", key=f"del_{blob_info['name']}"):
                                try:
                                    # 1. Delete from Blob Storage
                                    blob_client = container_client.get_blob_client(f"drawings/{blob_info['name']}")
                                    blob_client.delete_blob()
                                    
                                    # 2. Delete from Search Index
                                    search_manager = get_search_manager()
                                    
                                    # Find docs to delete
                                    safe_filename = blob_info['name'].replace("'", "''")
                                    
                                    # Clean up index
                                    results = search_manager.search_client.search(
                                        search_text="*",
                                        filter=f"project eq 'drawings_analysis'",
                                        select=["id", "metadata_storage_name"]
                                    )
                                    
                                    ids_to_delete = []
                                    import unicodedata
                                    safe_blob_name = unicodedata.normalize('NFC', blob_info['name'])
                                    
                                    for doc in results:
                                        if doc['metadata_storage_name'].startswith(safe_blob_name):
                                            ids_to_delete.append({"id": doc['id']})
                                    
                                    if ids_to_delete:
                                        search_manager.search_client.delete_documents(documents=ids_to_delete)
                                    
                                    # Clear JSON state if exists
                                    json_key = f"json_data_{blob_info['name']}"
                                    if json_key in st.session_state:
                                        del st.session_state[json_key]

                                    st.success(f"{blob_info['name']} 삭제 완료")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"삭제 실패: {e}")
            else:
                st.warning("분석된 문서가 없습니다. '문서 업로드 및 분석' 탭에서 문서를 업로드하세요.")
        except Exception as e:
            st.error(f"문서 목록을 불러오는 중 오류 발생: {e}")
        
        st.divider()
        
        # Chat Interface (Similar to main chat but focused)
        if "rag_chat_messages" not in st.session_state:
            st.session_state.rag_chat_messages = []
            
        for message in st.session_state.rag_chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "citations" in message and message["citations"]:
                    st.markdown("---")
                    st.caption("📚 **참조 문서:**")
                    for i, citation in enumerate(message["citations"], 1):
                        filepath = citation.get('filepath', 'Unknown')
                        url = citation.get('url', '')
                        
                        # Generate SAS URL for browser viewing
                        if url:
                            display_url = url
                        else:
                            try:
                                blob_service_client = get_blob_service_client()
                                # Generate SAS with inline content disposition
                                sas_token = generate_blob_sas(
                                    account_name=blob_service_client.account_name,
                                    container_name=CONTAINER_NAME,
                                    blob_name=filepath,
                                    account_key=blob_service_client.credential.account_key,
                                    permission=BlobSasPermissions(read=True),
                                    expiry=datetime.utcnow() + timedelta(hours=1),
                                    content_disposition="inline",
                                    content_type="application/pdf"
                                )
                                display_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{urllib.parse.quote(filepath)}?{sas_token}"
                                
                                # Add page number if available
                                page_num = citation.get('page')
                                if page_num:
                                    display_url += f"#page={page_num}"
                            except:
                                display_url = "#"
                        
                        st.markdown(f"{i}. [{filepath}]({display_url})")

        if prompt := st.chat_input("도면이나 스펙에 대해 질문하세요..."):
            st.session_state.rag_chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("분석 중..."):
                    try:
                        chat_manager = get_chat_manager()
                        
                        conversation_history = [
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in st.session_state.rag_chat_messages[:-1]
                        ]
                        
                        # Use 'any' search mode for better recall (find documents even with partial keyword match)
                        # This is important because technical drawings may have specific terms
                        # Filter to only search documents from the drawings folder
                        # Pass selected_filenames for specific file filtering
                        # If selected_filenames is empty (user deselected all), we should probably warn or search nothing.
                        # But for now let's pass it. If empty, the chat manager might search nothing or all depending on logic.
                        # Actually, let's default to all if none selected? No, user explicitly deselected.
                        # Let's pass the list as is.
                        
                        # Note: selected_filenames comes from the UI loop above
                        current_files = locals().get('selected_filenames', [])
                        
                        response_text, citations, context = chat_manager.get_chat_response(
                            prompt, 
                            conversation_history,
                            search_mode="any",  # Changed from 'all' to 'any' for better recall
                            use_semantic_ranker=False,  # Disable semantic ranker if using Basic tier
                            filter_expr="project eq 'drawings_analysis'",  # Only search drawings documents
                            available_files=current_files
                        )
                        
                        st.markdown(response_text)
                        
                        if citations:
                            st.markdown("---")
                            st.caption("📚 **참조 문서:**")
                            for i, citation in enumerate(citations, 1):
                                filepath = citation.get('filepath', 'Unknown')
                                url = citation.get('url', '')
                                
                                # Generate SAS URL for browser viewing
                                if url:
                                    display_url = url
                                else:
                                    try:
                                        blob_service_client = get_blob_service_client()
                                        # Generate SAS with inline content disposition
                                        sas_token = generate_blob_sas(
                                            account_name=blob_service_client.account_name,
                                            container_name=CONTAINER_NAME,
                                            blob_name=filepath,
                                            account_key=blob_service_client.credential.account_key,
                                            permission=BlobSasPermissions(read=True),
                                            expiry=datetime.utcnow() + timedelta(hours=1),
                                            content_disposition="inline",
                                            content_type="application/pdf"
                                        )
                                        display_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{urllib.parse.quote(filepath)}?{sas_token}"
                                        
                                        # Add page number if available
                                        page_num = citation.get('page')
                                        if page_num:
                                            display_url += f"#page={page_num}"
                                    except:
                                        display_url = "#"
                                
                                st.markdown(f"{i}. [{filepath}]({display_url})")
                        
                        # Debug: Show Context
                        with st.expander("🔍 검색된 컨텍스트 확인 (Debug Context)", expanded=False):
                            st.text_area("LLM에게 전달된 원문 데이터", value=context, height=300)

                        st.session_state.rag_chat_messages.append({
                            "role": "assistant",
                            "content": response_text,
                            "citations": citations,
                            "context": context
                        })
                        st.rerun()


                    except Exception as e:
                        st.error(f"오류: {e}")
                        import traceback
                        st.code(traceback.format_exc())

    # -----------------------------
    # 디버깅 도구 (Debug Tools)
    # -----------------------------
    with st.expander("🛠️ 인덱스 및 검색 진단 (Debug Tools)", expanded=False):
        st.warning("이 도구는 검색 문제를 진단하기 위한 것입니다.")
        
        if st.button("🔍 인덱스 상태 및 검색 테스트 실행"):
            try:
                search_manager = get_search_manager()
                client = search_manager.search_client
                
                st.write("### 1. 인덱스 문서 확인 (project='drawings_analysis')")
                results = client.search(search_text="*", filter="project eq 'drawings_analysis'", select=["id", "metadata_storage_name", "project"], top=20)
                
                docs = list(results)
                st.write(f"총 {len(docs)}개의 문서가 발견되었습니다.")
                
                if docs:
                    for doc in docs:
                        st.code(f"ID: {doc['id']}\nName: {doc['metadata_storage_name']}\nProject: {doc['project']}")
                else:
                    st.error("인덱스에 'drawings_analysis' 프로젝트 문서가 없습니다!")
                
                st.write("---")
                st.write("### 2. 키워드 검색 테스트 ('foundation loading data')")
                search_results = client.search(search_text="foundation loading data", filter="project eq 'drawings_analysis'", top=5, select=["metadata_storage_name", "content"])
                search_docs = list(search_results)
                
                st.write(f"검색 결과: {len(search_docs)}개")
                for doc in search_docs:
                    st.text(f"Match: {doc['metadata_storage_name']}")
                    st.caption(f"Content: {doc['content'][:200]}...")
                
                st.write("---")
                st.write("### 3. 와일드카드 검색 테스트 ('*')")
                wild_results = client.search(search_text="*", filter="project eq 'drawings_analysis'", top=5, select=["metadata_storage_name", "content"])
                wild_docs = list(wild_results)
                
                st.write(f"검색 결과: {len(wild_docs)}개")
                for doc in wild_docs:
                    st.text(f"Match: {doc['metadata_storage_name']}")
                    st.caption(f"Content: {doc['content'][:200]}...")
                    
            except Exception as e:
                st.error(f"진단 중 오류 발생: {str(e)}")
                st.code(str(e))
        
        st.write("---")
        st.write("### 🧪 사용자 지정 검색 테스트")
        debug_query = st.text_input("검색어 입력 (예: filter element)", key="debug_query")
        if st.button("검색 테스트 실행", key="run_debug_search"):
            if debug_query:
                try:
                    search_manager = get_search_manager()
                    client = search_manager.search_client
                    
                    st.write(f"Query: '{debug_query}'")
                    # Use 'any' search mode to match behavior
                    results = client.search(
                        search_text=debug_query, 
                        filter="project eq 'drawings_analysis'", 
                        search_mode="any",
                        select=["metadata_storage_name", "content"],
                        top=10
                    )
                    docs = list(results)
                    st.write(f"검색 결과: {len(docs)}개")
                    
                    if docs:
                        for doc in docs:
                            st.text(f"Match: {doc['metadata_storage_name']}")
                            st.caption(f"Content: {doc['content'][:200]}...")
                    else:
                        st.warning("검색 결과가 없습니다.")
                except Exception as e:
                    st.error(f"검색 오류: {e}")

        st.write("---")
        st.write("### ⚠️ 인덱스 초기화")
        if st.button("🗑️ 모든 도면 데이터 삭제 (Index & Blob)", type="primary"):
            try:
                # 1. Delete all blobs in drawings/
                blob_service_client = get_blob_service_client()
                container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                blobs = container_client.list_blobs(name_starts_with="drawings/")
                for blob in blobs:
                    container_client.delete_blob(blob.name)
                
                # 2. Delete all docs in index with project='drawings_analysis'
                search_manager = get_search_manager()
                results = search_manager.search_client.search(
                    search_text="*",
                    filter="project eq 'drawings_analysis'",
                    select=["id"]
                )
                ids_to_delete = [{"id": doc['id']} for doc in results]
                if ids_to_delete:
                    # Delete in batches of 1000 if needed, but for now simple
                    search_manager.search_client.delete_documents(documents=ids_to_delete)
                
                st.success("모든 도면 데이터가 삭제되었습니다. 이제 파일을 다시 업로드하세요.")
                st.rerun()
            except Exception as e:
                st.error(f"초기화 실패: {e}")

        if st.button("🧹 '페이지 번호 없는' 중복 데이터 정리 (권장)", help="인덱스에서 (p.N) 형식이 아닌 잘못된 데이터를 찾아 삭제합니다."):
            try:
                search_manager = get_search_manager()
                results = search_manager.search_client.search(
                    search_text="*",
                    filter="project eq 'drawings_analysis'",
                    select=["id", "metadata_storage_name"],
                    top=1000
                )
                
                ids_to_delete = []
                count = 0
                for doc in results:
                    name = doc['metadata_storage_name']
                    # Delete if it doesn't contain "(p." (standard page suffix)
                    if "(p." not in name:
                        ids_to_delete.append({"id": doc['id']})
                        count += 1
                
                if ids_to_delete:
                    search_manager.search_client.delete_documents(documents=ids_to_delete)
                    st.success(f"정리 완료! {count}개의 중복/잘못된 문서를 삭제했습니다.")
                    st.rerun()
                else:
                    st.info("삭제할 잘못된 데이터가 없습니다. 인덱스가 깨끗합니다! ✨")
                    
            except Exception as e:
                st.error(f"정리 중 오류 발생: {e}")
        with st.expander("📊 선택된 파일 토큰 분석 (Token Analyzer)", expanded=False):
            st.caption("특정 파일의 인덱스 내용을 분석하여 토큰 사용량을 확인합니다.")
            target_file_input = st.text_input("분석할 파일명 (일부만 입력해도 됨)", value="PH20-810-EC115-00540")
            
            if st.button("분석 실행", key="analyze_token_btn"):
                try:
                    search_manager = get_search_manager()
                    # Search for chunks matching the filename
                    results = search_manager.search_client.search(
                        search_text="*",
                        filter=f"search.ismatch('{target_file_input}', 'metadata_storage_name')",
                        select=["metadata_storage_name", "content", "metadata_storage_path"]
                    )
                    
                    results_list = list(results)
                    st.info(f"검색된 청크(Chunk) 수: {len(results_list)}개")
                    
                    total_chars = 0
                    for i, doc in enumerate(results_list):
                        content = doc.get('content', '')
                        char_count = len(content)
                        total_chars += char_count
                        
                        with st.expander(f"Chunk {i+1}: {doc.get('metadata_storage_name')} ({char_count}자)"):
                            st.code(content[:1000] + ("..." if len(content) > 1000 else ""))
                    
                    st.divider()
                    st.metric("총 글자 수 (Total Characters)", f"{total_chars:,}")
                    est_tokens = int(total_chars / 4)
                    st.metric("예상 토큰 수 (Estimated Tokens)", f"{est_tokens:,}")
                    
                    if est_tokens > 5000:
                        st.warning(f"⚠️ 토큰 수가 많습니다 ({est_tokens} > 5000). AI 답변 생성 시 'Token Limit Exceeded' 오류가 발생할 수 있습니다.")
                    else:
                        st.success(f"✅ 토큰 수가 적절합니다 ({est_tokens}).")
                        
                except Exception as e:
                    st.error(f"분석 실패: {e}")
        
        if st.button("🗑️ 대화 초기화", key="clear_rag_chat"):
            st.session_state.rag_chat_messages = []
            st.rerun()

    st.markdown("---")

if menu == "엑셀데이터 자동추출":
    # Integrated Excel Tool
    excel_manager.render_excel_tool()

if menu == "사진대지 자동작성":
    st.caption("건설 현장 사진을 업로드하여 Excel 사진대지를 자동으로 생성합니다.")
    
    # Embed Photo Log app via iframe
    st.components.v1.iframe(
        src="https://photo-log-a0215.web.app/",
        height=800,
        scrolling=True
    )

if menu == "작업계획 및 투입비 자동작성":
    st.caption("작업 계획을 수립하고 투입비를 자동으로 산출합니다.")
    
    # Embed Work Schedule app via iframe
    st.components.v1.iframe(
        src="https://workschedule-7b1cf.web.app/",
        height=800,
        scrolling=True
    )

if menu == "관리자 설정":
    # st.subheader("⚙️ 관리자 설정") - Removed to avoid duplication
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
                
            # 2.5 Skillset (OCR) - Optional
            skillset_name = None
            enable_ocr = st.checkbox("📸 OCR(이미지 텍스트 추출) 활성화", value=False, help="PDF 도면이나 이미지 파일에서 텍스트를 추출합니다. Azure AI Services 키가 필요하며 비용이 발생할 수 있습니다.")
            
            if enable_ocr:
                st.write(f"2.5. Skillset (OCR) 생성 중...")
                # Use Translator Key as Cognitive Services Key (assuming it's a multi-service key)
                cog_key = st.secrets.get("AZURE_TRANSLATOR_KEY", os.environ.get("AZURE_TRANSLATOR_KEY"))
                
                if not cog_key:
                    st.warning("⚠️ Azure AI Services 키(AZURE_TRANSLATOR_KEY)가 설정되지 않아 OCR을 건너뜁니다.")
                else:
                    skillset_name = f"skillset-{target_folder}" if target_folder else "skillset-all"
                    success, msg = manager.create_skillset(skillset_name, cog_key)
                    if success:
                        st.success(msg)
                    else:
                        st.error(f"Skillset 생성 실패: {msg}")
                        skillset_name = None # Fallback to no skillset
                
            # 3. Indexer (폴더별)
            st.write(f"3. Indexer 생성 중... (폴더: {selected_folder})")
            # 기존 인덱서 삭제 (같은 폴더의 이전 설정 제거)
            manager.delete_indexer(target_folder)
            success, msg, indexer_name = manager.create_indexer(target_folder, datasource_name, skillset_name=skillset_name)
            if success:
                st.success(msg)
                st.info(f"✅ '{selected_folder}' 폴더에 대한 인덱싱 설정이 완료되었습니다. 아래 '인덱서 수동 실행'을 눌러 인덱싱을 시작하세요.")
            else:
                st.error(msg)
    
    st.divider()
    
    # ------------------------------------------------------------------
    # 4. 인덱스 내용 조회 (디버깅용)
    # ------------------------------------------------------------------
    st.subheader("🔍 인덱스 내용 조회 (OCR 확인용)")
    with st.expander("특정 파일의 인덱싱된 내용 확인하기"):
        target_filename = st.text_input("확인할 파일명 (예: drawing.pdf)", help="정확한 파일명을 입력하세요.")
        if st.button("내용 조회"):
            if target_filename:
                manager = get_search_manager()
                with st.spinner("조회 중..."):
                    content = manager.get_document_content(target_filename)
                    st.text_area("인덱싱된 내용 (앞부분 2000자)", content[:2000], height=300)
            else:
                st.warning("파일명을 입력하세요.")

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
            
    # Add Delete Indexer Button
    if st.button("🛑 인덱서 삭제 (자동 인덱싱 중지)", help="자동으로 실행되는 인덱서를 삭제하여 중복 인덱싱을 방지합니다."):
        manager = get_search_manager()
        indexer_name = f"indexer-{target_folder}" if target_folder else "indexer-all"
        try:
            manager.indexer_client.delete_indexer(indexer_name)
            st.success(f"인덱서 '{indexer_name}'가 삭제되었습니다. 이제 자동 인덱싱이 중지됩니다.")
        except Exception as e:
            st.error(f"인덱서 삭제 실패: {e}")
            
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

if menu == "사용자 설정":
    from modules.user_settings_module import render_user_settings
    render_user_settings(auth_manager)



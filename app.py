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
import fitz # PyMuPDF for page count

# Search Manager Import
from search_manager import AzureSearchManager

# Chat Manager Import  
from chat_manager_v2 import AzureOpenAIChatManager
from doc_intel_manager import DocumentIntelligenceManager
import excel_manager

# Authentication imports
from utils.auth_manager import AuthManager
from modules.login_page import render_login_page
import extra_streamlit_components as stx

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

def generate_sas_url(blob_service_client, container_name, blob_name=None, permission="r", expiry_hours=1, content_disposition=None):
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
        if content_disposition is None:
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

# Initialize Cookie Manager
# Initialize Cookie Manager
cookie_manager = stx.CookieManager(key="auth_cookie_manager")

# Initialize login state
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

# Check for existing session cookie (Auto-login)
if not st.session_state.is_logged_in and not st.session_state.get('just_logged_out', False):
    try:
        auth_email = cookie_manager.get(cookie="auth_email")
        if auth_email:
            # Validate email exists in auth_manager
            user = auth_manager.get_user_by_email(auth_email)
            if user:
                st.session_state.is_logged_in = True
                st.session_state.user_info = user
                st.toast(f"자동 로그인되었습니다: {user.get('name')}")
    except Exception as e:
        print(f"Cookie check failed: {e}")

# Check if user is logged in
if not st.session_state.is_logged_in:
    render_login_page(auth_manager, cookie_manager)
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

# Define role-based menu permissions (Fallback / Admin)
ALL_MENUS = ["홈", "번역하기", "파일 보관함", "검색 & AI 채팅", "도면/스펙 비교", "엑셀데이터 자동추출", "사진대지 자동작성", "작업계획 및 투입비 자동작성", "관리자 설정", "사용자 설정", "디버그 (Debug)"]
GUEST_MENUS = ["홈", "사용자 설정"]

if user_role == 'admin':
    available_menus = ALL_MENUS
else:
    # Use assigned permissions, ensuring mandatory menus are present
    available_menus = user_perms if user_perms else GUEST_MENUS
    
    # Map old menu names to new names (Migration fix)
    available_menus = [
        "도면/스펙 비교" if menu == "도면/스펙 분석" else menu 
        for menu in available_menus
    ]
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
        st.session_state.just_logged_out = True # Prevent immediate auto-login
        # Delete cookie
        cookie_manager.delete("auth_email")
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
                    input_blob_name = f"{user_folder}/original/{original_filename}"
                    
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
    
    st.divider()
    
    if st.button("🔄 목록 새로고침"):
        st.rerun()
        
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        
        # 탭으로 Input/Output 구분
        tab1, tab2 = st.tabs(["원본 문서 (Input)", "번역된 문서 (Output)"])
        
        def render_file_list(prefixes, tab_name):
            all_blobs = []
            for prefix in prefixes:
                blobs = list(container_client.list_blobs(name_starts_with=prefix))
                all_blobs.extend(blobs)
            
            # 중복 제거 (혹시 모를 경우 대비)
            unique_blobs = {b.name: b for b in all_blobs}.values()
            blobs = list(unique_blobs)
            blobs.sort(key=lambda x: x.creation_time, reverse=True)
            
            if not blobs:
                st.info(f"{tab_name}에 파일이 없습니다.")
                return

            for i, blob in enumerate(blobs):
                file_name = blob.name.split("/")[-1]
                creation_time = blob.creation_time.strftime('%Y-%m-%d %H:%M')
                
                # 폴더 경로 표시 (관리자 편의)
                folder_path = "/".join(blob.name.split("/")[:-1])
                
                with st.container():
                    col1, col2, col3 = st.columns([6, 2, 2])
                    
                    with col1:
                        sas_url = generate_sas_url(blob_service_client, CONTAINER_NAME, blob.name)
                        st.markdown(f"**[{file_name}]({sas_url})**")
                        st.caption(f"📂 {folder_path} | 📅 {creation_time} | 📦 {blob.size / 1024:.1f} KB")
                    
                    with col2:
                        # 수정 (이름 변경)
                        with st.popover("수정"):
                            new_name = st.text_input("새 파일명", value=file_name, key=f"rename_{i}_{blob.name}")
                            if st.button("이름 변경", key=f"btn_rename_{i}_{blob.name}"):
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
            input_prefixes = [f"{user_folder}/documents/"]
            if user_role == 'admin':
                input_prefixes.extend(["input/", "gulflng/"])
            render_file_list(input_prefixes, "내 문서 (Documents)")
            
        with tab2:
            output_prefixes = [f"{user_folder}/translated/"]
            if user_role == 'admin':
                output_prefixes.extend(["output/"])
            render_file_list(output_prefixes, "번역된 문서")
                
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
                # Search Filter Logic
                if user_role == 'admin':
                    # Admin can search everything
                    filter_expr = None
                else:
                    # Regular users are restricted to their folder
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
                        response_text, citations, context, final_filter, search_results = chat_manager.get_chat_response(
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
                            "citations": citations,
                            "context": context,
                            "debug_filter": final_filter
                        })
                        
                        # Debug: Show Context
                        with st.expander("🔍 검색된 컨텍스트 확인 (Debug Context)", expanded=False):
                            if final_filter:
                                st.caption(f"**OData Filter:** `{final_filter}`")
                            st.text_area("LLM에게 전달된 원문 데이터", value=context, height=300)
                        
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {str(e)}")
        
        # Clear chat button
        # Clear chat button
        if st.session_state.chat_messages:
            if st.button("🗑️ 대화 초기화"):
                st.session_state.chat_messages = []
                st.rerun()

elif menu == "도면/스펙 비교":
    # st.subheader("🏗️ 도면/스펙 정밀 분석 (RAG)") - Removed to avoid duplication
    
    tab1, tab2 = st.tabs(["📤 문서 업로드", "💬 AI분석"])
    
    with tab1:
        
        if "drawing_uploader_key" not in st.session_state:
            st.session_state.drawing_uploader_key = 0
            
        # High Resolution OCR Toggle
        use_high_res = st.toggle("고해상도 OCR 적용 (도면 미세 글자 추출용)", value=False, help="복잡한 도면의 작은 글씨를 더 정확하게 읽습니다. 분석 시간이 더 오래 걸릴 수 있습니다.")
        
        uploaded_files = st.file_uploader("PDF 도면, 스펙, 사양서 등을 업로드하세요", accept_multiple_files=True, type=['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'], key=f"drawing_{st.session_state.drawing_uploader_key}")
        
        if uploaded_files:
            if "analysis_status" not in st.session_state:
                st.session_state.analysis_status = {}
                
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
                        
                        # Initialize status
                        st.session_state.analysis_status[safe_filename] = {
                            "status": "Extracting",
                            "total_pages": 0,
                            "processed_pages": 0,
                            "chunks": {},
                            "error": None
                        }
                        
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
                        
                        # 3. Analyze with Document Intelligence (Chunked)
                        file.seek(0)
                        pdf_data = file.read()
                        doc = fitz.open(stream=pdf_data, filetype="pdf")
                        total_pages = doc.page_count
                        file.seek(0)
                        
                        status_text.text(f"분석 준비 중 ({idx+1}/{total_files}): {file.name} (총 {total_pages} 페이지)")
                        
                        st.session_state.analysis_status[safe_filename]["total_pages"] = total_pages
                        
                        chunk_size = 50
                        page_chunks = []
                        
                        for start_page in range(1, total_pages + 1, chunk_size):
                            end_page = min(start_page + chunk_size - 1, total_pages)
                            page_range = f"{start_page}-{end_page}"
                            
                            st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Extracting"
                            status_text.text(f"분석 중 ({idx+1}/{total_files}): {file.name} - 페이지 {page_range} 분석 중...")
                            
                            # Retry logic for each chunk
                            max_retries = 3
                            for retry in range(max_retries):
                                try:
                                    chunks = doc_intel_manager.analyze_document(blob_url, page_range=page_range, high_res=use_high_res)
                                    page_chunks.extend(chunks)
                                    st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Ready"
                                    st.session_state.analysis_status[safe_filename]["processed_pages"] += len(chunks)
                                    break
                                except Exception as e:
                                    if retry == max_retries - 1:
                                        st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Failed"
                                        st.session_state.analysis_status[safe_filename]["error"] = str(e)
                                        raise e
                                    
                                    # Transient error - show friendly message
                                    wait_time = 5 * (retry + 1)
                                    status_text.text(f"⏳ 일시적 지연으로 재연결 중 ({retry+1}/{max_retries}): {file.name} - 페이지 {page_range} (약 {wait_time}초 대기)...")
                                    time.sleep(wait_time)
                        
                        # 4. Indexing
                        st.session_state.analysis_status[safe_filename]["status"] = "Indexing"
                        
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
                                "project": "drawings_analysis",  # Tag for filtering
                                "page_number": page_chunk['page_number'],
                                "filename": safe_filename
                            }
                            documents_to_index.append(document)
                        
                        # Batch upload all pages (50 pages at a time to avoid request size limits)
                        if documents_to_index:
                            batch_size = 50
                            for i in range(0, len(documents_to_index), batch_size):
                                batch = documents_to_index[i:i + batch_size]
                                status_text.text(f"인덱싱 중 ({idx+1}/{total_files}): {safe_filename} - 배치 전송 중 ({i//batch_size + 1}/{(len(documents_to_index)-1)//batch_size + 1})")
                                success, msg = search_manager.upload_documents(batch)
                                if not success:
                                    st.error(f"인덱싱 실패 ({file.name}, 배치 {i//batch_size + 1}): {msg}")
                                    break
                            
                            # 5. Save Analysis JSON to Blob Storage (Dual Retrieval Strategy)
                            # This allows exact retrieval by filename without AI Search
                            status_text.text(f"분석 결과 저장 중 ({idx+1}/{total_files}): {safe_filename}...")
                            search_manager.upload_analysis_json(container_client, user_folder, safe_filename, page_chunks)
                        
                        st.session_state.analysis_status[safe_filename]["status"] = "Ready"
                        progress_bar.progress((idx + 1) / total_files)
                        
                    except Exception as e:
                        st.error(f"오류 발생 ({file.name}): {str(e)}")
                
                status_text.text("모든 작업이 완료되었습니다!")
                st.success("업로드, 분석 및 인덱싱이 완료되었습니다.")
                
                # 성공적으로 완료되면 업로더 초기화
                st.session_state.drawing_uploader_key += 1
                time.sleep(2)
                st.rerun()

        # 📊 분석 모니터링 대시보드
        if "analysis_status" in st.session_state and st.session_state.analysis_status:
            st.divider()
            st.markdown("#### 📊 분석 모니터링 대시보드")
            for filename, info in st.session_state.analysis_status.items():
                status_color = "green" if info['status'] == "Ready" else "orange" if info['status'] != "Failed" else "red"
                with st.expander(f":{status_color}[{filename}] - {info['status']}", expanded=(info['status'] != "Ready")):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**전체 상태:** {info['status']}")
                        progress = info['processed_pages'] / info['total_pages'] if info['total_pages'] > 0 else 0
                        st.progress(progress)
                        st.write(f"**진행도:** {info['processed_pages']} / {info['total_pages']} 페이지 완료")
                    
                    if info['error']:
                        st.error(f"**최근 오류:** {info['error']}")
                    
                    # 세부 청크 상태
                    if info['chunks']:
                        st.markdown("---")
                        st.caption("🧩 **페이지 청크별 상태**")
                        chunk_cols = st.columns(4)
                        for i, (chunk_range, chunk_status) in enumerate(info['chunks'].items()):
                            with chunk_cols[i % 4]:
                                if chunk_status == "Ready":
                                    st.success(f"✅ {chunk_range}")
                                elif chunk_status == "Failed":
                                    st.error(f"❌ {chunk_range}")
                                    # 재시도 버튼 (간소화된 구현)
                                    if st.button("🔄", key=f"retry_{filename}_{chunk_range}", help=f"{chunk_range} 재시도"):
                                        st.info("재시도는 '업로드 및 분석 시작'을 다시 눌러주세요 (멱등성 보장)")
                                else:
                                    st.info(f"⏳ {chunk_range}")

    with tab2:

        
        # Display analyzed documents
        st.markdown("#### 📋 분석된 문서 목록")
        try:
            blob_service_client = get_blob_service_client()
            container_client = blob_service_client.get_container_client(CONTAINER_NAME)
            
            # List files in user's drawings folder + Admin access to root drawings
            blobs = []
            # User folder
            blobs.extend(list(container_client.list_blobs(name_starts_with=f"{user_folder}/drawings/")))
            
            if user_role == 'admin':
                # Admin root folder
                blobs.extend(list(container_client.list_blobs(name_starts_with="drawings/")))
            
            # Deduplicate
            unique_blobs = {b.name: b for b in blobs}.values()
            
            blob_list = []
            available_filenames = []
            for blob in unique_blobs:
                if not blob.name.endswith('/'):  # Skip folder markers
                    filename = blob.name.split('/')[-1]
                    blob_list.append({
                        'name': filename,
                        'full_name': blob.name,
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
                    # Update state for ALL files in the list, not just existing keys
                    for b in blob_list:
                        st.session_state[f"chk_{b['name']}"] = new_state

                select_all = st.checkbox("전체 선택", value=True, key="select_all_files", on_change=toggle_all)
                
                # Display as expandable list
                with st.expander("📄 문서 목록 및 선택", expanded=True):
                    for idx, blob_info in enumerate(blob_list, 1):
                        col0, col1, col2, col3 = st.columns([0.5, 4, 1.2, 1])
                        with col0:
                            # Checkbox for selection
                            # Initialize state if missing
                            chk_key = f"chk_{blob_info['name']}"
                            if chk_key not in st.session_state:
                                st.session_state[chk_key] = True # Default to True (Select All default)
                                
                            is_selected = st.checkbox(f"select_{idx}", key=chk_key, label_visibility="collapsed")
                            if is_selected:
                                selected_filenames.append(blob_info['name'])
                        
                        with col1:
                            size_mb = blob_info['size'] / (1024 * 1024)
                            modified_str = blob_info['modified'].strftime('%Y-%m-%d %H:%M')
                            st.markdown(f"**{blob_info['name']}** ({size_mb:.2f} MB)")
                        
                        with col2:
                            # Use sub-columns to align icons horizontally
                            sub_c1, sub_c2, sub_c3 = st.columns([1, 1, 1])
                            
                            with sub_c1:
                                # 1. Download Button
                                try:
                                    sas_url = generate_sas_url(
                                        blob_service_client, 
                                        CONTAINER_NAME, 
                                        blob_info['full_name'], 
                                        content_disposition="attachment"
                                    )
                                    # Use st.link_button for consistent UI (Box style)
                                    st.link_button("📥", sas_url, help="다운로드", use_container_width=True)
                                except Exception as e:
                                    st.error(f"Err: {e}")

                            with sub_c2:
                                # 2. Rename Button (Popover)
                                # Popover button is wide by default, try to make it compact?
                                # Streamlit buttons expand to column width.
                                with st.popover("✏️", use_container_width=True):
                                    new_name_input = st.text_input("새 파일명", value=blob_info['name'], key=f"ren_{blob_info['name']}")
                                    if st.button("이름 변경", key=f"btn_ren_{blob_info['name']}"):
                                        if new_name_input != blob_info['name']:
                                            try:
                                                with st.spinner("이름 변경 및 인덱스 업데이트 중..."):
                                                    # A. Rename Blob
                                                    old_blob_name = blob_info['full_name']
                                                    folder_path = old_blob_name.rsplit('/', 1)[0]
                                                    new_blob_name = f"{folder_path}/{new_name_input}"
                                                    
                                                    source_blob = container_client.get_blob_client(old_blob_name)
                                                    dest_blob = container_client.get_blob_client(new_blob_name)
                                                    
                                                    # Copy
                                                    source_sas = generate_sas_url(blob_service_client, CONTAINER_NAME, old_blob_name)
                                                    dest_blob.start_copy_from_url(source_sas)
                                                    
                                                    # Wait for copy
                                                    for _ in range(20):
                                                        props = dest_blob.get_blob_properties()
                                                        if props.copy.status == "success":
                                                            break
                                                        time.sleep(0.2)
                                                    
                                                    # B. Update Search Index (Preserve OCR Data)
                                                    search_manager = get_search_manager()
                                                    import unicodedata
                                                    safe_old_filename = unicodedata.normalize('NFC', blob_info['name'])
                                                    safe_new_filename = unicodedata.normalize('NFC', new_name_input)
                                                    
                                                    # Find old docs
                                                    results = search_manager.search_client.search(
                                                        search_text="*",
                                                        filter=f"project eq 'drawings_analysis'",
                                                        select=["id", "content", "content_exact", "metadata_storage_name", "metadata_storage_path", "metadata_storage_size", "metadata_storage_content_type"]
                                                    )
                                                    
                                                    docs_to_upload = []
                                                    ids_to_delete = []
                                                    
                                                    for doc in results:
                                                        # Check if this doc belongs to the file (by name prefix)
                                                        # Name format: "{filename} (p.{page})"
                                                        if doc['metadata_storage_name'].startswith(safe_old_filename):
                                                            # Create new doc
                                                            page_suffix = doc['metadata_storage_name'].split(safe_old_filename)[-1] # e.g. " (p.1)"
                                                            
                                                            # New ID
                                                            import base64
                                                            # Extract page number from suffix or path if possible, or just reconstruct
                                                            # Path format: .../filename#page=N
                                                            try:
                                                                page_num = doc['metadata_storage_path'].split('#page=')[-1]
                                                                new_page_id_str = f"{new_blob_name}_page_{page_num}"
                                                                new_doc_id = base64.urlsafe_b64encode(new_page_id_str.encode('utf-8')).decode('utf-8')
                                                                
                                                                new_doc = {
                                                                    "id": new_doc_id,
                                                                    "content": doc['content'],
                                                                    "content_exact": doc.get('content_exact', doc['content']),
                                                                    "metadata_storage_name": f"{safe_new_filename}{page_suffix}",
                                                                    "metadata_storage_path": f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{new_blob_name}#page={page_num}",
                                                                    "metadata_storage_last_modified": datetime.utcnow().isoformat() + "Z",
                                                                    "metadata_storage_size": doc['metadata_storage_size'],
                                                                    "metadata_storage_content_type": doc['metadata_storage_content_type'],
                                                                    "project": "drawings_analysis"
                                                                }
                                                                docs_to_upload.append(new_doc)
                                                                ids_to_delete.append({"id": doc['id']})
                                                            except:
                                                                pass

                                                    if docs_to_upload:
                                                        search_manager.upload_documents(docs_to_upload)
                                                    if ids_to_delete:
                                                        search_manager.search_client.delete_documents(documents=ids_to_delete)

                                                    # C. Delete old blob
                                                    source_blob.delete_blob()
                                                    
                                                    st.success("이름 변경 완료!")
                                                    time.sleep(1)
                                                    st.rerun()
                                                    
                                            except Exception as e:
                                                st.error(f"변경 실패: {e}")

                            with sub_c3:
                                # 3. Re-analyze Button
                                if st.button("🔄", key=f"reanalyze_{blob_info['name']}", help="재분석 (인덱스 복구)"):
                                    try:
                                        with st.spinner("재분석 시작... (파일 다운로드 중)"):
                                            # A. Download Blob to memory
                                            blob_client = container_client.get_blob_client(blob_info['full_name'])
                                            download_stream = blob_client.download_blob()
                                            pdf_data = download_stream.readall()
                                            
                                            # B. Count Pages
                                            import fitz
                                            doc = fitz.open(stream=pdf_data, filetype="pdf")
                                            total_pages = doc.page_count
                                            
                                            # C. Initialize Status
                                            if "analysis_status" not in st.session_state:
                                                st.session_state.analysis_status = {}
                                            
                                            safe_filename = blob_info['name']
                                            st.session_state.analysis_status[safe_filename] = {
                                                "status": "Extracting",
                                                "total_pages": total_pages,
                                                "processed_pages": 0,
                                                "chunks": {},
                                                "error": None
                                            }
                                            
                                            # D. Analyze Chunks
                                            doc_intel_manager = get_doc_intel_manager()
                                            search_manager = get_search_manager()
                                            blob_service_client = get_blob_service_client()
                                            
                                            # Generate SAS for Analysis
                                            sas_token = generate_blob_sas(
                                                account_name=blob_service_client.account_name,
                                                container_name=CONTAINER_NAME,
                                                blob_name=blob_info['full_name'],
                                                account_key=blob_service_client.credential.account_key,
                                                permission=BlobSasPermissions(read=True),
                                                expiry=datetime.utcnow() + timedelta(hours=1)
                                            )
                                            # Use relative path for URL construction if needed, but full_name is usually relative to container if listed from container_client?
                                            # container_client.list_blobs returns name relative to container.
                                            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{urllib.parse.quote(blob_info['full_name'])}?{sas_token}"
                                            
                                            chunk_size = 50
                                            page_chunks = []
                                            
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()
                                            
                                            for start_page in range(1, total_pages + 1, chunk_size):
                                                end_page = min(start_page + chunk_size - 1, total_pages)
                                                page_range = f"{start_page}-{end_page}"
                                                
                                                st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Extracting"
                                                status_text.text(f"재분석 중: {safe_filename} ({page_range})...")
                                                
                                                # Retry logic
                                                max_retries = 3
                                                for retry in range(max_retries):
                                                    try:
                                                        chunks = doc_intel_manager.analyze_document(blob_url, page_range=page_range, high_res=use_high_res)
                                                        page_chunks.extend(chunks)
                                                        st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Ready"
                                                        st.session_state.analysis_status[safe_filename]["processed_pages"] += len(chunks)
                                                        break
                                                    except Exception as e:
                                                        if retry == max_retries - 1:
                                                            st.session_state.analysis_status[safe_filename]["chunks"][page_range] = "Failed"
                                                            st.session_state.analysis_status[safe_filename]["error"] = str(e)
                                                            raise e
                                                        time.sleep(5 * (retry + 1))
                                            
                                            # E. Indexing
                                            st.session_state.analysis_status[safe_filename]["status"] = "Indexing"
                                            status_text.text("인덱싱 중...")
                                            
                                            documents_to_index = []
                                            for page_chunk in page_chunks:
                                                import base64
                                                # Use full_name (path in container) for ID generation to match upload logic
                                                page_id_str = f"{blob_info['full_name']}_page_{page_chunk['page_number']}"
                                                doc_id = base64.urlsafe_b64encode(page_id_str.encode('utf-8')).decode('utf-8')
                                                
                                                document = {
                                                    "id": doc_id,
                                                    "content": page_chunk['content'],
                                                    "content_exact": page_chunk['content'],
                                                    "metadata_storage_name": f"{safe_filename} (p.{page_chunk['page_number']})",
                                                    "metadata_storage_path": f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_info['full_name']}#page={page_chunk['page_number']}",
                                                    "metadata_storage_last_modified": datetime.utcnow().isoformat() + "Z",
                                                    "metadata_storage_size": blob_info['size'],
                                                    "metadata_storage_content_type": "application/pdf",
                                                    "project": "drawings_analysis",
                                                    "page_number": page_chunk['page_number'],
                                                    "filename": safe_filename
                                                }
                                                documents_to_index.append(document)
                                            
                                            if documents_to_index:
                                                batch_size = 50
                                                for i in range(0, len(documents_to_index), batch_size):
                                                    batch = documents_to_index[i:i + batch_size]
                                                    search_manager.upload_documents(batch)
                                                
                                                # Save JSON
                                                search_manager.upload_analysis_json(container_client, user_folder, safe_filename, page_chunks)
                                            
                                            st.session_state.analysis_status[safe_filename]["status"] = "Ready"
                                            st.success("재분석 완료! 이제 검색이 가능합니다.")
                                            time.sleep(1)
                                            st.rerun()

                                    except Exception as e:
                                        st.error(f"재분석 실패: {e}")

                            # 3. JSON (Admin only)
                            if user_role == 'admin':
                                json_key = f"json_data_{blob_info['name']}"
                                
                                if json_key not in st.session_state:
                                    if st.button("JSON", key=f"gen_json_{blob_info['name']}"):
                                        with st.spinner("..."):
                                            search_manager = get_search_manager()
                                            # Dual Retrieval Strategy: Try Blob first
                                            docs = search_manager.get_document_json_from_blob(container_client, user_folder, blob_info['name'])
                                            
                                            # Fallback to AI Search if Blob JSON not found (for older files)
                                            if not docs:
                                                st.info("Blob JSON을 찾을 수 없어 AI Search에서 검색합니다...")
                                                docs = search_manager.get_document_json(blob_info['name'])
                                                
                                            if docs:
                                                import json
                                                json_str = json.dumps(docs, ensure_ascii=False, indent=2)
                                                st.session_state[json_key] = json_str
                                                st.rerun()
                                            else:
                                                st.error(f"No Data found for '{blob_info['name']}'")
                                                # Try one more time without project filter to see if it exists at all
                                                safe_name = blob_info['name'].replace("'", "''")
                                                debug_docs = search_manager.search_client.search(
                                                    search_text="*",
                                                    filter=f"search.ismatch('\"{safe_name}*\"', 'metadata_storage_name')",
                                                    select=["metadata_storage_name", "project"],
                                                    top=5
                                                )
                                                debug_list = list(debug_docs)
                                                if debug_list:
                                                    st.warning(f"Found {len(debug_list)} docs without correct project tag. Example: {debug_list[0].get('metadata_storage_name')} (Project: {debug_list[0].get('project')})")
                                                else:
                                                    st.error("Document not found in index at all.")
                                else:
                                    # Show download button
                                    json_data = st.session_state[json_key]
                                    st.download_button(
                                        label="💾",
                                        data=json_data,
                                        file_name=f"{blob_info['name']}.json",
                                        mime="application/json",
                                        key=f"dl_json_{blob_info['name']}"
                                    )

                        with col3:
                            if st.button("🗑️ 삭제", key=f"del_{blob_info['name']}"):
                                try:
                                    # 1. Delete from Blob Storage (Use full_name)
                                    blob_client = container_client.get_blob_client(blob_info['full_name'])
                                    blob_client.delete_blob()
                                    
                                    # 2. Delete from Search Index
                                    search_manager = get_search_manager()
                                    
                                    # Find docs to delete
                                    import unicodedata
                                    safe_filename = unicodedata.normalize('NFC', blob_info['name'])
                                    
                                    # Clean up index (Find ALL pages)
                                    ids_to_delete = []
                                    while True:
                                        results = search_manager.search_client.search(
                                            search_text="*",
                                            filter=f"project eq 'drawings_analysis'",
                                            select=["id", "metadata_storage_name"],
                                            top=1000
                                        )
                                        
                                        batch_ids = []
                                        for doc in results:
                                            # Use NFC normalization for comparison
                                            doc_name = unicodedata.normalize('NFC', doc['metadata_storage_name'])
                                            if doc_name.startswith(safe_filename):
                                                batch_ids.append({"id": doc['id']})
                                        
                                        if not batch_ids:
                                            break
                                            
                                        search_manager.search_client.delete_documents(documents=batch_ids)
                                        ids_to_delete.extend(batch_ids)
                                        
                                        # If we found less than 1000, we might be done, but to be safe we continue 
                                        # until a search returns no matches for our file.
                                        # Actually, if we delete them, the next search will return different docs.
                                        # So we continue until no more docs match.
                                        if len(batch_ids) == 0:
                                            break
                                    
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
        
        # DEBUG: Show selected files
        st.write(f"DEBUG: Selected Files ({len(selected_filenames)}): {selected_filenames}")
        
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
                        
                        # Note: selected_filenames is defined in the outer scope of the tab
                        current_files = selected_filenames
                        
                        # Construct robust filter expression
                        # Include fallback for documents that might have lost their project tag but are in the drawings folder
                        base_filter = "(project eq 'drawings_analysis' or search.ismatch('/drawings/', 'metadata_storage_path'))"
                        
                        # Note: We used to filter by path here, but OData encoding issues caused 0 results.
                        # Now we pass user_folder to chat_manager for Python-side filtering.

                        response_text, citations, context, final_filter, search_results = chat_manager.get_chat_response(
                            prompt, 
                            conversation_history,
                            search_mode="any",
                            use_semantic_ranker=False,
                            filter_expr=base_filter,
                            available_files=current_files,
                            user_folder=user_folder # Pass user folder for Python-side filtering
                        )
                        
                        st.markdown(response_text)
                        
                        # Display Google-like search results (Snippets + Links)
                        if search_results:
                            with st.expander("🔍 검색 결과 및 스니펫 (상위 후보)", expanded=True):
                                for i, res in enumerate(search_results[:5]): # Show top 5 for clarity
                                    res_name = res.get('metadata_storage_name', 'Unknown')
                                    res_path = res.get('metadata_storage_path', '')
                                    
                                    # Extract snippet from highlights
                                    highlights = res.get('@search.highlights', {})
                                    snippet = highlights.get('content', [""])[0] if highlights else ""
                                    if not snippet:
                                        snippet = res.get('content', '')[:200] + "..."
                                    
                                    # Generate SAS link for the result
                                    try:
                                        # Extract blob path from metadata_storage_path
                                        from urllib.parse import unquote
                                        import re
                                        
                                        if "https://direct_fetch/" in res_path:
                                            # Handle custom direct fetch scheme
                                            path_without_scheme = res_path.replace("https://direct_fetch/", "")
                                            blob_path_part = path_without_scheme.split('#')[0]
                                            blob_path_part = unquote(blob_path_part)
                                        elif CONTAINER_NAME in res_path:
                                            # Handle standard Azure Blob URL
                                            blob_path_part = res_path.split(f"/{CONTAINER_NAME}/")[1].split('#')[0]
                                            blob_path_part = unquote(blob_path_part)
                                        else:
                                            # Fallback or relative path
                                            blob_path_part = res_path
                                        
                                        # CRITICAL FIX: Strip " (p.N)" suffix if present in the path
                                        # This happens if the indexer appended it to the path
                                        blob_path_part = re.sub(r'\s*\(p\.\d+\)$', '', blob_path_part)
                                            
                                        sas_url = chat_manager.generate_sas_url(blob_path_part)
                                    except:
                                        sas_url = "#"

                                    st.markdown(f"**{i+1}. {res_name}**")
                                    st.write(f"_{snippet}_")
                                    if sas_url != "#":
                                        st.markdown(f"[📥 원본 다운로드]({sas_url})")
                                    st.divider()

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
                            if final_filter:
                                st.caption(f"**OData Filter:** `{final_filter}`")
                            if search_results:
                                st.caption(f"**Search Results:** {len(search_results)} chunks found")
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

elif menu == "디버그 (Debug)":
    st.title("🕵️‍♂️ RAG Deep Diagnostic Tool (Integrated)")
    
    # Check if admin
    if user_role != 'admin':
        st.error("Admin access required.")
        st.stop()

    search_manager = get_search_manager()
    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Fetch list of files for selection (Filter for drawings only)
    blob_list = []
    try:
        blobs = container_client.list_blobs()
        for b in blobs:
            # Filter: Must be a file (not folder) AND must be in a 'drawings' folder
            if not b.name.endswith('/') and '/drawings/' in b.name:
                blob_list.append(b.name)
    except Exception as e:
        st.error(f"Failed to list blobs: {e}")
    
    blob_list.sort(key=lambda x: x.split('/')[-1]) # Sort by filename
    
    target_blob = st.selectbox("Select Target File", blob_list)
    
    # Extract filename for search
    if target_blob:
        filename = target_blob.split('/')[-1]
        st.caption(f"Selected Filename for Search: `{filename}`")
    else:
        filename = st.text_input("Target Filename", value="제4권 도면(청주).pdf")

    if st.button("Run Diagnostics"):
        st.divider()
        
        # 1. Index Inspection
        st.subheader("1. Index Inspection")
        
        # Search for ALL pages
        try:
            # Attempt 1: Exact Match Filter (Most accurate)
            safe_filename = filename.replace("'", "''")
            results = search_manager.search_client.search(
                search_text="*",
                filter=f"metadata_storage_name eq '{safe_filename}'",
                select=["id", "metadata_storage_name", "metadata_storage_path", "project", "content"],
                top=50
            )
            results = list(results)
        except Exception as e:
            st.warning(f"Exact match filter failed ({str(e)}). Switching to fallback search...")
            # Attempt 2: Fallback Text Search (Broader)
            # Search for the filename as a phrase
            results = search_manager.search_client.search(
                search_text=f"\"{filename}\"",
                search_mode="all",
                select=["id", "metadata_storage_name", "metadata_storage_path", "project", "content"],
                top=100
            )
            # Filter client-side to ensure we get the file AND its chunks
            # Allow exact match OR "filename (p.N)" format
            import unicodedata
            norm_filename = unicodedata.normalize('NFC', filename)
            results = [
                doc for doc in results 
                if unicodedata.normalize('NFC', doc['metadata_storage_name']).startswith(norm_filename)
            ]
        
        st.write(f"Found **{len(results)}** documents in index.")
        
        if results:
            # Analyze First Result
            first = results[0]
            st.json({
                "First Doc ID": first['id'],
                "Name": first['metadata_storage_name'],
                "Path": first['metadata_storage_path'],
                "Project": first['project']
            })
        else:
            st.error("No documents found in index matching this filename.")
            
            # Debug: List what IS in the index
            st.divider()
            st.subheader("🕵️ Index Content Peek (Top 20)")
            try:
                # Get top 20 docs to see what's actually there
                peek_results = search_manager.search_client.search(
                    search_text="*",
                    select=["metadata_storage_name", "project", "metadata_storage_last_modified"],
                    top=20
                )
                peek_list = list(peek_results)
                if peek_list:
                    st.write(f"Index contains at least {len(peek_list)} documents. Here are the top 20:")
                    peek_data = []
                    for d in peek_list:
                        peek_data.append({
                            "Name": d.get('metadata_storage_name'),
                            "Project": d.get('project'),
                            "Modified": d.get('metadata_storage_last_modified')
                        })
                    st.table(peek_data)
                else:
                    st.error("⚠️ The Index appears to be COMPLETELY EMPTY.")
            except Exception as e:
                st.error(f"Failed to peek index: {e}")

        # 2. Blob Verification
        st.subheader("2. Blob Verification")
            path = first['metadata_storage_path']
            blob_path = None
            
            if "https://direct_fetch/" in path:
                st.warning("⚠️ Using 'direct_fetch' scheme. This is a virtual path.")
                blob_path = path.replace("https://direct_fetch/", "").split('#')[0]
            elif CONTAINER_NAME in path:
                try:
                    blob_path = path.split(f"/{CONTAINER_NAME}/")[1].split('#')[0]
                    blob_path = urllib.parse.unquote(blob_path)
                except:
                    pass
            
            if blob_path:
                st.write(f"**Extracted Blob Path:** `{blob_path}`")
                blob_client = container_client.get_blob_client(blob_path)
                if blob_client.exists():
                    st.success("✅ Blob exists in storage.")
                else:
                    st.error("❌ Blob DOES NOT exist at this path!")
                    
                    # Search for it
                    st.write("Searching for file in container...")
                    found_blobs = list(container_client.list_blobs(name_starts_with=os.path.dirname(blob_path)))
                    if found_blobs:
                        st.write("Found similar blobs:")
                        for b in found_blobs:
                            st.code(b.name)
                    else:
                        st.warning("No similar blobs found.")
            else:
                st.error("Could not extract blob path from metadata.")

            # 3. List Page Check
            st.subheader("3. List Page Check")
            list_keywords = ["PIPING AND INSTRUMENT DIAGRAM FOR LIST", "DRAWING LIST", "도면 목록"]
            found_list = False
            
            for doc in results:
                # Handle None content safely
                content = doc.get('content')
                if content is None:
                    content = ""
                    st.warning(f"⚠️ Document '{doc['metadata_storage_name']}' has NO CONTENT (NULL).")
                
                content_upper = content.upper()
                if any(k in content_upper for k in list_keywords):
                    st.success(f"✅ Found List Page! Name: `{doc['metadata_storage_name']}`")
                    st.text_area("Content Preview", content[:500], height=150)
                    found_list = True
                    break
            
            if not found_list:
                st.error("❌ List Page NOT found in the top 50 results.")
                st.write("Top 5 Results Content Snippets:")
                for i, doc in enumerate(results[:5]):
                    content_preview = (doc.get('content') or "")[:100]
                    st.text(f"{i+1}. {doc['metadata_storage_name']}: {content_preview}...")

            # 4. Cleanup Tool
            st.divider()
            st.subheader("4. Index Cleanup")
            st.warning("If this document is corrupt (No Content / No Project), you can delete it here.")
            
            if st.button(f"🗑️ Delete ALL {len(results)} found documents from Index"):
                try:
                    # Collect IDs
                    ids_to_delete = [{"id": doc['id']} for doc in results]
                    search_manager.search_client.delete_documents(documents=ids_to_delete)
                    st.success(f"Successfully deleted {len(results)} documents.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

        else:
            st.error("No documents found in index matching this filename.")

    # -----------------------------
    # 디버깅 도구 (Debug Tools)
    # -----------------------------
    if user_role == 'admin':
        with st.expander("🛠️ 인덱스 및 검색 진단 (Debug Tools)", expanded=False):
            st.warning("이 도구는 검색 문제를 진단하기 위한 것입니다.")
            
            # Secret Inspector
            st.write("### 🔐 자격 증명 확인 (Secret Inspector)")
            def mask_secret(s):
                if not s: return "Not Set"
                if len(s) <= 8: return "*" * len(s)
                return s[:4] + "*" * (len(s)-8) + s[-4:]
            
            secrets_to_check = {
                "AZURE_STORAGE_CONNECTION_STRING": STORAGE_CONN_STR,
                "AZURE_BLOB_CONTAINER_NAME": CONTAINER_NAME,
                "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
                "AZURE_OPENAI_KEY": AZURE_OPENAI_KEY,
                "AZURE_SEARCH_ENDPOINT": SEARCH_ENDPOINT,
                "AZURE_SEARCH_KEY": SEARCH_KEY,
                "AZURE_TRANSLATOR_KEY": TRANSLATOR_KEY,
                "AZURE_DOC_INTEL_ENDPOINT": AZURE_DOC_INTEL_ENDPOINT,
                "AZURE_DOC_INTEL_KEY": AZURE_DOC_INTEL_KEY
            }
            
            import pandas as pd
            secret_data = []
            for k, v in secrets_to_check.items():
                secret_data.append({"Secret Key": k, "Status": "✅ Loaded" if v else "❌ Missing", "Value (Masked)": mask_secret(v)})
            
            st.table(pd.DataFrame(secret_data))
            
            st.write("---")
            
            if st.button("🔍 인덱스 상태 및 검색 테스트 실행"):
                try:
                    search_manager = get_search_manager()
                    client = search_manager.search_client
                    
                    st.write("### 1. 인덱스 문서 확인 (project='drawings_analysis')")
                    results = client.search(search_text="*", filter="project eq 'drawings_analysis'", select=["id", "metadata_storage_name", "project"], top=20)
                    
                    docs = list(results)
                    st.write(f"Found {len(docs)} docs with project='drawings_analysis'")
                    
                    if docs:
                        for doc in docs:
                            st.code(f"ID: {doc['id']}\nName: {doc['metadata_storage_name']}\nProject: {doc['project']}")
                    
                    st.write("---")
                    st.write("### 1-B. 인덱스 문서 확인 (전체 - 필터 없음)")
                    results_all = client.search(search_text="*", select=["id", "metadata_storage_name", "project"], top=20)
                    docs_all = list(results_all)
                    st.write(f"Found {len(docs_all)} docs in total (top 20)")
                    for doc in docs_all:
                        proj = doc.get('project', 'None')
                        st.code(f"Name: {doc['metadata_storage_name']}\nProject: {proj}")
                    
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
            st.write("### 🔍 인덱스 데이터 확인")
            if st.button("📑 인덱스된 모든 파일명 보기"):
                with st.spinner("인덱스 조회 중..."):
                    try:
                        search_manager = get_search_manager()
                        # Get all docs (limit to top 1000 to be safe)
                        results = search_manager.search("*", select=["metadata_storage_name"], top=1000)
                        indexed_files = set()
                        for res in results:
                            # Remove page suffix (p.N) to get base filename
                            name = res['metadata_storage_name']
                            base_name = name.split(' (p.')[0]
                            indexed_files.add(base_name)
                        
                        st.write(f"총 {len(indexed_files)}개의 파일이 인덱스에서 발견되었습니다.")
                        st.dataframe(list(indexed_files), use_container_width=True)
                    except Exception as e:
                        st.error(f"조회 실패: {e}")

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
                    # 1. Delete all blobs in any drawings/, json/ folder (Global reset)
                    blob_service_client = get_blob_service_client()
                    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                    
                    # List all blobs and filter for drawings or json
                    blobs = container_client.list_blobs()
                    deleted_blobs = 0
                    for blob in blobs:
                        if '/drawings/' in blob.name or blob.name.startswith('drawings/') or '/json/' in blob.name or blob.name.startswith('json/'):
                            container_client.delete_blob(blob.name)
                            deleted_blobs += 1
                    
                    # 2. Delete all docs in index with project='drawings_analysis'
                    search_manager = get_search_manager()
                    
                    deleted_total = 0
                    while True:
                        results = search_manager.search_client.search(
                            search_text="*",
                            filter="project eq 'drawings_analysis'",
                            select=["id"],
                            top=1000
                        )
                        ids_to_delete = [{"id": doc['id']} for doc in results]
                        if not ids_to_delete:
                            break
                            
                        search_manager.search_client.delete_documents(documents=ids_to_delete)
                        deleted_total += len(ids_to_delete)
                        if len(ids_to_delete) < 1000:
                            break
                    
                    st.success(f"모든 도면 데이터가 삭제되었습니다. (Blob 삭제 완료, Index {deleted_total}개 삭제 완료) 이제 파일을 다시 업로드하세요.")
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

            if st.button("🏷️ 누락된 'drawings_analysis' 태그 복구", help="드로잉 폴더에 있지만 프로젝트 태그가 없는 문서를 찾아 태그를 추가합니다."):
                try:
                    search_manager = get_search_manager()
                    # Search for all docs with missing project tag and filter path in Python
                    results = search_manager.search_client.search(
                        search_text="*",
                        filter="(project eq null)",
                        select=["id", "metadata_storage_name", "metadata_storage_path", "content", "content_exact", "metadata_storage_last_modified", "metadata_storage_size", "metadata_storage_content_type"],
                        top=10000 # Increase to cover all docs
                    )
                    
                    docs_to_fix = []
                    for doc in results:
                        # Filter by path in Python
                        if '/drawings/' in doc.get('metadata_storage_path', ''):
                            doc['project'] = 'drawings_analysis'
                            docs_to_fix.append(doc)
                    
                    if docs_to_fix:
                        success, msg = search_manager.upload_documents(docs_to_fix)
                        if success:
                            st.success(f"복구 완료! {len(docs_to_fix)}개의 문서에 'drawings_analysis' 태그를 추가했습니다.")
                            st.rerun()
                        else:
                            st.error(f"복구 실패: {msg}")
                    else:
                        st.info("태그를 복구할 문서가 없습니다.")
                except Exception as e:
                    st.error(f"태그 복구 중 오류 발생: {e}")

            if st.button("📊 인덱스 통계 확인", help="프로젝트별 문서 개수를 확인합니다."):
                try:
                    search_manager = get_search_manager()
                    
                    # Count drawings_analysis
                    drawings_res = search_manager.search_client.search(
                        search_text="*",
                        filter="project eq 'drawings_analysis'",
                        include_total_count=True,
                        top=0
                    )
                    drawings_count = drawings_res.get_count()
                    
                    # Count others (likely standard indexed)
                    others_res = search_manager.search_client.search(
                        search_text="*",
                        filter="project eq null",
                        include_total_count=True,
                        top=0
                    )
                    others_count = others_res.get_count()
                    
                    st.write(f"**도면 분석 데이터 (drawings_analysis):** {drawings_count}개")
                    st.write(f"**일반 문서 데이터 (Standard Indexer):** {others_count}개")
                    
                    # Check Standard Indexer Status
                    st.divider()
                    st.write("**표준 인덱서 (Standard Indexer) 상태 확인:**")
                    # Try common indexer names
                    for idx_name in ["pdf-indexer", "indexer-all", "indexer-drawings"]:
                        try:
                            status = search_manager.indexer_client.get_indexer_status(idx_name)
                            last_res = status.last_result
                            if last_res:
                                st.write(f"- `{idx_name}`: {last_res.status} (성공: {last_res.item_count}, 실패: {last_res.failed_item_count})")
                                if last_res.failed_item_count > 0:
                                    with st.expander(f"❌ {idx_name} 에러 상세 보기"):
                                        for err in last_res.errors[:5]:
                                            st.error(f"문서: {err.key}\n에러: {err.message}")
                            else:
                                st.write(f"- `{idx_name}`: 실행 기록 없음")
                        except:
                            pass

                    if drawings_count == 0 and others_count > 0:
                        st.warning("도면 데이터가 하나도 없습니다. 인덱싱 과정에 문제가 있을 수 있습니다.")
                except Exception as e:
                    st.error(f"통계 확인 중 오류 발생: {e}")

            with st.expander("🔍 인덱스 상세 진단 도구", expanded=False):
                st.caption("인덱스에 저장된 실제 파일명과 태그를 직접 확인합니다.")
                
                # Add search input for specific file diagnosis (Outside button for persistence)
                diag_query = st.text_input("진단할 파일명 검색 (일부만 입력 가능)", value="", key="diag_query")
                diag_path_filter = st.checkbox("'/drawings/' 경로만 보기", value=True, key="diag_path_filter")
                
                if st.button("📋 진단 실행 (최근 100개)"):
                    try:
                        search_manager = get_search_manager()
                        
                        # Use a more inclusive search for diagnosis
                        # If query is provided, use it as search_text. If not, use *
                        results = search_manager.search_client.search(
                            search_text=diag_query if diag_query else "*",
                            select=["metadata_storage_name", "project", "metadata_storage_path"],
                            top=1000 # Increase for better diagnosis
                        )
                        
                        dump_data = []
                        for doc in results:
                            name = doc.get('metadata_storage_name', '')
                            path = doc.get('metadata_storage_path', '')
                            
                            if diag_path_filter and '/drawings/' not in path:
                                continue
                                
                            dump_data.append({
                                "Name": name,
                                "Project": doc.get('project'),
                                "Path": path
                            })
                        
                        if dump_data:
                            st.write(f"검색 결과: {len(dump_data)}개의 문서 발견")
                            st.table(dump_data)
                        else:
                            st.warning("검색 결과가 없습니다. 파일명이 인덱스에 존재하지 않거나 필터에 걸러졌을 수 있습니다.")
                            
                        # Extra check: Search by path only if query failed
                        if diag_query and not dump_data:
                            st.info(f"'{diag_query}'로 검색된 결과가 없어 경로 기반으로 다시 찾습니다...")
                            # Use startswith on metadata_storage_path (SimpleField/Filterable)
                            # We don't know the full prefix, but we can try to find anything in drawings
                            path_results = search_manager.search_client.search(
                                search_text="*",
                                filter="startswith(metadata_storage_path, 'https://')", # Broad filter
                                select=["metadata_storage_name", "project", "metadata_storage_path"],
                                top=5000 # Increase to cover more docs
                            )
                            # Filter for '/drawings/' in Python for maximum reliability
                            path_data = [
                                {"Name": d['metadata_storage_name'], "Project": d['project'], "Path": d['metadata_storage_path']} 
                                for d in path_results 
                                if '/drawings/' in d.get('metadata_storage_path', '')
                            ]
                            if path_data:
                                st.write("'/drawings/' 경로에서 발견된 파일들 (최근 100개 중):")
                                st.table(path_data[:20])
                            else:
                                st.error("'/drawings/' 경로에서 문서를 찾을 수 없습니다. 인덱서가 해당 폴더를 스캔하지 않았을 수 있습니다.")
                                
                    except Exception as e:
                        st.error(f"진단 중 오류 발생: {e}")
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



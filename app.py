import streamlit as st
import os
import time
import uuid
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, generate_container_sas, ContainerSasPermissions
from azure.ai.translation.document import DocumentTranslationClient
from azure.core.credentials import AzureKeyCredential

# -----------------------------
# 설정 및 비밀 관리
# -----------------------------
st.set_page_config(page_title="Azure 문서 번역기", page_icon="🌏", layout="centered")

def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.environ.get(key)

# 필수 자격 증명
STORAGE_CONN_STR = get_secret("AZURE_STORAGE_CONNECTION_STRING")
TRANSLATOR_KEY = get_secret("AZURE_TRANSLATOR_KEY")
TRANSLATOR_ENDPOINT = get_secret("AZURE_TRANSLATOR_ENDPOINT")
CONTAINER_NAME = get_secret("AZURE_BLOB_CONTAINER_NAME") or "blob-leesunguk"

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
st.title("🌏 Azure 문서 번역기")
st.caption("Azure Document Translation & Blob Storage 기반")

# 지원 언어 목록 (Azure Document Translation 지원 코드)
# 실제로는 API로 가져올 수도 있지만, 주요 언어 하드코딩 또는 간단히 입력 받음
# 여기서는 주요 언어만 예시로 제공
LANGUAGES = {
    "한국어": "ko",
    "영어": "en",
    "일본어": "ja",
    "중국어(간체)": "zh-Hans",
    "중국어(번체)": "zh-Hant",
    "프랑스어": "fr",
    "독일어": "de",
    "스페인어": "es",
    "베트남어": "vi",
    "태국어": "th",
    "인도네시아어": "id",
    "러시아어": "ru"
}

with st.sidebar:
    st.header("설정")
    target_lang_label = st.selectbox("목표 언어 선택", list(LANGUAGES.keys()))
    target_lang_code = LANGUAGES[target_lang_label]
    
    st.info(f"선택된 목표 언어: {target_lang_code}")
    
    # 자격 증명 상태 확인
    if STORAGE_CONN_STR and TRANSLATOR_KEY:
        st.success("✅ Azure 자격 증명 확인됨")
    else:
        st.warning("⚠️ Azure 자격 증명이 누락되었습니다. secrets.toml을 확인하세요.")

uploaded_file = st.file_uploader("번역할 문서 업로드 (PPTX, PDF, DOCX, XLSX 등)", type=["pptx", "pdf", "docx", "xlsx"])

if st.button("번역 시작", type="primary", disabled=not uploaded_file):
    if not uploaded_file:
        st.error("파일을 업로드해주세요.")
    else:
        with st.spinner("Azure Blob에 파일 업로드 중..."):
            try:
                blob_service_client = get_blob_service_client()
                container_client = blob_service_client.get_container_client(CONTAINER_NAME)
                
                # 컨테이너 접근 권한 확인 (AuthenticationFailed 방지)
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
                # Output은 폴더별로 구분 (targetUrl은 컨테이너 레벨 SAS여야 함, 하지만 폴더 지정 가능)
                # Azure Document Translation은 Target URL이 컨테이너 SAS여야 하며, 결과 파일명을 지정하거나 폴더 구조를 따름.
                # 여기서는 output/{uuid}/ 폴더에 결과가 저장되도록 설정하고 싶음.
                # 하지만 Target URL은 컨테이너 루트여야 하거나, 특정 가상 디렉토리여야 함.
                # 가장 쉬운 방법: Target URL을 `output/{file_uuid}/` 가상 디렉토리를 포함한 SAS로 생성.
                
                output_prefix = f"output/{file_uuid}/"
                target_url = generate_sas_url(blob_service_client, CONTAINER_NAME) # 컨테이너 전체 권한 SAS
                # 주의: Document Translation의 targetUrl은 쓰기 권한이 있는 컨테이너 SAS URL이어야 함.
                # prefix를 지정하지 않으면 컨테이너 루트에 생길 수 있음.
                
            except Exception as e:
                st.error(f"업로드/SAS 생성 실패: {e}")
                st.stop()

        with st.spinner("번역 작업 요청 및 대기 중..."):
            try:
                client = get_translation_client()
                
                # 번역 작업 시작
                # sourceUrl: 특정 파일의 SAS URL
                # targetUrl: 결과가 저장될 컨테이너 SAS URL (여기서는 컨테이너 전체)
                # targetUrl에 prefix를 붙여서 특정 폴더에 저장되도록 유도? 
                # API 상 targetUrl은 컨테이너 URL이어야 함. 
                # 하지만 우리는 입력 파일이 1개이므로, storageSource=File 로 지정하면 됨?
                # Python SDK `begin_translation`은 배치 번역임.
                # SourceInput에 storageSource='File' 옵션이 있는지 확인 필요. 
                # SDK 문서를 보면 Single Blob 번역은 `begin_translation`에서 source_url이 구체적 파일이면 됨.
                # 하지만 Target은 컨테이너여야 함.
                
                # SDK 사용법:
                # inputs = [DocumentTranslationInput(source_url=..., targets=[TranslationTarget(target_url=..., language=...)])]
                # 여기서 source_url이 구체적 파일(SAS 포함)이면 그 파일만 번역됨.
                # target_url은 컨테이너(SAS 포함)여야 함.
                # 결과 파일명은 원본과 같게 유지되거나 설정에 따름.
                # 겹치지 않게 하기 위해 output_prefix를 사용해야 하는데 SDK에서 어떻게 지정하나?
                # TranslationTarget에 `category`나 `glossaries`는 있지만 prefix는 없음.
                # 그러나 target_url 자체에 가상 디렉토리를 포함할 수 있는지? 
                # -> 보통은 컨테이너 URL + SAS 쿼리.
                
                # 해결책: Target Container를 `blob-leesunguk`으로 하고, 
                # 결과가 섞이지 않게 하려면? 
                # Azure Document Translation은 입력 파일의 상대 경로 구조를 출력 컨테이너에 유지함.
                # 입력이 `input/uuid/file.pptx` 였으므로, 
                # 출력이 `input/uuid/file.pptx` 위치에 덮어씌워지거나, 
                # Target URL이 가리키는 곳에 저장됨.
                # 만약 Target URL이 `.../blob-leesunguk?sas` 라면, 
                # 결과는 `blob-leesunguk/input/uuid/file.pptx` (언어 코드 붙을 수 있음) 로 저장될 것임.
                # 이렇게 되면 input과 섞임.
                
                # 따라서 Target URL을 `.../blob-leesunguk/output/uuid?sas` 처럼 하위 경로로 줄 수 있는지 확인 필요.
                # Azure Blob SAS는 컨테이너 레벨에서 생성되지만, URL 자체에 경로를 붙여서 주면 그 경로를 루트로 인식할 수도 있음?
                # 아니면, Source Input에서 `storage_source="AzureBlob"` (default) 대신 구체적 파일 지정 시
                # prefix 옵션 등을 활용.
                
                # 전략: 
                # Source URL: `.../input/uuid/file.pptx?sas`
                # Target URL: `.../output/uuid?sas` (이게 작동하는지 불확실, 보통은 컨테이너 루트)
                # 만약 Target URL이 컨테이너 루트여야 한다면, 
                # Source의 `prefix`나 `filter`를 쓰는게 아니라 직접 파일 URL을 주었으므로,
                # 결과는 Target Container의 루트에 `file.pptx`로 생길 가능성 높음.
                # -> 테스트 필요.
                
                # 안전한 방법: 
                # Target URL을 `https://.../blob-leesunguk?sas` 로 주고,
                # 결과 파일이 어디 생기는지 확인 후 다운로드.
                # 보통은 `TargetContainer/RelativePathFromSource` 구조를 따름.
                # Source가 `input/uuid/file.pptx` 였으니, Target에도 `input/uuid/file.pptx`로 생길 수 있음.
                # 이를 방지하기 위해 Source URL을 줄 때, 컨테이너 루트가 아닌 Blob URL을 직접 주면,
                # 상대 경로가 없음 -> 루트에 생김?
                
                # 일단 진행하고 결과 경로를 추적하여 다운로드.
                
                from azure.ai.translation.document import DocumentTranslationInput, TranslationTarget
                
                # Output 폴더를 구분하기 위해, Target URL을 `.../blob-leesunguk?sas`로 하고
                # 결과 파일은 `input/uuid/` 경로를 따라갈 것으로 예상됨.
                # 하지만 우리는 `output` 폴더에 넣고 싶음.
                # SDK에는 `target_url`에 폴더 경로를 포함시키는 것을 허용하는 경우가 많음.
                # 시도: `https://.../blob-leesunguk/output/{file_uuid}?sas`
                
                target_folder_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/output/{file_uuid}?{generate_container_sas(blob_service_client.account_name, CONTAINER_NAME, blob_service_client.credential.account_key, permission=ContainerSasPermissions(write=True, list=True, read=True), expiry=datetime.utcnow() + timedelta(hours=1))}"
                # 위 방식은 SAS 서명이 컨테이너 기준이라 URL 경로와 불일치할 수 있음.
                # SAS는 컨테이너에 대해 발급받고, URL 문자열만 조작해서 폴더 경로를 넣는 방식.
                
                # 정확한 방식:
                # SAS는 컨테이너 전체 권한.
                # Target URL = `https://<account>.blob.core.windows.net/<container>/output/<uuid>?<sas_token>`
                
                sas_token = generate_container_sas(
                    account_name=blob_service_client.account_name,
                    container_name=CONTAINER_NAME,
                    account_key=blob_service_client.credential.account_key,
                    permission=ContainerSasPermissions(write=True, list=True, read=True),
                    expiry=datetime.utcnow() + timedelta(hours=1)
                )
                
                target_base_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}"
                target_output_url = f"{target_base_url}/output/{file_uuid}?{sas_token}"
                
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
                
                # 결과 파일 찾기 및 다운로드 링크 생성
                # 잠시 대기 (Eventual Consistency)
                time.sleep(2)
                
                output_prefix_search = f"output/{file_uuid}"
                output_blobs = list(container_client.list_blobs(name_starts_with=output_prefix_search))
                
                if not output_blobs:
                    # 디버깅: output 폴더의 모든 파일 확인
                    all_output = list(container_client.list_blobs(name_starts_with="output/"))
                    debug_msg = "\n".join([b.name for b in all_output[:10]])
                    st.error(f"결과 파일을 찾을 수 없습니다. (검색 경로: {output_prefix_search})\n현재 output 폴더 파일 목록:\n{debug_msg}")
                else:
                    st.subheader("다운로드")
                    for blob in output_blobs:
                        blob_name = blob.name
                        # 다운로드용 SAS (Read)
                        download_sas = generate_blob_sas(
                            account_name=blob_service_client.account_name,
                            container_name=CONTAINER_NAME,
                            blob_name=blob_name,
                            account_key=blob_service_client.credential.account_key,
                            permission=BlobSasPermissions(read=True),
                            expiry=datetime.utcnow() + timedelta(hours=1)
                        )
                        download_url = f"{target_base_url}/{blob_name}?{download_sas}"
                        
                        # 파일명 추출
                        file_name = blob_name.split("/")[-1]
                        
                        # Streamlit 다운로드 버튼 (URL 대신 바이트 다운로드 방식 사용)
                        # URL로 바로 다운로드하게 하려면 st.markdown 링크 사용
                        st.markdown(f"[{file_name} 다운로드]({download_url})", unsafe_allow_html=True)
                        
                        # 또는 직접 바이트 읽어서 버튼 제공 (더 안정적)
                        blob_client_out = container_client.get_blob_client(blob_name)
                        data = blob_client_out.download_blob().readall()
                        st.download_button(
                            label=f"📥 {file_name} 다운로드",
                            data=data,
                            file_name=file_name
                        )
                        
            except Exception as e:
                st.error(f"번역 요청 중 오류 발생: {e}")

import os
import io
import zipfile
import tempfile
import pathlib
from typing import List, Tuple, Optional

import streamlit as st
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

# ---- PyMuPDF (PDF) ----
import fitz  # PyMuPDF

# ---- DeepL ----
try:
    import deepl
except Exception as e:
    st.error("`deepl` 패키지가 필요합니다. 터미널에서 `pip install deepl` 후 다시 실행하세요.")
    st.stop()


# ==============================
# Secrets / Config
# ==============================
def get_deepl_key() -> str:
    """시크릿(우선) -> 환경변수에서 DeepL API 키를 읽는다."""
    try:
        if "DEEPL_API_KEY" in st.secrets:
            return st.secrets["DEEPL_API_KEY"]
    except Exception:
        # 로컬에서 st.secrets가 없을 수 있음
        pass
    return os.environ.get("DEEPL_API_KEY", "")


@st.cache_resource(show_spinner=False)
def get_translator() -> deepl.Translator:
    key = get_deepl_key()
    if not key:
        st.error("DeepL API 키가 없습니다. Streamlit Secrets에 DEEPL_API_KEY를 등록해주세요.")
        st.stop()
    try:
        return deepl.Translator(key)
    except Exception as e:
        st.error(f"DeepL 초기화 실패: {e}")
        st.stop()


@st.cache_data(show_spinner=False, ttl=3600)
def list_target_languages() -> List[Tuple[str, str]]:
    """[(코드, 이름)] 목록"""
    tr = get_translator()
    langs = tr.get_target_languages()
    return [(lng.code, lng.name) for lng in langs]


# ==============================
# Utilities
# ==============================
def safe_st_rerun():
    try:
        st.rerun()
    except Exception:
        pass


def guess_download_name(base: str, code: str, ext: str) -> str:
    return f"{pathlib.Path(base).stem}.translated_{code}{ext}"


def save_uploaded_file(uploaded_file) -> pathlib.Path:
    suffix = pathlib.Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        return pathlib.Path(tmp.name)


def to_zip_bytes(files: List[pathlib.Path], base: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, arcname=p.name)
    buf.seek(0)
    return buf.read()


# ==============================
# PPTX Translation
# ==============================
def translate_text_deepl(text: str, target_code: str, formality: Optional[str] = None) -> str:
    tr = get_translator()
    try:
        result = tr.translate_text(text, target_lang=target_code, formality=formality)
        return result.text
    except Exception as e:
        # 실패 시 원문 fallback
        return text


def translate_pptx(src_path: pathlib.Path, target_code: str, formality: Optional[str]) -> pathlib.Path:
    prs = Presentation(src_path)

    for slide in prs.slides:
        for shape in slide.shapes:
            # 텍스트 상자 / 제목 / 표 내부 텍스트 등
            if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                tf = shape.text_frame
                for p in tf.paragraphs:
                    original = "".join(run.text for run in p.runs) or p.text
                    if not original.strip():
                        continue

                    translated = translate_text_deepl(original, target_code, formality=formality)

                    # run 개수 유지가 어려운 경우가 많아 단일 run로 재작성(서식 유지 최대화 어려움)
                    # 기존 단락 정렬 등은 유지됨
                    for r in list(p.runs):
                        r.text = ""
                    if p.runs:
                        p.runs[0].text = translated
                    else:
                        p.text = translated

            # 표(Table) 처리
            if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
                table = shape.table
                for r in table.rows:
                    for c in r.cells:
                        if c.text_frame:
                            for p in c.text_frame.paragraphs:
                                original = "".join(run.text for run in p.runs) or p.text
                                if not original.strip():
                                    continue
                                translated = translate_text_deepl(original, target_code, formality=formality)
                                for rn in list(p.runs):
                                    rn.text = ""
                                if p.runs:
                                    p.runs[0].text = translated
                                else:
                                    p.text = translated

    out_path = src_path.with_name(guess_download_name(src_path.name, target_code, ".pptx"))
    prs.save(out_path)
    return out_path


# ==============================
# PDF Translation (PyMuPDF only)
# - 간단한 레이아웃 보존 전략:
#   1) 각 페이지 텍스트 블록(block) 단위로 추출
#   2) 동일 위치에 텍스트 박스(Rect)에 번역문 삽입
#   3) 폰트/크기는 기본값(가독성 우선), 선택적으로 width에 맞춰 줄바꿈
# ==============================
def translate_pdf(src_path: pathlib.Path, target_code: str, formality: Optional[str]) -> pathlib.Path:
    doc = fitz.open(src_path)
    out = fitz.open()

    for page_index in range(len(doc)):
        src = doc[page_index]
        # 새로운 페이지(원본과 동일 크기) 생성
        dst = out.new_page(width=src.rect.width, height=src.rect.height)

        # 원본을 이미지로 깔고 위에 텍스트만 재배치하기보다는
        # 텍스트 블록만 추출하여 해당 영역에 번역 텍스트를 채움
        blocks = src.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, ...)
        # 배경 무늬/표/도형은 재현하지 않음(클라우드 리소스/일반성 우선)

        for b in blocks:
            if len(b) < 5:
                continue
            x0, y0, x1, y1, text = b[:5]
            if not isinstance(text, str) or not text.strip():
                continue

            translated = translate_text_deepl(text, target_code, formality=formality)

            rect = fitz.Rect(x0, y0, x1, y1)
            # 텍스트 박스 안에 자동 줄바꿈
            dst.insert_textbox(
                rect,
                translated,
                fontsize=11,  # 경험상 가독성 좋은 기본값
                fontname="helv",  # 기본 폰트(유니코드 광범위 지원은 제한적일 수 있음)
                color=(0, 0, 0),
                align=0,  # left
            )

    out_path = src_path.with_name(guess_download_name(src_path.name, target_code, ".pdf"))
    out.save(out_path)
    out.close()
    doc.close()
    return out_path


# ==============================
# UI
# ==============================
st.set_page_config(page_title="문서 번역기 (DeepL, Secrets Only)", page_icon="🌐", layout="wide")

st.title("🌐 문서 번역기")
st.caption("시크릿에 저장된 DeepL API 키만 사용합니다. (입력칸 없음)")

with st.sidebar:
    st.subheader("번역 설정")
    langs = list_target_languages()
    if not langs:
        st.error("DeepL 대상 언어 목록을 불러오지 못했습니다.")
        st.stop()

    # 언어 선택
    lang_codes = [c for c, _ in langs]
    lang_display = [f"{name} ({code})" for code, name in langs]
    default_code = "KO" if "KO" in lang_codes else lang_codes[0]

    sel = st.selectbox("대상 언어", options=list(range(len(langs))),
                       index=lang_codes.index(default_code) if default_code in lang_codes else 0,
                       format_func=lambda i: lang_display[i])

    target_code = langs[sel][0]

    # 선택 사항: 정중/보통(formality)
    formality = st.selectbox("말투(옵션)", ["auto", "less", "more"], index=0)
    formality_val = None if formality == "auto" else formality

st.markdown("#### 파일 업로드")
uploaded_files = st.file_uploader(
    "PDF 또는 PPTX 파일을 업로드하세요(복수 선택 가능).",
    type=["pdf", "pptx", "ppt"],
    accept_multiple_files=True,
)

col_go, col_clear = st.columns([1, 1])
start = col_go.button("번역 시작", type="primary", use_container_width=True)
clear = col_clear.button("초기화", use_container_width=True)

if clear:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.experimental_set_query_params()  # 간단 초기화
    safe_st_rerun()

if start:
    if not uploaded_files:
        st.warning("먼저 파일을 업로드해주세요.")
        st.stop()

    results: List[pathlib.Path] = []
    errors: List[Tuple[str, str]] = []

    with st.status("번역 중...", expanded=False) as status:
        try:
            for uf in uploaded_files:
                tmp_path = save_uploaded_file(uf)
                suffix = tmp_path.suffix.lower()
                out_path = None

                if suffix in [".pptx", ".ppt"]:
                    out_path = translate_pptx(tmp_path, target_code, formality_val)
                elif suffix == ".pdf":
                    out_path = translate_pdf(tmp_path, target_code, formality_val)
                else:
                    errors.append((uf.name, "지원하지 않는 형식입니다. PDF 또는 PPTX만 업로드하세요."))

                if out_path and out_path.exists():
                    results.append(out_path)
            status.update(label="번역 완료", state="complete", expanded=False)
        except Exception as e:
            status.update(label="오류 발생", state="error", expanded=True)
            st.exception(e)

    st.markdown("---")

    if results:
        st.subheader("다운로드")
        # 단건이면 개별 버튼, 복수면 ZIP 버튼도 제공
        for p in results:
            with open(p, "rb") as f:
                st.download_button(
                    label=f"⬇️ {p.name}",
                    data=f.read(),
                    file_name=p.name,
                    mime="application/octet-stream",
                    key=f"dl-{p.name}",
                    use_container_width=True,
                )
        if len(results) > 1:
            base = pathlib.Path(uploaded_files[0].name).stem
            zbytes = to_zip_bytes(results, base)
            st.download_button(
                label=f"⬇️ ZIP으로 모두 받기 ({len(results)}개)",
                data=zbytes,
                file_name=f"{base}_translations.zip",
                mime="application/zip",
                use_container_width=True,
            )

    if errors:
        st.subheader("오류")
        for fname, msg in errors:
            st.error(f"**{fname}**: {msg}")

st.markdown("---")
st.caption(
    "주의: PDF는 PyMuPDF만 사용하며, 복잡한 레이아웃(도형/표/중첩 텍스트 등)은 완전 재현이 어려울 수 있습니다. "
    "핵심 텍스트 가독성을 우선합니다. PPTX는 텍스트 프레임/표 텍스트를 번역해 슬라이드 서식을 최대한 유지합니다."
)

# 외국인 근로자 교재 번역기 (DeepL + Streamlit)

DeepL의 **문서 번역(Document Translation)** 기능을 사용해 **PDF, PPTX, DOCX, XLSX** 등의 문서를 **서식을 최대한 유지**하면서 번역합니다.

## 빠른 시작

```bash
# 1) 가상환경(선택)
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)

# 2) 설치
pip install -r requirements.txt

# 3) DeepL API 키 설정 (둘 중 하나 선택)
export DEEPL_API_KEY=your_api_key_here        # macOS/Linux
# set DEEPL_API_KEY=your_api_key_here         # Windows PowerShell

# 또는 Streamlit 실행 후 사이드바에 직접 입력

# 4) 실행
streamlit run app.py
```

## 기능
- 📎 파일 업로드: PDF, PPTX, DOCX, XLSX
- 🌐 타겟 언어 선택 (한국어/영어/일본어/중국어 등)
- 🧠 원문 언어 자동 감지 (옵션)
- ✍️ 문체(formality) 옵션 (지원 언어에서 적용)
- 💾 번역 파일 그대로 다운로드

## 주의사항
- DeepL 문서 번역은 요금제/계정에 따라 **파일 크기/페이지 수 제한**이 있습니다.
- PDF는 원본 구조/글꼴 등에 따라 서식 보존 정도가 달라질 수 있습니다.
- 업로드한 파일은 일시적으로만 디스크에 저장되며, 번역 완료 후 정리합니다.
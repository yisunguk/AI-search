import fitz
import zipfile
import io
import os

# Mock Streamlit UploadedFile
class MockUploadedFile:
    def __init__(self, name, content):
        self.name = name
        self.content = content
    
    def getvalue(self):
        return self.content

def is_drm_protected(uploaded_file):
    """
    Copy of the function from app.py for testing
    """
    try:
        file_type = uploaded_file.name.split('.')[-1].lower()
        
        # 1. PDF Check
        if file_type == 'pdf':
            try:
                # Read file stream
                bytes_data = uploaded_file.getvalue()
                with fitz.open(stream=bytes_data, filetype="pdf") as doc:
                    if doc.is_encrypted:
                        return True
            except Exception as e:
                print(f"PDF DRM Check Error: {e}")
                # If we can't open it with fitz, it might be corrupted or heavily encrypted
                return False 

        # 2. Office Files (docx, pptx, xlsx) Check
        elif file_type in ['docx', 'pptx', 'xlsx']:
            try:
                bytes_data = uploaded_file.getvalue()
                # Check if it is a valid zip file
                if not zipfile.is_zipfile(io.BytesIO(bytes_data)):
                    # Not a zip -> Likely Encrypted/DRM (OLE format)
                    return True
                
                # Optional: Try to open it to be sure
                with zipfile.ZipFile(io.BytesIO(bytes_data)) as zf:
                    # Check for standard OOXML structure (e.g., [Content_Types].xml)
                    if '[Content_Types].xml' not in zf.namelist():
                        return True
            except Exception as e:
                print(f"Office DRM Check Error: {e}")
                return True # Assume protected if we can't parse structure
                
        return False
    except Exception as e:
        print(f"General DRM Check Error: {e}")
        return False

def create_sample_files():
    # 1. Normal PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello World")
    normal_pdf_bytes = doc.tobytes()
    doc.close()
    
    # 2. Encrypted PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Secret World")
    # encrypt with password "secret"
    doc.save("temp_enc.pdf", encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secret", user_pw="secret")
    doc.close()
    with open("temp_enc.pdf", "rb") as f:
        enc_pdf_bytes = f.read()
    os.remove("temp_enc.pdf")

    # 3. Normal DOCX (Valid Zip)
    # Create a valid minimal zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<Types></Types>')
    normal_docx_bytes = buf.getvalue()

    # 4. Fake Encrypted DOCX (Not a Zip)
    enc_docx_bytes = b"This is not a zip file, simulating OLE header..."

    return [
        MockUploadedFile("normal.pdf", normal_pdf_bytes),
        MockUploadedFile("encrypted.pdf", enc_pdf_bytes),
        MockUploadedFile("normal.docx", normal_docx_bytes),
        MockUploadedFile("encrypted.docx", enc_docx_bytes)
    ]

def run_tests():
    files = create_sample_files()
    
    print("Running DRM Detection Tests...")
    
    # Test 1: Normal PDF
    assert is_drm_protected(files[0]) == False, "Normal PDF should not be detected as DRM"
    print("PASS: Normal PDF")
    
    # Test 2: Encrypted PDF
    assert is_drm_protected(files[1]) == True, "Encrypted PDF should be detected as DRM"
    print("PASS: Encrypted PDF")
    
    # Test 3: Normal DOCX
    assert is_drm_protected(files[2]) == False, "Normal DOCX should not be detected as DRM"
    print("PASS: Normal DOCX")
    
    # Test 4: Encrypted DOCX (Non-Zip)
    assert is_drm_protected(files[3]) == True, "Encrypted DOCX (Non-Zip) should be detected as DRM"
    print("PASS: Encrypted DOCX")
    
    print("All tests passed!")

if __name__ == "__main__":
    run_tests()

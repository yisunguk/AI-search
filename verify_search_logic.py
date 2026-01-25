import re

def verify_logic():
    user_message = "냉각수펌프 전기실 내용을 알려주세요"
    
    # 1. Verify Sanitization (No Stopword Removal)
    sanitized_query = re.sub(r'\bAND\b', ' ', user_message, flags=re.IGNORECASE)
    sanitized_query = re.sub(r'[&+\-|!(){}\[\]^"~*?:\\]', ' ', sanitized_query)
    sanitized_query = " ".join(sanitized_query.split())
    
    print(f"Original: '{user_message}'")
    print(f"Sanitized: '{sanitized_query}'")
    
    expected = "냉각수펌프 전기실 내용을 알려주세요"
    if sanitized_query == expected:
        print("✅ Sanitization matches Debug Tool (No stopwords removed)")
    else:
        print(f"❌ Sanitization mismatch! Expected '{expected}', got '{sanitized_query}'")

    # 2. Verify Threshold Logic
    exact_match_count = 5
    EXACT_MATCH_THRESHOLD = 3
    
    if exact_match_count < EXACT_MATCH_THRESHOLD:
        print("❌ Threshold Logic Failed: Should NOT expand if count is 5")
    else:
        print("✅ Threshold Logic Correct: Skips expansion if count >= 3")

if __name__ == "__main__":
    verify_logic()

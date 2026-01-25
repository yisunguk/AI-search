"""
Login Page Module
Renders login UI
"""

import streamlit as st
from utils.auth_manager import AuthManager
from datetime import datetime, timedelta

def render_login_page(auth_manager: AuthManager, cookie_manager):
    """
    Render login page
    
    Args:
        auth_manager: AuthManager instance
        cookie_manager: CookieManager instance
    """
    # Custom CSS for login page
    st.markdown("""
    <style>
        /* Center login box */
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* Header styling */
        .login-header {
            text-align: center;
            margin-bottom: 10px;
        }
        
        .login-title {
            font-size: 18px;
            color: #333;
            margin: 0;
        }
        
        .login-subtitle {
            font-size: 14px;
            color: #666;
            margin: 5px 0 30px 0;
        }
        
        /* Form styling */
        .stTextInput > label {
            font-size: 14px;
            font-weight: 500;
            color: #333;
        }
        
        /* Button styling */
        .stButton > button {
            width: 100%;
            background-color: #1E88E5;
            color: white;
            font-weight: 600;
            border-radius: 8px;
            padding: 12px;
            border: none;
            font-size: 16px;
        }
        
        .stButton > button:hover {
            background-color: #1565C0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Logo and Title (Outside columns for full width centering)
    st.markdown("""
    <div style="text-align: center; padding-top: 5vh; padding-bottom: 2rem;">
        <h1 style="font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">🏗️ 인텔리전트 다큐먼트</h1>
        <p style="font-size: 1.2rem; color: #666;">RAG 기반 지능형 문서 분석 시스템</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Use columns to center the login form
    _, col_center, _ = st.columns([1, 1.5, 1])
    
    with col_center:
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 2rem; border-radius: 15px; border: 1px solid #e9ecef; box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-bottom: 2rem;">
            <h2 style="text-align: center; margin-top: 0; margin-bottom: 1.5rem; font-weight: 600; color: #333;">로그인</h2>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("이메일", placeholder="example@email.com")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")
            
            if submitted:
                if not email or not password:
                    st.error("이메일과 비밀번호를 입력해주세요.")
                else:
                    with st.spinner("인증 중..."):
                        success, user_info, message = auth_manager.login(email, password)
                        
                        if success:
                            st.session_state.is_logged_in = True
                            st.session_state.user_info = user_info
                            
                            # Set cookie (expires in 7 days)
                            expires = datetime.now() + timedelta(days=7)
                            cookie_manager.set("auth_email", email, expires_at=expires)
                            
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
        
        st.markdown("""
        </div>
        <p style="text-align: center; color: #6c757d; font-size: 0.9rem;">
            ℹ️ 계정 생성 및 비밀번호 초기화는 관리자에게 문의하세요.
        </p>
        """, unsafe_allow_html=True)
        
        # Debug info in expander
        with st.expander("🛠️ 시스템 디버그 정보", expanded=False):
            user_count = len(auth_manager.users)
            if user_count == 0:
                st.error("⚠️ 사용자 정보가 로드되지 않았습니다. Secrets 설정을 확인하세요.")
                try:
                    st.write("Available Secret Keys:", list(st.secrets.keys()))
                except:
                    st.write("Secrets access failed")
            else:
                st.caption(f"Debug: {user_count} users loaded from secrets.")
                try:
                    emails = [str(u.get('email', 'No Email')) for u in auth_manager.users.values()]
                    st.code(f"Loaded Emails: {emails}")
                except Exception as e:
                    st.caption(f"Error displaying emails: {e}")


"""
Login Page Module
Renders login UI
"""

import streamlit as st
from utils.auth_manager import AuthManager

def render_login_page(auth_manager: AuthManager):
    """
    Render login page
    
    Args:
        auth_manager: AuthManager instance
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
    
    # Logo and Title
    st.markdown("""
    <div class="login-header">
        <h1 style="font-size: 24px; margin: 0;">🏗️ 현장똑똑 AI</h1>
        <p class="login-subtitle">RAG 기반 시스템</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Main container
    with st.container():
        _render_login_form(auth_manager)


def _render_login_form(auth_manager: AuthManager):
    """Render login form"""
    st.markdown("<h3 style='text-align: center; margin-bottom: 30px;'>로그인</h3>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        email = st.text_input("이메일", placeholder="example@email.com")
        password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        
        submitted = st.form_submit_button("로그인", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("이메일과 비밀번호를 입력해주세요.")
            else:
                success, user_info, message = auth_manager.login(email, password)
                
                if success:
                    st.session_state.is_logged_in = True
                    st.session_state.user_info = user_info
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    st.info("ℹ️ 계정 생성 및 비밀번호 초기화는 관리자에게 문의하세요.")

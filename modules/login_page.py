"""
Login Page Module
Renders login and signup UI
"""

import streamlit as st
from utils.auth_manager import AuthManager

def render_login_page(auth_manager: AuthManager):
    """
    Render login/signup page
    
    Args:
        auth_manager: AuthManager instance
    """
    # Initialize view state
    if 'auth_view' not in st.session_state:
        st.session_state.auth_view = 'login'  # 'login' or 'signup'
    
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
        
        /* Link buttons */
        .link-button {
            text-align: center;
            margin-top: 20px;
        }
        
        .link-button button {
            background: none !important;
            border: none !important;
            color: #1E88E5 !important;
            text-decoration: underline;
            font-size: 14px;
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
        if st.session_state.auth_view == 'login':
            _render_login_form(auth_manager)
        else:
            _render_signup_form(auth_manager)


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
    
    # Password reset (mockup)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("비밀번호 재설정", key="reset_pw"):
            st.info("비밀번호 재설정 기능은 관리자에게 문의해주세요.")
    
    with col2:
        if st.button("회원가입하기", key="goto_signup"):
            st.session_state.auth_view = 'signup'
            st.rerun()


def _render_signup_form(auth_manager: AuthManager):
    """Render signup form"""
    st.markdown("<h3 style='text-align: center; margin-bottom: 30px;'>회원가입</h3>", unsafe_allow_html=True)
    
    with st.form("signup_form"):
        name = st.text_input("이름", placeholder="홍길동")
        email = st.text_input("이메일", placeholder="example@email.com")
        password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        password_confirm = st.text_input("비밀번호 확인", type="password", placeholder="비밀번호를 다시 입력하세요")
        
        submitted = st.form_submit_button("회원가입", use_container_width=True)
        
        if submitted:
            if not all([name, email, password, password_confirm]):
                st.error("모든 필드를 입력해주세요.")
            elif password != password_confirm:
                st.error("비밀번호가 일치하지 않습니다.")
            elif len(password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                success, message = auth_manager.signup(email, password, name)
                
                if success:
                    st.success(message + " 이제 로그인하세요.")
                    st.session_state.auth_view = 'login'
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
    
    # Back to login
    if st.button("← 로그인으로 돌아가기", key="back_to_login"):
        st.session_state.auth_view = 'login'
        st.rerun()

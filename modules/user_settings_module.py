"""
User Settings Module
Allows users to manage their profile and settings
"""

import streamlit as st
from utils.auth_manager import AuthManager

def render_user_settings(auth_manager: AuthManager):
    """
    Render user settings page
    
    Args:
        auth_manager: AuthManager instance
    """
    user_info = st.session_state.get('user_info', {})
    
    st.markdown("### 👤 내 정보")
    st.write(f"**이름:** {user_info.get('name', 'Unknown')}")
    st.write(f"**이메일:** {user_info.get('email', 'Unknown')}")
    st.write(f"**권한:** {user_info.get('role', 'user').upper()}")
    
    st.divider()
    
    # Password change
    st.markdown("### 🔒 비밀번호 변경")
    
    with st.form("change_password_form"):
        old_password = st.text_input("현재 비밀번호", type="password")
        new_password = st.text_input("새 비밀번호", type="password")
        new_password_confirm = st.text_input("새 비밀번호 확인", type="password")
        
        submitted = st.form_submit_button("비밀번호 변경")
        
        if submitted:
            if not all([old_password, new_password, new_password_confirm]):
                st.error("모든 필드를 입력해주세요.")
            elif new_password != new_password_confirm:
                st.error("새 비밀번호가 일치하지 않습니다.")
            elif len(new_password) < 6:
                st.error("비밀번호는 최소 6자 이상이어야 합니다.")
            else:
                success, message = auth_manager.update_password(
                    user_info['email'],
                    old_password,
                    new_password
                )
                
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    st.divider()
    
    # Admin features
    if user_info.get('role') == 'admin':
        _render_admin_panel(auth_manager)


def _render_admin_panel(auth_manager: AuthManager):
    """Render admin panel for user management"""
    st.markdown("### ⚙️ 관리자 기능")
    st.caption("사용자 관리 및 권한 설정")
    
    users = auth_manager.get_all_users()
    
    if users:
        st.markdown(f"**총 사용자 수:** {len(users)}명")
        
        for user in users:
            with st.expander(f"{user['name']} ({user['email']})"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**ID:** {user['id']}")
                    st.write(f"**가입일:** {user['created_at']}")
                    st.write(f"**현재 권한:** {user['role'].upper()}")
                
                with col2:
                    new_role = st.selectbox(
                        "권한 변경",
                        options=['user', 'admin'],
                        index=0 if user['role'] == 'user' else 1,
                        key=f"role_{user['id']}"
                    )
                    
                    if st.button("변경", key=f"btn_{user['id']}"):
                        if new_role != user['role']:
                            success, message = auth_manager.update_user_role(user['id'], new_role)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
    else:
        st.info("등록된 사용자가 없습니다.")

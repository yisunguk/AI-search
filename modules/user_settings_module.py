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
    
    st.info("ℹ️ 비밀번호 변경이나 정보 수정은 관리자에게 문의하세요.")
    
    st.divider()
    
    # Admin features
    if user_info.get('role') == 'admin':
        _render_admin_panel(auth_manager)


def _render_admin_panel(auth_manager: AuthManager):
    """Render admin panel for user management"""
    st.markdown("### ⚙️ 관리자 기능 (읽기 전용)")
    st.caption("현재 등록된 사용자 목록입니다. 사용자 추가/수정은 Streamlit Cloud Secrets 설정에서 가능합니다.")
    
    users = auth_manager.get_all_users()
    
    if users:
        st.markdown(f"**총 사용자 수:** {len(users)}명")
        
        for user in users:
            with st.expander(f"{user['name']} ({user['email']})"):
                st.write(f"**ID (Key):** {user['id']}")
                st.write(f"**권한:** {user['role'].upper()}")
                
                # Menu Permissions
                st.markdown("#### 🔐 메뉴 접근 권한")
                current_perms = user.get('permissions', [])
                if 'all' in current_perms:
                    st.success("모든 메뉴 접근 가능 (Admin)")
                elif current_perms:
                    for perm in current_perms:
                        st.write(f"- {perm}")
                else:
                    st.warning("접근 가능한 메뉴가 없습니다.")
                    
    else:
        st.info("등록된 사용자가 없습니다.")

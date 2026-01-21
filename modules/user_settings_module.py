"""
User Settings Module
Allows users to manage their profile and settings
"""

import streamlit as st
import time
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
    st.markdown("### ⚙️ 관리자 기능")
    st.caption("사용자 권한 관리 (Azure Storage에 저장됨)")
    
    users = auth_manager.get_all_users()
    
    if users:
        st.markdown(f"**총 사용자 수:** {len(users)}명")
        
        for user in users:
            with st.expander(f"{user['name']} ({user['email']})"):
                st.write(f"**ID (Key):** {user['id']}")
                st.write(f"**권한:** {user['role'].upper()}")
                
                # Menu Permissions
                st.markdown("#### 🔐 메뉴 접근 권한")
                all_menus = ["번역하기", "파일 보관함", "검색 & AI 채팅", "도면/스펙 분석", "엑셀데이터 자동추출", "사진대지 자동작성", "작업계획 및 투입비 자동작성"]
                
                # Current permissions
                current_perms = user.get('permissions', [])
                
                # Check if user has 'all' permission (Admin usually)
                is_admin_all = 'all' in current_perms
                
                if is_admin_all:
                    st.success("✅ 모든 메뉴 접근 가능 (Admin/All)")
                    st.info("이 사용자는 'all' 권한을 가지고 있어 개별 메뉴 선택이 불필요합니다.")
                else:
                    # Ensure "홈" and "사용자 설정" are not in the selection list (they are mandatory)
                    default_selection = [m for m in current_perms if m in all_menus]
                    
                    selected_menus = st.multiselect(
                        "허용할 메뉴 선택",
                        options=all_menus,
                        default=default_selection,
                        key=f"perms_{user['id']}"
                    )
                    
                    if st.button("메뉴 권한 저장", key=f"btn_perms_{user['id']}"):
                        # Always include mandatory menus
                        # Note: We store only the selected menus + mandatory ones. 
                        # 'all' is not added here unless manually handled, but we are editing specific menus.
                        final_permissions = ["홈", "사용자 설정"] + selected_menus
                        
                        success, message = auth_manager.update_user_permissions(user['email'], final_permissions)
                        if success:
                            st.success(message)
                            time.sleep(1) # Wait for propagation
                            st.rerun()
                        else:
                            st.error(message)
                    
    else:
        st.info("등록된 사용자가 없습니다.")

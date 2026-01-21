"""
Authentication Manager (Secrets-based)
Handles user authentication using Streamlit Secrets
"""

import streamlit as st
from typing import Optional, Tuple, Dict

class AuthManager:
    def __init__(self):
        # Load users from secrets
        self.users = self._load_users()
    
    def _load_users(self) -> Dict:
        """Load users from st.secrets"""
        try:
            return st.secrets.get("auth_users", {})
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
    
    def login(self, email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Authenticate user against secrets
        """
        # Iterate through users in secrets to find matching email
        input_email = email.strip().lower()
        
        for username, user_data in self.users.items():
            stored_email = str(user_data.get("email", "")).strip().lower()
            
            if stored_email == input_email:
                # Check password (exact match required)
                # Handle both string and integer passwords from secrets
                stored_password = str(user_data.get("password", ""))
                if stored_password == str(password):
                    # Login Success
                    user_info = {
                        'id': username,  # Use key as ID
                        'email': user_data['email'],
                        'name': user_data['name'],
                        'role': user_data.get('role', 'user'),
                        'permissions': user_data.get('permissions', [])
                    }
                    return True, user_info, f"환영합니다, {user_data['name']}님!"
                else:
                    return False, None, "비밀번호가 올바르지 않습니다."
        
        return False, None, "등록되지 않은 이메일입니다."
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user information by email"""
        for username, user_data in self.users.items():
            if user_data.get("email") == email:
                return {
                    'id': username,
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'role': user_data.get('role', 'user'),
                    'permissions': user_data.get('permissions', [])
                }
        return None
    
    def get_all_users(self) -> list:
        """Get all users (admin only)"""
        users_list = []
        for username, user_data in self.users.items():
            users_list.append({
                'id': username,
                'email': user_data['email'],
                'name': user_data['name'],
                'role': user_data.get('role', 'user'),
                'permissions': user_data.get('permissions', [])
            })
        return users_list

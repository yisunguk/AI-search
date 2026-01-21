"""
Authentication Manager
Handles user authentication, database management, and role-based access control
"""

import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional, Tuple, Dict

class AuthManager:
    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database and create users table if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create default admin user if no users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            admin_hash = self.hash_password('admin123')
            cursor.execute(
                'INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)',
                ('admin@example.com', admin_hash, 'Administrator', 'admin')
            )
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        salt = b'현장똑똑AI_SALT'  # In production, use random salt per user
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()
    
    def signup(self, email: str, password: str, name: str) -> Tuple[bool, str]:
        """
        Create new user account
        
        Returns:
            (success: bool, message: str)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute('SELECT email FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                return False, "이미 등록된 이메일입니다."
            
            # Insert new user
            password_hash = self.hash_password(password)
            cursor.execute(
                'INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)',
                (email, password_hash, name, 'user')
            )
            
            conn.commit()
            conn.close()
            return True, "회원가입이 완료되었습니다!"
            
        except Exception as e:
            return False, f"회원가입 실패: {str(e)}"
    
    def login(self, email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
        """
        Authenticate user
        
        Returns:
            (success: bool, user_info: dict or None, message: str)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            password_hash = self.hash_password(password)
            cursor.execute(
                'SELECT id, email, name, role, approved FROM users WHERE email = ? AND password_hash = ?',
                (email, password_hash)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return False, None, "이메일 또는 비밀번호가 올바르지 않습니다."
            
            user_id, email, name, role, approved = result
            
            if not approved:
                return False, None, "계정이 승인 대기 중입니다. 관리자에게 문의하세요."
            
            user_info = {
                'id': user_id,
                'email': email,
                'name': name,
                'role': role
            }
            
            return True, user_info, f"환영합니다, {name}님!"
            
        except Exception as e:
            return False, None, f"로그인 실패: {str(e)}"
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user information by email"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT id, email, name, role FROM users WHERE email = ?',
                (email,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'email': result[1],
                    'name': result[2],
                    'role': result[3]
                }
            return None
            
        except Exception as e:
            return None
    
    def update_password(self, email: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Update user password"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify old password
            old_hash = self.hash_password(old_password)
            cursor.execute(
                'SELECT id FROM users WHERE email = ? AND password_hash = ?',
                (email, old_hash)
            )
            
            if not cursor.fetchone():
                conn.close()
                return False, "현재 비밀번호가 올바르지 않습니다."
            
            # Update to new password
            new_hash = self.hash_password(new_password)
            cursor.execute(
                'UPDATE users SET password_hash = ? WHERE email = ?',
                (new_hash, email)
            )
            
            conn.commit()
            conn.close()
            return True, "비밀번호가 변경되었습니다."
            
        except Exception as e:
            return False, f"비밀번호 변경 실패: {str(e)}"
    
    def get_all_users(self) -> list:
        """Get all users (admin only)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, email, name, role, created_at, approved FROM users')
            results = cursor.fetchall()
            conn.close()
            
            users = []
            for row in results:
                users.append({
                    'id': row[0],
                    'email': row[1],
                    'name': row[2],
                    'role': row[3],
                    'created_at': row[4],
                    'approved': row[5]
                })
            
            return users
            
        except Exception as e:
            return []
    
    def update_user_role(self, user_id: int, new_role: str) -> Tuple[bool, str]:
        """Update user role (admin only)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
            conn.commit()
            conn.close()
            
            return True, "권한이 변경되었습니다."
            
        except Exception as e:
            return False, f"권한 변경 실패: {str(e)}"

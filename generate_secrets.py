import random
import string

def generate_password():
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits = ''.join(random.choices(string.digits, k=4))
    return letters + digits

users = [
    {"id": "piere", "email": "piere@poscoenc.com", "name": "이성욱", "role": "admin", "permissions": ["all"], "password": "ER2312"},
    {"id": "user1", "email": "kobari@poscoenc.com", "name": "고은경", "role": "user", "permissions": ["번역하기", "파일 보관함"], "password": "NU1763"},
    {"id": "user2", "email": "lee.jieun@example.com", "name": "이지은", "role": "user", "permissions": ["검색 & AI 채팅", "도면/스펙 분석"], "password": "VX8661"},
    {"id": "user3", "email": "park.junho@example.com", "name": "박준호", "role": "user", "permissions": ["엑셀데이터 자동추출", "사진대지 자동작성"], "password": "PF4413"},
    {"id": "user4", "email": "choi.yuna@example.com", "name": "최유나", "role": "user", "permissions": ["작업계획 및 투입비 자동작성", "번역하기"], "password": "DT5081"},
    {"id": "user5", "email": "jung.woosung@example.com", "name": "정우성", "role": "user", "permissions": ["파일 보관함", "검색 & AI 채팅", "도면/스펙 분석"], "password": "VT2871"},
    {"id": "r9t", "email": "r9t@poscoenc.com", "name": "이근배", "role": "user", "permissions": ["검색 & AI 채팅", "도면/스펙 분석", "파일 보관함"]}
]

with open("secrets_output.toml", "w", encoding="utf-8") as f:
    f.write("[auth_users]\n\n")

    for user in users:
        # Use existing password if available, otherwise generate new one
        pwd = user.get("password", generate_password())
        
        f.write(f"# {user['name']}\n")
        f.write(f"[auth_users.{user['id']}]\n")
        f.write(f'email = "{user["email"]}"\n')
        f.write(f'name = "{user["name"]}"\n')
        f.write(f'password = "{pwd}"\n')
        f.write(f'role = "{user["role"]}"\n')
        # Permissions need to be formatted as TOML array strings
        perms_str = ', '.join([f'"{p}"' for p in user['permissions']])
        f.write(f'permissions = [{perms_str}]\n')
        f.write('\n')

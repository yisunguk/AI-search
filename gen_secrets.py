import random
import string
import sys

# Set stdout to utf-8
sys.stdout.reconfigure(encoding='utf-8')

def generate_password():
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits = ''.join(random.choices(string.digits, k=4))
    return letters + digits

users = [
    {"id": "piere", "email": "piere@poscoenc.com", "name": "Lee Sungwook", "role": "admin", "permissions": ["all"]},
    {"id": "user1", "email": "kim.minsoo@example.com", "name": "Kim Minsoo", "role": "user", "permissions": ["번역하기", "파일 보관함"]},
    {"id": "user2", "email": "lee.jieun@example.com", "name": "Lee Jieun", "role": "user", "permissions": ["검색 & AI 채팅", "도면/스펙 분석"]},
    {"id": "user3", "email": "park.junho@example.com", "name": "Park Junho", "role": "user", "permissions": ["엑셀데이터 자동추출", "사진대지 자동작성"]},
    {"id": "user4", "email": "choi.yuna@example.com", "name": "Choi Yuna", "role": "user", "permissions": ["작업계획 및 투입비 자동작성", "번역하기"]},
    {"id": "user5", "email": "jung.woosung@example.com", "name": "Jung Woosung", "role": "user", "permissions": ["파일 보관함", "검색 & AI 채팅", "도면/스펙 분석"]}
]

with open("temp_secrets.txt", "w", encoding="utf-8") as f:
    f.write("[auth_users]\n\n")

    for user in users:
        pwd = generate_password()
        f.write(f"# {user['name']}\n")
        f.write(f"[auth_users.{user['id']}]\n")
        f.write(f'email = "{user["email"]}"\n')
        f.write(f'name = "{user["name"]}"\n')
        f.write(f'password = "{pwd}"\n')
        f.write(f'role = "{user["role"]}"\n')
        perms_str = ', '.join([f'"{p}"' for p in user['permissions']])
        f.write(f'permissions = [{perms_str}]\n')
        f.write('\n')

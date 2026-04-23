#!/usr/bin/env python3
"""检查数据库中admin用户的密码hash信息"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import User

db = SessionLocal()
user = db.query(User).filter(User.username == "admin").first()

if user:
    print("=" * 70)
    print("Admin用户信息")
    print("=" * 70)
    print(f"用户名: {user.username}")
    print(f"邮箱: {user.email}")
    print(f"角色: {user.user_role}")
    print(f"是否激活: {user.is_active}")
    print(f"\npassword_hash长度: {len(user.password_hash)}")
    print(f"password_hash内容: {user.password_hash}")
    print(f"\npassword_hash类型: {type(user.password_hash)}")
    
    # 检查是不是bcrypt hash或plaintext
    if user.password_hash.startswith("$2"):
        print("✅ 看起来是bcrypt hash格式")
    elif user.password_hash.startswith("$"):
        print("⚠️  看起来是其他hash格式")
    else:
        print("⚠️  看起来可能是plaintext!")
        if user.password_hash == "admin123":
            print("   确实是plaintext: admin123")
else:
    print("❌ 找不到admin用户")

db.close()

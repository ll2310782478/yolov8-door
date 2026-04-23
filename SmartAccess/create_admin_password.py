#!/usr/bin/env python3
"""创建或更新admin用户为已知密码"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import User, Role
from app.auth import get_password_hash
from sqlalchemy.orm import noload

db = SessionLocal()

# 查找admin用户
user = db.query(User).options(noload(User.faces)).filter(User.username == "admin").first()

if user:
    print(f"Found admin user, updating password...")
    # 更新密码为"Test@1234"
    user.password_hash = get_password_hash("Test@1234")
    db.commit()
    print(f"Updated admin password to: Test@1234")
    print(f"New password_hash: {user.password_hash}")
else:
    print("ERROR: admin user not found")

db.close()

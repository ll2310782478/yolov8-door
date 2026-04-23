#!/usr/bin/env python3
"""测试verify_password是否返回正确的布尔值"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import User
from app.auth import verify_password
import json

db = SessionLocal()
user = db.query(User).filter(User.username == "admin").first()

print("=" * 70)
print("verify_password test" )
print("=" * 70)

if user:
    print(f"\npassword_hash: {user.password_hash}")
    print(f"test password: admin123")
    
    # 直接调用verify_password
    print("\nCalling verify_password...")
    try:
        result = verify_password("admin123", user.password_hash)
        print(f"OK: verify_password returned: {result}")
        print(f"   type: {type(result)}")
        print(f"   is bool: {isinstance(result, bool)}")
        
        # 尝试JSON序列化
        test_dict = {"result": result}
        json_str = json.dumps(test_dict)
        print(f"   JSON serialize success: {json_str}")
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"   Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
else:
    print("ERROR: admin user not found")

db.close()


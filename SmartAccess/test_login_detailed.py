#!/usr/bin/env python3
"""
在本地测试登录流程并打印完整的堆栈跟踪
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 直接在Python中导入并测试，这样可以看到完整的错误
from app.database import SessionLocal
from app.models import User
from app.auth import verify_password, create_access_token
from app.routers.auth import LoginRequest, LoginResponse, Token
from datetime import timedelta
from sqlalchemy.orm import noload
import traceback

print("=" * 70)
print("完整登录流程调试 - 捕获所有异常")
print("=" * 70)

try:
    db = SessionLocal()
    
    # Step 1: 查询用户 (WITH noload)
    print("\n[Step 1] 查询用户 (带noload)...")
    user = db.query(User).options(noload(User.faces)).filter(User.username == "admin").first()
    print(f"  ✅ 用户查询成功: {user}")
    if user:
        print(f"     用户名: {user.username}")
        print(f"     邮箱: {user.email}")
        print(f"     角色: {user.user_role}")
    
    # Step 2: 验证密码
    print("\n[Step 2] 验证密码...")
    if user:
        is_valid = verify_password("admin123", user.password_hash)
        print(f"  {'✅' if is_valid else '❌'} 密码验证: {is_valid}")
    
    # Step 3: 创建令牌
    print("\n[Step 3] 创建令牌...")
    if user and is_valid and user.is_active:
        token_data = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.user_role
        }
        access_token = create_access_token(token_data, timedelta(minutes=30))
        print(f"  ✅ 令牌创建成功")
        print(f"     令牌长度: {len(access_token)}")
        print(f"     令牌前缀: {access_token[:20]}...")
        
        # Step 4  Serialize Token
        print("\n[Step 4] 序列化Token对象...")
        try:
            token_obj = Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=30 * 60
            )
            print(f"  ✅ Token对象创建成功")
            print(f"     {token_obj}")
            
            # 尝试转换为dict（FastAPI会调用这个）
            print("\n[Step 5] 尝试转换Token为dict...")
            token_dict = token_obj.dict()
            print(f"  ✅ 成功转换为dict")
            
            # Step 6: Create LoginResponse
            print("\n[Step 6] 创建LoginResponse...")
            response = LoginResponse(
                code=200,
                message="登录成功",
                data=token_obj
            )
            print(f"  ✅ LoginResponse创建成功")
            
            # 尝试序列化
            print("\n[Step 7] 尝试序列化LoginResponse...")
            response_dict = response.dict()
            print(f"  ✅ 成功序列化为dict")
            
            # 最后尝试JSON序列化
            print("\n[Step 8] JSON序列化测试...")
            import json
            json_str = json.dumps(response_dict)
            print(f"  ✅ JSON序列化成功")
            print(f"     JSON长度: {len(json_str)}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            traceback.print_exc()
    
    db.close()
    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ 异常发生: {e}")
    print("\n完整堆栈跟踪:")
    traceback.print_exc()

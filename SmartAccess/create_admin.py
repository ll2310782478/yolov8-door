"""创建管理员账户脚本"""

import os
import sys
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.models import User, Role, UserPermission

load_dotenv()

def create_admin_user(username: str = "admin", password: str = "admin@123456", email: str = "admin@smartaccess.com"):
    """创建管理员用户"""
    init_db()  # 确保数据库初始化
    
    db = SessionLocal()
    try:
        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"❌ 用户 '{username}' 已存在")
            return False
        
        # 创建用户
        user = User(
            username=username,
            password_hash=password,  # 注意：这里应该被哈希处理
            email=email,
            phone="00000000000",
            full_name="系统管理员",
            is_active=True
        )
        db.add(user)
        db.flush()  # 获取生成的 user_id
        
        # 创建管理员角色
        admin_role = Role(
            user_id=user.id,
            role_name="admin",
            permissions='["users:create","users:read","users:update","users:delete","hardware:manage","logs:read","system:manage"]'
        )
        db.add(admin_role)
        
        # 创建权限配置
        permission_types = ["face_recognition", "nfc", "bluetooth", "qrcode"]
        for perm_type in permission_types:
            perm = UserPermission(
                user_id=user.id,
                permission_type=perm_type,
                is_enabled=True
            )
            db.add(perm)
        
        db.commit()
        print("✅ 管理员账户创建成功！")
        print(f"   用户名: {username}")
        print(f"   密码: {password}")
        print(f"   邮箱: {email}")
        print("\n⚠️  安全提示:")
        print("   1. 请妥善保管管理员密码")
        print("   2. 首次登录后请修改默认密码")
        print("   3. 生产环境应使用强密码")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        return False
    finally:
        db.close()


def list_users():
    """列出所有用户"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("📭 目前没有用户")
            return
        
        print("\n📋 用户列表:")
        print("-" * 60)
        for user in users:
            role = db.query(Role).filter(Role.user_id == user.id).first()
            role_name = role.role_name if role else "未分配"
            status = "✅ 激活" if user.is_active else "❌ 禁用"
            print(f"ID: {user.id} | 用户名: {user.username:20} | 角色: {role_name:10} | {status}")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ 获取用户列表失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SmartAccess 管理员管理工具")
    parser.add_argument("--create", action="store_true", help="创建管理员账户")
    parser.add_argument("--list", action="store_true", help="列出所有用户")
    parser.add_argument("--username", default="admin", help="用户名 (默认: admin)")
    parser.add_argument("--password", default="admin@123456", help="密码 (默认: admin@123456)")
    parser.add_argument("--email", default="admin@smartaccess.com", help="邮箱 (默认: admin@smartaccess.com)")
    
    args = parser.parse_args()
    
    if args.create:
        create_admin_user(args.username, args.password, args.email)
    elif args.list:
        list_users()
    else:
        parser.print_help()

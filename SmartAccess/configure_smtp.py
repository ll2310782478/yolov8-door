#!/usr/bin/env python3
"""
SMTP配置脚本
用于配置邮件发送服务，实现访客二维码下发功能
"""

import os
import sys
import getpass

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import SystemConfig
from sqlalchemy.orm import sessionmaker

def configure_smtp():
    """配置SMTP服务器设置"""

    print("="*60)
    print("  SmartAccess SMTP 配置工具")
    print("="*60)
    print("此工具将配置邮件发送服务，用于访客二维码下发")
    print()

    # SMTP配置选项
    smtp_configs = {
        "gmail": {
            "host": "smtp.gmail.com",
            "port": "587",
            "description": "Gmail邮箱 (推荐)"
        },
        "163": {
            "host": "smtp.163.com",
            "port": "465",
            "description": "163邮箱"
        },
        "qq": {
            "host": "smtp.qq.com",
            "port": "587",
            "description": "QQ邮箱"
        },
        "custom": {
            "host": "",
            "port": "",
            "description": "自定义SMTP服务器"
        }
    }

    print("可用的SMTP服务：")
    for key, config in smtp_configs.items():
        print(f"  {key}: {config['description']}")

    while True:
        choice = input("\n请选择SMTP服务 (gmail/163/qq/custom): ").strip().lower()
        if choice in smtp_configs:
            break
        print("无效选择，请重新输入")

    if choice == "custom":
        smtp_host = input("请输入SMTP服务器地址: ").strip()
        smtp_port = input("请输入SMTP端口 (通常587或465): ").strip()
    else:
        smtp_host = smtp_configs[choice]["host"]
        smtp_port = smtp_configs[choice]["port"]

    smtp_user = input("请输入邮箱地址: ").strip()
    smtp_password = getpass.getpass("请输入邮箱密码/授权码: ")

    # 验证输入
    if not smtp_user or not smtp_password:
        print("❌ 邮箱地址和密码不能为空")
        return False

    # 保存配置到数据库
    try:
        db = SessionLocal()

        # 更新或创建配置
        configs = {
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password": smtp_password
        }

        for key, value in configs.items():
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                config.value = value
            else:
                config = SystemConfig(
                    key=key,
                    value=value,
                    description=f"SMTP配置: {key}"
                )
                db.add(config)

        db.commit()
        print("✅ SMTP配置已保存到数据库")

        # 显示配置信息
        print("\n配置信息:")
        print(f"  SMTP服务器: {smtp_host}:{smtp_port}")
        print(f"  邮箱地址: {smtp_user}")
        print("  密码: *******")
        print("\n📧 现在您可以测试邮件发送功能了！")

        return True

    except Exception as e:
        print(f"❌ 配置保存失败: {str(e)}")
        return False
    finally:
        db.close()

def test_email():
    """测试邮件发送功能"""
    print("\n" + "="*40)
    print("  邮件发送测试")
    print("="*40)

    test_email = input("请输入测试邮箱地址: ").strip()
    if not test_email:
        print("❌ 测试邮箱不能为空")
        return

    try:
        import requests

        # 调用API测试邮件发送
        BASE_URL = "http://localhost:8000"
        response = requests.post(
            f"{BASE_URL}/api/test-email",
            json={"email": test_email}
        )

        if response.status_code == 200:
            print("✅ 测试邮件发送成功！请检查邮箱")
        else:
            print(f"❌ 测试邮件发送失败: {response.text}")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        print("请确保服务器正在运行 (python -m uvicorn app.main:app --reload)")

if __name__ == "__main__":
    if configure_smtp():
        choice = input("\n是否现在测试邮件发送? (y/n): ").strip().lower()
        if choice == 'y':
            test_email()

    print("\n配置完成！您现在可以使用访客二维码下发功能了。")
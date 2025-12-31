"""
二维码邮件发送测试脚本
用于测试访客二维码邮件发送功能
"""

import requests
import json

# API 基础URL
BASE_URL = "http://localhost:8000"

def test_qrcode_email():
    """测试二维码邮件发送完整流程"""
    
    print("="*60)
    print("  SmartAccess 二维码邮件发送测试")
    print("="*60)
    
    # 步骤1: 创建访客
    print("\n[步骤1] 创建访客...")
    visitor_data = {
        "name": "测试访客-张三",
        "email": "test@example.com",  # 替换为真实邮箱
        "phone": "13800138000",
        "company": "测试公司",
        "purpose": "功能测试",
        "max_duration_hours": 8
    }
    
    response = requests.post(f"{BASE_URL}/api/visitors/", json=visitor_data)
    
    if response.status_code == 200:
        visitor = response.json()
        visitor_id = visitor["id"]
        print(f"✅ 访客创建成功！")
        print(f"   访客ID: {visitor_id}")
        print(f"   姓名: {visitor['name']}")
        print(f"   邮箱: {visitor['email']}")
        print(f"   二维码路径: {visitor['qr_code_path']}")
    else:
        print(f"❌ 创建失败: {response.text}")
        return
    
    # 步骤2: 发送二维码邮件
    print("\n[步骤2] 发送二维码到邮箱...")
    
    response = requests.post(
        f"{BASE_URL}/api/visitors/{visitor_id}/send-qrcode",
        params={"send_via": "email"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 邮件发送成功！")
        print(f"   状态: {result['status']}")
        print(f"   消息: {result['message']}")
        print(f"   收件人: {result['sent_to']}")
    else:
        print(f"❌ 发送失败: {response.text}")
        return
    
    # 步骤3: 验证二维码（模拟扫码）
    print("\n[步骤3] 验证二维码...")
    
    # 获取二维码token
    response = requests.get(f"{BASE_URL}/api/visitors/{visitor_id}/qrcode")
    
    if response.status_code == 200:
        qrcode_info = response.json()
        qrcode_token = qrcode_info["qrcode_token"]
        
        # 验证二维码
        response = requests.post(
            f"{BASE_URL}/api/visitors/qrcode/verify",
            params={"qrcode_token": qrcode_token, "device_id": "test-device-001"}
        )
        
        if response.status_code == 200:
            verify_result = response.json()
            print(f"✅ 二维码验证结果: {verify_result['status']}")
            if verify_result['status'] == 'valid':
                print(f"   访客姓名: {verify_result['visitor_name']}")
                print(f"   公司: {verify_result['company']}")
                print(f"   访问次数: {verify_result['access_count']}")
        else:
            print(f"❌ 验证失败: {response.text}")
    else:
        print(f"❌ 获取二维码失败: {response.text}")
    
    print("\n" + "="*60)
    print("  测试完成！")
    print("="*60)
    print("\n📧 请检查邮箱是否收到二维码邮件")
    print("   如果未收到，请检查：")
    print("   1. .env 中的 SMTP_USER 和 SMTP_PASSWORD 是否正确")
    print("   2. 邮箱是否开启了SMTP服务")
    print("   3. 邮件是否进入垃圾箱")


if __name__ == "__main__":
    try:
        test_qrcode_email()
    except requests.exceptions.ConnectionError:
        print("❌ 错误：无法连接到服务器")
        print("   请确保服务已启动：")
        print("   cd U:\\BYSJ\\yolov-door\\yolov8-door\\SmartAccess")
        print("   python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")

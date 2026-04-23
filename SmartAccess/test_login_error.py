#!/usr/bin/env python3
"""捕获登录错误的精确堆栈跟踪"""

import requests
import json
import sys
import os
import traceback

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = f"{BASE_URL}/api"

def test_login():
    """测试登录并捕获详细错误"""
    print("=" * 70)
    print("登录测试 - 捕获详细错误堆栈")
    print("=" * 70)
    
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print(f"\n发送请求: POST {API_PREFIX}/auth/login")
    print(f"数据: {login_data}")
    
    try:
        response = requests.post(
            f"{API_PREFIX}/auth/login",
            data=login_data,
            timeout=10
        )
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"\n响应体 (原始):")
        print(response.text[:2000])  # 前2000字符
        
        if response.status_code != 200:
            print(f"\n❌ 登录失败")
            print(f"错误详情:")
            try:
                json_resp = response.json()
                print(json.dumps(json_resp, indent=2, ensure_ascii=False))
            except:
                print(response.text)
                
            # 如果是500，尝试在服务器端检查日志
            if response.status_code == 500:
                print("\n⚠️  服务器返回500错误，请检查服务器logs")
        else:
            print(f"\n✅ 登录成功")
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ 未知异常: {e}")
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    success = test_login()
    sys.exit(0 if success else 1)

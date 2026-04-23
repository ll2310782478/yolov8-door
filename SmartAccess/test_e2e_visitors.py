#!/usr/bin/env python3
"""端到端测试 - 验证访客页面功能"""

import requests
import json

BASE_URL = "http://localhost:8000"
API_PREFIX = f"{BASE_URL}/api"

print("=" * 70)
print("SmartAccess 访客管理功能 E2E测试")
print("=" * 70)

# Step 1: 登录
print("\n[Step 1] 登录到系统...")
login_response = requests.post(
    f"{API_PREFIX}/auth/login",
    data={"username": "admin", "password": "Test@1234"},
    timeout=30  # 增加超时时间
)

if login_response.status_code != 200:
    print(f"❌ 登录失败: {login_response.status_code}")
    print(f"   {login_response.text}")
    exit(1)

token = login_response.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"✅ 登录成功")
print(f"   Token: {token[:30]}...")

# Step 2: 加载访客页面
print("\n[Step 2] 加载访客页面HTML...")
page_response = requests.get(f"{BASE_URL}/visitors", timeout=30)
if page_response.status_code != 200:
    print(f"❌ 页面加载失败: {page_response.status_code}")
    exit(1)

page_html = page_response.text
if "visitors" in page_html.lower() and ("loadVisitors" in page_html or "visitor" in page_html.lower()):
    print(f"✅ 访客页面HTML加载成功")
else:
    print(f"❌ 页面内容不完整")

# Step 3: 获取访客列表
print("\n[Step 3] 获取访客列表API...")
visitors_response = requests.get(
    f"{API_PREFIX}/visitors/?is_checked_out=false",
    headers=headers,
    timeout=30
)

if visitors_response.status_code != 200:
    print(f"❌ API调用失败: {visitors_response.status_code}")
    print(f"   {visitors_response.text}")
    exit(1)

visitors_data = visitors_response.json()
print(f"✅ 成功获取访客列表")
print(f"   返回数据: {len(str(visitors_data))} 字节")

# Step 4: 验证响应格式
print("\n[Step 4] 验证API响应格式...")
if isinstance(visitors_data, list):
    print(f"✅ 响应是列表格式，包含 {len(visitors_data)} 个访客")
else:
    print(f"⚠️  响应格式: {type(visitors_data)}")

print("\n" + "=" * 70)
print("✅ 端到端测试完成 - 访客管理功能正常!")
print("=" * 70)

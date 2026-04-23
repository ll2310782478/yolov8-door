#!/usr/bin/env python3
"""用新密码测试登录"""

import requests
import json

BASE_URL = "http://localhost:8000"
API_PREFIX = f"{BASE_URL}/api"

print("=" * 70)
print("Login Test with correct password")
print("=" * 70)

login_data = {
    "username": "admin",
    "password": "Test@1234"  # New password we just set
}

print(f"\nSending login request...")
print(f"Username: admin")
print(f"Password: Test@1234")

response = requests.post(
    f"{API_PREFIX}/auth/login",
    data=login_data,
    timeout=10
)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Body:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if response.status_code == 200:
    print("\nSUCCESS! Login worked!")
    data = response.json()
    token = data.get('data', {}).get('access_token', '')
    if token:
        print(f"Token: {token[:50]}...")
else:
    print(f"\nFAILED: Got status {response.status_code}")

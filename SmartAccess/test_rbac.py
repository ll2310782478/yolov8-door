"""Test RBAC system"""
import requests, json, base64

BASE = 'http://localhost:8099'

# 1. Login as admin
r = requests.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin@123456'})
print('=== Login ===')
print('Status:', r.status_code)
login_data = r.json()
token = login_data.get('data', {}).get('access_token', '')

# Decode token payload
parts = token.split('.')
payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
decoded = json.loads(base64.b64decode(payload))
print('Token payload:', decoded)

headers = {'Authorization': f'Bearer {token}'}

# 2. Test /me
print('\n=== /me ===')
r = requests.get(f'{BASE}/api/auth/me', headers=headers)
print('Status:', r.status_code)
print('Response:', r.json())

# 3. Test protected endpoint WITHOUT token
print('\n=== Users (no auth) ===')
r = requests.get(f'{BASE}/api/users/')
print('Status:', r.status_code)
print('Response:', r.json())

# 4. Test protected endpoint WITH admin token
print('\n=== Users (admin) ===')
r = requests.get(f'{BASE}/api/users/', headers=headers)
print('Status:', r.status_code)
users = r.json()
if isinstance(users, list):
    for u in users:
        print(f"  {u['username']}: role={u.get('user_role', 'N/A')}")

# 5. Test visitors (no auth)
print('\n=== Visitors (no auth) ===')
r = requests.get(f'{BASE}/api/visitors/')
print('Status:', r.status_code)

# 6. Test visitors (admin)
print('\n=== Visitors (admin) ===')
r = requests.get(f'{BASE}/api/visitors/', headers=headers)
print('Status:', r.status_code)

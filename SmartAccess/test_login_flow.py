"""Test Login Flow - Verifies authentication works end-to-end"""

import requests
import sys

BASE_URL = "http://localhost:8000"

def test_login():
    """Test login with admin credentials"""
    print("=" * 60)
    print("Testing Login Flow")
    print("=" * 60)
    
    # Step 1: Try to login
    print("\n[Step 1] Attempting login as 'admin'...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={
                "username": "admin",
                "password": "Admin@123456"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Login SUCCESS!")
            print(f"  Response code: {data.get('code')}")
            print(f"  Message: {data.get('message')}")
            
            token = data['data']['access_token']
            username = data['data']['username']
            print(f"  Token received: {token[:50]}...")
            print(f"  Username: {username}")
            
            # Step 2: Validate token by calling /api/auth/me
            print("\n[Step 2] Validating token with /api/auth/me...")
            headers = {"Authorization": f"Bearer {token}"}
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            
            if me_response.status_code == 200:
                me_data = me_response.json()
                print(f"✓ Token validation SUCCESS!")
                print(f"  User ID: {me_data['data']['id']}")
                print(f"  Username: {me_data['data']['username']}")
                print(f"  Email: {me_data['data'].get('email', 'N/A')}")
                
                print("\n" + "=" * 60)
                print("✓ ALL TESTS PASSED! Authentication is working correctly.")
                print("=" * 60)
                return True
            else:
                print(f"✗ Token validation FAILED!")
                print(f"  Status: {me_response.status_code}")
                print(f"  Response: {me_data.text}")
                return False
                
        elif response.status_code == 401:
            print(f"✗ Login FAILED - 401 Unauthorized")
            print(f"  Detail: {response.json().get('detail')}")
            print("\nPossible causes:")
            print("  1. Wrong username/password")
            print("  2. User doesn't exist in database")
            print("  3. Password hash mismatch")
            return False
        else:
            print(f"✗ Unexpected response: {response.status_code}")
            print(f"  Body: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_login()
    sys.exit(0 if success else 1)

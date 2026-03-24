"""Comprehensive Login Flow Diagnostic Script"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def test_step(step_num, description, func):
    """Helper to test a step and report results"""
    print(f"[Step {step_num}] {description}...", end=" ")
    try:
        result = func()
        if result['success']:
            print("PASS")
            if result.get('details'):
                for k, v in result['details'].items():
                    print(f"         {k}: {v}")
            return result
        else:
            print("FAIL")
            if result.get('error'):
                print(f"         Error: {result['error']}")
            return None
    except Exception as e:
        print(f"ERROR: {e}")
        return {'success': False, 'error': str(e)}

# ========== Test Steps ==========

def step1_check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        return {
            'success': True,
            'details': {
                'Status': f'{response.status_code}',
                'Server': 'Running'
            }
        }
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'Server not reachable'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def step2_test_login(username='admin', password='Admin@123456'):
    """Test login endpoint"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={'username': username, 'password': password},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('data', {}).get('access_token', '')
            return {
                'success': True,
                'details': {
                    'HTTP Status': response.status_code,
                    'Code': data.get('code'),
                    'Message': data.get('message'),
                    'Token Length': len(token),
                    'Username': data.get('data', {}).get('username')
                },
                'token': token
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def step3_validate_token(token):
    """Validate token by calling /api/auth/me"""
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user_data = data.get('data', {})
            return {
                'success': True,
                'details': {
                    'HTTP Status': response.status_code,
                    'User ID': user_data.get('id'),
                    'Username': user_data.get('username'),
                    'Email': user_data.get('email', 'N/A'),
                    'Active': user_data.get('is_active')
                }
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def step4_test_wrong_password():
    """Test login with wrong password (should fail)"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={'username': 'admin', 'password': 'wrongpassword'},
            timeout=10
        )
        
        if response.status_code == 401:
            return {
                'success': True,
                'details': {
                    'Expected Behavior': 'Correctly rejected',
                    'HTTP Status': response.status_code
                }
            }
        else:
            return {
                'success': False,
                'error': f'Should return 401 but got {response.status_code}'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def step5_check_dashboard_accessible(token):
    """Check if dashboard page loads"""
    try:
        headers = {'Cookie': f'token={token}'}
        response = requests.get(f"{BASE_URL}/web/dashboard", headers=headers, timeout=10)
        
        if response.status_code == 200:
            return {
                'success': True,
                'details': {
                    'HTTP Status': response.status_code,
                    'Page Size': f'{len(response.text)} bytes'
                }
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ========== Main Execution ==========

def main():
    print_section("SmartAccess Login Flow Comprehensive Diagnostic")
    
    results = []
    token = None
    
    # Step 1: Check server
    r1 = test_step(1, "Checking server connectivity", step1_check_server)
    results.append(r1)
    
    if not r1 or not r1['success']:
        print("\n[ABORT] Server is not running. Please start the server first.")
        sys.exit(1)
    
    # Step 2: Test login
    r2 = test_step(2, "Testing login with admin credentials", step2_test_login)
    results.append(r2)
    
    if r2 and r2['success']:
        token = r2.get('token')
    else:
        print("\n[INFO] Login failed. Trying to check if admin user exists...")
    
    # Step 3: Validate token
    if token:
        r3 = test_step(3, "Validating token with /api/auth/me", lambda: step3_validate_token(token))
        results.append(r3)
        
        # Step 5: Check dashboard
        if r3 and r3['success']:
            r5 = test_step(5, "Checking dashboard accessibility", lambda: step5_check_dashboard_accessible(token))
            results.append(r5)
    
    # Step 4: Test wrong password (security check)
    r4 = test_step(4, "Testing security (wrong password rejection)", step4_test_wrong_password)
    results.append(r4)
    
    # Summary
    print_section("Diagnostic Summary")
    passed = sum(1 for r in results if r and r['success'])
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("\nSUCCESS: All login flow components are working correctly!")
        print("\nYou can now:")
        print("  1. Open http://localhost:8000/web/auth in your browser")
        print("  2. Login with username: admin, password: Admin@123456")
        print("  3. You should be redirected to the dashboard")
        sys.exit(0)
    else:
        print("\nWARNING: Some tests failed. See details above.")
        print("\nTroubleshooting tips:")
        print("  - Make sure the server is running: uvicorn app.main:app --reload")
        print("  - Check if admin user exists in database")
        print("  - Verify DATABASE_URL in .env file")
        sys.exit(1)

if __name__ == "__main__":
    main()

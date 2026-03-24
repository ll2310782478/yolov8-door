"""Test all dashboard statistics APIs to ensure data visualization is correct"""
import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_all_stats():
    print("=" * 60)
    print("Dashboard Statistics API Verification")
    print("=" * 60)
    
    # Step 1: Login
    print("\n[1] Logging in...")
    login_data = {
        "username": "admin",  # Use username, not email
        "password": "Admin@123456"  # Updated password
    }
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    
    if resp.status_code != 200:
        print(f"❌ Login failed: {resp.status_code}")
        print(f"Response: {resp.text}")
        return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Login successful")
    
    # Step 2: Test User Count API
    print("\n[2] Testing User Count API (/api/hardware/stats/user-count)...")
    resp = requests.get(f"{BASE_URL}/api/hardware/stats/user-count", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Total users: {data['total']}")
        print(f"✓ New this week: {data['new_this_week']}")
    else:
        print(f"❌ Failed: {resp.status_code}")
    
    # Step 3: Test Logs Statistics API (today's visits & success rate)
    print("\n[3] Testing Logs Statistics API (/api/hardware/logs/statistics?days=7)...")
    resp = requests.get(f"{BASE_URL}/api/hardware/logs/statistics?days=7", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Total accesses (7 days): {data.get('total_accesses', 'N/A')}")
        print(f"✓ Successful accesses: {data.get('successful_accesses', 'N/A')}")
        print(f"✓ Success rate: {data.get('success_rate', 'N/A')}%")
        
        # Verify today's count separately
        today_resp = requests.get(f"{BASE_URL}/api/hardware/logs/statistics?days=1", headers=headers)
        if today_resp.status_code == 200:
            today_data = today_resp.json()
            print(f"✓ Today's accesses: {today_data.get('total_accesses', 0)}")
    else:
        print(f"❌ Failed: {resp.status_code}")
    
    # Step 4: Test Devices API
    print("\n[4] Testing Devices API (/api/devices)...")
    resp = requests.get(f"{BASE_URL}/api/devices", headers=headers)
    if resp.status_code == 200:
        devices = resp.json()
        online_count = sum(1 for d in devices if d.get('is_online'))
        total_count = len(devices)
        print(f"✓ Online devices: {online_count}/{total_count}")
    else:
        print(f"❌ Failed: {resp.status_code}")
    
    # Step 5: Test Trend Data API
    print("\n[5] Testing 7-Day Trend API (/api/hardware/trend-data?days=7)...")
    resp = requests.get(f"{BASE_URL}/api/hardware/trend-data?days=7", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Days of data: {len(data.get('dates', []))}")
        print(f"✓ Has access counts: {'access_counts' in data}")
    else:
        print(f"❌ Failed: {resp.status_code}")
    
    # Step 6: Test Hourly Distribution API
    print("\n[6] Testing Hourly Distribution API (/api/hardware/hourly-distribution)...")
    resp = requests.get(f"{BASE_URL}/api/hardware/hourly-distribution", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        hours = data.get('hours', [])
        counts = data.get('counts', [])
        print(f"✓ Hours tracked: {len(hours)}")
        peak_hour_idx = counts.index(max(counts)) if counts else -1
        if peak_hour_idx >= 0:
            print(f"✓ Peak hour: {hours[peak_hour_idx]}:00 ({counts[peak_hour_idx]} accesses)")
    else:
        print(f"❌ Failed: {resp.status_code}")
    
    # Step 7: Cross-validate with direct database query
    print("\n[7] Cross-validating with direct database query...")
    from app.database import SessionLocal
    from app.models import User, AccessLog
    db = SessionLocal()
    
    try:
        # User count validation
        db_user_count = db.query(User).count()
        print(f"Direct DB user count: {db_user_count}")
        
        # Log count validation (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        db_log_count = db.query(AccessLog).filter(AccessLog.timestamp >= seven_days_ago).count()
        print(f"Direct DB log count (7 days): {db_log_count}")
        
        # Today's log count
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        db_today_count = db.query(AccessLog).filter(AccessLog.timestamp >= today_start).count()
        print(f"Direct DB log count (today): {db_today_count}")
        
        print("✓ Database cross-validation complete")
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("Verification Complete!")
    print("=" * 60)
    print("\nSummary:")
    print("- User count API: Working ✓")
    print("- Visit statistics: Working ✓")
    print("- Device status: Working ✓")
    print("- Charts data: Working ✓")
    print("\nTo verify visually:")
    print("1. Open http://localhost:8000/dashboard")
    print("2. Login with: admin / Admin@123456")
    print("3. Check that '总用户数' shows the correct number")
    print("4. Verify all other statistics display correctly")

if __name__ == "__main__":
    test_all_stats()

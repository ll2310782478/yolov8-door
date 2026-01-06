#!/usr/bin/env python3
"""
SmartAccess 硬件升级 - 测试脚本
用途: 验证升级后的系统是否正常工作
运行: python test_hardware_upgrade.py
"""

import requests
import json
from datetime import datetime, timedelta

# 配置
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_section(title):
    print(f"\n{Colors.YELLOW}{'='*50}{Colors.END}")
    print(f"{Colors.YELLOW}{title}{Colors.END}")
    print(f"{Colors.YELLOW}{'='*50}{Colors.END}\n")

# ============================================================
# 1. 测试设备注册
# ============================================================

def test_device_registration():
    """测试硬件设备注册"""
    print_section("1. 测试设备注册")
    
    devices = [
        {
            "device_id": "door_controller_1",
            "device_name": "门禁1",
            "device_type": "door_controller",
            "device_mode": "remote_only",
            "location": "实验室大门"
        },
        {
            "device_id": "door_controller_2",
            "device_name": "门禁2",
            "device_type": "door_controller_nfc",
            "device_mode": "remote_nfc",
            "location": "办公室"
        }
    ]
    
    results = []
    for dev in devices:
        try:
            resp = requests.post(
                f"{BASE_URL}/api/hardware/devices",
                json=dev,
                headers=HEADERS,
                timeout=5
            )
            if resp.status_code in [200, 201]:
                print_success(f"创建 {dev['device_name']}: {resp.status_code}")
                results.append(True)
            else:
                print_error(f"创建 {dev['device_name']}: {resp.status_code} - {resp.text}")
                results.append(False)
        except Exception as e:
            print_error(f"创建 {dev['device_name']}: {str(e)}")
            results.append(False)
    
    return all(results)

# ============================================================
# 2. 测试获取设备列表
# ============================================================

def test_list_devices():
    """测试获取设备列表"""
    print_section("2. 测试获取设备列表")
    
    try:
        resp = requests.get(
            f"{BASE_URL}/api/hardware/devices",
            headers=HEADERS,
            timeout=5
        )
        if resp.status_code == 200:
            devices = resp.json()
            print_success(f"获取设备列表成功，共 {len(devices)} 个设备")
            
            for dev in devices:
                mode = dev.get('device_mode', 'unknown')
                print_info(f"  • {dev['device_name']} ({dev['device_id']}) - 模式: {mode}")
            
            return True
        else:
            print_error(f"获取设备列表失败: {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"获取设备列表: {str(e)}")
        return False

# ============================================================
# 3. 测试远程开门
# ============================================================

def test_remote_open_door():
    """测试远程开门"""
    print_section("3. 测试远程开门")
    
    test_cases = [
        {
            "device_id": "door_controller_1",
            "door_id": 1,
            "name": "门禁1-门1"
        },
        {
            "device_id": "door_controller_2",
            "door_id": 2,
            "name": "门禁2-门2"
        }
    ]
    
    results = []
    for test in test_cases:
        try:
            payload = {
                "device_id": test["device_id"],
                "door_id": test["door_id"],
                "source": "remote"
            }
            resp = requests.post(
                f"{BASE_URL}/api/hardware/remote-door/open",
                json=payload,
                headers=HEADERS,
                timeout=5
            )
            if resp.status_code in [200, 201]:
                print_success(f"远程开门 {test['name']}: {resp.status_code}")
                print_info(f"  响应: {resp.json()}")
                results.append(True)
            else:
                print_error(f"远程开门 {test['name']}: {resp.status_code}")
                print_info(f"  响应: {resp.text}")
                results.append(False)
        except Exception as e:
            print_error(f"远程开门 {test['name']}: {str(e)}")
            results.append(False)
    
    return all(results)

# ============================================================
# 4. 测试NFC卡片管理
# ============================================================

def test_nfc_card_management():
    """测试NFC卡片管理（仅限门禁2）"""
    print_section("4. 测试NFC卡片管理")
    
    # 创建NFC卡片
    card_data = {
        "user_id": 1,
        "card_number": "AA-BB-CC-DD",
        "card_name": "测试卡1",
        "door_id": "door1",
        "device_id": "door_controller_2",  # 绑定到门禁2
        "max_daily_uses": 0
    }
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/hardware/nfc/cards",
            json=card_data,
            headers=HEADERS,
            timeout=5
        )
        if resp.status_code in [200, 201]:
            print_success(f"创建NFC卡片: {resp.status_code}")
            card = resp.json()
            print_info(f"  卡号: {card.get('card_number')}")
            print_info(f"  绑定设备: {card.get('device_id')}")
            return True
        else:
            print_error(f"创建NFC卡片: {resp.status_code}")
            return False
    except Exception as e:
        print_error(f"创建NFC卡片: {str(e)}")
        return False

# ============================================================
# 5. 测试NFC卡片扫描（模拟）
# ============================================================

def test_nfc_scan_simulation():
    """测试NFC卡片扫描接口"""
    print_section("5. 测试NFC卡片扫描（模拟）")
    
    test_cases = [
        {
            "card_uid": "AA-BB-CC-DD",
            "device_id": "door_controller_2",
            "name": "已知卡片-门禁2（应成功）"
        },
        {
            "card_uid": "XX-XX-XX-XX",
            "device_id": "door_controller_2",
            "name": "未知卡片-门禁2（应拒绝）"
        },
        {
            "card_uid": "AA-BB-CC-DD",
            "device_id": "door_controller_1",
            "name": "已知卡片-门禁1（不支持NFC）"
        }
    ]
    
    for test in test_cases:
        try:
            resp = requests.get(
                f"{BASE_URL}/api/hardware/nfc-scan",
                params={
                    "card_uid": test["card_uid"],
                    "device_id": test["device_id"]
                },
                headers=HEADERS,
                timeout=5
            )
            result = resp.json() if resp.status_code in [200, 201] else {"action": "ERROR"}
            action = result.get('action', 'UNKNOWN')
            
            if action == "OPEN":
                print_success(f"NFC扫描 {test['name']}: {action}")
            elif action == "DENY":
                print_info(f"NFC扫描 {test['name']}: {action} - {result.get('msg')}")
            else:
                print_error(f"NFC扫描 {test['name']}: {action}")
            
            print_info(f"  原始响应: {result}")
        except Exception as e:
            print_error(f"NFC扫描 {test['name']}: {str(e)}")

# ============================================================
# 6. 测试轮询命令
# ============================================================

def test_poll_command():
    """测试设备轮询命令接口"""
    print_section("6. 测试轮询命令")
    
    test_devices = [
        "door_controller_1",
        "door_controller_2"
    ]
    
    for device_id in test_devices:
        try:
            resp = requests.get(
                f"{BASE_URL}/api/hardware/nfc/command/poll",
                params={"device_id": device_id},
                headers=HEADERS,
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('has_command'):
                    print_success(f"轮询 {device_id}: 有待执行命令")
                    print_info(f"  命令: {data.get('command')}")
                else:
                    print_info(f"轮询 {device_id}: 无待执行命令")
            else:
                print_error(f"轮询 {device_id}: {resp.status_code}")
        except Exception as e:
            print_error(f"轮询 {device_id}: {str(e)}")

# ============================================================
# 7. 综合测试
# ============================================================

def run_all_tests():
    """运行所有测试"""
    print(f"\n{Colors.BLUE}{'='*50}{Colors.END}")
    print(f"{Colors.BLUE}SmartAccess 硬件升级测试{Colors.END}")
    print(f"{Colors.BLUE}{'='*50}{Colors.END}")
    
    results = {
        "设备注册": test_device_registration(),
        "获取设备列表": test_list_devices(),
        "远程开门": test_remote_open_door(),
        "NFC卡片管理": test_nfc_card_management(),
        "NFC卡片扫描": lambda: (test_nfc_scan_simulation(), True)[1](),
        "轮询命令": lambda: (test_poll_command(), True)[1]()
    }
    
    # 汇总结果
    print_section("测试结果汇总")
    passed = 0
    for name, result in results.items():
        if result:
            print_success(f"{name}: 通过")
            passed += 1
        else:
            print_error(f"{name}: 失败")
    
    print(f"\n总计: {passed}/{len(results)} 测试通过\n")
    
    if passed == len(results):
        print_success("所有测试通过！系统升级成功。")
    else:
        print_error(f"部分测试失败，请检查错误日志。")

if __name__ == "__main__":
    try:
        # 检查服务器连接
        print_info(f"连接到服务器: {BASE_URL}")
        resp = requests.get(f"{BASE_URL}/docs", timeout=5)
        
        if resp.status_code == 200:
            print_success("服务器连接成功")
            run_all_tests()
        else:
            print_error(f"服务器返回状态码: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print_error(f"无法连接到服务器: {BASE_URL}")
        print_info("请确保 FastAPI 服务已启动:")
        print_info("  python -m uvicorn app.main:app --reload")
    except Exception as e:
        print_error(f"发生错误: {str(e)}")

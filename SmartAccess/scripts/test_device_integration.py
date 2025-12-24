#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
设备注册端到端集成测试脚本
用于验证后端设备注册接口的完整功能

使用方法：
  python test_device_integration.py
"""

import requests
import json
import time
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/hardware"
HEALTH_URL = f"{BASE_URL}/health"

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*50}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^50}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*50}{Colors.ENDC}\n")

def print_section(text):
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")

# ==================== 测试函数 ====================

def test_server_health():
    """测试服务器是否运行"""
    print_section("1. 检查服务器健康状态")
    
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"服务器运行正常 (状态: {data.get('status', 'ok')})")
            return True
        else:
            print_error(f"服务器返回错误状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"无法连接到服务器: {BASE_URL}")
        print_warning("请确保 FastAPI 服务已启动 (python -m uvicorn app.main:app --reload)")
        return False
    except Exception as e:
        print_error(f"检查服务器时出错: {str(e)}")
        return False

def test_register_device(device_id="nfc_reader_01", device_name="一楼门禁"):
    """测试设备注册"""
    print_section("2. 测试设备注册")
    
    payload = {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": "nfc_reader",
        "location": "主入口",
        "ip_address": "192.168.1.102"
    }
    
    print_info(f"注册设备: {device_id}")
    print_info(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(
            f"{API_BASE}/devices",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 201:
            data = response.json()
            print_success(f"设备注册成功 (ID: {data.get('device_id')})")
            print_info(f"设备信息: {json.dumps(data, ensure_ascii=False, indent=2)}")
            return True
        elif response.status_code == 400:
            data = response.json()
            if "已存在" in str(data.get('detail', '')):
                print_warning(f"设备已存在: {data.get('detail')}")
                return "exists"
            else:
                print_error(f"注册失败: {data.get('detail')}")
                return False
        else:
            print_error(f"注册失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return False
    except Exception as e:
        print_error(f"注册时出错: {str(e)}")
        return False

def test_list_devices():
    """测试获取设备列表"""
    print_section("3. 测试获取设备列表")
    
    try:
        response = requests.get(f"{API_BASE}/devices", timeout=5)
        
        if response.status_code == 200:
            devices = response.json()
            if isinstance(devices, list) and len(devices) > 0:
                print_success(f"获取设备列表成功 (共 {len(devices)} 台)")
                for device in devices:
                    status_color = Colors.GREEN if device.get('connection_status') == 'online' else Colors.YELLOW
                    print(f"  • {device.get('device_id'):20} {device.get('device_name'):15} {status_color}{device.get('connection_status')}{Colors.ENDC}")
                return True
            else:
                print_warning("设备列表为空")
                return "empty"
        else:
            print_error(f"获取列表失败 (状态码: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"获取列表时出错: {str(e)}")
        return False

def test_send_heartbeat(device_id="nfc_reader_01"):
    """测试发送心跳"""
    print_section("4. 测试发送心跳信号")
    
    payload = {
        "connection_status": "online",
        "firmware_version": "1.1",
        "ip_address": "192.168.1.102"
    }
    
    print_info(f"目标设备: {device_id}")
    print_info(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(
            f"{API_BASE}/devices/{device_id}/heartbeat",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"心跳发送成功")
            print_info(f"设备: {data.get('device_id')}, 时间: {data.get('timestamp')}")
            return True
        elif response.status_code == 404:
            print_error(f"设备不存在: {device_id}")
            return False
        else:
            print_error(f"心跳发送失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return False
    except Exception as e:
        print_error(f"发送心跳时出错: {str(e)}")
        return False

def test_multiple_heartbeats(device_id="nfc_reader_01", count=3, interval=2):
    """测试多次心跳"""
    print_section("5. 测试多次心跳信号（模拟设备保活）")
    
    print_info(f"发送 {count} 次心跳，间隔 {interval} 秒")
    
    for i in range(count):
        print_info(f"第 {i+1}/{count} 次心跳...")
        result = test_send_heartbeat(device_id)
        if not result:
            print_error(f"第 {i+1} 次心跳失败")
            return False
        
        if i < count - 1:  # 最后一次不需要等待
            time.sleep(interval)
    
    print_success("所有心跳发送成功")
    return True

def test_query_by_type():
    """按设备类型查询"""
    print_section("6. 测试按类型查询设备")
    
    device_type = "nfc_reader"
    
    try:
        response = requests.get(
            f"{API_BASE}/devices",
            params={"device_type": device_type},
            timeout=5
        )
        
        if response.status_code == 200:
            devices = response.json()
            print_success(f"查询类型 '{device_type}' 的设备成功 (共 {len(devices)} 台)")
            for device in devices:
                print(f"  • {device.get('device_id')} - {device.get('device_name')}")
            return True
        else:
            print_error(f"查询失败 (状态码: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"查询时出错: {str(e)}")
        return False

def test_update_device(device_id="nfc_reader_01"):
    """测试更新设备信息"""
    print_section("7. 测试更新设备信息")
    
    payload = {
        "device_name": "一楼主门禁（已更新）",
        "location": "主楼入口"
    }
    
    print_info(f"目标设备: {device_id}")
    print_info(f"更新内容: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.put(
            f"{API_BASE}/devices/{device_id}",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"设备信息更新成功")
            print_info(f"新名称: {data.get('device_name')}, 新位置: {data.get('location')}")
            return True
        elif response.status_code == 404:
            print_error(f"设备不存在: {device_id}")
            return False
        else:
            print_error(f"更新失败 (状态码: {response.status_code})")
            print_error(f"响应: {response.text}")
            return False
    except Exception as e:
        print_error(f"更新设备时出错: {str(e)}")
        return False

def test_delete_device(device_id="nfc_reader_test_delete"):
    """测试删除设备"""
    print_section("8. 测试删除设备")
    
    print_info(f"目标设备: {device_id}")
    
    try:
        response = requests.delete(
            f"{API_BASE}/devices/{device_id}",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"设备删除成功: {data.get('message')}")
            return True
        elif response.status_code == 404:
            print_warning(f"设备不存在（无法删除）: {device_id}")
            return "not_found"
        else:
            print_error(f"删除失败 (状态码: {response.status_code})")
            return False
    except Exception as e:
        print_error(f"删除设备时出错: {str(e)}")
        return False

def test_error_handling():
    """测试错误处理"""
    print_section("9. 测试错误处理")
    
    # 测试 1: 注册相同 ID 的设备
    print_info("测试 1: 重复注册相同 ID")
    payload1 = {
        "device_id": "duplicate_test",
        "device_name": "测试设备",
        "device_type": "nfc_reader"
    }
    
    try:
        # 第一次注册
        response1 = requests.post(f"{API_BASE}/devices", json=payload1, timeout=5)
        if response1.status_code == 201:
            print_info("  首次注册成功")
            
            # 第二次注册（应该失败）
            response2 = requests.post(f"{API_BASE}/devices", json=payload1, timeout=5)
            if response2.status_code == 400:
                print_success("  重复注册被正确拒绝")
            else:
                print_error("  未能正确处理重复注册")
                return False
        else:
            print_warning("  首次注册失败，跳过此测试")
    except Exception as e:
        print_error(f"  测试出错: {str(e)}")
        return False
    
    # 测试 2: 查询不存在的设备
    print_info("测试 2: 查询不存在的设备")
    try:
        response = requests.post(
            f"{API_BASE}/devices/nonexistent_device/heartbeat",
            json={"connection_status": "online"},
            timeout=5
        )
        if response.status_code == 404:
            print_success("  正确返回 404")
        else:
            print_warning(f"  状态码: {response.status_code}（预期 404）")
    except Exception as e:
        print_error(f"  测试出错: {str(e)}")
    
    return True

# ==================== 主函数 ====================

def main():
    print_header("设备注册端到端集成测试")
    
    print(f"{Colors.CYAN}开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")
    
    # 检查服务器
    if not test_server_health():
        print_error("服务器未运行，无法继续测试")
        return False
    
    # 执行测试
    results = []
    
    # 基础测试
    results.append(("注册设备", test_register_device()))
    results.append(("获取设备列表", test_list_devices()))
    results.append(("发送心跳", test_send_heartbeat()))
    results.append(("多次心跳", test_multiple_heartbeats(count=3, interval=1)))
    results.append(("按类型查询", test_query_by_type()))
    results.append(("更新设备", test_update_device()))
    results.append(("删除测试", test_delete_device("duplicate_test")))
    results.append(("错误处理", test_error_handling()))
    
    # 统计结果
    print_header("测试结果总结")
    
    passed = sum(1 for _, result in results if result is True)
    total = len(results)
    
    for test_name, result in results:
        if result is True:
            print_success(f"{test_name}")
        elif result == "exists" or result == "empty" or result == "not_found":
            print_warning(f"{test_name} (预期行为)")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{Colors.BOLD}总体结果: {passed}/{total} 项测试通过{Colors.ENDC}")
    print(f"成功率: {(passed/total)*100:.1f}%\n")
    
    if passed == total:
        print_success("所有测试通过！设备注册功能工作正常。")
    else:
        print_warning(f"有 {total-passed} 项测试失败，请检查相关配置。")
    
    print(f"\n{Colors.CYAN}结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

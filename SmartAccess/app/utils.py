"""工具函数"""

import json
from datetime import datetime
from app.time_utils import now_utc8
import os
from typing import Optional, Dict, List


def check_permission_valid(permission_start_date: datetime, permission_end_date: Optional[datetime]) -> bool:
    """检查权限是否在有效期内"""
    now = now_utc8()
    
    # 检查开始日期
    if permission_start_date and permission_start_date > now:
        return False
    
    # 检查结束日期
    if permission_end_date and permission_end_date < now:
        return False
    
    return True


def check_time_period_valid(time_periods_json: Optional[str]) -> bool:
    """检查当前时间是否在允许的时间段内"""
    if not time_periods_json:
        return True  # 没有时间限制
    
    try:
        time_periods = json.loads(time_periods_json)
    except:
        return True
    
    # 如果没有为今天设置时间段，则允许
    today_name = now_utc8().strftime('%A').lower()
    if today_name not in time_periods:
        return True
    
    current_time = now_utc8().strftime('%H:%M')
    allowed_periods = time_periods.get(today_name, [])
    
    for period in allowed_periods:
        start_time, end_time = period.split('-')
        if start_time <= current_time <= end_time:
            return True
    
    return False


def check_daily_limit(max_daily_uses: int, daily_use_count: int, last_use_date: Optional[datetime]) -> bool:
    """检查是否超过每日使用限制"""
    if max_daily_uses == 0:  # 0 表示无限制
        return True
    
    # 如果上次使用日期是今天
    if last_use_date:
        today = now_utc8().date()
        if last_use_date.date() == today:
            return daily_use_count < max_daily_uses
    
    # 首次使用或上次使用不是今天
    return True


def increment_daily_use_count(daily_use_count: int, last_use_date: Optional[datetime]) -> tuple:
    """增加每日使用计数"""
    today = now_utc8().date()
    
    # 如果上次使用不是今天，则重置计数
    if last_use_date and last_use_date.date() != today:
        return 1, now_utc8()
    
    return daily_use_count + 1, now_utc8()


def save_file(upload_file) -> str:
    """保存上传的文件"""
    import shutil
    
    upload_dir = "static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 使用原始文件名，添加时间戳避免冲突
    timestamp = now_utc8().strftime('%Y%m%d%H%M%S')
    file_path = os.path.join(upload_dir, f"{timestamp}_{upload_file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    return file_path


def delete_file(file_path: str) -> bool:
    """删除文件"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"删除文件失败: {e}")
    
    return False


def parse_time_periods(time_periods_str: Optional[str]) -> Dict:
    """解析时间段 JSON 字符串"""
    if not time_periods_str:
        return {}
    
    try:
        return json.loads(time_periods_str)
    except:
        return {}


def format_time_periods(time_periods_dict: Dict) -> str:
    """格式化时间段字典为 JSON 字符串"""
    return json.dumps(time_periods_dict, ensure_ascii=False)


def generate_permission_summary(user) -> Dict:
    """生成用户权限汇总"""
    summary = {
        "user_id": user.id,
        "username": user.username,
        "permissions": {}
    }
    
    # 人脸识别权限
    face_perms = [f for f in user.permissions if f.permission_type == "face_recognition"]
    if face_perms:
        perm = face_perms[0]
        summary["permissions"]["face_recognition"] = {
            "enabled": perm.is_enabled,
            "start_date": perm.start_date.isoformat() if perm.start_date else None,
            "end_date": perm.end_date.isoformat() if perm.end_date else None,
            "valid": check_permission_valid(perm.start_date, perm.end_date)
        }
    
    # NFC 权限
    nfc_perms = [f for f in user.permissions if f.permission_type == "nfc"]
    if nfc_perms:
        perm = nfc_perms[0]
        summary["permissions"]["nfc"] = {
            "enabled": perm.is_enabled,
            "start_date": perm.start_date.isoformat() if perm.start_date else None,
            "end_date": perm.end_date.isoformat() if perm.end_date else None,
            "valid": check_permission_valid(perm.start_date, perm.end_date)
        }
    
    # 蓝牙权限
    bluetooth_perms = [f for f in user.permissions if f.permission_type == "bluetooth"]
    if bluetooth_perms:
        perm = bluetooth_perms[0]
        summary["permissions"]["bluetooth"] = {
            "enabled": perm.is_enabled,
            "start_date": perm.start_date.isoformat() if perm.start_date else None,
            "end_date": perm.end_date.isoformat() if perm.end_date else None,
            "valid": check_permission_valid(perm.start_date, perm.end_date)
        }
    
    return summary


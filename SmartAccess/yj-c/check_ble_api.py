# BLE API 修复验证脚本
# 用途: 快速检查固件代码中是否还有不兼容的 BLE API

import os
import re
from pathlib import Path

# 要检查的问题API
PROBLEMATIC_APIs = [
    r'clearAdvertisementData\(',
    r'clearScanResponseData\(',
    r'setCompleteLocalName\(',
    r'setAdvertisementType\(ADV_TYPE_IND\)',
    r'\.setIntMax\(',
    r'\.setIntMin\(',
]

# 排除的行（注释中的示例可以忽略）
EXCLUDE_PATTERNS = [
    r'^\s*//',  # 单行注释
    r'^\s*\*',  # 多行注释
]

def check_file(filepath):
    """检查文件中是否存在问题的 BLE API"""
    print(f"\n📂 检查文件: {filepath}")
    
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                # 跳过注释行
                if any(re.match(pattern, line) for pattern in EXCLUDE_PATTERNS):
                    continue
                
                # 检查问题API
                for api_pattern in PROBLEMATIC_APIs:
                    if re.search(api_pattern, line):
                        issues.append({
                            'line': line_num,
                            'pattern': api_pattern,
                            'content': line.strip()[:80]
                        })
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return None
    
    return issues

def main():
    print("=" * 60)
    print("  🔍 BLE API 兼容性检查工具")
    print("=" * 60)
    
    # 定位固件文件
    sketch_path = Path("u:/BYSJ/yolov-door/yolov8-door/SmartAccess/yj-c/http-nfc-s3-dual-core/http-nfc-s3-dual-core.ino")
    
    if not sketch_path.exists():
        print(f"\n❌ 错误: 未找到文件 {sketch_path}")
        return 1
    
    print(f"\n✅ 找到固件文件: {sketch_path}")
    
    # 检查文件
    issues = check_file(sketch_path)
    
    if issues is None:
        return 1
    
    # 输出结果
    print("\n" + "=" * 60)
    print("检查结果")
    print("=" * 60)
    
    if not issues:
        print("\n✅ 太棒了！没有发现问题的 BLE API")
        print("\n修复状态:")
        print("  ✓ clearAdvertisementData() - 已移除")
        print("  ✓ clearScanResponseData() - 已移除")
        print("  ✓ setCompleteLocalName() - 已移除")
        print("  ✓ setAdvertisementType(ADV_TYPE_IND) - 已替换")
        print("  ✓ setIntMax() - 已替换")
        print("  ✓ setIntMin() - 已替换")
        print("\n✨ 代码已准备好编译！")
        return 0
    else:
        print(f"\n⚠️  发现 {len(issues)} 个问题:\n")
        for issue in issues:
            print(f"  行 {issue['line']}: {issue['pattern']}")
            print(f"    {issue['content']}")
        print("\n❌ 请手动修复这些 API 调用")
        return 1

if __name__ == "__main__":
    exit(main())

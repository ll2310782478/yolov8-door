#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update hardware.py to add date filtering support"""

import re

FILE_PATH = 'app/routers/hardware.py'

def main():
    # Read the file
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Step 1: Update docstring
    old_doc = '    """获取访问日志"""'
    new_doc = '''    """获取访问日志
    
    Args:
        skip: 跳过记录数（分页）
        limit: 返回记录数限制
        access_type: 访问类型过滤（face/nfc/qrcode/bluetooth/manual）
        status: 状态过滤（success/failed/denied）
        days: 最近N 天的日志（当未指定start_date/end_date 时使用）
        start_date: 开始日期（ISO 格式：YYYY-MM-DD），优先级高于days
        end_date: 结束日期（ISO 格式：YYYY-MM-DD），默认为今天
    """'''
    
    content = content.replace(old_doc, new_doc)
    
    # Step 2: Replace the date filtering logic
    old_logic = '''    # 按时间范围筛选
    start_date = datetime.utcnow() - timedelta(days=days)
    query = query.filter(AccessLog.timestamp >= start_date)'''
    
    new_logic = '''    # 处理日期范围筛选
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(AccessLog.timestamp >= start_dt)
            
            # 如果提供了 end_date，也应用它
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                    # 将结束日期设置为当天的23:59:59
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    query = query.filter(AccessLog.timestamp <= end_dt)
                except ValueError:
                    raise HTTPException(status_code=400, detail="无效的end_date格式，请使用YYYY-MM-DD")
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的start_date格式，请使用YYYY-MM-DD")
    else:
        # 如果没有提供start_date，使用days参数
        start_dt = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AccessLog.timestamp >= start_dt)'''
    
    content = content.replace(old_logic, new_logic)
    
    # Write the file back
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Successfully updated {FILE_PATH}')

if __name__ == '__main__':
    main()

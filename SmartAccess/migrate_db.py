#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据库迁移脚本 - 添加双门支持"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import ProgrammingError
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smartaccess.db")

print("=" * 60)
print("📊 SmartAccess 数据库迁移脚本")
print("=" * 60)
print(f"🔗 数据库: {DATABASE_URL}")

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 10,
    }
)

inspector = inspect(engine)

try:
    # 检查 nfc_cards 表是否存在
    if "nfc_cards" not in inspector.get_table_names():
        print("❌ nfc_cards 表不存在，无法进行迁移")
        sys.exit(1)
    
    print("✅ nfc_cards 表存在")
    
    # 获取 nfc_cards 的列
    columns = {col['name']: col for col in inspector.get_columns('nfc_cards')}
    print(f"📋 当前列数: {len(columns)}")
    
    # 检查 door_id 列是否存在
    if 'door_id' in columns:
        print("✅ door_id 列已存在，无需添加")
        col_info = columns['door_id']
        print(f"   - 类型: {col_info['type']}")
        print(f"   - 可为空: {col_info['nullable']}")
        print(f"   - 默认值: {col_info['default']}")
    else:
        print("⚠️  door_id 列不存在，正在添加...")
        
        with engine.connect() as conn:
            # 添加 door_id 列
            alter_sql = """
            ALTER TABLE nfc_cards 
            ADD COLUMN door_id VARCHAR(20) NOT NULL DEFAULT 'door1' AFTER card_name
            """
            conn.execute(text(alter_sql))
            conn.commit()
            
        print("✅ door_id 列已添加")
        print("   - 类型: VARCHAR(20)")
        print("   - 默认值: door1")
    
    print("\n" + "=" * 60)
    print("✨ 数据库迁移完成！")
    print("=" * 60)
    print("\n接下来请启动项目:")
    print("  cd SmartAccess")
    print("  ./.venv/Scripts/Activate.ps1")
    print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    
except ProgrammingError as e:
    print(f"❌ 数据库错误: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 错误: {e}")
    sys.exit(1)
finally:
    engine.dispose()

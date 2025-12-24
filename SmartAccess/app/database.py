"""数据库连接配置"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smartaccess.db")

# 创建数据库引擎（区分 SQLite 和 MySQL）
if "mysql" in DATABASE_URL:
    # MySQL 配置
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DEBUG", "False") == "True",
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args={
            "charset": "utf8mb4",
            "connect_timeout": 10,
        }
    )
else:
    # SQLite 配置
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("DEBUG", "False") == "True",
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    # 如果是 MySQL，先尝试创建数据库
    if "mysql" in DATABASE_URL:
        try:
            # 解析数据库 URL
            from urllib.parse import urlparse
            parsed = urlparse(DATABASE_URL)
            db_name = parsed.path.lstrip("/")
            
            # 创建不指定数据库的引擎来连接 MySQL
            root_url = f"mysql+pymysql://{parsed.username}:{parsed.password}@{parsed.hostname}"
            if parsed.port:
                root_url += f":{parsed.port}"
            
            root_engine = create_engine(
                root_url,
                connect_args={
                    "charset": "utf8mb4",
                    "connect_timeout": 10,
                }
            )
            
            # 创建数据库
            with root_engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                conn.commit()
            
            root_engine.dispose()
        except Exception as e:
            print(f"警告：无法创建数据库 - {e}")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)

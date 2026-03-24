"""系统配置管理路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SystemConfig
from app.auth import require_role, TokenData
from typing import Dict, Any
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/system",
    tags=["system"],
    responses={404: {"description": "Not found"}},
)

# ==================== Pydantic 模型 ====================

class SmtpConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: str
    smtp_user: str
    smtp_password: str

class SmtpConfigResponse(BaseModel):
    smtp_host: str = None
    smtp_port: str = None
    smtp_user: str = None
    smtp_password: str = None  # 不会返回实际密码

# ==================== API端点 ====================

@router.post("/smtp-config")
def save_smtp_config(config: SmtpConfigRequest, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """保存SMTP配置"""
    try:
        # 保存配置到数据库
        configs = {
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "smtp_user": config.smtp_user,
            "smtp_password": config.smtp_password
        }

        for key, value in configs.items():
            # 检查是否已存在
            existing = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if existing:
                existing.value = value
            else:
                new_config = SystemConfig(
                    key=key,
                    value=value,
                    description=f"SMTP配置: {key}"
                )
                db.add(new_config)

        db.commit()

        return {
            "status": "success",
            "message": "SMTP配置已保存",
            "config": {
                "smtp_host": config.smtp_host,
                "smtp_port": config.smtp_port,
                "smtp_user": config.smtp_user
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")

@router.get("/smtp-config")
def get_smtp_config(db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """获取SMTP配置"""
    try:
        configs = {}
        keys = ["smtp_host", "smtp_port", "smtp_user", "smtp_password"]

        for key in keys:
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                # 密码字段不返回实际值
                if key == "smtp_password":
                    configs[key] = "********" if config.value else None
                else:
                    configs[key] = config.value

        return {
            "status": "success",
            "config": configs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

@router.delete("/smtp-config")
def delete_smtp_config(db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除SMTP配置"""
    try:
        # 删除所有SMTP相关配置
        smtp_keys = ["smtp_host", "smtp_port", "smtp_user", "smtp_password"]
        deleted_count = 0

        for key in smtp_keys:
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                db.delete(config)
                deleted_count += 1

        db.commit()

        return {
            "status": "success",
            "message": f"已删除 {deleted_count} 个SMTP配置项"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除配置失败: {str(e)}")
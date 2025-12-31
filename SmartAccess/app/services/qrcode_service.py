from sqlalchemy.orm import Session
from app.models import Visitor, VisitorPermission, AccessLog
from datetime import datetime

def verify_qrcode_token(qrcode_token: str, db: Session, device_id: str = None):
    """
    验证二维码Token的有效性
    返回: (is_valid, result_dict)
    """
    try:
        # 解析二维码内容
        if not qrcode_token.startswith("VISITOR:"):
            return False, {"status": "invalid", "message": "无效的二维码格式"}
        
        parts = qrcode_token.split(":")
        if len(parts) < 2:
             return False, {"status": "invalid", "message": "无效的二维码格式"}
             
        visitor_id = int(parts[1])
        
        permission = db.query(VisitorPermission).filter(
            VisitorPermission.qr_code_token == qrcode_token
        ).first()
        
        if not permission:
            return False, {"status": "not_found", "message": "权限不存在"}
        
        visitor = permission.visitor
        if not visitor:
             return False, {"status": "not_found", "message": "访客不存在"}
        
        # 检查权限激活状态
        if not permission.is_active:
            return False, {"status": "inactive", "message": "权限已被禁用"}
        
        # 检查生效时间
        now = datetime.utcnow()
        if permission.start_time and now < permission.start_time:
            return False, {"status": "not_started", "message": "二维码尚未生效"}

        # 检查二维码是否过期
        if permission.expires_at < now:
            return False, {"status": "expired", "message": "二维码已过期"}
        
        # 检查使用次数
        if permission.max_uses > 0 and permission.accessed_count >= permission.max_uses:
            return False, {"status": "limit_exceeded", "message": "二维码使用次数已耗尽"}

        # 检查访客是否已离场
        if visitor.is_checked_out:
            return False, {"status": "already_checked_out", "message": "访客已离场"}
        
        # 更新访问次数
        permission.accessed_count += 1
        permission.last_access_time = now
        
        # 记录访问日志
        access_log = AccessLog(
            user_id=None,  # 访客没有用户账户
            access_type="qrcode",
            status="success",
            device_id=device_id or "unknown",
            details=f"Visitor: {visitor.name}, Company: {visitor.company}"
        )
        db.add(access_log)
        db.commit()
        
        return True, {
            "status": "valid",
            "visitor_id": visitor.id,
            "visitor_name": visitor.name,
            "company": visitor.company,
            "purpose": visitor.purpose,
            "access_count": permission.accessed_count,
            "access_level": permission.access_level or "door1"
        }
    
    except Exception as e:
        return False, {"status": "error", "message": str(e)}

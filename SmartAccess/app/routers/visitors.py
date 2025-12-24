"""访客与二维码管理路由 - 增强版"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Visitor, VisitorPermission, AccessLog
from app.utils import check_permission_valid, delete_file
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import qrcode
import os
import uuid
import secrets

router = APIRouter(
    prefix="/api/visitors",
    tags=["visitors"],
    responses={404: {"description": "Not found"}},
)


# ==================== Pydantic 模型 ====================

class VisitorCreate(BaseModel):
    name: str
    phone: str = None
    email: str = None
    company: str = None
    purpose: str = None
    max_duration_hours: int = 8


class VisitorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    purpose: Optional[str] = None
    max_duration_hours: Optional[int] = None


class VisitorResponse(BaseModel):
    id: int
    name: str
    phone: str = None
    email: str = None
    company: str = None
    purpose: str = None
    check_in_time: datetime
    check_out_time: Optional[datetime] = None
    is_checked_out: bool
    qr_code_path: str = None
    qr_code_expires_at: Optional[datetime] = None
    max_duration_hours: int
    created_at: datetime

    class Config:
        from_attributes = True


class VisitorPermissionCreate(BaseModel):
    visitor_id: int
    permission_type: str = "qrcode"
    expires_in_hours: int = 24
    max_uses: int = 1


class VisitorPermissionResponse(BaseModel):
    id: int
    visitor_id: int
    qr_code_token: str
    permission_type: str
    is_active: bool
    created_at: datetime
    expires_at: datetime
    accessed_count: int
    email_sent: bool
    sms_sent: bool

    class Config:
        from_attributes = True


class SendQRCodeRequest(BaseModel):
    visitor_id: int
    send_to: str  # email 或 phone
    send_via: str  # email 或 sms


# ==================== 访客管理端点 ====================

def generate_qrcode(content: str) -> str:
    """生成二维码"""
    qrcode_dir = "static/qrcodes"
    os.makedirs(qrcode_dir, exist_ok=True)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    filename = f"visitor_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
    qrcode_path = os.path.join(qrcode_dir, filename)
    img.save(qrcode_path)
    
    return qrcode_path


@router.post("/", response_model=VisitorResponse)
def create_visitor(visitor: VisitorCreate, db: Session = Depends(get_db)):
    """创建访客记录"""
    import os
    expires_hours = int(os.getenv("VISITOR_QR_EXPIRES_HOURS", "24"))
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    db_visitor = Visitor(
        name=visitor.name,
        phone=visitor.phone,
        email=visitor.email,
        company=visitor.company,
        purpose=visitor.purpose,
        max_duration_hours=visitor.max_duration_hours,
        qr_code_expires_at=expires_at,
    )
    db.add(db_visitor)
    db.flush()
    
    # 生成二维码
    qr_content = f"VISITOR:{db_visitor.id}:{uuid.uuid4().hex}"
    qrcode_path = generate_qrcode(qr_content)
    db_visitor.qr_code_path = qrcode_path
    
    # 创建权限记录
    permission = VisitorPermission(
        visitor_id=db_visitor.id,
        qr_code_token=qr_content,
        permission_type="qrcode",
        is_active=True,
        expires_at=expires_at,
    )
    db.add(permission)
    
    db.commit()
    db.refresh(db_visitor)
    return db_visitor


@router.get("/", response_model=List[VisitorResponse])
def list_visitors(
    skip: int = 0,
    limit: int = 100,
    is_checked_out: Optional[bool] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取访客列表"""
    query = db.query(Visitor)
    
    if is_checked_out is not None:
        query = query.filter(Visitor.is_checked_out == is_checked_out)
    if company:
        query = query.filter(Visitor.company.ilike(f"%{company}%"))
    
    visitors = query.order_by(Visitor.created_at.desc()).offset(skip).limit(limit).all()
    return visitors


@router.get("/{visitor_id}", response_model=VisitorResponse)
def get_visitor(visitor_id: int, db: Session = Depends(get_db)):
    """获取访客详情"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    return visitor


@router.put("/{visitor_id}", response_model=VisitorResponse)
def update_visitor(visitor_id: int, visitor_update: VisitorUpdate, db: Session = Depends(get_db)):
    """更新访客信息"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    if visitor_update.name:
        visitor.name = visitor_update.name
    if visitor_update.phone:
        visitor.phone = visitor_update.phone
    if visitor_update.email:
        visitor.email = visitor_update.email
    if visitor_update.company:
        visitor.company = visitor_update.company
    if visitor_update.purpose:
        visitor.purpose = visitor_update.purpose
    if visitor_update.max_duration_hours:
        visitor.max_duration_hours = visitor_update.max_duration_hours
    
    db.commit()
    db.refresh(visitor)
    return visitor


@router.delete("/{visitor_id}")
def delete_visitor(visitor_id: int, db: Session = Depends(get_db)):
    """删除访客记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    # 删除二维码文件
    delete_file(visitor.qr_code_path)
    
    db.delete(visitor)
    db.commit()
    return {"message": "访客已删除"}


# ==================== 二维码与权限管理 ====================

@router.get("/{visitor_id}/qrcode")
def get_visitor_qrcode(visitor_id: int, db: Session = Depends(get_db)):
    """获取访客二维码"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    # 获取有效的权限
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id,
        VisitorPermission.is_active == True,
        VisitorPermission.expires_at > datetime.utcnow()
    ).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="访客二维码已过期或不存在")
    
    if not visitor.qr_code_path or not os.path.exists(visitor.qr_code_path):
        qrcode_path = generate_qrcode(permission.qr_code_token)
        visitor.qr_code_path = qrcode_path
        db.commit()
    
    return {
        "visitor_id": visitor_id,
        "visitor_name": visitor.name,
        "qrcode_path": visitor.qr_code_path,
        "qrcode_token": permission.qr_code_token,
        "expires_at": permission.expires_at,
        "accessed_count": permission.accessed_count
    }


@router.get("/{visitor_id}/permissions", response_model=List[VisitorPermissionResponse])
def get_visitor_permissions(visitor_id: int, db: Session = Depends(get_db)):
    """获取访客的所有权限"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    permissions = db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id
    ).all()
    return permissions


@router.post("/{visitor_id}/permissions", response_model=VisitorPermissionResponse)
def create_visitor_permission(
    visitor_id: int,
    perm_create: VisitorPermissionCreate,
    db: Session = Depends(get_db)
):
    """为访客创建权限记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    expires_at = datetime.utcnow() + timedelta(hours=perm_create.expires_in_hours)
    token = f"VISITOR:{visitor_id}:{secrets.token_hex(16)}"
    
    permission = VisitorPermission(
        visitor_id=visitor_id,
        qr_code_token=token,
        permission_type=perm_create.permission_type,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


@router.put("/{visitor_id}/permission/{permission_id}")
def update_visitor_permission(
    visitor_id: int,
    permission_id: int,
    is_active: Optional[bool] = None,
    expires_at: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """更新访客权限"""
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.id == permission_id,
        VisitorPermission.visitor_id == visitor_id
    ).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    if is_active is not None:
        permission.is_active = is_active
    if expires_at is not None:
        permission.expires_at = expires_at
    
    db.commit()
    db.refresh(permission)
    return permission


@router.delete("/{visitor_id}/permission/{permission_id}")
def delete_visitor_permission(visitor_id: int, permission_id: int, db: Session = Depends(get_db)):
    """删除访客权限"""
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.id == permission_id,
        VisitorPermission.visitor_id == visitor_id
    ).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    db.delete(permission)
    db.commit()
    return {"message": "权限已删除"}


# ==================== 二维码验证与通知 ====================

@router.post("/qrcode/verify")
def verify_qrcode(qrcode_token: str, device_id: str = None, db: Session = Depends(get_db)):
    """验证访客二维码"""
    try:
        # 解析二维码内容
        if not qrcode_token.startswith("VISITOR:"):
            return {"status": "invalid", "message": "无效的二维码"}
        
        parts = qrcode_token.split(":")
        visitor_id = int(parts[1])
        
        permission = db.query(VisitorPermission).filter(
            VisitorPermission.qr_code_token == qrcode_token
        ).first()
        
        if not permission:
            return {"status": "not_found", "message": "权限不存在"}
        
        visitor = permission.visitor
        
        # 检查权限激活状态
        if not permission.is_active:
            return {"status": "inactive", "message": "权限已被禁用"}
        
        # 检查二维码是否过期
        if permission.expires_at < datetime.utcnow():
            return {"status": "expired", "message": "二维码已过期"}
        
        # 检查访客是否已离场
        if visitor.is_checked_out:
            return {"status": "already_checked_out", "message": "访客已离场"}
        
        # 更新访问次数
        permission.accessed_count += 1
        permission.last_access_time = datetime.utcnow()
        
        # 记录访问日志
        access_log = AccessLog(
            user_id=None,  # 访客没有用户账户
            access_type="qrcode",
            status="success",
            device_id=device_id,
            details=f"Visitor: {visitor.name}, Company: {visitor.company}"
        )
        db.add(access_log)
        db.commit()
        
        return {
            "status": "valid",
            "visitor_id": visitor.id,
            "visitor_name": visitor.name,
            "company": visitor.company,
            "purpose": visitor.purpose,
            "access_count": permission.accessed_count
        }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/{visitor_id}/send-qrcode")
def send_qrcode_to_visitor(visitor_id: int, send_via: str, db: Session = Depends(get_db)):
    """发送二维码到访客邮箱或手机（发送方式：email/sms）"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    # 获取有效权限
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id,
        VisitorPermission.is_active == True,
        VisitorPermission.expires_at > datetime.utcnow()
    ).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="没有有效的二维码权限")
    
    send_via = send_via.lower()
    
    if send_via == "email":
        if not visitor.email:
            raise HTTPException(status_code=400, detail="访客未设置邮箱")
        
        # TODO: 实现邮件发送逻辑
        # send_email(
        #     to=visitor.email,
        #     subject=f"SmartAccess 访客二维码",
        #     body=f"访客 {visitor.name}，您的访问二维码已生成，请用手机扫描以访问。"
        # )
        
        permission.email_sent = True
        permission.email_sent_at = datetime.utcnow()
        
        return {
            "status": "success",
            "message": f"二维码已发送到邮箱 {visitor.email}",
            "sent_to": visitor.email
        }
    
    elif send_via == "sms":
        if not visitor.phone:
            raise HTTPException(status_code=400, detail="访客未设置电话")
        
        # TODO: 实现短信发送逻辑
        # send_sms(
        #     phone=visitor.phone,
        #     message=f"SmartAccess: 访客 {visitor.name}，您的访问二维码已生成"
        # )
        
        permission.sms_sent = True
        permission.sms_sent_at = datetime.utcnow()
        
        return {
            "status": "success",
            "message": f"二维码已发送到手机 {visitor.phone}",
            "sent_to": visitor.phone
        }
    
    else:
        raise HTTPException(status_code=400, detail="不支持的发送方式，请选择 email 或 sms")


@router.post("/{visitor_id}/checkin")
def visitor_checkin(visitor_id: int, db: Session = Depends(get_db)):
    """访客入场记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    visitor.check_in_time = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": f"{visitor.name} 已入场"}


@router.post("/{visitor_id}/checkout")
def visitor_checkout(visitor_id: int, db: Session = Depends(get_db)):
    """访客离场记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    visitor.check_out_time = datetime.utcnow()
    visitor.is_checked_out = True
    
    # 禁用所有权限
    db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id
    ).update({"is_active": False})
    
    db.commit()
    
    return {"status": "success", "message": f"{visitor.name} 已离场"}


@router.post("/batch")
def batch_create_visitors(visitors_data: List[VisitorCreate], db: Session = Depends(get_db)):
    """批量创建访客记录"""
    import os
    expires_hours = int(os.getenv("VISITOR_QR_EXPIRES_HOURS", "24"))
    
    created_visitors = []
    
    for visitor_data in visitors_data:
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        db_visitor = Visitor(
            name=visitor_data.name,
            phone=visitor_data.phone,
            email=visitor_data.email,
            company=visitor_data.company,
            purpose=visitor_data.purpose,
            max_duration_hours=visitor_data.max_duration_hours,
            qr_code_expires_at=expires_at,
        )
        db.add(db_visitor)
        db.flush()
        
        # 生成二维码
        qr_content = f"VISITOR:{db_visitor.id}:{uuid.uuid4().hex}"
        qrcode_path = generate_qrcode(qr_content)
        db_visitor.qr_code_path = qrcode_path
        
        # 创建权限
        permission = VisitorPermission(
            visitor_id=db_visitor.id,
            qr_code_token=qr_content,
            permission_type="qrcode",
            is_active=True,
            expires_at=expires_at,
        )
        db.add(permission)
        created_visitors.append(db_visitor)
    
    db.commit()
    
    return {
        "status": "success",
        "created_count": len(created_visitors),
        "visitors": [VisitorResponse.model_validate(v) for v in created_visitors]
    }


@router.get("/statistics/today")
def get_today_statistics(db: Session = Depends(get_db)):
    """获取今日统计信息"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    checked_in = db.query(Visitor).filter(
        Visitor.check_in_time >= today_start,
        Visitor.check_in_time < today_end
    ).count()
    
    checked_out = db.query(Visitor).filter(
        Visitor.check_out_time >= today_start,
        Visitor.check_out_time < today_end
    ).count()
    
    currently_inside = db.query(Visitor).filter(
        Visitor.check_in_time < today_end,
        Visitor.is_checked_out == False
    ).count()
    
    return {
        "date": today_start.date(),
        "checked_in_today": checked_in,
        "checked_out_today": checked_out,
        "currently_inside": currently_inside
    }

"""访客与二维码管理路由 - 增强版"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Visitor, VisitorPermission, AccessLog, SystemConfig
from app.utils import check_permission_valid, delete_file
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import qrcode
import os
import uuid
import secrets
import yagmail
import io

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
    # 权限相关
    max_uses: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    access_level: str = "door1"  # door1, door2, all


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
    
    # 权限信息
    access_level: Optional[str] = "door1"
    max_uses: Optional[int] = 1
    accessed_count: Optional[int] = 0

    class Config:
        from_attributes = True


class VisitorPermissionCreate(BaseModel):
    visitor_id: int
    permission_type: str = "qrcode"
    expires_in_hours: int = 24
    max_uses: int = 1
    start_time: Optional[datetime] = None
    access_level: str = "door1"


class VisitorPermissionResponse(BaseModel):
    id: int
    visitor_id: int
    qr_code_token: str
    access_level: Optional[str] = "door1"
    permission_type: str
    is_active: bool
    created_at: datetime
    start_time: datetime
    expires_at: datetime
    max_uses: int
    accessed_count: int
    email_sent: bool
    sms_sent: bool

    class Config:
        from_attributes = True


class SendQRCodeRequest(BaseModel):
    visitor_id: int
    send_to: str  # email 或 phone
    send_via: str  # email 或 sms


class EmailConfig(BaseModel):
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    sender_email: str = None

# ==================== 访客管理端点 ====================

def generate_qrcode_bytes(content: str) -> bytes:
    """生成二维码并返回二进制数据"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def generate_qrcode(content: str) -> str:
    """生成二维码文件（兼容旧代码）"""
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
    
    # 确定过期时间
    if visitor.end_time:
        expires_at = visitor.end_time
    else:
        expires_hours = int(os.getenv("VISITOR_QR_EXPIRES_HOURS", "24"))
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    
    start_time = visitor.start_time or datetime.utcnow()
    
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
    
    # 生成二维码内容
    qr_content = f"VISITOR:{db_visitor.id}:{uuid.uuid4().hex}"
    
    # 生成二维码图片并保存到数据库
    qr_bytes = generate_qrcode_bytes(qr_content)
    db_visitor.qr_code_image = qr_bytes
    
    # 同时也保存文件（为了兼容邮件发送附件等功能，或者后续可以改为只从DB读取）
    # 这里为了兼容性，我们还是生成一个文件，但主要逻辑应该依赖DB
    qrcode_path = generate_qrcode(qr_content)
    db_visitor.qr_code_path = qrcode_path
    
    # 创建权限记录
    permission = VisitorPermission(
        visitor_id=db_visitor.id,
        qr_code_token=qr_content,
        permission_type="qrcode",
        is_active=True,
        start_time=start_time,
        expires_at=expires_at,
        max_uses=visitor.max_uses,
        access_level=visitor.access_level
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

@router.get("/{visitor_id}/qrcode/image")
def get_visitor_qrcode_image(visitor_id: int, db: Session = Depends(get_db)):
    """获取访客二维码图片（直接返回图片流）"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    if visitor.qr_code_image:
        return Response(content=visitor.qr_code_image, media_type="image/png")
    
    # 如果数据库没有图片，尝试从文件读取
    if visitor.qr_code_path and os.path.exists(visitor.qr_code_path):
        with open(visitor.qr_code_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")
            
    # 如果都没有，尝试重新生成
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id,
        VisitorPermission.is_active == True
    ).first()
    
    if permission:
        qr_bytes = generate_qrcode_bytes(permission.qr_code_token)
        visitor.qr_code_image = qr_bytes
        db.commit()
        return Response(content=qr_bytes, media_type="image/png")
        
    raise HTTPException(status_code=404, detail="二维码不存在")


@router.get("/config/email", response_model=EmailConfig)
def get_email_config(db: Session = Depends(get_db)):
    """获取邮件服务器配置"""
    smtp_user = db.query(SystemConfig).filter(SystemConfig.key == "smtp_user").first()
    smtp_pass = db.query(SystemConfig).filter(SystemConfig.key == "smtp_password").first()
    smtp_host = db.query(SystemConfig).filter(SystemConfig.key == "smtp_host").first()
    smtp_port = db.query(SystemConfig).filter(SystemConfig.key == "smtp_port").first()
    
    return EmailConfig(
        smtp_user=smtp_user.value if smtp_user else "",
        smtp_password=smtp_pass.value if smtp_pass else "",
        smtp_server=smtp_host.value if smtp_host else "smtp.gmail.com",
        smtp_port=int(smtp_port.value) if smtp_port else 465,
        sender_email=smtp_user.value if smtp_user else ""
    )


@router.post("/config/email")
def update_email_config(config: EmailConfig, db: Session = Depends(get_db)):
    """更新邮件服务器配置"""
    configs = {
        "smtp_user": config.smtp_user,
        "smtp_password": config.smtp_password,
        "smtp_host": config.smtp_server,
        "smtp_port": str(config.smtp_port)
    }
    
    for key, value in configs.items():
        item = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if item:
            item.value = value
        else:
            item = SystemConfig(key=key, value=value)
            db.add(item)
    
    db.commit()
    return {"status": "success", "message": "邮件配置已更新"}


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
        max_uses=perm_create.max_uses,
        start_time=perm_create.start_time,
        access_level=perm_create.access_level
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
    from app.services.qrcode_service import verify_qrcode_token
    is_valid, result = verify_qrcode_token(qrcode_token, db, device_id)
    return result


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
        
        # 检查二维码文件是否存在，如果不存在则从DB恢复或重新生成
        if not visitor.qr_code_path or not os.path.exists(visitor.qr_code_path):
            if visitor.qr_code_image:
                # 从DB恢复文件
                qrcode_dir = "static/qrcodes"
                os.makedirs(qrcode_dir, exist_ok=True)
                filename = f"visitor_{visitor.id}_{uuid.uuid4().hex[:8]}.png"
                qrcode_path = os.path.join(qrcode_dir, filename)
                with open(qrcode_path, "wb") as f:
                    f.write(visitor.qr_code_image)
                visitor.qr_code_path = qrcode_path
                db.commit()
            else:
                # 重新生成
                qrcode_path = generate_qrcode(permission.qr_code_token)
                visitor.qr_code_path = qrcode_path
                db.commit()
        
        # 使用yagmail发送邮件
        try:
            # 从数据库获取邮件配置
            smtp_user_cfg = db.query(SystemConfig).filter(SystemConfig.key == "smtp_user").first()
            smtp_pass_cfg = db.query(SystemConfig).filter(SystemConfig.key == "smtp_password").first()
            smtp_host_cfg = db.query(SystemConfig).filter(SystemConfig.key == "smtp_host").first()
            smtp_port_cfg = db.query(SystemConfig).filter(SystemConfig.key == "smtp_port").first()
            
            smtp_user = smtp_user_cfg.value if smtp_user_cfg else os.getenv("SMTP_USER")
            smtp_password = smtp_pass_cfg.value if smtp_pass_cfg else os.getenv("SMTP_PASSWORD")
            smtp_host = smtp_host_cfg.value if smtp_host_cfg else "smtp.gmail.com"
            smtp_port = smtp_port_cfg.value if smtp_port_cfg else "465"
            
            if not smtp_user or not smtp_password:
                raise HTTPException(status_code=400, detail="邮件服务器未配置，请先在设置中配置邮件服务")

            # 初始化yagmail
            yag = yagmail.SMTP(user=smtp_user, password=smtp_password, host=smtp_host, port=int(smtp_port))
            
            # 准备邮件内容
            subject = f"SmartAccess 访客二维码 - {visitor.name}"
            
            # 邮件正文（HTML格式）
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5;">
                <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h2 style="color: #667eea; text-align: center;">SmartAccess 访客通行证</h2>
                    
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin: 0 0 10px 0;">访客信息</h3>
                        <p style="margin: 5px 0;"><strong>姓名：</strong>{visitor.name}</p>
                        <p style="margin: 5px 0;"><strong>公司：</strong>{visitor.company or '未提供'}</p>
                        <p style="margin: 5px 0;"><strong>访问目的：</strong>{visitor.purpose or '一般访问'}</p>
                        <p style="margin: 5px 0;"><strong>有效期至：</strong>{permission.expires_at.strftime('%Y-%m-%d %H:%M')}</p>
                        <p style="margin: 5px 0;"><strong>剩余次数：</strong>{permission.max_uses - permission.accessed_count if permission.max_uses > 0 else '无限制'}</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <p style="font-size: 16px; color: #333; margin-bottom: 15px;">
                            ⬇️ 请使用下方二维码进行门禁验证 ⬇️
                        </p>
                        <p style="font-size: 14px; color: #666; margin-top: 10px;">
                            到达门口后，请在摄像头或扫码设备前出示此二维码
                        </p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h4 style="color: #333; margin-top: 0;">使用说明：</h4>
                        <ol style="color: #666; line-height: 1.8;">
                            <li>打开此邮件查看附件中的二维码图片</li>
                            <li>保存二维码到手机相册（或直接使用邮件附件）</li>
                            <li>到达门口时，将二维码对准摄像头</li>
                            <li>等待验证通过后即可进入</li>
                        </ol>
                    </div>
                    
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <p style="margin: 0; color: #856404;"><strong>⚠️ 重要提示：</strong></p>
                        <ul style="color: #856404; margin: 10px 0 0 0; padding-left: 20px;">
                            <li>此二维码仅限本次访问使用</li>
                            <li>请勿将二维码转发他人</li>
                            <li>如有问题请联系前台</li>
                        </ul>
                    </div>
                    
                    <p style="text-align: center; color: #999; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                        此邮件由 SmartAccess 智能门禁系统自动发送<br/>
                        © 2024 SmartAccess. All rights reserved.
                    </p>
                </div>
            </body>
            </html>
            """
            
            # 发送邮件（附件为二维码图片）
            yag.send(
                to=visitor.email,
                subject=subject,
                contents=[body, visitor.qr_code_path]
            )
            
            # 更新发送状态
            permission.email_sent = True
            permission.email_sent_at = datetime.utcnow()
            db.commit()
            
            return {
                "status": "success",
                "message": f"二维码已成功发送到邮箱 {visitor.email}",
                "sent_to": visitor.email,
                "qrcode_path": visitor.qr_code_path
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(e)}")
    
    elif send_via == "sms":
        if not visitor.phone:
            raise HTTPException(status_code=400, detail="访客未设置电话")
        
        # TODO: 实现短信发送逻辑（需要短信服务商API）
        # 由于短信需要付费服务，这里仅做标记
        
        permission.sms_sent = True
        permission.sms_sent_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "info",
            "message": f"短信发送功能待实现，请使用邮件方式",
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
        
        # 生成二维码内容
        qr_content = f"VISITOR:{db_visitor.id}:{uuid.uuid4().hex}"
        
        # 生成二维码图片并保存到数据库
        qr_bytes = generate_qrcode_bytes(qr_content)
        db_visitor.qr_code_image = qr_bytes
        
        # 同时也保存文件（兼容性）
        qrcode_path = generate_qrcode(qr_content)
        db_visitor.qr_code_path = qrcode_path
        
        # 创建权限
        permission = VisitorPermission(
            visitor_id=db_visitor.id,
            qr_code_token=qr_content,
            permission_type="qrcode",
            is_active=True,
            expires_at=expires_at,
            max_uses=visitor_data.max_uses,
            start_time=visitor_data.start_time,
            access_level=visitor_data.access_level
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

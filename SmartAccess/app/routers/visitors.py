"""访客与二维码管理路由 - 增强版"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Visitor, VisitorPermission, AccessLog, SystemConfig
from app.utils import check_permission_valid, delete_file
from app.auth import get_current_user, require_role, TokenData
from datetime import datetime, timedelta
from app.time_utils import now_utc8
from typing import List, Optional
from pydantic import BaseModel
import qrcode
import os
import uuid
import secrets
import io
import logging
import smtplib
from email.message import EmailMessage
import mimetypes

router = APIRouter(
    prefix="/api/visitors",
    tags=["visitors"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)
SMTP_TIMEOUT_SECONDS = 20


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
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    purpose: Optional[str] = None
    check_in_time: datetime
    check_out_time: Optional[datetime] = None
    is_checked_out: bool
    qr_code_path: Optional[str] = None
    qr_code_expires_at: Optional[datetime] = None
    max_duration_hours: int
    created_at: datetime
    
    # 权限信息
    access_level: Optional[str] = "door1"
    max_uses: Optional[int] = 1
    accessed_count: Optional[int] = 0
    permission_start_time: Optional[datetime] = None
    permission_expires_at: Optional[datetime] = None

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
    filename = f"visitor_{now_utc8().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
    qrcode_path = os.path.join(qrcode_dir, filename)
    img.save(qrcode_path)
    
    return qrcode_path


def _cfg(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    item = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return item.value if item else default


def _normalize_security(port: int, security: Optional[str]) -> str:
    mode = (security or "auto").strip().lower()
    if mode not in {"auto", "ssl", "starttls"}:
        mode = "auto"
    if mode == "auto":
        # 常见约定：587 使用 STARTTLS，其余默认 SSL
        return "starttls" if int(port) == 587 else "ssl"
    return mode


def _security_candidates(port: int, security: Optional[str]) -> List[str]:
    """为邮件发送生成协议候选顺序，auto 模式下先按常规端口，再尝试兜底。"""
    mode = (security or "auto").strip().lower()
    if mode in {"ssl", "starttls"}:
        return [mode]

    preferred = _normalize_security(port, security)
    fallback = "ssl" if preferred == "starttls" else "starttls"
    return [preferred, fallback]


def _build_mail_channels(db: Session) -> List[dict]:
    channels: List[dict] = []

    primary = {
        "name": "primary",
        "host": _cfg(db, "smtp_host", "smtp.gmail.com"),
        "port": int(_cfg(db, "smtp_port", "465") or "465"),
        "user": _cfg(db, "smtp_user", os.getenv("SMTP_USER", "")),
        "password": _cfg(db, "smtp_password", os.getenv("SMTP_PASSWORD", "")),
        "security": _cfg(db, "smtp_security", "auto"),
    }
    if primary["user"] and primary["password"]:
        channels.append(primary)

    backup_enabled = (_cfg(db, "backup_smtp_enabled", "false") or "false").lower() == "true"
    if backup_enabled:
        backup = {
            "name": "backup",
            "host": _cfg(db, "backup_smtp_host", ""),
            "port": int(_cfg(db, "backup_smtp_port", "587") or "587"),
            "user": _cfg(db, "backup_smtp_user", ""),
            "password": _cfg(db, "backup_smtp_password", ""),
            "security": _cfg(db, "backup_smtp_security", "auto"),
        }
        if backup["host"] and backup["user"] and backup["password"]:
            channels.append(backup)
        else:
            logger.warning("备用SMTP已启用，但配置不完整，已跳过备用通道")

    return channels


def _build_email_message(from_addr: str, to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("请使用支持HTML的邮件客户端查看此邮件。")
    msg.add_alternative(body, subtype="html")

    if attachment_path:
        if not os.path.exists(attachment_path):
            raise FileNotFoundError(f"附件文件不存在: {attachment_path}")
        mime_type, _ = mimetypes.guess_type(attachment_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        main_type, sub_type = mime_type.split("/", 1)
        with open(attachment_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=main_type,
                subtype=sub_type,
                filename=os.path.basename(attachment_path),
            )

    return msg


def _send_mail_via_channel(channel: dict, to: str, subject: str, body: str, attachment_path: Optional[str] = None):
    host = channel["host"]
    port = int(channel["port"])
    user = channel["user"]
    password = channel["password"]
    message = _build_email_message(user, to, subject, body, attachment_path)

    errors: List[str] = []
    for mode in _security_candidates(port, channel.get("security")):
        try:
            if mode == "ssl":
                with smtplib.SMTP_SSL(host=host, port=port, timeout=SMTP_TIMEOUT_SECONDS) as server:
                    server.login(user, password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(host=host, port=port, timeout=SMTP_TIMEOUT_SECONDS) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(user, password)
                    server.send_message(message)
            return
        except Exception as e:
            errors.append(f"{mode}: {type(e).__name__} - {str(e)}")

    raise RuntimeError(" | ".join(errors) if errors else "SMTP发送失败")


def send_qrcode_email_internal(visitor: Visitor, permission: VisitorPermission, db: Session) -> dict:
    """发送访客二维码邮件（内部复用函数）"""
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

    channels = _build_mail_channels(db)
    if not channels:
        raise HTTPException(status_code=400, detail="邮件服务器未配置，请先在设置中配置邮件服务")

    # 准备邮件内容
    subject = f"SmartAccess 访客二维码 - {visitor.name}"

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
                © 2026 SmartAccess. All rights reserved.
            </p>
        </div>
    </body>
    </html>
    """

    send_errors: List[str] = []
    used_channel = ""
    for channel in channels:
        try:
            _send_mail_via_channel(
                channel=channel,
                to=visitor.email,
                subject=subject,
                body=body,
                attachment_path=visitor.qr_code_path,
            )
            used_channel = channel["name"]
            break
        except Exception as e:
            send_errors.append(f"{channel['name']}: {type(e).__name__} - {str(e)}")
            logger.warning(f"邮件通道发送失败 [{channel['name']}]: {e}")

    if not used_channel:
        raise HTTPException(
            status_code=502,
            detail="; ".join(send_errors) if send_errors else "所有邮件通道发送失败"
        )

    permission.email_sent = True
    permission.email_sent_at = now_utc8()
    db.commit()

    return {
        "status": "success",
        "message": f"二维码已成功发送到邮箱 {visitor.email}（通道: {used_channel}）",
        "sent_to": visitor.email,
        "qrcode_path": visitor.qr_code_path,
        "channel": used_channel
    }


@router.post("/", response_model=VisitorResponse)
def create_visitor(visitor: VisitorCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """创建访客记录（仅管理员）"""
    import os
    
    # 确定过期时间
    if visitor.end_time:
        expires_at = visitor.end_time
    else:
        expires_hours = int(os.getenv("VISITOR_QR_EXPIRES_HOURS", "24"))
        expires_at = now_utc8() + timedelta(hours=expires_hours)
    
    start_time = visitor.start_time or now_utc8()
    
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

    # 创建成功后立即尝试邮件发送（访客填写邮箱时）
    if db_visitor.email:
        try:
            send_qrcode_email_internal(db_visitor, permission, db)
        except Exception as e:
            logger.error(f"访客创建后自动发送邮件失败 visitor_id={db_visitor.id}: {e}")

    return db_visitor


@router.get("/", response_model=List[VisitorResponse])
def list_visitors(
    skip: int = 0,
    limit: int = 100,
    is_checked_out: Optional[bool] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取访客列表（仅管理员）"""
    query = db.query(Visitor).options(joinedload(Visitor.visitor_permissions))
    
    if is_checked_out is not None:
        query = query.filter(Visitor.is_checked_out == is_checked_out)
    if company:
        query = query.filter(Visitor.company.ilike(f"%{company}%"))
    
    visitors = query.order_by(Visitor.created_at.desc()).offset(skip).limit(limit).all()
    return visitors


@router.get("/{visitor_id}", response_model=VisitorResponse)
def get_visitor(visitor_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """获取访客详情（仅管理员）"""
    visitor = db.query(Visitor).options(joinedload(Visitor.visitor_permissions)).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    return visitor


@router.put("/{visitor_id}", response_model=VisitorResponse)
def update_visitor(visitor_id: int, visitor_update: VisitorUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """更新访客信息（仅管理员）"""
    visitor = db.query(Visitor).options(joinedload(Visitor.visitor_permissions)).filter(Visitor.id == visitor_id).first()
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
def delete_visitor(visitor_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除访客记录（仅管理员）"""
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
        VisitorPermission.expires_at > now_utc8()
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
def get_visitor_permissions(visitor_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
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
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """为访客创建权限记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    expires_at = now_utc8() + timedelta(hours=perm_create.expires_in_hours)
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
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
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
def delete_visitor_permission(visitor_id: int, permission_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
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
def send_qrcode_to_visitor(visitor_id: int, send_via: str, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """发送二维码到访客邮箱或手机（发送方式：email/sms）"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    # 获取有效权限
    permission = db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id,
        VisitorPermission.is_active == True,
        VisitorPermission.expires_at > now_utc8()
    ).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="没有有效的二维码权限")
    
    send_via = send_via.lower()
    
    if send_via == "email":
        try:
            return send_qrcode_email_internal(visitor, permission, db)
        except HTTPException:
            raise
        except smtplib.SMTPAuthenticationError:
            raise HTTPException(
                status_code=400,
                detail="SMTP认证失败：请检查邮箱账号、SMTP授权码，以及是否已开启SMTP服务"
            )
        except smtplib.SMTPServerDisconnected:
            raise HTTPException(
                status_code=502,
                detail="SMTP连接被服务器断开：可能是授权码错误、账号异常、登录频率限制或服务器繁忙"
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(e)}")
    
    elif send_via == "sms":
        if not visitor.phone:
            raise HTTPException(status_code=400, detail="访客未设置电话")
        
        # TODO: 实现短信发送逻辑（需要短信服务商API）
        # 由于短信需要付费服务，这里仅做标记
        
        permission.sms_sent = True
        permission.sms_sent_at = now_utc8()
        db.commit()
        
        return {
            "status": "info",
            "message": f"短信发送功能待实现，请使用邮件方式",
            "sent_to": visitor.phone
        }
    
    else:
        raise HTTPException(status_code=400, detail="不支持的发送方式，请选择 email 或 sms")


@router.post("/{visitor_id}/checkin")
def visitor_checkin(visitor_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """访客入场记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    visitor.check_in_time = now_utc8()
    db.commit()
    
    return {"status": "success", "message": f"{visitor.name} 已入场"}


@router.post("/{visitor_id}/checkout")
def visitor_checkout(visitor_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """访客离场记录"""
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="访客不存在")
    
    visitor.check_out_time = now_utc8()
    visitor.is_checked_out = True
    
    # 禁用所有权限
    db.query(VisitorPermission).filter(
        VisitorPermission.visitor_id == visitor_id
    ).update({"is_active": False})
    
    db.commit()
    
    return {"status": "success", "message": f"{visitor.name} 已离场"}


@router.post("/batch")
def batch_create_visitors(visitors_data: List[VisitorCreate], db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """批量创建访客记录"""
    import os
    expires_hours = int(os.getenv("VISITOR_QR_EXPIRES_HOURS", "24"))
    
    created_visitors = []
    
    for visitor_data in visitors_data:
        expires_at = now_utc8() + timedelta(hours=expires_hours)
        
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

    # 批量创建后，对填写了邮箱的访客自动发送二维码邮件
    for v in created_visitors:
        if not v.email:
            continue
        permission = db.query(VisitorPermission).filter(
            VisitorPermission.visitor_id == v.id,
            VisitorPermission.is_active == True
        ).order_by(VisitorPermission.created_at.desc()).first()
        if not permission:
            continue
        try:
            send_qrcode_email_internal(v, permission, db)
        except Exception as e:
            logger.error(f"批量创建后自动发送邮件失败 visitor_id={v.id}: {e}")
    
    return {
        "status": "success",
        "created_count": len(created_visitors),
        "visitors": [VisitorResponse.model_validate(v) for v in created_visitors]
    }


@router.get("/statistics/today")
def get_today_statistics(db: Session = Depends(get_db)):
    """获取今日统计信息"""
    today_start = now_utc8().replace(hour=0, minute=0, second=0, microsecond=0)
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


# ==================== 测试邮件API ====================

class TestEmailRequest(BaseModel):
    email: str

@router.post("/test-email")
def test_email_send(request: TestEmailRequest, db: Session = Depends(get_db)):
    """测试邮件发送功能"""
    try:
        channels = _build_mail_channels(db)
        if not channels:
            raise HTTPException(status_code=400, detail="邮件服务器未配置，请先在设置中配置邮件服务")

        # 发送测试邮件
        subject = "SmartAccess 邮件测试"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>SmartAccess 邮件测试</h2>
            <p>恭喜！您的邮件配置成功。</p>
            <p>现在您可以使用访客二维码下发功能了。</p>
            <p><strong>测试时间：</strong>{now_utc8().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                此邮件由 SmartAccess 系统自动发送
            </p>
        </body>
        </html>
        """

        errors: List[str] = []
        used_channel = None
        for channel in channels:
            try:
                _send_mail_via_channel(
                    channel=channel,
                    to=request.email,
                    subject=subject,
                    body=body,
                    attachment_path=None,
                )
                used_channel = channel
                break
            except Exception as e:
                errors.append(f"{channel['name']}: {type(e).__name__} - {str(e)}")

        if not used_channel:
            raise HTTPException(status_code=502, detail="; ".join(errors) if errors else "测试邮件发送失败")

        return {
            "status": "success",
            "message": f"测试邮件已发送到 {request.email}",
            "smtp_config": {
                "host": used_channel["host"],
                "port": str(used_channel["port"]),
                "user": used_channel["user"],
                "security": used_channel.get("security", "auto"),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"邮件发送失败: {str(e)}")


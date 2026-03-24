"""硬件接口路由 - 增强版 (NFC/蓝牙/日志)"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import HardwareDevice, AccessLog, User, NFCCard, BluetoothBinding, UserPermission, NFCTask, BluetoothPairingRecord
from app.utils import check_permission_valid
from app.auth import get_current_user, require_role, TokenData
from datetime import datetime, timedelta
from app.time_utils import now_utc8
from typing import List, Optional, Dict
from pydantic import BaseModel
from fastapi import Request
import time

router = APIRouter(
    prefix="/api/hardware",
    tags=["hardware"],
    responses={404: {"description": "Not found"}},
)

# ==================== 蓝牙扫描缓存 ====================
# 全局缓存：存储最近扫描到的蓝牙设备 {mac: {data, timestamp}}
bluetooth_scan_cache: Dict[str, dict] = {}
CACHE_EXPIRE_SECONDS = 60  # 缓存60秒

# ==================== 蓝牙开门冷却期缓存 ====================
# 全局缓存：记录设备最后开门时间 {mac: timestamp}
bluetooth_cooldown_cache: Dict[str, float] = {}
COOLDOWN_PERIOD_SECONDS = 180  # 冷却期3分钟（180秒）

# ==================== Pydantic 模型 ====================

class HardwareDeviceCreate(BaseModel):
    device_id: str
    device_name: str
    device_type: str  # door_controller, door_controller_nfc
    device_mode: str = "remote_only"  # remote_only(门禁1), remote_nfc(门禁2)
    location: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None


class HardwareDeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_mode: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None


class HardwareHeartbeat(BaseModel):
    connection_status: str = "online"
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None


class HardwareDeviceResponse(BaseModel):
    id: int
    device_id: str
    device_name: str
    device_type: str
    device_mode: Optional[str] = None
    location: Optional[str] = None
    is_active: bool
    last_heartbeat: Optional[datetime] = None
    connection_status: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AccessLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None  # 允许NULL（访客或系统日志）
    access_type: str
    status: str
    timestamp: datetime
    device_id: str
    details: Optional[str] = None

    class Config:
        orm_mode = True


# ======================== NFC 卡片模型 ========================

class NFCCardCreate(BaseModel):
    user_id: Optional[int] = None  # 允许NULL（访客或系统日志）
    card_number: str
    card_name: Optional[str] = None
    permission_end_date: Optional[datetime] = None
    max_daily_uses: int = 0
    door_id: str = "door1"  # door1 / door2
    device_id: Optional[str] = None  # 绑定的设备ID，为空则对所有设备有效


class NFCCardUpdate(BaseModel):
    card_name: Optional[str] = None
    is_active: Optional[bool] = None
    permission_end_date: Optional[datetime] = None
    max_daily_uses: Optional[int] = None
    time_periods: Optional[str] = None
    door_id: Optional[str] = None
    device_id: Optional[str] = None  # 绑定的设备ID


class NFCCardResponse(BaseModel):
    id: int
    user_id: Optional[int] = None  # 允许NULL（访客或系统日志）
    card_number: str
    card_name: Optional[str] = None
    door_id: Optional[str] = None
    device_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    permission_start_date: datetime
    permission_end_date: Optional[datetime]
    max_daily_uses: int
    daily_use_count: int

    class Config:
        orm_mode = True


# ======================== 蓝牙设备模型 ========================

class BluetoothBindingCreate(BaseModel):
    user_id: Optional[int] = None  # 允许NULL（访客或系统日志）
    device_id: str
    device_name: Optional[str] = None
    is_paired: bool = False
    permission_end_date: Optional[datetime] = None
    max_daily_uses: int = 0


class BluetoothBindingUpdate(BaseModel):
    device_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_paired: Optional[bool] = None
    permission_end_date: Optional[datetime] = None
    max_daily_uses: Optional[int] = None


class BluetoothBindingResponse(BaseModel):
    id: int
    user_id: Optional[int] = None  # 允许NULL（访客或系统日志）
    device_id: str
    device_name: Optional[str] = None
    is_paired: bool
    is_active: bool
    created_at: datetime
    last_connect_time: Optional[datetime]
    permission_start_date: datetime
    permission_end_date: Optional[datetime]
    max_daily_uses: int
    daily_use_count: int = 0
    last_use_date: Optional[datetime] = None

    class Config:
        orm_mode = True


class BluetoothPairingRecordResponse(BaseModel):
    id: int
    binding_id: int
    device_irk: Optional[str] = None
    device_ltk: Optional[str] = None
    device_name: Optional[str] = None
    pairing_method: str
    pairing_timestamp: datetime
    last_connection: Optional[datetime] = None
    connection_count: int
    firmware_version: Optional[str] = None

    class Config:
        orm_mode = True


class StartPairingRequest(BaseModel):
    """开始配对请求
    说明：原先仅返回提示信息，未向硬件发出任何指令。
    本次扩展支持可选的 controller_device_id，用于向指定门禁控制器
    下发“进入配对模式”的任务（通过 NFCTask 队列），从而触发硬件开启 BLE 广播。
    """
    binding_id: int
    controller_device_id: Optional[str] = None  # 目标门禁控制器 device_id（可选）
    timeout_seconds: int = 30  # 配对模式超时秒数（默认30秒）


class CompletePairingRequest(BaseModel):
    """完成配对请求"""
    binding_id: int
    device_irk: str  # 16字节十六进制
    device_ltk: str  # 16字节十六进制
    device_name: str
    firmware_version: Optional[str] = None


# ==================== 硬件设备管理 ====================

@router.get("/devices", response_model=List[HardwareDeviceResponse])
def list_devices(
    device_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取所有硬件设备（仅管理员）"""
    query = db.query(HardwareDevice)
    
    if device_type:
        query = query.filter(HardwareDevice.device_type == device_type)
    if is_active is not None:
        query = query.filter(HardwareDevice.is_active == is_active)
    
    devices = query.all()
    return devices


@router.post("/devices", response_model=HardwareDeviceResponse)
def create_device(device: HardwareDeviceCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """注册新硬件设备（仅管理员）"""
    existing = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device.device_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备ID已存在")

    db_device = HardwareDevice(
        device_id=device.device_id,
        device_name=device.device_name,
        device_type=device.device_type,
        device_mode=device.device_mode,
        location=device.location,
        ip_address=device.ip_address,
        port=device.port,
        connection_status="offline"
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device


@router.put("/devices/{device_id}", response_model=HardwareDeviceResponse)
def update_device(device_id: str, device_update: HardwareDeviceUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """更新硬件设备信息（仅管理员）"""
    db_device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device_update.device_name:
        db_device.device_name = device_update.device_name
    if device_update.device_mode:
        db_device.device_mode = device_update.device_mode
    if device_update.location:
        db_device.location = device_update.location
    if device_update.is_active is not None:
        db_device.is_active = device_update.is_active
    if device_update.ip_address:
        db_device.ip_address = device_update.ip_address
    if device_update.port:
        db_device.port = device_update.port
    
    db.commit()
    db.refresh(db_device)
    return db_device


@router.post("/devices/{device_id}/heartbeat")
def device_heartbeat(
    device_id: str,
    heartbeat: HardwareHeartbeat = Body(default=None),
    db: Session = Depends(get_db)
):
    """设备心跳检测"""
    db_device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    payload = heartbeat or HardwareHeartbeat()
    db_device.last_heartbeat = now_utc8()
    db_device.is_active = True
    db_device.connection_status = payload.connection_status or "online"
    if payload.ip_address:
        db_device.ip_address = payload.ip_address
    if payload.firmware_version:
        db_device.firmware_version = payload.firmware_version
    db.commit()
    return {
        "status": "ok",
        "device_id": device_id,
        "connection_status": db_device.connection_status,
        "timestamp": now_utc8(),
    }


@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除硬件设备（仅管理员）"""
    db_device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    db.delete(db_device)
    db.commit()
    return {"message": "设备已删除"}


# ==================== NFC 卡片管理 ====================

@router.post("/nfc/cards", response_model=NFCCardResponse)
def create_nfc_card(card: NFCCardCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """创建 NFC 卡片记录（仅管理员）"""
    user = db.query(User).filter(User.id == card.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    existing = db.query(NFCCard).filter(
        NFCCard.card_number == card.card_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="卡片号已存在")
    
    nfc_card = NFCCard(
        user_id=card.user_id,
        card_number=card.card_number,
        card_name=card.card_name,
        door_id=card.door_id,
        device_id=card.device_id,
        permission_start_date=now_utc8(),
        permission_end_date=card.permission_end_date,
        max_daily_uses=card.max_daily_uses,
    )
    db.add(nfc_card)
    db.commit()
    db.refresh(nfc_card)
    return nfc_card


@router.get("/nfc/cards", response_model=List[NFCCardResponse])
def list_nfc_cards(
    user_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取 NFC 卡片列表（仅管理员）"""
    query = db.query(NFCCard)
    
    if user_id:
        query = query.filter(NFCCard.user_id == user_id)
    if is_active is not None:
        query = query.filter(NFCCard.is_active == is_active)
    
    cards = query.all()
    return cards


@router.get("/nfc/card/{card_id}", response_model=NFCCardResponse)
def get_nfc_card(card_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """获取 NFC 卡片详情"""
    card = db.query(NFCCard).filter(NFCCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return card


@router.put("/nfc/card/{card_id}", response_model=NFCCardResponse)
def update_nfc_card(card_id: int, card_update: NFCCardUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """更新 NFC 卡片信息（仅管理员）"""
    card = db.query(NFCCard).filter(NFCCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    if card_update.card_name:
        card.card_name = card_update.card_name
    if card_update.is_active is not None:
        card.is_active = card_update.is_active
    if card_update.permission_end_date is not None:
        card.permission_end_date = card_update.permission_end_date
    if card_update.max_daily_uses is not None:
        card.max_daily_uses = card_update.max_daily_uses
    if card_update.time_periods:
        card.time_periods = card_update.time_periods
    if card_update.door_id:
        card.door_id = card_update.door_id
    if card_update.device_id is not None:
        card.device_id = card_update.device_id
    
    db.commit()
    db.refresh(card)
    return card


@router.delete("/nfc/card/{card_id}")
def delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除 NFC 卡片（仅管理员）"""
    card = db.query(NFCCard).filter(NFCCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    
    db.delete(card)
    db.commit()
    return {"message": "卡片已删除"}


@router.post("/nfc/access")
def nfc_access(card_number: str, device_id: str, db: Session = Depends(get_db)):
    """NFC 门禁访问"""
    card = db.query(NFCCard).filter(NFCCard.card_number == card_number).first()
    
    if not card:
        access_log = AccessLog(
            user_id=None,
            access_type="nfc",
            status="failed",
            device_id=device_id,
            details="Unknown NFC card"
        )
        db.add(access_log)
        db.commit()
        return {"status": "failed", "message": "未知的卡片"}
    
    if not card.is_active:
        access_log = AccessLog(
            user_id=card.user_id,
            access_type="nfc",
            status="denied",
            device_id=device_id,
            details="Card disabled"
        )
        db.add(access_log)
        db.commit()
        return {"status": "denied", "message": "卡片已被禁用"}
    
    # 检查权限时效
    if not check_permission_valid(card.permission_start_date, card.permission_end_date):
        access_log = AccessLog(
            user_id=card.user_id,
            access_type="nfc",
            status="denied",
            device_id=device_id,
            details="Card permission expired"
        )
        db.add(access_log)
        db.commit()
        return {"status": "denied", "message": "卡片权限已过期"}
    
    # 记录访问日志
    access_log = AccessLog(
        user_id=card.user_id,
        access_type="nfc",
        status="success",
        device_id=device_id,
        details=f"NFC card access - Card: {card.card_name or card.card_number}"
    )
    db.add(access_log)
    
    # 更新使用统计
    card.daily_use_count += 1
    card.last_use_date = now_utc8()
    
    db.commit()
    user = card.user
    return {
        "status": "success",
        "message": f"欢迎 {user.full_name or user.username}",
        "user_id": user.id,
        "user_name": user.full_name or user.username
    }


# ==================== PN532 / 设备 对接：主动上报扫描结果 ====================


class NFCScanRequest(BaseModel):
    card_uid: str
    device_id: Optional[str] = None


@router.post("/nfc-scan")
@router.get("/nfc-scan")
def nfc_scan(
    card_uid: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    req: Optional[NFCScanRequest] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """供设备上报读取到的卡号。返回 action: OPEN/DENY 和 message。

    支持两种调用方式:
    1. POST JSON: {"card_uid":"AA-BB-CC-...","device_id":"door_controller_2"}
    2. GET Query: ?card_uid=AA-BB-CC-...&device_id=door_controller_2
    """
    # 从POST或GET获取参数
    if req:
        card_uid = req.card_uid
        device_id = req.device_id or request.client.host
    else:
        device_id = device_id or request.client.host if request else None

    if not card_uid:
        return {"action": "DENY", "msg": "卡号不能为空"}

    card_uid = card_uid.strip().upper()

    # 检查设备是否存在及其模式
    device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()

    if not device:
        return {"action": "DENY", "msg": "设备不存在"}

    # 检查是否存在未完成的 NFCTask（最近 30 秒内）并将结果挂到任务上
    task = db.query(NFCTask).filter(
        NFCTask.device_id == device_id,
        NFCTask.status.in_(["pending", "sent"])
    ).order_by(NFCTask.created_at.desc()).first()

    # 检查设备是否支持NFC：兼容旧数据，device_mode为空但 device_type 含 nfc 也视为支持
    supports_nfc = (device.device_mode == "remote_nfc") or (device.device_type and "nfc" in device.device_type)
    if not supports_nfc:
        if task:
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}","status":"unsupported_device"}}'
            task.consumed_at = now_utc8()
            db.commit()
        return {"action": "DENY", "msg": "此设备不支持NFC功能"}

    # 查找卡片
    card = db.query(NFCCard).filter(NFCCard.card_number == card_uid).first()

    if not card:
        # 如果卡片不存在且有ENROLL任务，记录卡片UID到任务结果，不创建AccessLog
        if task and task.command == "ENROLL":
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}"}}'
            task.consumed_at = now_utc8()
            db.commit()
            return {"action": "ACCEPT", "msg": "卡片已识别，请等待后台注册"}
        
        # 如果是SCAN或其他命令，不创建NULL user_id的AccessLog，直接返回DENY
        if task:
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}","status":"unknown"}}'
            task.consumed_at = now_utc8()
        db.commit()
        return {"action": "DENY", "msg": "未知卡片"}

    # 检查卡片是否绑定到此设备（device_id不为空时）
    if card.device_id and card.device_id != device_id:
        access_log = AccessLog(
            user_id=card.user_id,
            access_type="nfc",
            status="denied",
            device_id=device_id,
            details=f"Card not assigned to this device (bound to {card.device_id})"
        )
        db.add(access_log)
        if task:
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}","status":"device_mismatch"}}'
            task.consumed_at = now_utc8()
        db.commit()
        return {"action": "DENY", "msg": "卡片未授权给此设备"}

    # 校验卡片是否启用/时效等
    if not card.is_active:
        access_log = AccessLog(
            user_id=card.user_id,
            access_type="nfc",
            status="denied",
            device_id=device_id,
            details="Card disabled"
        )
        db.add(access_log)
        if task:
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}","status":"disabled"}}'
            task.consumed_at = now_utc8()
        db.commit()
        return {"action": "DENY", "msg": "卡片已被禁用"}

    if not check_permission_valid(card.permission_start_date, card.permission_end_date):
        access_log = AccessLog(
            user_id=card.user_id,
            access_type="nfc",
            status="denied",
            device_id=device_id,
            details="Card permission expired"
        )
        db.add(access_log)
        if task:
            task.status = "done"
            task.result = f'{{"card_uid":"{card_uid}","status":"expired"}}'
            task.consumed_at = now_utc8()
        db.commit()
        return {"action": "DENY", "msg": "卡片权限已过期"}

    # 成功：记录日志，更新统计，关联任务
    access_log = AccessLog(
        user_id=card.user_id,
        access_type="nfc",
        status="success",
        device_id=device_id,
        details=f"NFC card access - Card: {card.card_name or card.card_number}"
    )
    db.add(access_log)

    card.daily_use_count += 1
    card.last_use_date = now_utc8()

    if task:
        task.status = "done"
        task.result = f"{{\"card_uid\":\"{card_uid}\",\"status\":\"success\",\"user_id\":{card.user_id},\"door\":\"{card.door_id}\"}}"
        task.consumed_at = now_utc8()

    db.commit()

    user = card.user
    return {"action": "OPEN", "door": card.door_id, "msg": f"欢迎 {user.full_name or user.username}"}


# ==================== Web -> 设备 的命令队列（用于点击触发扫描） ====================


class NFCTaskCreate(BaseModel):
    device_id: str
    command: str = "SCAN"
    payload: Optional[str] = None


class NFCTaskResponse(BaseModel):
    id: int
    device_id: str
    command: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime]
    consumed_at: Optional[datetime]
    result: Optional[str]

    class Config:
        orm_mode = True


@router.post("/nfc/command", response_model=NFCTaskResponse)
def create_nfc_command(task_in: NFCTaskCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """Web 后台创建一个 NFC 任务（通常是 SCAN），设备会轮询并执行。"""
    task = NFCTask(
        device_id=task_in.device_id,
        command=task_in.command,
        payload=task_in.payload,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


class PollRequest(BaseModel):
    """轮询请求模型"""
    device_id: str


class RemoteDoorRequest(BaseModel):
    """远程开门请求"""
    device_id: str
    door_id: int  # 1 或 2
    source: str = "remote"  # 触发来源


@router.post("/remote-door/open")
def remote_open_door(request: RemoteDoorRequest, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """
    远程开门接口 - Web端调用
    创建一个OPEN指令任务，设备轮询时会执行
    """
    # 检查设备是否存在
    device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == request.device_id
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if not device.is_active:
        raise HTTPException(status_code=400, detail="设备未激活")
    
    # 创建开门任务
    door_str = f"door{request.door_id}"
    task = NFCTask(
        device_id=request.device_id,
        command="OPEN",
        payload=f'{{"door": "{door_str}", "source": "{request.source}"}}',
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "success": True,
        "message": f"开门指令已下发到设备 {request.device_id}",
        "task_id": task.id,
        "door": door_str
    }


@router.post("/nfc/command/poll")
@router.get("/nfc/command/poll")
def poll_nfc_command(
    device_id: Optional[str] = Query(None), 
    request_body: Optional[PollRequest] = None,
    db: Session = Depends(get_db)
):
    """
    设备轮询此接口以获取待执行命令
    支持 GET 和 POST 两种方法
    - GET: ?device_id=xxx
    - POST: {"device_id": "xxx"}
    """
    # 从GET参数或POST body获取device_id
    dev_id = device_id if device_id else (request_body.device_id if request_body else None)
    
    if not dev_id:
        return {"has_command": False, "message": "未提供device_id"}
    
    # 查询待执行的命令
    task = db.query(NFCTask).filter(
        NFCTask.device_id == dev_id,
        NFCTask.status == "pending"
    ).order_by(NFCTask.created_at.asc()).first()
    
    if not task:
        return {"has_command": False}

    # 标记为已发送
    task.status = "sent"
    task.sent_at = now_utc8()
    db.commit()
    
    return {
        "has_command": True,
        "task_id": task.id,
        "command": task.command,
        "payload": task.payload
    }


@router.get("/nfc/command/status/{task_id}")
def get_nfc_command_status(task_id: int, db: Session = Depends(get_db)):
    task = db.query(NFCTask).filter(NFCTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id,
        "status": task.status,
        "result": task.result,
        "created_at": task.created_at,
        "consumed_at": task.consumed_at
    }



# ==================== 蓝牙设备管理 ====================

@router.post("/bluetooth/bindings", response_model=BluetoothBindingResponse)
def create_bluetooth_binding(binding: BluetoothBindingCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """创建蓝牙设备绑定（仅管理员）"""
    user = db.query(User).filter(User.id == binding.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    existing = db.query(BluetoothBinding).filter(
        BluetoothBinding.user_id == binding.user_id,
        BluetoothBinding.device_id == binding.device_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户已绑定此蓝牙设备")
    
    bt_binding = BluetoothBinding(
        user_id=binding.user_id,
        device_id=binding.device_id,
        device_name=binding.device_name,
        is_paired=binding.is_paired,
        permission_start_date=now_utc8(),
        permission_end_date=binding.permission_end_date,
        max_daily_uses=binding.max_daily_uses,
    )
    db.add(bt_binding)
    db.commit()
    db.refresh(bt_binding)
    return bt_binding


@router.get("/bluetooth/bindings")
def list_bluetooth_bindings(
    user_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取蓝牙设备绑定列表（仅管理员）"""
    query = db.query(BluetoothBinding)
    
    if user_id:
        query = query.filter(BluetoothBinding.user_id == user_id)
    if is_active is not None:
        query = query.filter(BluetoothBinding.is_active == is_active)
    
    bindings = query.all()
    
    # 为每个绑定添加使用统计
    result = []
    today = now_utc8().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    for binding in bindings:
        binding_dict = {
            "id": binding.id,
            "user_id": binding.user_id,
            "device_id": binding.device_id,
            "device_name": binding.device_name,
            "is_paired": binding.is_paired,
            "is_active": binding.is_active,
            "created_at": binding.created_at,
            "last_connect_time": binding.last_connect_time,
            "permission_start_date": binding.permission_start_date,
            "permission_end_date": binding.permission_end_date,
            "max_daily_uses": binding.max_daily_uses,
        }
        
        # 统计今日使用次数（从AccessLog）
        daily_count = db.query(AccessLog).filter(
            AccessLog.user_id == binding.user_id,
            AccessLog.access_type == "bluetooth",
            AccessLog.status == "success",
            AccessLog.timestamp >= today_start,
            AccessLog.details.like(f"%{binding.device_id}%")
        ).count()
        binding_dict["daily_use_count"] = daily_count
        
        # 获取最后使用时间（从AccessLog）
        last_log = db.query(AccessLog).filter(
            AccessLog.user_id == binding.user_id,
            AccessLog.access_type == "bluetooth",
            AccessLog.status == "success",
            AccessLog.details.like(f"%{binding.device_id}%")
        ).order_by(AccessLog.timestamp.desc()).first()
        
        binding_dict["last_use_date"] = last_log.timestamp if last_log else None
        
        result.append(binding_dict)
    
    return result


@router.put("/bluetooth/binding/{binding_id}", response_model=BluetoothBindingResponse)
def update_bluetooth_binding(binding_id: int, binding_update: BluetoothBindingUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """更新蓝牙设备绑定（仅管理员）"""
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    if binding_update.device_name:
        binding.device_name = binding_update.device_name
    if binding_update.is_active is not None:
        binding.is_active = binding_update.is_active
    if binding_update.is_paired is not None:
        binding.is_paired = binding_update.is_paired
    if binding_update.permission_end_date is not None:
        binding.permission_end_date = binding_update.permission_end_date
    if binding_update.max_daily_uses is not None:
        binding.max_daily_uses = binding_update.max_daily_uses
    
    db.commit()
    db.refresh(binding)
    return binding


@router.delete("/bluetooth/binding/{binding_id}")
def delete_bluetooth_binding(binding_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除蓝牙设备绑定（仅管理员）"""
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    db.delete(binding)
    db.commit()
    return {"message": "绑定已删除"}


class BluetoothScanReport(BaseModel):
    """蓝牙扫描上报数据模型（单个设备）"""
    mac: str
    rssi: int
    device_id: str
    name: Optional[str] = None


class BluetoothBatchScanReport(BaseModel):
    """蓝牙批量扫描上报数据模型"""
    devices: list
    device_id: str


@router.post("/bluetooth/report-scan")
def report_bluetooth_scan(report: BluetoothScanReport):
    """ESP32上报扫描到的蓝牙设备（单个）"""
    global bluetooth_scan_cache
    
    # 更新缓存
    bluetooth_scan_cache[report.mac.upper()] = {
        "mac": report.mac.upper(),
        "name": report.name or f"BLE-{report.mac[-8:]}",
        "rssi": report.rssi,
        "device_id": report.device_id,  # 上报设备ID
        "timestamp": time.time(),
        "last_seen": now_utc8().isoformat()
    }
    
    return {"status": "ok", "cached_devices": len(bluetooth_scan_cache)}


@router.post("/bluetooth/report-scan-batch")
def report_bluetooth_scan_batch(report: BluetoothBatchScanReport):
    """ESP32批量上报扫描到的蓝牙设备"""
    global bluetooth_scan_cache
    
    # 批量更新缓存
    current_time = time.time()
    for device in report.devices:
        mac = device.get("mac", "").upper()
        if mac:
            bluetooth_scan_cache[mac] = {
                "mac": mac,
                "name": device.get("name") or f"BLE-{mac[-8:]}",
                "rssi": device.get("rssi", -100),
                "device_id": report.device_id,
                "timestamp": current_time,
                "last_seen": now_utc8().isoformat()
            }
    
    return {"status": "ok", "received": len(report.devices), "cached_devices": len(bluetooth_scan_cache)}


@router.get("/bluetooth/scan")
def scan_bluetooth_devices():
    """获取最近扫描到的蓝牙设备（从缓存）"""
    global bluetooth_scan_cache
    
    # 清理过期缓存
    current_time = time.time()
    expired_keys = [
        mac for mac, data in bluetooth_scan_cache.items()
        if current_time - data.get("timestamp", 0) > CACHE_EXPIRE_SECONDS
    ]
    for key in expired_keys:
        del bluetooth_scan_cache[key]
    
    # 返回所有有效设备，按RSSI排序（信号强的在前）
    devices = sorted(
        bluetooth_scan_cache.values(),
        key=lambda x: x.get("rssi", -100),
        reverse=True
    )
    
    return devices


@router.post("/bluetooth/verify")
def verify_bluetooth_device(
    device_id: str = Body(...),
    bt_mac: str = Body(...),
    rssi: int = Body(...),
    device_irk: Optional[str] = Body(None),  # 配对后的IRK识别
    db: Session = Depends(get_db)
):
    """验证蓝牙设备权限 - 硬件轮询用（支持MAC和IRK识别）"""
    bt_mac_upper = bt_mac.upper()
    
    # ✅ 检查冷却期（3分钟内已开过门）
    current_time = time.time()
    cache_key = device_irk if device_irk else bt_mac_upper
    
    if cache_key in bluetooth_cooldown_cache:
        last_open_time = bluetooth_cooldown_cache[cache_key]
        time_since_last_open = current_time - last_open_time
        
        if time_since_last_open < COOLDOWN_PERIOD_SECONDS:
            # 仍在冷却期内
            remaining_seconds = int(COOLDOWN_PERIOD_SECONDS - time_since_last_open)
            remaining_minutes = remaining_seconds // 60
            remaining_secs = remaining_seconds % 60
            
            return {
                "allow": False,
                "user_name": "Cooldown",
                "reason": "In cooldown period",
                "in_cooldown": True,
                "cooldown_remaining_seconds": remaining_seconds,
                "cooldown_remaining_text": f"{remaining_minutes}分{remaining_secs}秒"
            }
    
    binding = None
    
    # 🔐 优先使用IRK识别（配对设备）
    if device_irk:
        pairing_record = db.query(BluetoothPairingRecord).filter(
            BluetoothPairingRecord.device_irk == device_irk.upper()
        ).first()
        
        if pairing_record:
            binding = pairing_record.binding
            # 更新连接信息
            pairing_record.last_connection = now_utc8()
            pairing_record.connection_count += 1
            db.commit()
    
    # 降级到MAC识别（未配对或配对失败）
    if not binding:
        binding = db.query(BluetoothBinding).filter(
            BluetoothBinding.device_id == bt_mac_upper,
            BluetoothBinding.is_active == True
        ).first()
    
    if not binding:
        return {"allow": False, "user_name": "Unknown", "reason": "Device not bound", "in_cooldown": False}
    
    # 检查权限是否有效
    if not check_permission_valid(binding.permission_start_date, binding.permission_end_date):
        return {"allow": False, "user_name": binding.user.username if binding.user else "Unknown", "reason": "Permission expired", "in_cooldown": False}
    
    # 检查每日使用次数限制
    if binding.max_daily_uses > 0:
        # 计算今天的使用次数
        today = now_utc8().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_count = db.query(AccessLog).filter(
            AccessLog.device_id == device_id,
            AccessLog.user_id == binding.user_id,
            AccessLog.access_type == "bluetooth",
            AccessLog.timestamp >= today_start
        ).count()
        
        if today_count >= binding.max_daily_uses:
            return {"allow": False, "user_name": binding.user.username if binding.user else "Unknown", "reason": "Daily limit reached", "in_cooldown": False}
    
    # 权限有效，允许开门
    user_name = binding.user.username if binding.user else f"User{binding.user_id}"
    return {
        "allow": True,
        "user_name": user_name,
        "user_id": binding.user_id,
        "binding_id": binding.id,
        "rssi": rssi,
        "in_cooldown": False
    }


@router.post("/bluetooth/unlock")
def bluetooth_unlock(user_id: int, device_id: str, db: Session = Depends(get_db)):
    """蓝牙远程开锁"""
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.user_id == user_id,
        BluetoothBinding.device_id == device_id
    ).first()
    
    if not binding:
        return {"status": "failed", "message": "设备绑定不存在"}
    
    if not binding.is_active:
        return {"status": "denied", "message": "绑定已被禁用"}
    
    if not check_permission_valid(binding.permission_start_date, binding.permission_end_date):
        return {"status": "denied", "message": "权限已过期"}
    
    # 这里可以调用实际的硬件开锁接口
    # TODO: 添加硬件开锁实现
    
    binding.daily_use_count += 1
    binding.last_use_date = now_utc8()
    
    access_log = AccessLog(
        user_id=user_id,
        access_type="bluetooth",
        status="success",
        device_id=device_id,
        details="Bluetooth remote unlock"
    )
    db.add(access_log)
    db.commit()
    
    return {
        "status": "success",
        "message": "开锁成功",
        "device_id": device_id,
        "timestamp": now_utc8()
    }


@router.post("/bluetooth/pairing-mode")
def enable_bluetooth_pairing(device_id: str, duration_seconds: int = 300, db: Session = Depends(get_db)):
    """启用蓝牙配对模式（供硬件调用）"""
    # 这是一个硬件设备调用的接口，用于启用配对模式
    # TODO: 实现硬件蓝牙配对逻辑
    
    return {
        "status": "pairing_mode_enabled",
        "device_id": device_id,
        "duration": duration_seconds,
        "expires_at": now_utc8() + timedelta(seconds=duration_seconds)
    }


@router.post("/bluetooth/access-log")
def record_bluetooth_access_log(
    device_id: str = Body(...),
    bt_mac: str = Body(...),
    access_type: str = Body(...),
    status: str = Body(...),
    db: Session = Depends(get_db)
):
    """记录蓝牙设备访问日志"""
    bt_mac_upper = bt_mac.upper()
    
    # 查询绑定信息获取user_id
    binding = db.query(BluetoothBinding).filter(
        BluetoothBinding.device_id == bt_mac_upper
    ).first()
    
    if binding:
        access_log = AccessLog(
            user_id=binding.user_id,
            access_type=access_type,
            status=status,
            device_id=device_id,
            details=f"Bluetooth {access_type}: {bt_mac}"
        )
        db.add(access_log)
        db.commit()
        
        # ✅ 开门成功后，记录冷却期（3分钟）
        if status == "success":
            bluetooth_cooldown_cache[bt_mac_upper] = time.time()
            print(f"[Cooldown] 添加设备到冷却期: {bt_mac_upper} (3分钟)")
        
        return {"status": "logged", "log_id": access_log.id}
    
    return {"status": "device_not_found"}


# ==================== 访问日志管理 ====================

@router.get("/logs", response_model=List[AccessLogResponse])
def get_access_logs(
    skip: int = 0,
    limit: int = 100,
    access_type: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取访问日志
    
    Args:
        skip: 跳过记录数（分页）
        limit: 返回记录数限制
        access_type: 访问类型过滤（face/nfc/qrcode/bluetooth/manual）
        status: 状态过滤（success/failed/denied）
        days: 最近N 天的日志（当未指定start_date/end_date 时使用）
        start_date: 开始日期（ISO 格式：YYYY-MM-DD），优先级高于days
        end_date: 结束日期（ISO 格式：YYYY-MM-DD），默认为今天
    """
    query = db.query(AccessLog)
    
    # 处理日期范围筛选
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
        start_dt = now_utc8() - timedelta(days=days)
        query = query.filter(AccessLog.timestamp >= start_dt)
    
    if access_type:
        query = query.filter(AccessLog.access_type == access_type)
    if status:
        query = query.filter(AccessLog.status == status)
    
    logs = query.order_by(AccessLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs


@router.get("/logs/user/{user_id}", response_model=List[AccessLogResponse])
def get_user_logs(user_id: int, limit: int = 50, days: int = 30, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """获取用户的访问日志"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    start_date = now_utc8() - timedelta(days=days)
    logs = db.query(AccessLog).filter(
        AccessLog.user_id == user_id,
        AccessLog.timestamp >= start_date
    ).order_by(AccessLog.timestamp.desc()).limit(limit).all()
    return logs


@router.get("/logs/device/{device_id}", response_model=List[AccessLogResponse])
def get_device_logs(device_id: str, limit: int = 50, days: int = 30, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """获取设备的访问日志"""
    device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    start_date = now_utc8() - timedelta(days=days)
    logs = db.query(AccessLog).filter(
        AccessLog.device_id == device_id,
        AccessLog.timestamp >= start_date
    ).order_by(AccessLog.timestamp.desc()).limit(limit).all()
    return logs


@router.get("/logs/statistics")
def get_access_statistics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取访问统计信息"""
    start_date = now_utc8() - timedelta(days=days)
    
    total_accesses = db.query(AccessLog).filter(AccessLog.timestamp >= start_date).count()
    success_accesses = db.query(AccessLog).filter(
        AccessLog.timestamp >= start_date,
        AccessLog.status == "success"
    ).count()
    failed_accesses = db.query(AccessLog).filter(
        AccessLog.timestamp >= start_date,
        AccessLog.status == "failed"
    ).count()
    denied_accesses = db.query(AccessLog).filter(
        AccessLog.timestamp >= start_date,
        AccessLog.status == "denied"
    ).count()
    
    # 按访问类型统计
    access_types = db.query(
        AccessLog.access_type,
        __import__('sqlalchemy').func.count(AccessLog.id).label('count')
    ).filter(AccessLog.timestamp >= start_date).group_by(AccessLog.access_type).all()
    
    return {
        "period_days": days,
        "start_date": start_date,
        "end_date": now_utc8(),
        "total_accesses": total_accesses,
        "success_accesses": success_accesses,
        "failed_accesses": failed_accesses,
        "denied_accesses": denied_accesses,
        "success_rate": f"{(success_accesses / total_accesses * 100) if total_accesses > 0 else 0:.2f}%",
        "access_by_type": {item[0]: item[1] for item in access_types}
    }


# ==================== 统一远程开门接口 ====================

class RemoteUnlockRequest(BaseModel):
    """远程开门请求"""
    device_id: str  # 设备ID，例如 "nfc_reader_01"
    door_id: str = "door1"  # 门编号：door1 或 door2
    user_id: Optional[int] = None  # 触发开门的用户ID（用于记录日志）
    reason: Optional[str] = "remote_unlock"  # 开门原因



# ==================== 新增统计接口 ====================

@router.get("/logs/trend")
def get_daily_trend(
    days: int = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取每日访问趋势"""
    trend_data = []
    
    for i in range(days - 1, -1, -1):
        date_start = now_utc8().date() - timedelta(days=i)
        date_end = date_start + timedelta(days=1)
        
        total = db.query(AccessLog).filter(
            AccessLog.timestamp >= date_start,
            AccessLog.timestamp < date_end
        ).count()
        
        success = db.query(AccessLog).filter(
            AccessLog.timestamp >= date_start,
            AccessLog.timestamp < date_end,
            AccessLog.status == "success"
        ).count()
        
        failed = db.query(AccessLog).filter(
            AccessLog.timestamp >= date_start,
            AccessLog.timestamp < date_end,
            AccessLog.status != "success"
        ).count()
        
        trend_data.append({
            "date": date_start.isoformat(),
            "total": total,
            "success": success,
            "failed": failed
        })
    
    return {"trend": trend_data}


@router.get("/logs/hourly-distribution")
def get_hourly_distribution(
    days: int = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取每小时活跃度分布"""
    start_date = now_utc8() - timedelta(days=days)
    
    hourly_counts = db.query(
        func.extract('hour', AccessLog.timestamp).label('hour'),
        func.count(AccessLog.id).label('count')
    ).filter(AccessLog.timestamp >= start_date).group_by(
        func.extract('hour', AccessLog.timestamp)
    ).all()
    
    # 转换为字典，确保所有小时都有值（包括没有数据的小时）
    distribution = {str(h).zfill(2): 0 for h in range(24)}
    for hour, count in hourly_counts:
        distribution[str(int(hour)).zfill(2)] = count
    
    return {"distribution": distribution}

@router.get("/stats/user-count")
def get_user_count(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取用户统计数据：总用户数和本周新增用户数"""
    # 计算总用户数
    total_users = db.query(User).count()
    
    # 计算本周新增用户数（过去 7天内注册的用户）
    week_ago = now_utc8() - timedelta(days=7)
    new_this_week = db.query(User).filter(User.created_at >= week_ago).count()
    
    return {
        "total": total_users,
        "new_this_week": new_this_week
    }


@router.post("/remote-unlock")
def remote_unlock_door(
    request: RemoteUnlockRequest,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """
    统一远程开门接口
    
    功能：
    - 向指定硬件设备发送开门命令
    - 支持人脸识别、蓝牙、管理员等多种方式调用
    - 记录开门日志
    
    参数：
    - device_id: 硬件设备ID
    - door_id: 门编号 (door1/door2)
    - user_id: 用户ID（可选，用于日志记录）
    - reason: 开门原因（可选，用于日志记录）
    """
    
    # 检查设备是否存在
    device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == request.device_id
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail=f"设备 {request.device_id} 不存在")
    
    if not device.is_active:
        raise HTTPException(status_code=400, detail=f"设备 {request.device_id} 未激活")
    
    try:
        # 创建开门任务
        task = NFCTask(
            device_id=request.device_id,
            command="OPEN",
            payload=f'{{"door_id": "{request.door_id}"}}',
            status="pending",
            created_at=now_utc8()
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id  # 立即保存ID，防止后续session失效
        
        # 记录访问日志
        if request.user_id:
            try:
                user = db.query(User).filter(User.id == request.user_id).first()
                if user:
                    # 截断 access_type 以适应数据库字段 (String(20))
                    access_type = request.reason[:20] if request.reason else "remote_unlock"
                    
                    log = AccessLog(
                        user_id=request.user_id,
                        access_type=access_type,
                        status="success",
                        timestamp=now_utc8(),
                        device_id=request.device_id,
                        details=f"远程开门: {request.door_id}, 原因: {request.reason}"
                    )
                    db.add(log)
                    db.commit()
            except Exception as log_error:
                print(f"Log recording failed: {str(log_error)}")
                # 日志记录失败不影响开门任务
        
        return {
            "status": "success",
            "message": f"开门命令已发送到设备 {request.device_id}",
            "task_id": task_id,
            "device_id": request.device_id,
            "door_id": request.door_id,
            "timestamp": now_utc8()
        }
    except Exception as e:
        print(f"Remote unlock error: {str(e)}")
        # 如果任务已创建但后续失败，仍返回成功但带有警告
        if 'task_id' in locals() and task_id:
            return {
                "status": "success",
                "message": f"开门命令已发送，但发生错误: {str(e)}",
                "task_id": task_id,
                "device_id": request.device_id,
                "warning": str(e)
            }
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# ==================== NFC 任务队列管理 ====================

class NFCTaskResponse(BaseModel):
    """NFC任务响应模型"""
    id: int
    device_id: str
    command: str
    payload: Optional[str]
    status: str
    result: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]
    consumed_at: Optional[datetime]
    
    class Config:
        orm_mode = True


@router.get("/tasks", response_model=List[NFCTaskResponse])
def get_nfc_tasks(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """
    查看NFC任务队列
    
    参数:
    - device_id: 设备ID（可选）
    - status: 任务状态（可选）：pending, sent, done, canceled
    - limit: 返回数量限制
    """
    query = db.query(NFCTask)
    
    if device_id:
        query = query.filter(NFCTask.device_id == device_id)
    if status:
        query = query.filter(NFCTask.status == status)
    
    tasks = query.order_by(NFCTask.created_at.desc()).limit(limit).all()
    return tasks


@router.get("/tasks/stats")
def get_tasks_statistics(
    device_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """获取任务队列统计信息"""
    query = db.query(NFCTask)
    
    if device_id:
        query = query.filter(NFCTask.device_id == device_id)
    
    total = query.count()
    pending = query.filter(NFCTask.status == "pending").count()
    sent = query.filter(NFCTask.status == "sent").count()
    done = query.filter(NFCTask.status == "done").count()
    canceled = query.filter(NFCTask.status == "canceled").count()
    
    return {
        "total": total,
        "pending": pending,
        "sent": sent,
        "done": done,
        "canceled": canceled,
        "device_id": device_id
    }


@router.delete("/tasks/clear")
def clear_nfc_tasks(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    older_than_hours: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """
    清除NFC任务队列
    
    参数:
    - device_id: 设备ID（可选，不指定则清除所有设备）
    - status: 任务状态（可选，不指定则清除所有状态）
    - older_than_hours: 清除多少小时之前的任务（可选）
    """
    query = db.query(NFCTask)
    
    if device_id:
        query = query.filter(NFCTask.device_id == device_id)
    
    if status:
        query = query.filter(NFCTask.status == status)
    
    if older_than_hours:
        cutoff_time = now_utc8() - timedelta(hours=older_than_hours)
        query = query.filter(NFCTask.created_at < cutoff_time)
    
    # 统计将要删除的任务数量
    count = query.count()
    
    # 执行删除
    query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "status": "success",
        "message": f"已清除 {count} 个任务",
        "deleted_count": count,
        "device_id": device_id,
        "status_filter": status,
        "older_than_hours": older_than_hours
    }


@router.delete("/tasks/{task_id}")
def delete_nfc_task(task_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(require_role("admin"))):
    """删除指定的NFC任务"""
    task = db.query(NFCTask).filter(NFCTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete(task)
    db.commit()
    
    return {
        "status": "success",
        "message": f"任务 {task_id} 已删除",
        "task_id": task_id
    }


# ==================== 蓝牙配对管理 ====================

@router.post("/bluetooth/pairing/start")
def start_bluetooth_pairing(request: StartPairingRequest, db: Session = Depends(get_db)):
    """开始蓝牙配对模式
    行为：
    - 校验绑定是否存在
    - 如提供 controller_device_id，则向该设备投递 NFCTask（命令：BLE_PAIRING_START），
      负载包含 binding_id 与 timeout_seconds，期望硬件据此进入 BLE 可发现/配对模式。
    - 如未提供 controller_device_id，仅返回提示信息（与旧行为兼容）。
    """
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == request.binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")

    task_id = None
    controller_status = None
    if request.controller_device_id:
        controller = db.query(HardwareDevice).filter(HardwareDevice.device_id == request.controller_device_id).first()
        if not controller:
            raise HTTPException(status_code=404, detail=f"门禁控制器 {request.controller_device_id} 不存在")
        if controller.is_active is False:
            controller_status = "inactive"

        # 通过 NFCTask 队列向设备下发配对指令
        try:
            payload = {
                "action": "ble_pairing_start",
                "binding_id": request.binding_id,
                "timeout_seconds": request.timeout_seconds
            }
            task = NFCTask(
                device_id=request.controller_device_id,
                command="BLE_PAIRING_START",
                payload=__import__('json').dumps(payload),
                status="pending",
                created_at=now_utc8()
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id
        except Exception as e:
            # 若下发任务失败，返回可诊断信息
            raise HTTPException(status_code=500, detail=f"下发配对任务失败: {str(e)}")

    return {
        "status": "pairing_mode_activated",
        "binding_id": binding.id,
        "device_id": binding.device_id,
        "device_name": binding.device_name,
        "pairing_method": "numeric_comparison",
        "timeout_seconds": request.timeout_seconds,
        "controller_device_id": request.controller_device_id,
        "task_id": task_id,
        "controller_status": controller_status,
        "message": "如提供 controller_device_id，则已向设备下发进入配对模式任务；否则仅返回提示信息。"
    }


@router.post("/bluetooth/pairing/complete", response_model=BluetoothPairingRecordResponse)
def complete_bluetooth_pairing(request: CompletePairingRequest, db: Session = Depends(get_db)):
    """完成蓝牙配对 - 保存IRK和LTK"""
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == request.binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    # 删除旧的配对记录（如果存在）
    db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == request.binding_id
    ).delete()
    
    # 创建新的配对记录
    pairing_record = BluetoothPairingRecord(
        binding_id=request.binding_id,
        device_irk=request.device_irk.upper(),
        device_ltk=request.device_ltk.upper(),
        device_name=request.device_name,
        pairing_method="numeric_comparison",
        firmware_version=request.firmware_version,
        connection_count=1,
        last_connection=now_utc8()
    )
    
    db.add(pairing_record)
    
    # 更新binding为已配对状态
    binding.is_paired = True
    binding.device_name = request.device_name
    binding.last_connect_time = now_utc8()
    
    db.commit()
    db.refresh(pairing_record)
    
    return pairing_record


@router.get("/bluetooth/pairing/{binding_id}", response_model=BluetoothPairingRecordResponse)
def get_pairing_record(binding_id: int, db: Session = Depends(get_db)):
    """获取蓝牙配对记录"""
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).first()
    
    if not pairing_record:
        raise HTTPException(status_code=404, detail="配对记录不存在")
    
    return pairing_record


@router.get("/bluetooth/pairings/{binding_id}")
def list_pairing_records(binding_id: int, db: Session = Depends(get_db)):
    """获取绑定的所有配对记录"""
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    records = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).order_by(BluetoothPairingRecord.pairing_timestamp.desc()).all()
    
    return records


@router.post("/bluetooth/pairing/verify-irk")
def verify_device_by_irk(irk: str = Query(...), db: Session = Depends(get_db)):
    """使用IRK验证蓝牙设备身份"""
    irk_upper = irk.upper()
    
    # 查找匹配的配对记录
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.device_irk == irk_upper
    ).first()
    
    if not pairing_record:
        return {"verified": False, "message": "IRK未找到"}
    
    # 更新连接统计
    pairing_record.last_connection = now_utc8()
    pairing_record.connection_count += 1
    db.commit()
    
    binding = pairing_record.binding
    return {
        "verified": True,
        "binding_id": binding.id,
        "user_id": binding.user_id,
        "device_name": binding.device_name,
        "last_connection": pairing_record.last_connection,
        "connection_count": pairing_record.connection_count
    }


@router.delete("/bluetooth/pairing/{binding_id}")
def delete_pairing_record(binding_id: int, db: Session = Depends(get_db)):
    """删除蓝牙配对记录 - 解除配对"""
    pairing_record = db.query(BluetoothPairingRecord).filter(
        BluetoothPairingRecord.binding_id == binding_id
    ).first()
    
    if not pairing_record:
        raise HTTPException(status_code=404, detail="配对记录不存在")
    
    db.delete(pairing_record)
    
    # 更新binding状态
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == binding_id).first()
    if binding:
        binding.is_paired = False
    
    db.commit()
    
    return {"status": "success", "message": "配对记录已删除"}





"""硬件接口路由 - 增强版 (NFC/蓝牙/日志)"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import HardwareDevice, AccessLog, User, NFCCard, BluetoothBinding, UserPermission
from app.utils import check_permission_valid
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/hardware",
    tags=["hardware"],
    responses={404: {"description": "Not found"}},
)


# ==================== Pydantic 模型 ====================

class HardwareDeviceCreate(BaseModel):
    device_id: str
    device_name: str
    device_type: str  # nfc_reader, bluetooth_scanner, camera, door_lock
    location: str = None
    ip_address: str = None
    port: int = None


class HardwareDeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None


class HardwareDeviceResponse(BaseModel):
    id: int
    device_id: str
    device_name: str
    device_type: str
    location: str = None
    is_active: bool
    last_heartbeat: Optional[datetime]
    connection_status: str = None
    created_at: datetime

    class Config:
        from_attributes = True


class AccessLogResponse(BaseModel):
    id: int
    user_id: int
    access_type: str
    status: str
    timestamp: datetime
    device_id: str
    details: str = None

    class Config:
        from_attributes = True


# ======================== NFC 卡片模型 ========================

class NFCCardCreate(BaseModel):
    user_id: int
    card_number: str
    card_name: str = None
    permission_end_date: Optional[datetime] = None
    max_daily_uses: int = 0


class NFCCardUpdate(BaseModel):
    card_name: Optional[str] = None
    is_active: Optional[bool] = None
    permission_end_date: Optional[datetime] = None
    max_daily_uses: Optional[int] = None
    time_periods: Optional[str] = None


class NFCCardResponse(BaseModel):
    id: int
    user_id: int
    card_number: str
    card_name: str = None
    is_active: bool
    created_at: datetime
    permission_start_date: datetime
    permission_end_date: Optional[datetime]
    max_daily_uses: int
    daily_use_count: int

    class Config:
        from_attributes = True


# ======================== 蓝牙设备模型 ========================

class BluetoothBindingCreate(BaseModel):
    user_id: int
    device_id: str
    device_name: str = None
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
    user_id: int
    device_id: str
    device_name: str = None
    is_paired: bool
    is_active: bool
    created_at: datetime
    last_connect_time: Optional[datetime]
    permission_start_date: datetime
    permission_end_date: Optional[datetime]
    max_daily_uses: int

    class Config:
        from_attributes = True


# ==================== 硬件设备管理 ====================

@router.get("/devices", response_model=List[HardwareDeviceResponse])
def list_devices(
    device_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """获取所有硬件设备"""
    query = db.query(HardwareDevice)
    
    if device_type:
        query = query.filter(HardwareDevice.device_type == device_type)
    if is_active is not None:
        query = query.filter(HardwareDevice.is_active == is_active)
    
    devices = query.all()
    return devices


@router.post("/devices", response_model=HardwareDeviceResponse)
def create_device(device: HardwareDeviceCreate, db: Session = Depends(get_db)):
    """注册新硬件设备"""
    existing = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device.device_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="设备ID已存在")

    db_device = HardwareDevice(
        device_id=device.device_id,
        device_name=device.device_name,
        device_type=device.device_type,
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
def update_device(device_id: str, device_update: HardwareDeviceUpdate, db: Session = Depends(get_db)):
    """更新硬件设备信息"""
    db_device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    if device_update.device_name:
        db_device.device_name = device_update.device_name
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
def device_heartbeat(device_id: str, connection_status: str = "online", db: Session = Depends(get_db)):
    """设备心跳检测"""
    db_device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    
    if not db_device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    db_device.last_heartbeat = datetime.utcnow()
    db_device.is_active = True
    db_device.connection_status = connection_status
    db.commit()
    return {"status": "ok", "device_id": device_id, "timestamp": datetime.utcnow()}


@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db)):
    """删除硬件设备"""
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
def create_nfc_card(card: NFCCardCreate, db: Session = Depends(get_db)):
    """创建 NFC 卡片记录"""
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
        permission_start_date=datetime.utcnow(),
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
    db: Session = Depends(get_db)
):
    """获取 NFC 卡片列表"""
    query = db.query(NFCCard)
    
    if user_id:
        query = query.filter(NFCCard.user_id == user_id)
    if is_active is not None:
        query = query.filter(NFCCard.is_active == is_active)
    
    cards = query.all()
    return cards


@router.get("/nfc/card/{card_id}", response_model=NFCCardResponse)
def get_nfc_card(card_id: int, db: Session = Depends(get_db)):
    """获取 NFC 卡片详情"""
    card = db.query(NFCCard).filter(NFCCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return card


@router.put("/nfc/card/{card_id}", response_model=NFCCardResponse)
def update_nfc_card(card_id: int, card_update: NFCCardUpdate, db: Session = Depends(get_db)):
    """更新 NFC 卡片信息（权限、时效等）"""
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
    
    db.commit()
    db.refresh(card)
    return card


@router.delete("/nfc/card/{card_id}")
def delete_nfc_card(card_id: int, db: Session = Depends(get_db)):
    """删除 NFC 卡片"""
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
    card.last_use_date = datetime.utcnow()
    
    db.commit()
    user = card.user
    return {
        "status": "success",
        "message": f"欢迎 {user.full_name or user.username}",
        "user_id": user.id,
        "user_name": user.full_name or user.username
    }


# ==================== 蓝牙设备管理 ====================

@router.post("/bluetooth/bindings", response_model=BluetoothBindingResponse)
def create_bluetooth_binding(binding: BluetoothBindingCreate, db: Session = Depends(get_db)):
    """创建蓝牙设备绑定"""
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
        permission_start_date=datetime.utcnow(),
        permission_end_date=binding.permission_end_date,
        max_daily_uses=binding.max_daily_uses,
    )
    db.add(bt_binding)
    db.commit()
    db.refresh(bt_binding)
    return bt_binding


@router.get("/bluetooth/bindings", response_model=List[BluetoothBindingResponse])
def list_bluetooth_bindings(
    user_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """获取蓝牙设备绑定列表"""
    query = db.query(BluetoothBinding)
    
    if user_id:
        query = query.filter(BluetoothBinding.user_id == user_id)
    if is_active is not None:
        query = query.filter(BluetoothBinding.is_active == is_active)
    
    bindings = query.all()
    return bindings


@router.put("/bluetooth/binding/{binding_id}", response_model=BluetoothBindingResponse)
def update_bluetooth_binding(binding_id: int, binding_update: BluetoothBindingUpdate, db: Session = Depends(get_db)):
    """更新蓝牙设备绑定"""
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
def delete_bluetooth_binding(binding_id: int, db: Session = Depends(get_db)):
    """删除蓝牙设备绑定"""
    binding = db.query(BluetoothBinding).filter(BluetoothBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    
    db.delete(binding)
    db.commit()
    return {"message": "绑定已删除"}


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
    binding.last_use_date = datetime.utcnow()
    
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
        "timestamp": datetime.utcnow()
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
        "expires_at": datetime.utcnow() + timedelta(seconds=duration_seconds)
    }


# ==================== 访问日志管理 ====================

@router.get("/logs", response_model=List[AccessLogResponse])
def get_access_logs(
    skip: int = 0,
    limit: int = 100,
    access_type: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """获取访问日志"""
    query = db.query(AccessLog)
    
    # 按时间范围筛选
    start_date = datetime.utcnow() - timedelta(days=days)
    query = query.filter(AccessLog.timestamp >= start_date)
    
    if access_type:
        query = query.filter(AccessLog.access_type == access_type)
    if status:
        query = query.filter(AccessLog.status == status)
    
    logs = query.order_by(AccessLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs


@router.get("/logs/user/{user_id}", response_model=List[AccessLogResponse])
def get_user_logs(user_id: int, limit: int = 50, days: int = 30, db: Session = Depends(get_db)):
    """获取用户的访问日志"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(AccessLog).filter(
        AccessLog.user_id == user_id,
        AccessLog.timestamp >= start_date
    ).order_by(AccessLog.timestamp.desc()).limit(limit).all()
    return logs


@router.get("/logs/device/{device_id}", response_model=List[AccessLogResponse])
def get_device_logs(device_id: str, limit: int = 50, days: int = 30, db: Session = Depends(get_db)):
    """获取设备的访问日志"""
    device = db.query(HardwareDevice).filter(
        HardwareDevice.device_id == device_id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(AccessLog).filter(
        AccessLog.device_id == device_id,
        AccessLog.timestamp >= start_date
    ).order_by(AccessLog.timestamp.desc()).limit(limit).all()
    return logs


@router.get("/logs/statistics")
def get_access_statistics(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """获取访问统计信息"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
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
        "end_date": datetime.utcnow(),
        "total_accesses": total_accesses,
        "success_accesses": success_accesses,
        "failed_accesses": failed_accesses,
        "denied_accesses": denied_accesses,
        "success_rate": f"{(success_accesses / total_accesses * 100) if total_accesses > 0 else 0:.2f}%",
        "access_by_type": {item[0]: item[1] for item in access_types}
    }

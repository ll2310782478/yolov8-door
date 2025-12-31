"""数据库 ORM 模型"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, LargeBinary, Float, Enum, Index
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    faces = relationship("FaceData", back_populates="user", cascade="all, delete-orphan")
    access_logs = relationship("AccessLog", back_populates="user", cascade="all, delete-orphan")
    role = relationship("Role", uselist=False, back_populates="user", cascade="all, delete-orphan")
    nfc_cards = relationship("NFCCard", back_populates="user", cascade="all, delete-orphan")
    bluetooth_devices = relationship("BluetoothBinding", back_populates="user", cascade="all, delete-orphan")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")


class FaceData(Base):
    """人脸数据模型"""
    __tablename__ = "face_data"
    __table_args__ = (Index('idx_user_id_is_primary', 'user_id', 'is_primary'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String(255), nullable=False)
    face_encoding = Column(LargeBinary)  # 人脸特征向量（旧字段，兼容）
    embedding_data = Column(LargeBinary)  # 人脸特征向量（InsightFace）
    is_primary = Column(Boolean, default=False)  # 是否为主要人脸
    is_active = Column(Boolean, default=True)  # 是否启用
    access_level = Column(String(50), default="door1")  # 允许通行的门：door1, door2, all
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 人脸权限和时效
    permission_start_date = Column(DateTime, default=datetime.utcnow)
    permission_end_date = Column(DateTime, nullable=True)  # 为空表示永久有效
    time_periods = Column(Text)  # JSON 格式：{"monday": ["09:00-17:00"], ...}
    max_daily_uses = Column(Integer, default=0)  # 0 表示无限制
    daily_use_count = Column(Integer, default=0)
    last_use_date = Column(DateTime)
    
    # 关系
    user = relationship("User", back_populates="faces")


class AccessLog(Base):
    """门禁日志模型"""
    __tablename__ = "access_logs"
    __table_args__ = (Index('idx_user_id_timestamp', 'user_id', 'timestamp'),
                      Index('idx_device_id_timestamp', 'device_id', 'timestamp'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_type = Column(String(20))  # face, nfc, qrcode, bluetooth, manual
    status = Column(String(20))  # success, failed, denied
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    device_id = Column(String(50), index=True)
    details = Column(Text)  # 详细信息
    
    # 关系
    user = relationship("User", back_populates="access_logs")


class NFCCard(Base):
    """NFC 卡片模型"""
    __tablename__ = "nfc_cards"
    __table_args__ = (Index('idx_user_id_is_active', 'user_id', 'is_active'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_number = Column(String(50), unique=True, index=True, nullable=False)  # 卡号
    card_name = Column(String(100))  # 卡片名称
    door_id = Column(String(20), default="door1")  # 门编号：door1/door2
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NFC 卡片权限和时效
    permission_start_date = Column(DateTime, default=datetime.utcnow)
    permission_end_date = Column(DateTime, nullable=True)  # 为空表示永久有效
    time_periods = Column(Text)  # JSON 格式：{"monday": ["09:00-17:00"], ...}
    max_daily_uses = Column(Integer, default=0)  # 0 表示无限制
    daily_use_count = Column(Integer, default=0)
    last_use_date = Column(DateTime)
    
    # 关系
    user = relationship("User", back_populates="nfc_cards")


class BluetoothBinding(Base):
    """蓝牙设备绑定模型"""
    __tablename__ = "bluetooth_bindings"
    __table_args__ = (Index('idx_user_id_device_id', 'user_id', 'device_id'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(String(50), index=True, nullable=False)  # 蓝牙设备 ID/MAC 地址
    device_name = Column(String(100))  # 设备名称
    is_paired = Column(Boolean, default=False)  # 是否已配对
    is_active = Column(Boolean, default=True)  # 是否启用此绑定
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_connect_time = Column(DateTime)  # 最后连接时间
    
    # 蓝牙设备权限和时效
    permission_start_date = Column(DateTime, default=datetime.utcnow)
    permission_end_date = Column(DateTime, nullable=True)
    time_periods = Column(Text)  # JSON 格式
    max_daily_uses = Column(Integer, default=0)
    daily_use_count = Column(Integer, default=0)
    last_use_date = Column(DateTime)
    
    # 关系
    user = relationship("User", back_populates="bluetooth_devices")


class Visitor(Base):
    """访客模型"""
    __tablename__ = "visitors"
    __table_args__ = (Index('idx_is_checked_out_created_at', 'is_checked_out', 'created_at'),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), index=True)
    email = Column(String(100), index=True)
    company = Column(String(100))
    purpose = Column(String(255))
    check_in_time = Column(DateTime, default=datetime.utcnow)
    check_out_time = Column(DateTime)
    is_checked_out = Column(Boolean, default=False, index=True)
    qr_code_path = Column(String(255))
    qr_code_image = Column(LargeBinary)  # 存储二维码图片二进制数据
    qr_code_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 访客权限信息
    access_locations = Column(Text)  # 允许访问的区域，JSON 格式
    max_duration_hours = Column(Integer, default=8)  # 最多停留时间（小时）
    
    # 关系
    visitor_permissions = relationship("VisitorPermission", back_populates="visitor", cascade="all, delete-orphan")

    @property
    def current_permission(self):
        if self.visitor_permissions:
            # Return the latest permission (assuming higher ID is later)
            return sorted(self.visitor_permissions, key=lambda x: x.id, reverse=True)[0]
        return None

    @property
    def access_level(self):
        perm = self.current_permission
        return perm.access_level if perm else "door1"

    @property
    def max_uses(self):
        perm = self.current_permission
        return perm.max_uses if perm else 1

    @property
    def accessed_count(self):
        perm = self.current_permission
        return perm.accessed_count if perm else 0


class VisitorPermission(Base):
    """访客权限模型"""
    __tablename__ = "visitor_permissions"
    __table_args__ = (Index('idx_visitor_id_is_active', 'visitor_id', 'is_active'),)

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False, index=True)
    qr_code_token = Column(String(255), unique=True, index=True, nullable=False)  # 二维码令牌
    permission_type = Column(String(20))  # qrcode, temp_pass
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, default=datetime.utcnow) # 生效开始时间
    expires_at = Column(DateTime, nullable=False)  # 权限过期时间
    max_uses = Column(Integer, default=1) # 最大使用次数
    accessed_count = Column(Integer, default=0)  # 使用次数
    last_access_time = Column(DateTime)  # 最后访问时间
    access_level = Column(String(50), default="door1")  # 允许通行的门：door1, door2, all
    
    # 通知信息
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    sms_sent_at = Column(DateTime)
    
    # 关系
    visitor = relationship("Visitor", back_populates="visitor_permissions")


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Role(Base):
    """权限角色模型"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role_name = Column(String(50), nullable=False)  # admin, manager, user
    permissions = Column(Text)  # 权限列表 (JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="role")


class UserPermission(Base):
    """用户权限模型（细粒度权限控制）"""
    __tablename__ = "user_permissions"
    __table_args__ = (Index('idx_user_id_permission_type', 'user_id', 'permission_type'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_type = Column(String(50), nullable=False)  # face_recognition, nfc, bluetooth, qrcode
    is_enabled = Column(Boolean, default=True)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)  # 为空表示永久有效
    time_periods = Column(Text)  # JSON 格式，时间段限制
    max_daily_uses = Column(Integer, default=0)  # 0 表示无限制
    daily_use_count = Column(Integer, default=0)
    last_use_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="permissions")


class HardwareDevice(Base):
    """硬件设备模型"""
    __tablename__ = "hardware_devices"
    __table_args__ = (Index('idx_device_id_is_active', 'device_id', 'is_active'),)

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True, nullable=False)
    device_name = Column(String(100))
    device_type = Column(String(50), index=True)  # nfc_reader, bluetooth_scanner, camera, door_lock
    location = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 设备特定信息（JSON 格式存储扩展字段）
    device_config = Column(Text)  # 设备配置信息
    firmware_version = Column(String(50))  # 固件版本
    connection_status = Column(String(20))  # online, offline, error
    
    # IP 地址和端口（用于网络设备）
    ip_address = Column(String(45))
    port = Column(Integer)


class NFCTask(Base):
    """NFC 命令/任务表，用于 Web -> 设备 的即时命令交互（例如触发一次扫描）。"""
    __tablename__ = "nfc_tasks"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)  # 目标设备 id
    command = Column(String(50), nullable=False)  # e.g., 'SCAN'
    payload = Column(Text, nullable=True)  # 可选的命令负载（JSON）
    status = Column(String(20), default="pending")  # pending, sent, done, canceled
    result = Column(Text, nullable=True)  # 设备执行后的返回内容（JSON/text）
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    consumed_at = Column(DateTime)



class SystemLog(Base):
    """系统日志模型"""
    __tablename__ = "system_logs"
    __table_args__ = (Index('idx_created_at_level', 'created_at', 'log_level'),)

    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(String(20))  # info, warning, error, critical
    message = Column(Text)
    module = Column(String(100))  # 日志来源模块
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text)  # 详细信息（JSON 格式）

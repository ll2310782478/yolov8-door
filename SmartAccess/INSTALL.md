# SmartAccess v2.0 - 安装与配置指南

## 📋 系统要求

- Python 3.8+
- MySQL 5.7+ 或 MariaDB 10.3+
- Node.js 12+ （可选，用于前端构建）

## 🚀 快速开始

### 1. 克隆项目

```bash
cd yolov8-door
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置数据库

#### 方案 A：使用 SQLite（开发环境）

`.env` 文件已默认配置为 SQLite：

```env
DATABASE_URL=sqlite:///./smartaccess.db
```

#### 方案 B：使用 MySQL（推荐生产环境）

1. 创建数据库和用户：

```sql
-- 登录 MySQL
mysql -u root -p

-- 创建数据库
CREATE DATABASE smartaccess CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（可选）
CREATE USER 'smartaccess'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON smartaccess.* TO 'smartaccess'@'localhost';
FLUSH PRIVILEGES;
```

2. 更新 `.env` 文件：

```env
DATABASE_URL=mysql+pymysql://smartaccess:your_password@localhost:3306/smartaccess
```

### 5. 初始化数据库

```bash
python -c "from app.database import init_db; init_db()"
```

或直接启动应用，它会自动初始化：

```bash
python -m uvicorn app.main:app --reload
```

### 6. 访问应用

- **首页**: http://localhost:8000/
- **API 文档**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔐 默认账户

- **用户名**: `admin`
- **密码**: `admin123`

⚠️ **重要**: 生产环境中必须修改默认密码！

## ⚙️ 环境变量配置

在 `.env` 文件中配置以下选项：

### 数据库配置

```env
DATABASE_URL=mysql+pymysql://user:password@host:port/database
```

### 应用配置

```env
APP_NAME=SmartAccess
DEBUG=True                          # 开发环境设为 True，生产环境设为 False
SECRET_KEY=your-secret-key-here     # 修改为复杂密钥
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 人脸识别配置
FACE_RECOGNITION_MODEL=face_recognition
CONFIDENCE_THRESHOLD=0.6
MAX_FACE_UPLOADS_PER_USER=5

# 访客配置
VISITOR_QR_EXPIRES_HOURS=24
VISITOR_MAX_DURATION_HOURS=8

# 邮件配置（用于发送访客二维码）
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=smartaccess@example.com

# NFC 设备配置
NFC_DEVICE_TIMEOUT=30
NFC_CARD_VALIDITY_DAYS=365

# 蓝牙设备配置
BLUETOOTH_SCAN_TIMEOUT=10
BLUETOOTH_LOCK_TIMEOUT=5
```

## 📦 核心功能模块

### 1. 用户管理 (`/api/users`)

- 用户创建、编辑、删除
- 人脸照片上传和管理
- 人脸权限和时效控制
- 用户权限批量管理

**关键端点**:

```bash
# 创建用户
POST /api/users/

# 上传人脸
POST /api/users/{user_id}/faces

# 更新人脸权限
PUT /api/users/face/{face_id}

# 检查人脸权限有效性
POST /api/users/{user_id}/faces/{face_id}/check-permission

# 管理用户权限
GET /api/users/{user_id}/permissions
PUT /api/users/permission/{permission_id}
```

### 2. NFC 卡片管理 (`/api/hardware/nfc`)

- NFC 卡片与用户绑定
- 权限和时效管理
- 每日使用次数限制
- 时间段访问控制

**关键端点**:

```bash
# 创建 NFC 卡片
POST /api/hardware/nfc/cards

# 更新卡片权限
PUT /api/hardware/nfc/card/{card_id}

# NFC 门禁访问
POST /api/hardware/nfc/access
```

### 3. 蓝牙设备管理 (`/api/hardware/bluetooth`)

- 蓝牙设备配对
- 用户绑定
- 远程开锁
- 设备状态监控

**关键端点**:

```bash
# 创建蓝牙绑定
POST /api/hardware/bluetooth/bindings

# 远程开锁
POST /api/hardware/bluetooth/unlock

# 启用配对模式
POST /api/hardware/bluetooth/pairing-mode
```

### 4. 访客管理 (`/api/visitors`)

- 访客登记
- 二维码自动生成
- 邮件/短信发送
- 权限和时效管理

**关键端点**:

```bash
# 创建访客
POST /api/visitors/

# 获取二维码
GET /api/visitors/{visitor_id}/qrcode

# 发送二维码
POST /api/visitors/{visitor_id}/send-qrcode

# 验证二维码
POST /api/visitors/qrcode/verify

# 访客入场/离场
POST /api/visitors/{visitor_id}/checkin
POST /api/visitors/{visitor_id}/checkout
```

### 5. 硬件设备管理 (`/api/hardware/devices`)

- 设备注册和配置
- 心跳检测
- 多种设备类型支持
- 设备状态监控

**关键端点**:

```bash
# 注册设备
POST /api/hardware/devices

# 设备心跳
POST /api/hardware/devices/{device_id}/heartbeat

# 获取访问日志
GET /api/hardware/logs
GET /api/hardware/logs/device/{device_id}
```

## 🔧 API 使用示例

### 创建用户并上传人脸

```bash
# 1. 创建用户
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "secure_password",
    "email": "john@example.com",
    "full_name": "John Doe"
  }'

# 2. 上传人脸（user_id=1）
curl -X POST "http://localhost:8000/api/users/1/faces" \
  -F "file=@face.jpg" \
  -F "is_primary=true" \
  -F "permission_end_date=2025-12-31T23:59:59"
```

### 创建 NFC 卡片

```bash
curl -X POST "http://localhost:8000/api/hardware/nfc/cards" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "card_number": "RF1234567890",
    "card_name": "办公卡",
    "permission_end_date": "2025-12-31T23:59:59",
    "max_daily_uses": 0
  }'
```

### 创建访客并发送二维码

```bash
# 1. 创建访客
curl -X POST "http://localhost:8000/api/visitors/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "张三",
    "email": "zhangsan@example.com",
    "company": "测试公司",
    "purpose": "业务洽谈"
  }'

# 2. 发送二维码到邮箱
curl -X POST "http://localhost:8000/api/visitors/1/send-qrcode" \
  -H "Content-Type: application/json" \
  -d '{"send_via": "email"}'
```

## 📊 数据库架构

### 主要表结构

| 表名 | 说明 |
|------|------|
| users | 用户表 |
| face_data | 人脸数据表 |
| nfc_cards | NFC 卡片表 |
| bluetooth_bindings | 蓝牙绑定表 |
| user_permissions | 用户权限表 |
| visitor_permissions | 访客权限表 |
| hardware_devices | 硬件设备表 |
| access_logs | 访问日志表 |
| system_logs | 系统日志表 |

## 🛠️ 硬件集成接口预留

所有硬件接口都支持扩展，以下是预留接口：

### 人脸识别引擎接口
```python
# app/services/face_recognition.py (待实现)
def extract_face_encoding(image_path: str) -> np.array:
    """提取人脸特征向量"""
    pass

def compare_faces(encoding1: np.array, encoding2: np.array) -> float:
    """比较两张人脸的相似度"""
    pass
```

### NFC 读卡接口
```python
# app/services/nfc_reader.py (待实现)
def read_nfc_card() -> str:
    """读取 NFC 卡号"""
    pass
```

### 蓝牙通信接口
```python
# app/services/bluetooth.py (待实现)
def scan_bluetooth_devices() -> List[str]:
    """扫描附近蓝牙设备"""
    pass

def unlock_door(device_id: str) -> bool:
    """远程开锁"""
    pass
```

## 🚨 常见问题

### Q1: 如何修改管理员密码？

```bash
python
>>> from passlib.context import CryptContext
>>> from app.database import SessionLocal
>>> from app.models import User
>>> 
>>> pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
>>> db = SessionLocal()
>>> user = db.query(User).filter(User.username == "admin").first()
>>> user.password_hash = pwd_context.hash("new_password")
>>> db.commit()
>>> exit()
```

### Q2: MySQL 连接失败怎么办？

1. 确认 MySQL 服务正在运行
2. 检查 `.env` 中的 `DATABASE_URL` 配置
3. 验证数据库用户和密码
4. 检查网络连接

### Q3: 如何支持多个数据库？

修改 `.env` 中的 `DATABASE_URL`：

```env
# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/smartaccess

# SQL Server
DATABASE_URL=mssql+pyodbc://user:password@host:port/database?driver=ODBC+Driver+17+for+SQL+Server
```

## 📚 进阶配置

### 启用 HTTPS

```python
# 在 main.py 中添加
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("path/to/cert.pem", "path/to/key.pem")
```

### 配置反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name smartaccess.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📞 技术支持

- 项目地址: https://github.com/ll2310782478/yolov8-door
- 问题反馈: 在 GitHub 上提交 Issue

## 📄 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

---

**版本**: 2.0.0  
**最后更新**: 2024 年 12 月 23 日

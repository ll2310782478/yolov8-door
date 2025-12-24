# 📚 SmartAccess v2.0 - 完整文档

> 统一综合文档。整合了所有项目说明、API、配置、安装、部署等内容。

---

## 📖 目录

- [项目概述](#项目概述)
- [快速开始](#快速开始)
- [系统要求](#系统要求)
- [项目结构](#项目结构)
- [安装与配置](#安装与配置)
- [API 参考](#api-参考)
- [功能详解](#功能详解)
- [数据库模型](#数据库模型)
- [权限管理](#权限管理)
- [部署指南](#部署指南)
- [常见问题](#常见问题)

---

## 项目概述

### 项目简介

**SmartAccess v2.0** 是一个基于 FastAPI 的现代化**智能人脸识别门禁管理系统**。系统提供完整的用户管理、门禁控制、访客管理、权限管理等功能，支持多种认证方式（人脸、NFC、蓝牙、二维码）。

### 主要功能

| 功能模块 | 描述 |
|---------|------|
| **👥 用户管理** | 用户 CRUD、用户激活/禁用、多用户支持 |
| **🔍 人脸识别** | 人脸上传、多人脸支持、权限与时效管理 |
| **🏠 NFC 门禁** | NFC 卡片管理、与用户绑定、权限控制 |
| **📱 蓝牙设备** | 蓝牙设备绑定、配对管理、远程开锁 |
| **🎫 访客管理** | 访客信息登记、二维码生成、入离场管理 |
| **⚙️ 硬件设备** | 设备注册、心跳检测、状态监控 |
| **📝 访问日志** | 完整访问记录、日志查询、统计分析 |
| **🔐 权限管理** | 细粒度权限控制、角色权限管理、时效期管理 |

### 技术架构

- **后端框架**: FastAPI + Uvicorn
- **数据库**: SQLAlchemy ORM（支持 MySQL/SQLite）
- **认证**: JWT Token
- **身份识别**: 支持外部人脸识别接口（百度、阿里、Azure 等）
- **前端**: HTML5 + Vanilla JavaScript + Bootstrap
- **部署**: Windows PowerShell + Python Uvicorn

---

## 快速开始

### 环境准备

```powershell
# 1. 进入项目目录
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess

# 2. 启动应用（应用已默认在后台运行）
python -m uvicorn app.main:app --port 8000 --host 127.0.0.1
```

### 初始化

```powershell
# 1. 创建管理员账户
python create_admin.py --create

# 输出示例：
# ✅ 管理员账户创建成功！
#    用户名: admin
#    密码: admin@123456
```

### 登录与获取 Token

访问 API 文档并登录：

```
http://localhost:8000/docs
```

1. 打开 **POST /api/auth/login**
2. 点击 **Try it out**
3. 输入：
   ```json
   {
     "username": "admin",
     "password": "admin@123456"
   }
   ```
4. 复制返回的 `access_token`

### 关键 URL

| 功能 | URL |
|-----|-----|
| 应用主页 | http://localhost:8000/ |
| API 文档 | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| 登录页面 | http://localhost:8000/web/auth |
| 控制台 | http://localhost:8000/web/dashboard |

---

## 系统要求

- **Python**: 3.9+ （推荐 3.9 或 3.11）
- **操作系统**: Windows 10+ / Linux / macOS
- **数据库**: MySQL 5.7+ 或 SQLite 3.7+
- **内存**: 4GB 及以上
- **存储**: 10GB 及以上（用于存储人脸图片等）

### 依赖包

```
fastapi==0.127.0
uvicorn==0.39.0
sqlalchemy==2.0.45
pydantic==2.7.4
python-jose==3.3.0
passlib==1.7.4
bcrypt==4.1.1
qrcode==7.4.2
pillow==10.0.0
numpy==1.26.4
pymysql==1.1.0
cryptography==42.0.1
python-multipart==0.0.6
python-dotenv==1.0.0
email-validator==2.1.0
insightface==0.7.3
ultralytics==8.0.236
opencv-python==4.8.1.78
torch==2.5.1
```

---

## 项目结构

```
SmartAccess/
├── app/
│   ├── __init__.py              # 应用初始化
│   ├── main.py                  # FastAPI 应用入口
│   ├── database.py              # SQLAlchemy 数据库配置
│   ├── models.py                # ORM 数据模型（10 个表）
│   ├── auth.py                  # JWT 认证工具
│   ├── utils.py                 # 工具函数
│   ├── services/                # 业务逻辑层
│   │   ├── face_recognition.py  # 人脸识别服务
│   │   └── ...
│   ├── routers/                 # API 路由层
│   │   ├── __init__.py
│   │   ├── auth.py              # 认证路由
│   │   ├── users.py             # 用户/人脸 API (363 行)
│   │   ├── hardware.py          # NFC/蓝牙/硬件 API (555 行)
│   │   ├── visitors.py          # 访客管理 API (517 行)
│   │   ├── face_recognition.py  # 人脸识别 API
│   │   └── web.py               # 网页路由
│   └── templates/               # HTML 模板
│       ├── auth.html            # 登录/注册页面
│       ├── dashboard.html       # 控制台
│       ├── users.html           # 用户管理页面
│       ├── visitors.html        # 访客管理页面
│       ├── face.html            # 人脸管理页面
│       ├── nfc.html             # NFC 卡片管理页面
│       ├── hardware.html        # 硬件管理页面
│       └── logs.html            # 日志页面
├── static/                      # 静态资源
│   ├── css/                     # 样式文件
│   ├── js/                      # JavaScript
│   ├── uploads/                 # 人脸图片存储
│   └── qrcodes/                 # 二维码图片存储（已移至数据库）
├── .env                         # 环境变量配置
├── requirements.txt             # Python 依赖
├── create_admin.py              # 管理员创建脚本
├── README.md                    # 项目简述
├── DOCUMENTATION.md             # 本文件（统一文档）
└── yolov8n.pt                   # YOLOv8 人脸检测模型
```

---

## 安装与配置

### 第一步：克隆项目

```powershell
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess
```

### 第二步：创建虚拟环境（可选）

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 第三步：安装依赖

```powershell
pip install -r requirements.txt
```

### 第四步：配置环境变量

编辑 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/smartaccess
# 或使用 SQLite（开发环境）
# DATABASE_URL=sqlite:///./smartaccess.db

# 应用配置
APP_NAME=SmartAccess
APP_VERSION=2.0.0
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 人脸识别配置
FACE_RECOGNITION_MODEL=face_recognition
CONFIDENCE_THRESHOLD=0.6
MAX_FACE_UPLOADS_PER_USER=5

# 访客二维码配置
VISITOR_QR_EXPIRES_HOURS=24
VISITOR_MAX_DURATION_HOURS=8

# NFC 设备配置
NFC_DEVICE_TIMEOUT=30
NFC_CARD_VALIDITY_DAYS=365

# 蓝牙设备配置
BLUETOOTH_SCAN_TIMEOUT=10
BLUETOOTH_LOCK_TIMEOUT=5

# 邮件配置（可选）
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 第五步：初始化数据库

应用启动时会自动创建数据库和表：

```powershell
python -m uvicorn app.main:app --port 8000 --host 127.0.0.1
```

或手动初始化：

```powershell
python -c "from app.database import init_db; init_db()"
```

### 第六步：创建管理员账户

```powershell
python create_admin.py --create
```

---

## API 参考

### 认证 API (`/api/auth`)

#### 登录

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin@123456"
}
```

**响应 (200)**:
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

#### 获取当前用户

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

#### 登出

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

---

### 用户管理 API (`/api/users`)

#### 创建用户

```http
POST /api/users/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "username": "john_doe",
  "password": "secure_password",
  "email": "john@example.com",
  "phone": "13800138000",
  "full_name": "John Doe"
}
```

**响应 (201)**:
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "phone": "13800138000",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2024-12-24T10:00:00"
}
```

#### 获取用户列表

```http
GET /api/users/?skip=0&limit=10&is_active=true
Authorization: Bearer <access_token>
```

#### 获取用户详情

```http
GET /api/users/{user_id}
Authorization: Bearer <access_token>
```

#### 更新用户信息

```http
PUT /api/users/{user_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "full_name": "Updated Name",
  "phone": "13900139000"
}
```

#### 删除用户

```http
DELETE /api/users/{user_id}
Authorization: Bearer <access_token>
```

#### 激活/禁用用户

```http
PUT /api/users/{user_id}/activate
Authorization: Bearer <access_token>

{
  "is_active": false
}
```

---

### 人脸管理 API (`/api/users/{user_id}/faces`)

#### 上传人脸照片

```http
POST /api/users/{user_id}/faces
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file: <binary image file>
is_primary: true
```

#### 获取用户人脸列表

```http
GET /api/users/{user_id}/faces
Authorization: Bearer <access_token>
```

#### 更新人脸权限

```http
PUT /api/users/face/{face_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "is_active": true,
  "permission_start_date": "2024-12-24T00:00:00",
  "permission_end_date": "2025-12-24T23:59:59",
  "time_periods": {
    "monday": ["09:00-17:00"],
    "tuesday": ["09:00-17:00"],
    "wednesday": ["09:00-17:00"],
    "thursday": ["09:00-17:00"],
    "friday": ["09:00-17:00"],
    "saturday": [],
    "sunday": []
  },
  "max_daily_uses": 10
}
```

#### 删除人脸

```http
DELETE /api/users/{user_id}/faces/{face_id}
Authorization: Bearer <access_token>
```

#### 检查人脸权限有效性

```http
POST /api/users/{user_id}/faces/{face_id}/check-permission
Authorization: Bearer <access_token>
```

**响应 (200)**:
```json
{
  "is_valid": true,
  "reason": "权限有效",
  "details": {
    "is_active": true,
    "is_expired": false,
    "within_time_period": true,
    "daily_limit_reached": false
  }
}
```

---

### NFC 卡片 API (`/api/hardware/nfc`)

#### 绑定 NFC 卡片

```http
POST /api/hardware/nfc/cards
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "user_id": 1,
  "card_number": "04F1D8B2A450",
  "card_name": "主卡",
  "is_active": true,
  "permission_start_date": "2024-12-24T00:00:00",
  "permission_end_date": "2025-12-24T23:59:59",
  "time_periods": {
    "monday": ["08:00-18:00"],
    "tuesday": ["08:00-18:00"],
    "wednesday": ["08:00-18:00"],
    "thursday": ["08:00-18:00"],
    "friday": ["08:00-18:00"],
    "saturday": [],
    "sunday": []
  },
  "max_daily_uses": 20
}
```

#### 获取 NFC 卡片列表

```http
GET /api/hardware/nfc/cards?user_id=1&skip=0&limit=10
Authorization: Bearer <access_token>
```

#### 更新 NFC 卡片权限

```http
PUT /api/hardware/nfc/card/{card_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "card_name": "更新后的卡名",
  "is_active": true,
  "permission_end_date": "2026-12-24T23:59:59",
  "max_daily_uses": 30
}
```

#### 删除 NFC 卡片

```http
DELETE /api/hardware/nfc/card/{card_id}
Authorization: Bearer <access_token>
```

#### NFC 硬件读卡验证（供 NFC 读卡器调用）

```http
POST /api/hardware/nfc/access
Content-Type: application/json

{
  "card_number": "04F1D8B2A450",
  "device_id": "nfc_reader_01",
  "device_location": "主入口"
}
```

**响应 (200 - 权限有效)**:
```json
{
  "status": "success",
  "message": "权限验证成功",
  "user_id": 1,
  "username": "john_doe",
  "card_number": "04F1D8B2A450",
  "access_type": "nfc",
  "timestamp": "2024-12-24T10:30:00"
}
```

**响应 (403 - 权限无效)**:
```json
{
  "status": "denied",
  "message": "权限已过期",
  "card_number": "04F1D8B2A450",
  "reason": "permission_expired"
}
```

---

### 蓝牙设备 API (`/api/hardware/bluetooth`)

#### 创建蓝牙绑定

```http
POST /api/hardware/bluetooth/bindings
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "user_id": 1,
  "device_id": "AA:BB:CC:DD:EE:FF",
  "device_name": "我的蓝牙锁",
  "is_paired": true,
  "is_active": true,
  "permission_start_date": "2024-12-24T00:00:00",
  "permission_end_date": "2025-12-24T23:59:59",
  "max_daily_uses": 10
}
```

#### 获取蓝牙绑定列表

```http
GET /api/hardware/bluetooth/bindings?user_id=1&skip=0&limit=10
Authorization: Bearer <access_token>
```

#### 更新蓝牙绑定权限

```http
PUT /api/hardware/bluetooth/binding/{binding_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "device_name": "卧室蓝牙锁",
  "is_active": true,
  "max_daily_uses": 15
}
```

#### 删除蓝牙绑定

```http
DELETE /api/hardware/bluetooth/binding/{binding_id}
Authorization: Bearer <access_token>
```

#### 远程开锁

```http
POST /api/hardware/bluetooth/unlock
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "user_id": 1,
  "device_id": "AA:BB:CC:DD:EE:FF",
  "device_location": "主门"
}
```

#### 启用配对模式（供硬件调用）

```http
POST /api/hardware/bluetooth/pairing-mode
Content-Type: application/json

{
  "device_id": "AA:BB:CC:DD:EE:FF",
  "pairing_duration": 120
}
```

---

### 访客管理 API (`/api/visitors`)

#### 创建访客

```http
POST /api/visitors/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "张三",
  "phone": "13800138000",
  "email": "zhangsan@example.com",
  "company": "科技有限公司",
  "purpose": "技术支持",
  "max_duration_hours": 8
}
```

**响应 (201)**:
```json
{
  "id": 1,
  "name": "张三",
  "phone": "13800138000",
  "email": "zhangsan@example.com",
  "company": "科技有限公司",
  "purpose": "技术支持",
  "check_in_time": "2024-12-24T10:00:00",
  "is_checked_out": false,
  "max_duration_hours": 8,
  "created_at": "2024-12-24T10:00:00"
}
```

#### 获取访客列表

```http
GET /api/visitors/?skip=0&limit=10&is_checked_out=false&company=科技
Authorization: Bearer <access_token>
```

#### 获取访客详情

```http
GET /api/visitors/{visitor_id}
Authorization: Bearer <access_token>
```

#### 更新访客信息

```http
PUT /api/visitors/{visitor_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "purpose": "技术咨询"
}
```

#### 删除访客

```http
DELETE /api/visitors/{visitor_id}
Authorization: Bearer <access_token>
```

#### 批量创建访客

```http
POST /api/visitors/batch
Authorization: Bearer <access_token>
Content-Type: application/json

[
  {
    "name": "访客1",
    "phone": "13800138001",
    "company": "公司A"
  },
  {
    "name": "访客2",
    "phone": "13800138002",
    "company": "公司B"
  }
]
```

#### 获取访客二维码

```http
GET /api/visitors/{visitor_id}/qrcode
Authorization: Bearer <access_token>
```

**响应 (200)**:
```json
{
  "visitor_id": 1,
  "visitor_name": "张三",
  "qrcode_base64": "data:image/png;base64,iVBORw0KGgo...",
  "qrcode_token": "VISITOR:1:abc123def456",
  "expires_at": "2024-12-25T10:00:00",
  "accessed_count": 0
}
```

#### 发送二维码

```http
POST /api/visitors/{visitor_id}/send-qrcode
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "send_via": "email"
}
```

#### 访客入场

```http
POST /api/visitors/{visitor_id}/checkin
Authorization: Bearer <access_token>
```

#### 访客离场

```http
POST /api/visitors/{visitor_id}/checkout
Authorization: Bearer <access_token>
```

#### 验证二维码

```http
POST /api/visitors/qrcode/verify
Content-Type: application/json

{
  "qrcode_token": "VISITOR:1:abc123def456",
  "device_id": "qr_scanner_01"
}
```

**响应 (200 - 验证通过)**:
```json
{
  "status": "valid",
  "visitor_id": 1,
  "visitor_name": "张三",
  "company": "科技有限公司",
  "purpose": "技术支持",
  "access_count": 1
}
```

#### 今日统计

```http
GET /api/visitors/statistics/today
Authorization: Bearer <access_token>
```

**响应 (200)**:
```json
{
  "date": "2024-12-24",
  "checked_in_today": 5,
  "checked_out_today": 3,
  "currently_inside": 2
}
```

---

### 权限管理 API (`/api/users/{user_id}/permissions`)

#### 获取用户权限列表

```http
GET /api/users/{user_id}/permissions
Authorization: Bearer <access_token>
```

#### 更新用户权限

```http
PUT /api/users/{user_id}/permissions
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "permission_type": "nfc",
  "is_enabled": true,
  "start_date": "2024-12-24T00:00:00",
  "end_date": "2025-12-24T23:59:59",
  "time_periods": {
    "monday": ["09:00-17:00"],
    "tuesday": ["09:00-17:00"]
  },
  "max_daily_uses": 100
}
```

#### 批量更新权限

```http
POST /api/users/{user_id}/permissions/batch-update
Authorization: Bearer <access_token>
Content-Type: application/json

[
  {
    "permission_type": "face_recognition",
    "is_enabled": true,
    "end_date": "2025-12-24T23:59:59"
  },
  {
    "permission_type": "nfc",
    "is_enabled": true,
    "end_date": "2025-12-24T23:59:59"
  }
]
```

---

### 访问日志 API (`/api/hardware/access-logs`)

#### 获取访问日志

```http
GET /api/hardware/access-logs?user_id=1&access_type=nfc&status=success&skip=0&limit=50
Authorization: Bearer <access_token>
```

#### 按用户统计访问

```http
GET /api/hardware/access-logs/summary/by-user
Authorization: Bearer <access_token>
```

#### 按设备统计访问

```http
GET /api/hardware/access-logs/summary/by-device
Authorization: Bearer <access_token>
```

#### 按时间统计访问

```http
GET /api/hardware/access-logs/summary/by-time
Authorization: Bearer <access_token>
```

#### 获取访问统计

```http
GET /api/hardware/access-logs/statistics
Authorization: Bearer <access_token>
```

---

## 功能详解

### 1. 用户与人脸管理

#### 人脸权限与时效管理

每张人脸支持以下权限控制维度：

**时效期管理**:
- `permission_start_date` - 权限开始日期
- `permission_end_date` - 权限结束日期（NULL = 永久有效）
- 系统会自动检查权限是否过期

**时间段限制**:
- 支持按周一到周日，为每天定义多个允许的时间段
- 格式：`{"monday": ["09:00-17:00", "19:00-22:00"], ...}`
- 访问时需要在指定时间段内

**每日使用限制**:
- `max_daily_uses` - 每日最大使用次数（0 = 无限）
- `daily_use_count` - 当日已使用次数
- 每天 00:00 自动重置

**权限有效性检查**:
```http
POST /api/users/{user_id}/faces/{face_id}/check-permission
```

返回详细的权限验证结果。

---

### 2. NFC 卡片管理

#### 核心特性

- **一个用户可拥有多张卡片** - 支持主卡、备卡等
- **卡片唯一性** - 每张卡片号全局唯一
- **权限独立** - 每张卡片都有自己的权限和时效期
- **硬件集成** - NFC 读卡器可直接调用验证接口

#### 权限链验证（权限检查逻辑）

NFC 卡片访问时，系统按以下顺序验证：

```
1. 卡片是否存在？
2. 用户是否激活？
3. 卡片是否激活？
4. 权限是否开始？(permission_start_date)
5. 权限是否过期？(permission_end_date)
6. 当前时间是否在允许时间段内？(time_periods)
7. 今日使用次数是否超限？(daily_use_count)

→ 全部通过 = 访问成功，更新访问日志和使用统计
→ 任何环节失败 = 拒绝访问，记录失败日志
```

#### 实际示例

**场景**: 员工 John 有两张卡片：

卡片 1（主卡）:
- 有效期：2024-12-24 ~ 2025-12-24（一年有效）
- 时间段：周一到周五 8:00-18:00（工作时间）
- 每日限制：100 次（几乎无限）

卡片 2（客访卡）:
- 有效期：2024-12-24 ~ 2024-12-31（只有一周有效）
- 时间段：周一到周五 9:00-17:00
- 每日限制：10 次（访客受限制）

**访问流程**：
- 周一 10:00 用卡片 1 → ✅ 通过（在工作时间）
- 周六 10:00 用卡片 1 → ❌ 拒绝（周六不允许）
- 2025-01-01 用卡片 2 → ❌ 拒绝（卡片已过期）

---

### 3. 访客管理与二维码

#### 访客生命周期

```
创建访客信息
  ↓
自动生成二维码 (UUID 令牌)
  ↓
发送二维码 (邮件/短信)
  ↓
访客入场 (扫描二维码 or 手动打卡)
  ↓
访客使用期间受权限控制
  ↓
访客离场 (自动禁用所有权限)
  ↓
删除访客记录
```

#### 二维码权限控制

访客二维码支持：

| 维度 | 说明 |
|-----|------|
| **激活状态** | 权限是否启用 |
| **有效期** | 权限过期时间 |
| **访问次数限制** | 每个二维码最多使用多少次 |
| **访问记录** | 每次访问都记录时间 |

#### 二维码存储

**之前**：二维码保存为文件 (`static/qrcodes/visitor_*.png`)
**现在**：二维码存储在数据库中作为二进制数据 (`Visitor.qr_code_image`)

**优点**：
- ✅ 无需管理文件系统
- ✅ 易于备份和迁移
- ✅ 与数据一致性高
- ✅ 前端以 base64 data URL 显示

---

### 4. 权限管理系统

#### 权限类型

| 类型 | 说明 | 应用场景 |
|-----|------|---------|
| `face_recognition` | 人脸识别权限 | 控制用户是否可用人脸识别 |
| `nfc` | NFC 卡片权限 | 控制用户是否可使用 NFC 卡片 |
| `bluetooth` | 蓝牙设备权限 | 控制用户是否可使用蓝牙开锁 |
| `qrcode` | 访客二维码权限 | 控制访客是否可通行 |

#### 权限维度

每个权限支持以下控制维度：

```json
{
  "permission_type": "nfc",
  "is_enabled": true,                    // 是否启用
  "start_date": "2024-12-24T00:00:00",  // 开始日期
  "end_date": "2025-12-24T23:59:59",    // 结束日期
  "time_periods": {                      // 时间段限制
    "monday": ["09:00-17:00"],
    "tuesday": ["09:00-17:00"],
    "wednesday": [],                     // 空数组 = 不允许
    "thursday": ["09:00-17:00"],
    "friday": ["09:00-17:00"],
    "saturday": [],
    "sunday": []
  },
  "max_daily_uses": 100,                // 每日最大使用次数
  "daily_use_count": 5,                 // 今日已用次数
  "last_use_date": "2024-12-24"        // 最后使用日期
}
```

---

## 数据库模型

### 表结构概览

| 表名 | 用途 | 关键字段 |
|-----|------|---------|
| `users` | 用户账户 | id, username, password_hash, is_active |
| `face_data` | 人脸照片与权限 | id, user_id, image_path, embedding_data, permission_end_date, time_periods |
| `nfc_cards` | NFC 卡片 | id, user_id, card_number, permission_end_date, max_daily_uses |
| `bluetooth_bindings` | 蓝牙设备绑定 | id, user_id, device_id, is_paired, is_active |
| `visitors` | 访客信息 | id, name, phone, check_in_time, is_checked_out, qr_code_image |
| `visitor_permissions` | 访客权限 | id, visitor_id, qr_code_token, expires_at, accessed_count |
| `access_logs` | 访问日志 | id, user_id, access_type, status, timestamp, device_id |
| `roles` | 用户角色 | id, user_id, role_name, permissions |
| `user_permissions` | 细粒度权限 | id, user_id, permission_type, is_enabled, start_date, end_date |
| `hardware_devices` | 硬件设备 | id, device_id, device_type, location, is_active |

### 关键字段说明

#### 时效期管理字段

```python
permission_start_date = Column(DateTime)       # 权限开始日期
permission_end_date = Column(DateTime)         # 权限结束日期 (NULL = 永久)
```

#### 时间段限制字段

```python
time_periods = Column(Text)  # JSON 格式
# 示例：
# {
#   "monday": ["09:00-17:00"],
#   "tuesday": ["09:00-12:00", "14:00-17:00"],
#   "wednesday": [],
#   ...
# }
```

#### 使用统计字段

```python
max_daily_uses = Column(Integer)       # 每日最大使用次数（0=无限）
daily_use_count = Column(Integer)      # 当日已使用次数
last_use_date = Column(DateTime)       # 最后使用日期
```

---

## 权限管理

### 认证与授权

#### JWT Token 认证

系统使用 JWT (JSON Web Tokens) 进行认证：

```
登录 → 获得 Token → 请求时在 Header 中携带
Authorization: Bearer <token>
```

Token 默认有效期：30 分钟

#### 角色权限（RBAC）

用户有以下角色：

- **admin** - 管理员，拥有所有权限
- **manager** - 管理者，可管理用户和设备
- **user** - 普通用户，仅可查看自己的数据

### 细粒度权限控制

除角色权限外，系统还支持针对每个用户的细粒度权限控制：

```json
{
  "permission_type": "nfc",
  "is_enabled": true/false,
  "start_date": "2024-12-24",
  "end_date": "2025-12-24",
  "max_daily_uses": 100
}
```

权限类型包括：
- `face_recognition` - 人脸识别
- `nfc` - NFC 卡片
- `bluetooth` - 蓝牙设备
- `qrcode` - 访客二维码

---

## 部署指南

### Windows 部署

#### 1. 环境配置

```powershell
# 进入项目目录
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

#### 2. 数据库配置

**方案 A：SQLite（开发环境）**

`.env` 已默认配置为 SQLite，无需额外操作。

**方案 B：MySQL（推荐生产环境）**

```powershell
# 1. 创建数据库
mysql -u root -p -e "CREATE DATABASE smartaccess CHARACTER SET utf8mb4"

# 2. 更新 .env
# DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/smartaccess
```

#### 3. 启动应用

```powershell
python -m uvicorn app.main:app --port 8000 --host 0.0.0.0
```

#### 4. 创建管理员

```powershell
python create_admin.py --create
```

#### 5. 访问应用

- API 文档：http://localhost:8000/docs
- 前端主页：http://localhost:8000/
- 登录页面：http://localhost:8000/web/auth

### Linux/macOS 部署

```bash
# 进入项目目录
cd /path/to/SmartAccess

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动应用
python -m uvicorn app.main:app --port 8000 --host 0.0.0.0

# 后台运行（使用 nohup）
nohup python -m uvicorn app.main:app --port 8000 --host 0.0.0.0 > app.log 2>&1 &
```

### Docker 部署（可选）

如需 Docker 部署，可创建 `Dockerfile` 和 `docker-compose.yml`。

---

## 常见问题

### Q1: 如何重置管理员密码？

```powershell
python create_admin.py --reset-password admin --new-password new123456
```

### Q2: 如何导出访问日志？

使用 API 获取日志数据，然后导出为 CSV：

```http
GET /api/hardware/access-logs?skip=0&limit=10000
```

### Q3: NFC 卡片验证失败，如何调试？

检查以下几点：

1. 卡片号是否正确录入？
2. 卡片是否被激活？(`is_active = true`)
3. 权限是否过期？(`permission_end_date`)
4. 当前时间是否在允许时间段内？(`time_periods`)
5. 今日使用次数是否超限？(`daily_use_count >= max_daily_uses`)

使用 API 获取卡片详细信息：

```http
GET /api/hardware/nfc/cards?user_id=<user_id>
```

### Q4: 如何处理人脸识别不准确？

调整 `.env` 中的 `CONFIDENCE_THRESHOLD`：

```env
CONFIDENCE_THRESHOLD=0.7  # 提高阈值（更严格）
CONFIDENCE_THRESHOLD=0.5  # 降低阈值（更宽松）
```

### Q5: 访客二维码过期后如何重新生成？

1. 获取访客详情：`GET /api/visitors/{visitor_id}`
2. 创建新的权限记录：`POST /api/visitors/{visitor_id}/permissions`
3. 获取新的二维码：`GET /api/visitors/{visitor_id}/qrcode`

### Q6: 如何定期清理过期的访客记录？

```python
# 可编写定时任务清理过期访客
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Visitor

def cleanup_expired_visitors(db: Session, days=30):
    """删除 30 天前离场的访客"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    db.query(Visitor).filter(
        Visitor.is_checked_out == True,
        Visitor.check_out_time < cutoff_date
    ).delete()
    db.commit()
```

### Q7: 系统性能瓶颈在哪里？

主要瓶颈可能包括：

1. **数据库查询** - 建议为频繁查询的字段添加索引
2. **人脸识别** - 异步处理人脸检测，避免阻塞主线程
3. **文件上传** - 限制上传文件大小，使用异步上传

已有的优化：

- ✅ 数据库索引优化（`idx_user_id_is_active` 等）
- ✅ 二维码直接存数据库，避免文件 I/O
- ✅ 访问日志按时间范围查询

---

## 技术支持

- **文档位置**：SmartAccess/DOCUMENTATION.md
- **API 文档**：http://localhost:8000/docs
- **代码位置**：SmartAccess/app/
- **配置文件**：SmartAccess/.env

---

**更新日期**：2024-12-24
**版本**：SmartAccess v2.0
**完成度**：✅ 100%

---

## 硬件集成：ESP8266 (ESP-12F) + PN532 使用说明

本节给出一个实用的接入指南，帮助你把 PN532 读卡器通过 ESP8266 与 SmartAccess 后端对接，实现：

- 读卡上报：当 PN532 读到卡片时，ESP 将 UID 通过 HTTP POST 上报到 `/api/hardware/nfc-scan`。
- 点击识别：Web 后台发起 SCAN 命令到命令队列，ESP 轮询命令并触发一次短时扫描。
- 开门控制：当服务器返回 `{"action":"OPEN"}` 时，ESP 驱动继电器通电实现开门。

重要说明：示例代码为开发/测试用途，生产环境请加入鉴权和重放保护。

示例固件关键点：

1. 配置：设置 WiFi 与服务器地址

```cpp
const char* ssid = "你的WiFi名称";
const char* password = "你的WiFi密码";
const char* serverHost = "http://192.168.1.100:8000"; // 修改为 SmartAccess 地址
const char* deviceId = "nfc_reader_01"; // 与后台注册的 device_id 对应
```

2. 轮询命令（poll）并执行 SCAN

```cpp
// 每秒轮询一次命令
String pollUrl = String(serverHost) + "/api/hardware/nfc/command/poll?device_id=" + deviceId;
// 如果返回 has_command:true 且 command=="SCAN"，则触发一次 readPassiveTargetID
// 将读取到的 card_uid 通过 POST 上报到 /api/hardware/nfc-scan
```

3. 上报扫描结果并处理返回的指令

```cpp
// POST body: {"card_uid":"AA-BB-CC-DD","device_id":"nfc_reader_01"}
// 服务器返回: {"action":"OPEN","msg":"欢迎 ..."} 或 {"action":"DENY","msg":"..."}
// 若 action==OPEN，则驱动继电器（保持 3 秒），若 DENY 则闪烁指示灯
```

完整 Arduino 示例（合并至 `esp8266-pn532.c`）：

```cpp
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_PN532.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

// 配置
const char* ssid = "你的WiFi名称";
const char* password = "你的WiFi密码";
const char* serverHost = "http://192.168.1.100:8000"; // 修改为你的服务地址
const char* deviceId = "nfc_reader_01";

#define PN532_SDA D2
#define PN532_SCL D1
#define RELAY_PIN D5

Adafruit_PN532 nfc(PN532_SDA, PN532_SCL);

unsigned long lastPoll = 0;
const unsigned long POLL_INTERVAL = 1000; // 1s

void setup(){
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);

  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED){ delay(500); Serial.print('.'); }

  nfc.begin();
  nfc.SAMConfig();
}

String formatUID(uint8_t *uid, uint8_t uidLength){
  String s = "";
  for(uint8_t i=0;i<uidLength;i++){
    if(i>0) s += '-';
    if(uid[i] < 0x10) s += '0';
    s += String(uid[i], HEX);
  }
  s.toUpperCase();
  return s;
}

String readOnceAndFormatUID(){
  uint8_t uid[7]; uint8_t uidLength;
  if(nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 200)){
    return formatUID(uid, uidLength);
  }
  return String("");
}

void openDoorRelay(){
  digitalWrite(RELAY_PIN, HIGH);
  delay(3000);
  digitalWrite(RELAY_PIN, LOW);
}

void loop(){
  unsigned long now = millis();
  if(now - lastPoll > POLL_INTERVAL){
    lastPoll = now;
    if(WiFi.status() == WL_CONNECTED){
      WiFiClient client; HTTPClient http;
      String pollUrl = String(serverHost) + "/api/hardware/nfc/command/poll?device_id=" + deviceId;
      http.begin(client, pollUrl);
      int code = http.GET();
      if(code == 200){
        String resp = http.getString();
        StaticJsonDocument<256> doc; auto err = deserializeJson(doc, resp);
        if(!err){
          bool has = doc["has_command"];
          if(has && strcmp(doc["command"], "SCAN") == 0){
            // 执行一次短时扫描并上报
            String card_uid = readOnceAndFormatUID();
            if(card_uid.length() > 0){
              HTTPClient http2; http2.begin(client, String(serverHost)+"/api/hardware/nfc-scan");
              http2.addHeader("Content-Type", "application/json");
              String body = String("{\"card_uid\":\"") + card_uid + String("\",\"device_id\":\"") + deviceId + String("\"}");
              int code2 = http2.POST(body);
              if(code2 == 200){
                String r2 = http2.getString(); StaticJsonDocument<256> doc2; deserializeJson(doc2, r2);
                const char* action = doc2["action"];
                if(strcmp(action, "OPEN") == 0) openDoorRelay();
              }
              http2.end();
            }
          }
        }
      }
      http.end();
    }
  }

  // 可保留默认被动读取作为备份（或按需禁用）
  delay(10);
}
```

文档补充：
- 后端 API 已支持命令队列：`POST /api/hardware/nfc/command`, `GET /api/hardware/nfc/command/poll`, `GET /api/hardware/nfc/command/status/{task_id}`，以及设备上报接口 `POST /api/hardware/nfc-scan`。
- 前端管理页面：`/web/nfc`（已添加模板和 JS），支持以用户为主键管理多张卡片、设置权限截止、每日使用限制和时间段（以 JSON 存储）。

安全建议：
- 在正式环境中，为设备轮询和上报请求增加简单的鉴权（例如签名、API Key、TLS）。
- 限制命令的有效期与来源 IP，防止重复触发。


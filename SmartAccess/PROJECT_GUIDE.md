# SmartAccess 项目文件导览

## 📂 项目结构总览

```
SmartAccess/
├── 📄 README.md                    # 项目简介
├── 📄 INSTALL.md                   # 安装与配置指南
├── 📄 COMPLETION_REPORT.md         # 项目完成报告（当前文件）
├── 📄 requirements.txt             # Python 依赖
├── 📄 .env                         # 环境配置
│
├── 📁 app/                         # 主应用程序
│   ├── 📄 main.py                  # FastAPI 主应用入口
│   ├── 📄 database.py              # 数据库连接与配置
│   ├── 📄 models.py                # 数据库 ORM 模型
│   ├── 📄 utils.py                 # 工具函数（权限检查等）
│   ├── 📄 __init__.py              # 包初始化
│   │
│   ├── 📁 routers/                 # API 路由
│   │   ├── 📄 users.py             # 用户与人脸 API (13 个端点)
│   │   ├── 📄 hardware.py          # NFC、蓝牙、硬件 API (23 个端点)
│   │   ├── 📄 visitors.py          # 访客与二维码 API (15 个端点)
│   │   └── 📄 __init__.py          # 路由初始化
│   │
│   └── 📁 templates/               # 前端模板（待开发）
│       ├── layout.html             # 基础布局模板
│       ├── users.html              # 用户管理页面
│       └── visitors.html           # 访客管理页面
│
└── 📁 static/                      # 静态资源
    ├── 📁 uploads/                 # 上传的人脸图片
    └── 📁 qrcodes/                 # 生成的二维码

```

## 🔍 关键文件详解

### 1️⃣ 应用入口 (`app/main.py`)
- **作用**: FastAPI 应用主入口，数据库初始化
- **包含**:
  - 应用创建与配置
  - CORS 配置
  - 路由注册 (users, hardware, visitors)
  - 启动事件 (数据库初始化、默认用户创建)
  - 健康检查端点
  - 首页 HTML
  - 静态文件服务

### 2️⃣ 数据库配置 (`app/database.py`)
- **作用**: 数据库连接与会话管理
- **支持**: SQLite (开发) 和 MySQL (生产)
- **包含**:
  - 数据库引擎创建
  - 连接池配置 (MySQL: pool_size=10, max_overflow=20)
  - SessionLocal 工厂
  - get_db() 依赖注入函数
  - init_db() 初始化函数

### 3️⃣ ORM 模型 (`app/models.py`)
- **作用**: 定义所有数据库表结构
- **10 个主要模型**:
  - `User` - 用户基本信息
  - `FaceData` - 人脸照片与权限
  - `NFCCard` - NFC 卡片与绑定
  - `BluetoothBinding` - 蓝牙设备绑定
  - `UserPermission` - 用户细粒度权限
  - `Visitor` - 访客信息
  - `VisitorPermission` - 访客二维码权限
  - `HardwareDevice` - 硬件设备注册
  - `AccessLog` - 访问日志
  - `SystemLog` - 系统日志

### 4️⃣ 工具函数 (`app/utils.py`)
- **作用**: 可重用的工具函数
- **包含**:
  - `check_permission_valid()` - 检查权限时效
  - `check_time_period_valid()` - 验证时间段有效性
  - `check_daily_limit()` - 检查每日限制
  - `increment_daily_use_count()` - 更新使用计数
  - `save_file()` - 文件保存
  - `delete_file()` - 文件删除
  - `generate_permission_summary()` - 权限汇总

### 5️⃣ 用户与人脸 API (`app/routers/users.py`)

#### 用户管理端点
```
GET    /api/users/                  # 获取用户列表
POST   /api/users/                  # 创建用户
GET    /api/users/{user_id}         # 获取用户详情
PUT    /api/users/{user_id}         # 修改用户信息
DELETE /api/users/{user_id}         # 删除用户
```

#### 人脸管理端点
```
POST   /api/users/{user_id}/faces                      # 上传人脸
GET    /api/users/{user_id}/faces                      # 列出用户人脸
PUT    /api/users/face/{face_id}                       # 修改人脸权限
DELETE /api/users/{user_id}/faces/{face_id}           # 删除人脸
POST   /api/users/{user_id}/faces/{face_id}/check     # 检查人脸权限
```

#### 权限管理端点
```
GET    /api/users/{user_id}/permissions                # 获取用户权限
PUT    /api/users/{user_id}/permissions                # 修改权限
POST   /api/users/{user_id}/permissions/batch-update   # 批量更新
```

### 6️⃣ 硬件集成 API (`app/routers/hardware.py`)

#### NFC 卡片管理
```
POST   /api/hardware/nfc/cards           # 绑定 NFC 卡片
GET    /api/hardware/nfc/cards           # 列出卡片
PUT    /api/hardware/nfc/card/{id}       # 修改卡片权限
DELETE /api/hardware/nfc/card/{id}       # 删除卡片
POST   /api/hardware/nfc/access          # 硬件读卡验证
```

#### 蓝牙设备管理
```
POST   /api/hardware/bluetooth/bindings              # 创建绑定
GET    /api/hardware/bluetooth/bindings              # 列出绑定
PUT    /api/hardware/bluetooth/binding/{id}          # 修改绑定
DELETE /api/hardware/bluetooth/binding/{id}          # 删除绑定
POST   /api/hardware/bluetooth/unlock                # 远程开锁
POST   /api/hardware/bluetooth/pairing-mode          # 启用配对
```

#### 硬件设备
```
POST   /api/hardware/devices                         # 注册设备
GET    /api/hardware/devices                         # 列出设备
PUT    /api/hardware/devices/{id}                    # 修改设备
DELETE /api/hardware/devices/{id}                    # 删除设备
POST   /api/hardware/devices/{id}/heartbeat          # 心跳检测
```

#### 访问日志
```
GET    /api/hardware/logs                            # 获取日志
GET    /api/hardware/logs/user/{user_id}             # 用户日志
GET    /api/hardware/logs/device/{device_id}         # 设备日志
GET    /api/hardware/logs/statistics                 # 统计数据
```

### 7️⃣ 访客管理 API (`app/routers/visitors.py`)

#### 访客核心操作
```
POST   /api/visitors/                                # 创建访客
GET    /api/visitors/                                # 列出访客
GET    /api/visitors/{id}                            # 访客详情
PUT    /api/visitors/{id}                            # 修改访客
DELETE /api/visitors/{id}                            # 删除访客
POST   /api/visitors/batch                           # 批量创建
```

#### 二维码与权限
```
GET    /api/visitors/{id}/qrcode                     # 获取二维码
POST   /api/visitors/{id}/send-qrcode                # 发送二维码
GET    /api/visitors/{id}/permissions                # 列出权限
POST   /api/visitors/{id}/permissions                # 创建权限
PUT    /api/visitors/{id}/permission/{perm_id}       # 修改权限
DELETE /api/visitors/{id}/permission/{perm_id}       # 删除权限
```

#### 访客核实
```
POST   /api/visitors/qrcode/verify                   # 验证二维码
POST   /api/visitors/{id}/checkin                    # 入场
POST   /api/visitors/{id}/checkout                   # 离场
GET    /api/visitors/statistics/today                # 今日统计
```

## 🗄️ 数据库表说明

### 用户与认证
| 表 | 用途 |
|---|---|
| `users` | 用户基本信息 |
| `user_permissions` | 用户权限控制 |

### 人脸识别
| 表 | 用途 |
|---|---|
| `face_data` | 人脸照片与权限 |

### NFC 卡片
| 表 | 用途 |
|---|---|
| `nfc_cards` | NFC 卡片与绑定 |

### 蓝牙设备
| 表 | 用途 |
|---|---|
| `bluetooth_bindings` | 蓝牙设备绑定 |

### 访客管理
| 表 | 用途 |
|---|---|
| `visitors` | 访客信息 |
| `visitor_permissions` | 访客二维码权限 |

### 硬件与日志
| 表 | 用途 |
|---|---|
| `hardware_devices` | 硬件设备注册 |
| `access_logs` | 访问日志 |
| `system_logs` | 系统日志 |

## 🚀 快速开发指南

### 添加新 API 端点

1. **在对应路由文件中添加** (如 `routers/users.py`):
```python
@router.post("/api/path")
async def endpoint_name(data: PydanticModel, db: Session = Depends(get_db)):
    # 实现逻辑
    return response
```

2. **定义 Pydantic 模型** (数据验证):
```python
class MyModel(BaseModel):
    field: str
    value: int
```

3. **使用权限检查工具**:
```python
from app.utils import check_permission_valid
is_valid = check_permission_valid(permission)
```

### 添加新数据库模型

1. **在 `models.py` 中定义**:
```python
class MyModel(Base):
    __tablename__ = "my_models"
    id = Column(Integer, primary_key=True)
    # ... 其他字段
```

2. **在 `main.py` 中初始化**:
```python
from app.models import MyModel  # 自动创建表
```

### 修改权限验证逻辑

1. **编辑 `utils.py` 中的验证函数**
2. **在相关 API 端点调用**
3. **测试权限链: 激活状态 → 时效日期 → 时间段 → 每日限制**

## 📝 配置文件说明

### `.env` 关键配置

```ini
# 数据库
DATABASE_URL=mysql+pymysql://user:pass@localhost/smartaccess

# 应用
APP_NAME=SmartAccess
SECRET_KEY=your-secret-key
DEBUG=True

# 人脸识别
CONFIDENCE_THRESHOLD=0.5
MAX_FACE_UPLOADS_PER_USER=5

# 访客
VISITOR_QR_EXPIRES_HOURS=24
VISITOR_MAX_DURATION_HOURS=8

# 邮件
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-password

# 硬件
NFC_TIMEOUT_SECONDS=5
BLUETOOTH_SCAN_TIMEOUT_SECONDS=10
```

## 🔗 API 文档访问

应用启动后，访问以下地址：

- **Swagger UI**: `http://localhost:8000/docs` ✨
- **ReDoc**: `http://localhost:8000/redoc`
- **首页**: `http://localhost:8000/`

所有 API 端点都在 Swagger 文档中完整显示，可直接测试！

## 🎯 下一步计划

### 待开发项目

1. **前端页面** (HTML/CSS/JS)
   - 人脸管理界面
   - NFC 卡片界面
   - 蓝牙设备界面
   - 访客权限界面
   - 权限管理界面

2. **硬件服务** (Python)
   - 人脸识别集成
   - NFC 读卡器驱动
   - 蓝牙控制
   - 邮件/短信发送

3. **高级功能**
   - 统计仪表板
   - 考勤报告
   - 数据导出
   - 审计日志

---

**📞 如需帮助，请参考各文件中的详细注释和 API 文档！**


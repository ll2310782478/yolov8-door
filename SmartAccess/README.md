# SmartAccess v2.0 - 智能人脸识别门禁系统

🚀 **[完整文档请查看 DOCUMENTATION.md](DOCUMENTATION.md)** ← 详细的安装、API、功能说明都在这里

## 📋 项目介绍

SmartAccess v2.0 是一个基于 FastAPI 的现代化**智能人脸识别门禁管理系统**。系统采用**基于角色的权限控制（RBAC）**，支持多种认证方式（人脸、NFC、蓝牙、二维码），提供完整的用户管理、权限控制、访客管理等功能。

## ✨ 主要功能

### 1. 👥 用户管理
- 用户注册和账户管理
- 用户信息编辑和删除
- 用户状态管理（激活/禁用）
- 用户搜索和筛选

### 2. 🔍 人脸识别
- 人脸照片上传和存储
- 通过**外部接口**进行人脸识别（不直接实现算法）
- 支持多种识别服务：百度云、阿里云、腾讯云、Azure、本地部署等
- 多人脸支持（主人脸和备用人脸）
- 📖 详见: [FACE_RECOGNITION_INTEGRATION.md](FACE_RECOGNITION_INTEGRATION.md)

### 3. 🚪 门禁控制
- **人脸识别门禁** - 使用人脸识别进行访问控制
- **NFC 门禁** - 支持 NFC 卡片门禁
- **蓝牙门禁** - 支持蓝牙设备门禁
- **二维码门禁** - 访客二维码快速通行

### 4. 📝 访问日志
- 完整的访问记录日志
- 按用户/设备/时间筛选
- 访问状态分析（成功/失败/拒绝）
- 详细的访问信息记录

### 5. 👤 访客管理
- 访客信息登记
- 自动生成访客二维码
- 访客入场/离场管理
- 访客通行证有效期管理
- 批量导入访客

### 6. ⚙️ 硬件设备管理
- 硬件设备注册和配置
- 设备心跳检测
- 多设备支持（NFC读卡器、蓝牙模块、摄像头等）
- 设备状态监控

### 7. 🔐 权限管理
- 角色权限分配（管理员/管理者/普通用户）
- 细粒度权限控制
- 用户角色管理

## 🏗️ 项目结构

```
SmartAccess/
├── app/
│   ├── __init__.py              # 应用初始化
│   ├── main.py                  # 启动入口
│   ├── models.py                # SQLAlchemy ORM 模型
│   ├── database.py              # 数据库连接配置
│   ├── routers/                 # 路由模块
│   │   ├── __init__.py
│   │   ├── users.py             # 用户/人脸/权限管理 API
│   │   ├── hardware.py          # 硬件/NFC/蓝牙/日志 API
│   │   └── visitors.py          # 访客与二维码管理 API
│   └── templates/               # 前端 HTML 页面
│       ├── layout.html          # 首页
│       ├── users.html           # 用户管理页面
│       └── visitors.html        # 访客管理页面
├── static/                      # 静态资源
│   ├── uploads/                 # 人脸图片存储
│   └── qrcodes/                 # 二维码图片存储
├── requirements.txt             # 依赖包列表
├── .env                         # 环境配置文件
└── README.md                    # 本文件
```

## 🚀 快速开始

> ⚠️ **详细的安装、配置、API 使用说明请参考 [DOCUMENTATION.md](DOCUMENTATION.md)**

### 快速启动（3 步）

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建管理员账户
python create_admin.py --create

# 3. 启动应用
python -m uvicorn app.main:app --port 8000 --host 127.0.0.1
```

访问应用：

```
主页:       http://localhost:8000/
API 文档:   http://localhost:8000/docs
登录页面:   http://localhost:8000/web/auth
```

## 📡 API 端点概览

| 模块 | 路由前缀 | 功能 | 端点数 |
|-----|---------|------|--------|
| 认证 | `/api/auth` | 用户登录、登出、获取信息 | 3 |
| 用户 | `/api/users` | 用户管理、人脸管理、权限检查 | 13 |
| NFC | `/api/hardware/nfc` | NFC 卡片管理、访问验证 | 8 |
| 蓝牙 | `/api/hardware/bluetooth` | 蓝牙设备管理、远程开锁 | 9 |
| 硬件 | `/api/hardware` | 设备管理、日志记录、统计 | 10 |
| 访客 | `/api/visitors` | 访客管理、二维码、入离场 | 15 |

**详见 [DOCUMENTATION.md - API 参考](DOCUMENTATION.md#api-参考)** 中的完整 API 文档

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/` | 创建访客 |
| GET | `/` | 获取访客列表 |
| GET | `/{visitor_id}` | 获取访客信息 |
| GET | `/{visitor_id}/qrcode` | 获取访客二维码 |
| POST | `/{visitor_id}/checkin` | 访客入场 |
| POST | `/{visitor_id}/checkout` | 访客离场 |
| POST | `/qrcode/verify` | 验证二维码 |
| POST | `/batch` | 批量创建访客 |

## 🗄️ 数据库模型

### User（用户表）
```python
- id: 主键
- username: 用户名 (唯一)
- password_hash: 密码哈希
- email: 邮箱 (唯一)
- phone: 电话
- full_name: 全名
- is_active: 是否激活
- created_at: 创建时间
- updated_at: 更新时间
```

### FaceData（人脸数据表）
```python
- id: 主键
- user_id: 用户 ID (外键)
- image_path: 图片路径
- face_encoding: 人脸编码
- is_primary: 是否主要人脸
- created_at: 创建时间
```

### AccessLog（访问日志表）
```python
- id: 主键
- user_id: 用户 ID (外键)
- access_type: 访问类型 (face/nfc/qrcode/manual)
- status: 访问状态 (success/failed/denied)
- timestamp: 时间戳
- device_id: 设备 ID
- details: 详细信息
```

### Visitor（访客表）
```python
- id: 主键
- name: 访客名称
- phone: 电话
- email: 邮箱
- company: 公司
- purpose: 访问目的
- check_in_time: 入场时间
- check_out_time: 离场时间
- is_checked_out: 是否已离场
- qr_code_path: 二维码路径
- qr_code_expires_at: 二维码过期时间
```

### Role（权限表）
```python
- id: 主键
- user_id: 用户 ID (外键)
- role_name: 角色名称 (admin/manager/user)
- permissions: 权限列表 (JSON)
- created_at: 创建时间
```

### HardwareDevice（硬件设备表）
```python
- id: 主键
- device_id: 设备 ID (唯一)
- device_name: 设备名称
- device_type: 设备类型 (nfc_reader/bluetooth/camera)
- location: 设备位置
- is_active: 是否激活
- last_heartbeat: 最后心跳时间
- created_at: 创建时间
- updated_at: 更新时间
```

## 🔐 默认账户

系统初始化时会自动创建一个默认管理员账户：

- **用户名**: `admin`
- **密码**: `admin123`
- **角色**: 管理员

**⚠️ 重要**: 请在生产环境中修改默认密码！

## 🔧 配置说明

### 数据库配置

支持多种数据库：

**SQLite（默认）**
```env
DATABASE_URL=sqlite:///./smartaccess.db
```

**MySQL**
```env
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/smartaccess
```

**PostgreSQL**
```env
DATABASE_URL=postgresql://username:password@localhost:5432/smartaccess
```

### 人脸识别配置

```env
# 人脸识别置信度阈值 (0-1)
CONFIDENCE_THRESHOLD=0.6

# 使用的人脸识别模型
FACE_RECOGNITION_MODEL=face_recognition
```

### 访客配置

```env
# 访客二维码有效期（小时）
VISITOR_QR_EXPIRES_HOURS=24
```

## 📦 依赖包说明

| 包名 | 版本 | 用途 |
|-----|------|------|
| fastapi | 0.104.1 | Web 框架 |
| uvicorn | 0.24.0 | ASGI 服务器 |
| sqlalchemy | 2.0.23 | ORM 框架 |
| python-dotenv | 1.0.0 | 环境变量管理 |
| pydantic | 2.5.0 | 数据验证 |
| python-multipart | 0.0.6 | 文件上传支持 |
| pillow | 10.1.0 | 图像处理 |
| qrcode | 7.4.2 | 二维码生成 |
| opencv-python | 4.8.1.78 | 计算机视觉 |
| numpy | 1.24.3 | 数值计算 |

## 🚦 项目状态

- ✅ 核心框架搭建
- ✅ 用户管理模块
- ✅ 人脸数据管理
- ✅ 访问日志记录
- ✅ 访客管理和二维码生成
- ✅ 硬件设备管理
- ✅ 基础前端页面
- 🔲 人脸识别算法集成
- 🔲 人脸对比匹配功能
- 🔲 NFC 硬件对接
- 🔲 蓝牙硬件对接
- 🔲 高级前端界面

## 🔮 未来计划

1. **人脸识别集成**
   - 集成第三方人脸识别 API（云服务或本地部署）
   - 支持多种识别引擎（百度、腾讯、Azure 等）
   - 详细的集成方案见: [FACE_RECOGNITION_INTEGRATION.md](FACE_RECOGNITION_INTEGRATION.md)

2. **硬件集成**
   - NFC 读卡器驱动
   - 蓝牙模块适配
   - 人脸识别设备集成

3. **增强功能**
   - 人脸识别报警
   - 陌生人检测告警
   - 访问权限时间段限制
   - 考勤统计分析

4. **前端优化**
   - Vue.js 全面重构
   - 实时数据更新
   - 统计图表展示
   - 移动端适配

5. **安全加强**
   - JWT 认证
   - 数据加密存储
   - 操作日志审计
   - SSL/TLS 支持

## 📝 使用示例

### 创建用户
```bash
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "secure_password",
    "email": "john@example.com",
    "phone": "13800000000",
    "full_name": "John Doe"
  }'
```

### 上传人脸照片
```bash
curl -X POST "http://localhost:8000/api/users/1/faces" \
  -F "file=@path/to/face_image.jpg"
```

### 创建访客
```bash
curl -X POST "http://localhost:8000/api/visitors/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "张三",
    "phone": "13800000001",
    "email": "zhangsan@example.com",
    "company": "测试公司",
    "purpose": "业务洽谈"
  }'
```

### 验证访客二维码
```bash
curl -X POST "http://localhost:8000/api/visitors/qrcode/verify" \
  -H "Content-Type: application/json" \
  -d '{"qrcode_data": "VISITOR:1"}'
```

## 🛠️ 开发指南

### 添加新的 API 端点

1. 在对应的 `routers/*.py` 文件中定义路由
2. 使用 Pydantic 模型进行数据验证
3. 使用依赖注入获取数据库会话
4. 在 `main.py` 中注册路由

### 添加新的数据库模型

1. 在 `models.py` 中定义新的模型类
2. 模型继承 `Base` 类
3. 定义表名和列定义
4. 创建数据库迁移（可选）

### 前端开发

- 使用原生 HTML/CSS/JavaScript
- 通过 Fetch API 调用后端接口
- 支持模态框、表单验证等交互

## 📞 联系方式

- 项目主页: [GitHub](https://github.com/ll2310782478/yolov8-door)
- 问题反馈: [Issues](https://github.com/ll2310782478/yolov8-door/issues)

## 📄 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## ⚠️ 免责声明

本项目仅供学习和研究使用。使用者需自行承担使用本项目代码的所有后果。

---

**最后更新**: 2024 年 12 月 23 日

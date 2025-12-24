# 🔐 SmartAccess v2.0 - 快速使用指南

## ✨ 概述

SmartAccess v2.0 是一个智能人脸识别门禁系统，支持多种认证方式（人脸、NFC、蓝牙、二维码）。系统采用**基于角色的权限控制（RBAC）**，需要用户登录后才能使用管理功能。

---

## 📋 目录

1. [初始化步骤](#初始化步骤)
2. [管理员登录](#管理员登录)
3. [系统功能](#系统功能)
4. [API 使用](#api-使用)
5. [常见问题](#常见问题)

---

## 初始化步骤

### 步骤 1️⃣：启动应用

应用已在后台运行。访问主页查看：

```
http://localhost:8000/
```

### 步骤 2️⃣：创建管理员账户

打开 PowerShell 并运行：

```powershell
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess
python create_admin.py --create
```

**输出示例：**
```
✅ 管理员账户创建成功！
   用户名: admin
   密码: admin@123456
   邮箱: admin@smartaccess.com
```

### 步骤 3️⃣：管理员登录

打开浏览器访问：

```
http://localhost:8000/docs
```

在 Swagger UI 中找到 **Auth** 分类，选择 **POST /api/auth/login**：

1. 点击 **Try it out**
2. 输入以下内容：
   ```json
   {
     "username": "admin",
     "password": "admin@123456"
   }
   ```
3. 点击 **Execute**

**成功响应（200）：**
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

✅ **复制 `access_token` 的值，后续 API 调用需要使用**

---

## 管理员登录

### 登录端点

```
POST /api/auth/login
```

**请求体：**
```json
{
  "username": "admin",
  "password": "admin@123456"
}
```

**响应：**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "JWT_TOKEN_HERE",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### 令牌有效期

- **默认有效期：30 分钟**
- 过期后需要重新登录获取新令牌

### 获取当前用户信息

```
GET /api/auth/me
```

**请求头：**
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

---

## 系统功能

### 1. 👥 用户管理

| 功能 | 端点 | 说明 |
|------|------|------|
| 创建用户 | POST `/api/users` | 创建新用户账户 |
| 获取所有用户 | GET `/api/users` | 列出所有用户 |
| 获取用户详情 | GET `/api/users/{id}` | 查看用户信息 |
| 更新用户 | PUT `/api/users/{id}` | 修改用户信息 |
| 删除用户 | DELETE `/api/users/{id}` | 删除用户账户 |

### 2. 🔍 人脸识别

| 功能 | 端点 | 说明 |
|------|------|------|
| 上传人脸 | POST `/api/users/{id}/faces` | 注册用户人脸 |
| 获取人脸列表 | GET `/api/users/{id}/faces` | 查看用户已注册的人脸 |
| 实时识别 | POST `/api/users/{id}/faces/recognize` | 识别图像中的人脸 |
| 检查权限 | POST `/api/users/{id}/faces/{face_id}/check-permission` | 检查人脸是否有权限 |

### 3. 🏷️ NFC 卡片

| 功能 | 端点 | 说明 |
|------|------|------|
| 绑定卡片 | POST `/api/users/{id}/nfc-cards` | 绑定 NFC 卡片 |
| 获取卡片列表 | GET `/api/users/{id}/nfc-cards` | 查看用户的卡片 |
| 删除卡片 | DELETE `/api/nfc-cards/{id}` | 删除已绑定的卡片 |

### 4. 🔵 蓝牙设备

| 功能 | 端点 | 说明 |
|------|------|------|
| 配对设备 | POST `/api/users/{id}/bluetooth-devices` | 配对蓝牙设备 |
| 获取设备列表 | GET `/api/users/{id}/bluetooth-devices` | 查看已配对设备 |
| 删除设备 | DELETE `/api/bluetooth-devices/{id}` | 移除已配对设备 |

### 5. 👤 访客管理

| 功能 | 端点 | 说明 |
|------|------|------|
| 添加访客 | POST `/api/visitors` | 新增访客记录 |
| 获取访客列表 | GET `/api/visitors` | 查看所有访客 |
| 生成二维码 | POST `/api/visitors/{id}/qrcode` | 为访客生成权限二维码 |

### 6. 🏢 硬件设备

| 功能 | 端点 | 说明 |
|------|------|------|
| 注册设备 | POST `/api/hardware/devices` | 注册门禁设备 |
| 获取设备列表 | GET `/api/hardware/devices` | 查看所有设备 |
| 更新设备 | PUT `/api/hardware/devices/{id}` | 修改设备配置 |

---

## API 使用

### 在 Swagger UI 中使用令牌

1. 获得 `access_token` 后
2. 在 Swagger UI 顶部找到 **Authorize** 按钮
3. 点击 Authorize，输入：
   ```
   Bearer YOUR_ACCESS_TOKEN
   ```
4. 点击 **Authorize** 确认
5. 现在可以直接在 Swagger UI 中调用受保护的 API

### 使用 curl 命令

```bash
# 登录获取令牌
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin@123456"}'

# 使用令牌调用 API
curl -X GET "http://localhost:8000/api/users" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 使用 PowerShell

```powershell
# 登录
$loginResponse = Invoke-WebRequest -Uri "http://localhost:8000/api/auth/login" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"username":"admin","password":"admin@123456"}' `
  -UseBasicParsing

$token = ($loginResponse.Content | ConvertFrom-Json).data.access_token

# 使用令牌
Invoke-WebRequest -Uri "http://localhost:8000/api/users" `
  -Method Get `
  -Headers @{"Authorization"="Bearer $token"} `
  -UseBasicParsing
```

---

## 常见问题

### Q1: 忘记管理员密码

**A:** 重新创建管理员账户：

```powershell
# 可选：删除旧账户
# DELETE FROM users WHERE username = 'admin';

# 创建新账户（可自定义密码）
python create_admin.py --create --username admin --password NewPassword123
```

### Q2: 令牌过期怎么办？

**A:** 重新登录获取新令牌，或刷新页面重新授权

### Q3: 创建普通用户

使用 POST `/api/users` 端点：

```json
{
  "username": "user1",
  "password": "password123",
  "email": "user1@example.com",
  "phone": "13800138000",
  "full_name": "用户一"
}
```

### Q4: 如何删除错误创建的用户？

```bash
DELETE /api/users/{user_id}
```

需要提供有效的 Authorization 令牌

### Q5: 支持多管理员吗？

**A:** 是的！可以创建多个 admin 角色的用户：

```powershell
python create_admin.py --create --username admin2 --password Admin2@123456
```

---

## 🔒 安全建议

1. **修改默认密码**
   ```
   首次登录后立即修改密码
   ```

2. **保护访问令牌**
   ```
   - 不要在公开环境中暴露令牌
   - 不要将令牌保存在客户端代码中
   - 令牌仅在 30 分钟内有效
   ```

3. **使用 HTTPS**
   ```
   生产环境必须使用 HTTPS
   避免在 HTTP 上传输敏感信息
   ```

4. **定期更新**
   ```
   修改 .env 中的 SECRET_KEY
   ```

---

## 📖 更多帮助

- **API 文档**: http://localhost:8000/docs
- **ReDoc 文档**: http://localhost:8000/redoc
- **主页**: http://localhost:8000/
- **详细指南**: 查看 `ADMIN_GUIDE.md`

---

**版本**: SmartAccess v2.0  
**最后更新**: 2025-12-23

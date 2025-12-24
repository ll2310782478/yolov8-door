# SmartAccess v2.0 - 使用指南

## 🚀 快速开始

### 1. 创建管理员账户

应用启动后，需要创建管理员账户来登录系统。

在项目根目录运行以下命令：

```powershell
# 创建默认管理员账户（用户名: admin, 密码: admin@123456）
python create_admin.py --create

# 或者自定义账户信息
python create_admin.py --create --username myAdmin --password MyPassword@123 --email admin@mycompany.com
```

**输出示例：**
```
✅ 管理员账户创建成功！
   用户名: admin
   密码: admin@123456
   邮箱: admin@smartaccess.com

⚠️  安全提示:
   1. 请妥善保管管理员密码
   2. 首次登录后请修改默认密码
   3. 生产环境应使用强密码
```

### 2. 管理员登录

#### 方式一：通过 API 文档界面（推荐）

1. 打开浏览器访问：http://localhost:8000/docs
2. 找到 **Auth** 分类下的 **POST /api/auth/login** 端点
3. 点击 **Try it out**，输入用户名和密码
4. 点击 **Execute** 执行

#### 方式二：使用 curl 命令

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin@123456"
  }'
```

**返回示例（成功）：**
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

### 3. 使用令牌访问受保护的 API

获得访问令牌后，在请求头中添加令牌：

```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 📖 API 端点

### 认证端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 管理员登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 用户管理端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users` | 获取所有用户 |
| GET | `/api/users/{user_id}` | 获取用户详情 |
| POST | `/api/users` | 创建新用户 |
| PUT | `/api/users/{user_id}` | 更新用户信息 |
| DELETE | `/api/users/{user_id}` | 删除用户 |

### 人脸识别端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/users/{user_id}/faces` | 上传人脸数据 |
| GET | `/api/users/{user_id}/faces` | 获取用户的人脸数据 |
| POST | `/api/users/{user_id}/faces/recognize` | 实时人脸识别 |
| POST | `/api/users/{user_id}/faces/{face_id}/check-permission` | 检查人脸权限 |

### 其他端点

- `/api/hardware/*` - 硬件设备管理
- `/api/visitors/*` - 访客管理
- `/api/face-recognition/*` - 人脸识别服务

## 🔐 安全建议

1. **修改默认密码**
   - 首次登录后立即修改默认密码
   
2. **保护访问令牌**
   - 不要在公开的环境中暴露令牌
   - 令牌有效期为 30 分钟（默认）

3. **使用 HTTPS**
   - 生产环境必须使用 HTTPS
   - 避免在 HTTP 上传输敏感信息

4. **定期更新密钥**
   - 修改 `.env` 文件中的 `SECRET_KEY`
   - 重新生成所有令牌

## 📊 用户查询

查看系统中的所有用户：

```powershell
python create_admin.py --list
```

**输出示例：**
```
📋 用户列表:
------------------------------------------------------------
ID: 1 | 用户名: admin               | 角色: admin        | ✅ 激活
ID: 2 | 用户名: user1               | 角色: user         | ✅ 激活
------------------------------------------------------------
```

## 🛠️ 常见问题

### Q: 忘记管理员密码怎么办？

**A:** 直接在数据库中删除该用户，重新创建管理员账户：

```powershell
# 在 MySQL 中执行
DELETE FROM users WHERE username = 'admin';

# 然后重新创建
python create_admin.py --create
```

### Q: 如何创建普通用户？

**A:** 有两种方式：

1. **通过 API**：POST `/api/users`
2. **通过数据库**：直接插入 `users` 表

### Q: 令牌过期了怎么办？

**A:** 重新登录获取新令牌：

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin@123456"}'
```

### Q: 支持多用户系统吗？

**A:** 是的，系统支持：
- 多个管理员账户（role: admin）
- 多个普通用户账户（role: user）
- 基于角色的权限控制（RBAC）

## 📝 注意事项

- 本版本使用明文密码存储（开发环境），**生产环境应改为 bcrypt**
- 默认数据库为 MySQL，可修改 `.env` 文件改用 SQLite
- API 文档可在 http://localhost:8000/docs 查看
- 有任何问题请查看应用日志

---

**版本:** SmartAccess v2.0  
**最后更新:** 2025-12-23

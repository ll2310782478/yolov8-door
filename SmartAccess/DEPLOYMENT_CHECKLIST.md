# SmartAccess v2.0 - 部署检查清单

## ✅ 部署前检查

### 环境准备
- [ ] Python 3.8 或更高版本已安装
- [ ] pip 已配置（`pip --version` 确认）
- [ ] Git 已安装（可选）
- [ ] 文本编辑器已准备（VS Code 推荐）

### 依赖检查
- [ ] 已运行 `pip install -r requirements.txt`
- [ ] 所有依赖已成功安装
- [ ] 未有任何 import 错误

### 数据库准备

#### 如果使用 SQLite（开发）
- [ ] `.env` 中配置: `DATABASE_URL=sqlite:///./smartaccess.db`
- [ ] 确保项目目录可写

#### 如果使用 MySQL（生产）
- [ ] MySQL Server 已安装且运行
- [ ] 已创建数据库: `CREATE DATABASE smartaccess;`
- [ ] 已创建用户: `CREATE USER 'smartaccess'@'localhost' IDENTIFIED BY 'password';`
- [ ] 已授予权限: `GRANT ALL ON smartaccess.* TO 'smartaccess'@'localhost';`
- [ ] `.env` 中配置正确的 `DATABASE_URL`

### 配置检查
- [ ] `.env` 文件已编辑（基于自己的环境）
- [ ] `SECRET_KEY` 已修改为强密码
- [ ] 数据库 URL 已验证无误
- [ ] 邮件配置已完成（可选）
- [ ] 短信配置已完成（可选）

### 文件权限
- [ ] `static/uploads/` 目录存在且可写
- [ ] `static/qrcodes/` 目录存在且可写
- [ ] `smartaccess.db`（如使用 SQLite）文件可读写

---

## 🚀 启动步骤

### 第一次启动
```bash
# 1. 进入项目目录
cd u:\BYSJ\yolov-door\yolov8-door\SmartAccess

# 2. 激活虚拟环境（如果有）
# python -m venv venv
# venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动应用
python -m uvicorn app.main:app --reload
```

- [ ] 应用启动无错误
- [ ] 看到 "Uvicorn running on http://127.0.0.1:8000"
- [ ] 可以访问 http://localhost:8000/

### 检查数据库初始化
- [ ] 访问 http://localhost:8000/ 看到首页
- [ ] 查看数据库中自动创建的表
- [ ] 确认默认 admin 用户已创建

### 验证 API 可用
- [ ] 访问 http://localhost:8000/docs 看到 Swagger 文档
- [ ] 尝试调用任一 API 端点
- [ ] 确认返回正确的 JSON 响应

---

## 🔐 安全检查清单

### 在部署到生产之前

#### 密钥与认证
- [ ] `SECRET_KEY` 已更改为强密码
- [ ] 默认 admin 密码已修改（登录后立即修改）
- [ ] 没有在代码中硬编码任何密钥

#### 数据库安全
- [ ] MySQL 用户有最小权限
- [ ] 数据库密码已加密存储
- [ ] 不使用 `root` 用户运行应用
- [ ] 已启用 MySQL SSL 连接（可选）

#### 应用安全
- [ ] `DEBUG=False` 在生产环境
- [ ] CORS 配置已根据需要限制
- [ ] 已设置适当的 HTTPS（可选）

#### 访问控制
- [ ] 防火墙已配置
- [ ] 只有授权 IP 可访问（可选）
- [ ] API 限流已配置（可选）

---

## 📊 初始化验证

### 数据库表检查

```bash
# 使用 MySQL 客户端
mysql -u smartaccess -p smartaccess
```

运行以下命令验证表已创建：
```sql
-- [ ] 查看所有表
SHOW TABLES;

-- [ ] 应该看到以下表:
-- users
-- face_data
-- nfc_cards
-- bluetooth_bindings
-- user_permissions
-- visitors
-- visitor_permissions
-- hardware_devices
-- access_logs
-- system_logs

-- [ ] 检查默认用户
SELECT * FROM users WHERE username='admin';
```

### API 端点验证

使用 Swagger UI (http://localhost:8000/docs) 或 curl：

```bash
# [ ] 获取用户列表
curl http://localhost:8000/api/users/

# [ ] 获取权限列表
curl http://localhost:8000/api/hardware/logs

# [ ] 获取访客列表
curl http://localhost:8000/api/visitors/
```

---

## 📈 性能优化检查

### 数据库优化
- [ ] 已启用所有索引
- [ ] 查询性能已测试
- [ ] 连接池大小已设置（MySQL: pool_size=10）
- [ ] 查询超时已配置

### 应用优化
- [ ] 使用生产级别的 WSGI 服务器（Gunicorn）
- [ ] 已设置适当的 worker 数（推荐: CPU 核心数 * 2 + 1）
- [ ] 已配置日志轮转
- [ ] 已启用内存监控（可选）

### API 优化
- [ ] 已实现 API 限流
- [ ] 已实现缓存策略（可选）
- [ ] 已优化数据库查询
- [ ] 已配置 gzip 压缩

---

## 🚨 故障排除检查

### 应用启动失败
- [ ] 检查 Python 版本: `python --version`
- [ ] 检查依赖: `pip list | grep -i fastapi`
- [ ] 检查 `.env` 文件存在
- [ ] 检查数据库连接: `DATABASE_URL` 是否正确
- [ ] 查看完整错误日志

### 数据库连接失败
- [ ] MySQL 服务是否运行？
- [ ] 数据库用户是否存在？
- [ ] 密码是否正确？
- [ ] 数据库名称是否正确？
- [ ] 防火墙是否阻止了连接？

### API 返回 500 错误
- [ ] 检查数据库连接状态
- [ ] 查看 `system_logs` 表中的错误
- [ ] 检查请求参数是否正确
- [ ] 查看应用输出日志

### 前端加载失败
- [ ] 检查 `static/` 目录是否存在
- [ ] 检查 `templates/` 目录是否存在
- [ ] 检查浏览器控制台是否有 JS 错误
- [ ] 清除浏览器缓存

---

## 📋 定期维护检查清单

### 每周检查
- [ ] 应用日志查看，排查异常
- [ ] 数据库备份已完成
- [ ] 监控磁盘空间使用
- [ ] 检查 `access_logs` 表大小

### 每月检查
- [ ] 数据库性能分析
- [ ] 慢查询日志分析
- [ ] 清理过期的访客权限
- [ ] 更新依赖包（`pip list --outdated`）

### 每季度检查
- [ ] 安全审计
- [ ] 性能基准测试
- [ ] 备份数据库恢复测试
- [ ] 审查访问日志

---

## 🔄 更新与升级

### 更新应用代码
```bash
# 1. 备份数据库
mysqldump -u smartaccess -p smartaccess > backup.sql

# 2. 更新代码（git pull）
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 重启应用
# 停止当前运行，然后重新启动
```

- [ ] 备份完成
- [ ] 代码更新完成
- [ ] 依赖更新完成
- [ ] 应用重启成功
- [ ] 验证所有 API 正常

### 数据库迁移
- [ ] 已备份当前数据库
- [ ] 已测试迁移脚本
- [ ] 已通知用户可能的停机时间
- [ ] 迁移完成后已验证数据完整性

---

## 📞 关键联系信息与资源

### 技术文档
- 快速开始: [README.md](README.md)
- 详细安装: [INSTALL.md](INSTALL.md)
- 项目总结: [FINAL_SUMMARY.md](FINAL_SUMMARY.md)
- 文件导览: [PROJECT_GUIDE.md](PROJECT_GUIDE.md)
- 快速索引: [INDEX.md](INDEX.md)

### API 文档
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 数据库
- MySQL 官方文档: https://dev.mysql.com/doc/
- SQLAlchemy 文档: https://docs.sqlalchemy.org/
- FastAPI 文档: https://fastapi.tiangolo.com/

---

## ✨ 部署成功的迹象

启动应用后，您应该看到：

```
✅ Uvicorn running on http://127.0.0.1:8000
✅ 数据库表已自动创建
✅ 默认 admin 用户已创建
✅ Swagger UI 可访问
✅ 所有 API 返回正确的 JSON
✅ 访问日志被记录到数据库
```

---

## 🎯 部署验收标准

部署完成后，请确保以下条件都满足：

- [ ] 应用能正常启动
- [ ] 数据库连接正常
- [ ] 所有表都已创建
- [ ] 默认用户可登录
- [ ] API 文档可访问
- [ ] 至少一个 API 端点可成功调用
- [ ] 访问日志被正确记录
- [ ] 没有启动错误或警告
- [ ] 性能在可接受范围内
- [ ] 安全配置已完成

**如果所有项都打勾了，恭喜您！部署完成！** 🎉

---

## 📝 部署日志模板

```
部署日期: ___________
部署人员: ___________
部署环境: [ ] 开发 [ ] 测试 [ ] 生产
数据库类型: [ ] SQLite [ ] MySQL
Python 版本: ___________

启动时间: ___________
停止时间: ___________

异常问题: ___________
解决方案: ___________

验收人签名: ___________ 日期: ___________
```

---

## 🚀 快速参考

### 常用命令
```bash
# 启动应用
python -m uvicorn app.main:app --reload

# 启动生产应用
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app

# 测试数据库
python -c "from app.database import engine; print('Database connected!' if engine else 'Failed')"

# 查看依赖
pip list

# 更新依赖
pip install -r requirements.txt --upgrade
```

### 关键文件位置
```
配置: .env
启动: app/main.py
数据库: app/database.py
模型: app/models.py
API: app/routers/
```

---

**准备好了吗？让我们部署 SmartAccess v2.0！** 🚀

# ✅ 硬件升级交付清单

## 📋 文件清单

### 固件文件 (📁 yj-c/)
- ✅ `esp8266_pn532_v2.ino` (v5.0) - 门禁1，纯远程控制版
- ✅ `esp32_s3_nfc_controller.ino` (v1.0) - 门禁2，远程+NFC版

### 后端代码文件 (📁 SmartAccess/app/)
- ✅ `models.py` - 数据模型更新（device_mode, device_id）
- ✅ `routers/hardware.py` - API路由更新

### 数据库文件 (📁 根目录)
- ✅ `MIGRATION_SCRIPT_v2.0.sql` - 数据库迁移脚本

### 文档文件 (📁 根目录)
- ✅ `HARDWARE_UPGRADE_GUIDE_v2.0.md` - 详细升级指南（强烈推荐）
- ✅ `QUICK_START_UPGRADE.md` - 快速启动指南
- ✅ `API_CHANGES_v2.0.md` - API 完整变更说明
- ✅ `UPGRADE_SUMMARY.md` - 变更汇总（快速参考）
- ✅ `HARDWARE_UPGRADE_COMPLETION_REPORT.md` - 完成报告

### 测试脚本 (📁 根目录)
- ✅ `test_hardware_upgrade.py` - 自动化测试脚本

---

## 📌 关键信息速查

### 新增设备

| 设备名 | 硬件平台 | 设备ID | 模式 | 功能 |
|--------|---------|--------|------|------|
| 门禁1 | ESP8266 | `door_controller_1` | `remote_only` | 远程开门 |
| 门禁2 | ESP32-S3 | `door_controller_2` | `remote_nfc` | 远程+NFC |

### 重要的数据库字段

| 表 | 新增列 | 说明 |
|----|--------|------|
| `hardware_devices` | `device_mode` | 设备模式（remote_only/remote_nfc） |
| `nfc_cards` | `device_id` | 绑定的设备ID（NULL表示对所有设备有效） |

### 核心API变更

| API | 变更 | 说明 |
|----|------|------|
| POST /api/hardware/devices | 新增device_mode | 创建设备时指定模式 |
| PUT /api/hardware/devices/{id} | 新增device_mode | 更新设备模式 |
| GET/POST /api/hardware/nfc-scan | 同时支持GET/POST | 验证设备模式和设备存在性 |
| POST /api/hardware/nfc/cards | 新增device_id | 创建卡片时可绑定设备 |
| PUT /api/hardware/nfc/card/{id} | 新增device_id | 更新卡片设备绑定 |

---

## 🚀 部署步骤

### 第1步: 备份 (5分钟)
```bash
# 备份数据库
mysqldump -u root -p smartaccess > backup_before_upgrade.sql

# 备份代码
git commit -am "Backup before upgrade"
```

### 第2步: 数据库迁移 (2分钟)
```bash
# 执行迁移脚本
mysql -u root -p smartaccess < MIGRATION_SCRIPT_v2.0.sql

# 验证迁移
mysql -u root -p smartaccess -e "SHOW COLUMNS FROM hardware_devices LIKE 'device_mode';"
mysql -u root -p smartaccess -e "SHOW COLUMNS FROM nfc_cards LIKE 'device_id';"
```

### 第3步: 后端更新 (5分钟)
```bash
# 复制更新后的文件
# - app/models.py
# - app/routers/hardware.py

# 重启服务
systemctl restart smartaccess
# 或
python -m uvicorn app.main:app --reload
```

### 第4步: 硬件更新 (15分钟)
```bash
# 门禁1: 编译并上传 esp8266_pn532_v2.ino (v5.0)
# 门禁2: 编译并上传 esp32_s3_nfc_controller.ino (v1.0)

# 验证: 检查串口日志，确保设备启动正常
```

### 第5步: 验证 (5分钟)
```bash
# 运行测试脚本
python test_hardware_upgrade.py

# 或手动验证
curl http://localhost:8000/api/hardware/devices
```

**总计时间**: ~30分钟（包括停机时间）

---

## 🧪 测试检查表

### 部署前
- [ ] 已阅读 `HARDWARE_UPGRADE_GUIDE_v2.0.md`
- [ ] 已备份数据库
- [ ] 已备份代码
- [ ] 已准备好新固件

### 数据库
- [ ] 迁移脚本无错误
- [ ] hardware_devices.device_mode 列已创建
- [ ] nfc_cards.device_id 列已创建
- [ ] 索引已创建

### 后端
- [ ] 代码更新无误
- [ ] 服务启动正常
- [ ] 无异常日志
- [ ] API响应正常

### 硬件
- [ ] 门禁1固件已上传 (v5.0)
- [ ] 门禁2固件已上传 (v1.0)
- [ ] 设备已成功注册
- [ ] 心跳信号正常

### 功能
- [ ] 远程开门 (门禁1) ✓
- [ ] 远程开门 (门禁2) ✓
- [ ] NFC刷卡 (门禁2) ✓
- [ ] 权限验证 ✓
- [ ] 访问日志记录 ✓

---

## 📖 文档使用指南

| 需求 | 推荐文档 | 阅读时间 |
|------|---------|--------|
| 快速了解升级内容 | `UPGRADE_SUMMARY.md` | 5分钟 |
| 快速部署指南 | `QUICK_START_UPGRADE.md` | 20分钟 |
| 详细升级说明 | `HARDWARE_UPGRADE_GUIDE_v2.0.md` | 45分钟 |
| API变更详情 | `API_CHANGES_v2.0.md` | 15分钟 |
| 故障排查 | `HARDWARE_UPGRADE_GUIDE_v2.0.md` 中的章节 | 按需 |
| 数据库脚本 | `MIGRATION_SCRIPT_v2.0.sql` | 参考 |
| 自动化测试 | `test_hardware_upgrade.py` | 运行 |

---

## 🆘 常见问题速查

### Q: 升级会影响现有功能吗？
A: 不会。系统完全向后兼容，现有API和数据无需改动。

### Q: 升级失败怎么回滚？
A: 运行备份的 `backup_before_upgrade.sql` 恢复数据库，替换回旧代码。

### Q: 门禁1和门禁2可以共存吗？
A: 可以，系统支持多设备独立运行。

### Q: NFC卡片可以被多个门禁使用吗？
A: 可以，创建卡片时若不指定 `device_id` 则对所有支持NFC的设备有效。

### Q: 如何只升级一个门禁？
A: 可以，系统支持部分升级。但建议完整升级以获得最佳体验。

---

## 📞 获取帮助

### 问题分类

**安装部署问题**
→ 参考 `QUICK_START_UPGRADE.md` 或 `HARDWARE_UPGRADE_GUIDE_v2.0.md`

**API相关问题**
→ 参考 `API_CHANGES_v2.0.md`

**硬件/固件问题**
→ 参考 `HARDWARE_UPGRADE_GUIDE_v2.0.md` 的故障排查章节

**数据库问题**
→ 参考 `MIGRATION_SCRIPT_v2.0.sql` 和相关文档

**测试/验证问题**
→ 运行 `test_hardware_upgrade.py`

---

## ✨ 升级完成确认

升级完成后，您应该看到：

1. ✅ 两个硬件设备注册到系统
2. ✅ 设备模式正确显示 (remote_only / remote_nfc)
3. ✅ 可以远程控制两个门禁
4. ✅ 可以刷NFC卡控制门禁2
5. ✅ NFC卡片权限验证正常
6. ✅ 访问日志记录完整

---

## 📊 版本信息

| 组件 | 版本 | 说明 |
|------|------|------|
| SmartAccess 后端 | v2.0 | 支持多设备 |
| 门禁1固件 | v5.0 | 纯远程控制 |
| 门禁2固件 | v1.0 | 远程+NFC |
| 数据库架构 | v2.0 | 支持device_mode和device_id |

---

## 📝 检查清单（可打印）

```
部署检查清单 - SmartAccess 硬件升级 v2.0
日期: ____________    负责人: ____________

准备阶段:
  [ ] 备份数据库
  [ ] 备份代码
  [ ] 阅读文档
  [ ] 准备硬件和固件

实施阶段:
  [ ] 执行数据库迁移
  [ ] 更新后端代码
  [ ] 重启服务
  [ ] 烧录门禁1固件 (v5.0)
  [ ] 烧录门禁2固件 (v1.0)

验证阶段:
  [ ] 检查数据库表结构
  [ ] 验证设备注册
  [ ] 测试远程开门
  [ ] 测试NFC刷卡
  [ ] 检查访问日志

完成:
  [ ] 所有测试通过
  [ ] 文档更新
  [ ] 用户通知

签名: ________________   日期: ____________
```

---

**升级版本**: v2.0  
**发布日期**: 2026-01-03  
**状态**: ✅ 生产就绪

---

> 🎉 **欢迎使用 SmartAccess v2.0 多设备架构！**

# 硬件升级变更汇总

## 📌 快速参考

### 系统升级
```
v1.0 单一门禁 → v2.0 多设备架构
```

### 新设备
- **门禁1** (ESP8266): 纯远程控制，NFC已移除
- **门禁2** (ESP32-S3): 远程+NFC混合，新增

---

## 📂 修改的文件

### 后端代码
```
✅ app/models.py
   • HardwareDevice.device_mode (新增)
   • NFCCard.device_id (新增)

✅ app/routers/hardware.py
   • HardwareDeviceCreate.device_mode (新增)
   • HardwareDeviceUpdate.device_mode (新增)
   • HardwareDeviceResponse.device_mode (新增)
   • NFCCardCreate.device_id (新增)
   • NFCCardUpdate.device_id (新增)
   • NFCCardResponse.device_id (新增)
   • nfc_scan() 接口 (支持GET/POST，验证device_mode)
```

### 硬件固件
```
✅ yj-c/esp8266_pn532_v2.ino (修改为v5.0)
   • 移除所有NFC代码
   • 更新设备标识为 door_controller_1
   • 设置模式为 remote_only

✅ yj-c/esp32_s3_nfc_controller.ino (新建，v1.0)
   • 新增NFC功能
   • 设备标识 door_controller_2
   • 模式为 remote_nfc
```

### 文档
```
✅ HARDWARE_UPGRADE_GUIDE_v2.0.md (详细指南)
✅ QUICK_START_UPGRADE.md (快速启动)
✅ API_CHANGES_v2.0.md (API文档)
✅ MIGRATION_SCRIPT_v2.0.sql (数据库迁移)
✅ HARDWARE_UPGRADE_COMPLETION_REPORT.md (完成报告)
```

---

## 🔄 数据库迁移

```sql
ALTER TABLE hardware_devices 
ADD COLUMN device_mode VARCHAR(50) DEFAULT 'remote_only';

ALTER TABLE nfc_cards 
ADD COLUMN device_id VARCHAR(50) NULL;

ALTER TABLE nfc_cards 
ADD INDEX idx_device_id (device_id);
```

---

## 🔑 关键参数

### 设备模式
- `remote_only` - 仅远程控制（门禁1）
- `remote_nfc` - 远程+NFC（门禁2）

### 设备ID
- `door_controller_1` - 门禁1
- `door_controller_2` - 门禁2

---

## 📋 验证清单

部署前检查：
- [ ] 数据库迁移脚本已备份
- [ ] 后端代码已更新
- [ ] 门禁1固件已编译（v5.0）
- [ ] 门禁2固件已编译（v1.0）
- [ ] 文档已阅读

部署后验证：
- [ ] 数据库表结构正确
- [ ] 后端服务启动正常
- [ ] 门禁1设备可注册
- [ ] 门禁2设备可注册
- [ ] 远程开门可用
- [ ] NFC卡片扫描可用（门禁2）

---

## 🆘 故障排查快速链接

| 问题 | 参考文档 |
|------|---------|
| 设备无法注册 | HARDWARE_UPGRADE_GUIDE_v2.0.md § 调试和故障排查 |
| NFC不响应 | HARDWARE_UPGRADE_GUIDE_v2.0.md § 门禁2常见问题 |
| API错误 | API_CHANGES_v2.0.md § 逻辑流程图 |
| 数据库问题 | MIGRATION_SCRIPT_v2.0.sql |

---

## 📞 获取帮助

1. **快速了解**: 读 QUICK_START_UPGRADE.md (5分钟)
2. **详细部署**: 读 HARDWARE_UPGRADE_GUIDE_v2.0.md (20分钟)
3. **API变更**: 读 API_CHANGES_v2.0.md (10分钟)
4. **故障排查**: 读 HARDWARE_UPGRADE_GUIDE_v2.0.md 中的故障排查章节

---

**状态**: ✅ 生产就绪  
**最后更新**: 2026-01-03

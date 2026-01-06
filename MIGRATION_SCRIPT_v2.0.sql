-- ============================================================
-- SmartAccess 硬件升级迁移脚本 v2.0
-- 日期: 2026-01-03
-- 说明: 从单一设备升级到多设备架构
-- ============================================================

-- 1. 为硬件设备表添加设备模式字段
-- 用于区分不同功能的门禁设备
ALTER TABLE hardware_devices ADD COLUMN device_mode VARCHAR(50) DEFAULT 'remote_only' COMMENT '设备模式: remote_only(门禁1), remote_nfc(门禁2)等';

-- 2. 为NFC卡片表添加设备绑定字段
-- 支持将卡片绑定到特定的硬件设备
ALTER TABLE nfc_cards ADD COLUMN device_id VARCHAR(50) NULL COMMENT '绑定的硬件设备ID，NULL表示对所有支持NFC的设备有效';

-- 3. 为device_id添加索引，提高查询性能
ALTER TABLE nfc_cards ADD INDEX idx_device_id (device_id);

-- ============================================================
-- 升级后的建议初始化数据
-- ============================================================

-- 如果之前已存在硬件设备，需要手动设置device_mode
-- 示例：将旧的门禁设置为门禁1（纯远程）
UPDATE hardware_devices SET device_mode = 'remote_only' WHERE device_id = 'nfc_reader_01';

-- ============================================================
-- 验证脚本 - 运行以确认升级成功
-- ============================================================

-- 1. 检查新列是否存在
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'hardware_devices' AND COLUMN_NAME = 'device_mode';

-- 2. 检查device_id列是否存在于nfc_cards
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'nfc_cards' AND COLUMN_NAME = 'device_id';

-- 3. 查看当前硬件设备及其模式
SELECT id, device_id, device_name, device_type, device_mode, is_active FROM hardware_devices;

-- 4. 查看NFC卡片及其设备绑定
SELECT id, card_number, card_name, device_id, is_active FROM nfc_cards;

-- ============================================================
-- 回滚脚本 - 如果需要撤销升级
-- ============================================================
/*
ALTER TABLE nfc_cards DROP COLUMN device_id;
ALTER TABLE hardware_devices DROP COLUMN device_mode;
*/

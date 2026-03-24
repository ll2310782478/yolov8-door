# LocalStorage Key Unification Fix Report

## Problem Identified
页面反复跳转的问题是由于不同HTML 页面使用了不一致的localStorage key：
- **认证页面** (`auth.html`)：使用`smartaccess_token` 
- **其他页面** (`dashboard.html`, `logs.html`等)：期望读取`token`

这导致登录后跳转到其他页面时，因找不到token 而被重定向回登录页，形成无限循环。

## Solution Applied
统一所有活动模板文件的 localStorage key：
- `'smartaccess_token'` → `'token'`
- `'smartaccess_username'` → `'username'`

## Files Fixed (5 files)
1. ✅ [`face.html`](app/templates/face.html)
2. ✅ [`hardware.html`](app/templates/hardware.html)
3. ✅ [`test_hardware.html`](app/templates/test_hardware.html)
4. ✅ [`users.html`](app/templates/users.html)
5. ✅ [`visitors.html`](app/templates/visitors.html)

## Already Correct (7 files)
- ✅ [`auth.html`](app/templates/auth.html) - Fixed earlier
- ✅ [`bluetooth.html`](app/templates/bluetooth.html)
- ✅ [`dashboard.html`](app/templates/dashboard.html) - New file created today
- ✅ [`face_gate.html`](app/templates/face_gate.html) - Fixed earlier
- ✅ [`logs.html`](app/templates/logs.html) - Fixed earlier
- ✅ [`nfc.html`](app/templates/nfc.html)
- ✅ [`remote_door.html`](app/templates/remote_door.html)
- ✅ [`settings.html`](app/templates/settings.html)

## Skipped (Backup/Broken files)
- ⚠️ `dashboard_backup_corrupted.html` - Corrupted backup, not in use
- ⚠️ `dashboard_old_broken.html` - Old broken version, not in use

## Verification
执行后验证确认：
- 所有**活动模板文件**已统一使用`localStorage.getItem('token')`
- 仅备份/损坏文件保留旧的 key（不影响功能）

## Expected Behavior After Fix
1. 用户在`/web/auth` 登录
2. Token 保存到localStorage 的`token` key
3. 跳转到`/web/dashboard` 或其他页面
4. 页面成功读取到token，正常显示内容
5. ✅ **不再出现无限跳转循环**

## Testing Steps
1. 清除浏览器缓存和localStorage
2. 访问http://localhost:8000/web/auth
3. 输入凭据登录
4. 应成功跳转到仪表盘且无重复跳转
5. 尝试导航到其他页面（用户管理、日志等）
6. 所有页面应正常工作

---
**Fix Date:** 2026-03-22  
**Status:** ✅ COMPLETE

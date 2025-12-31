# 二维码邮件发送功能使用指南

## 📧 功能说明

SmartAccess 现已集成**最简单的二维码邮件发送方案**，访客可通过邮箱接收访问二维码。

## 🚀 核心流程

```
1. 创建访客 → 2. 生成二维码 → 3. 发送邮件（附带二维码图片）→ 4. 访客手机扫码
```

## ⚙️ 配置步骤

### 1. 安装依赖

```bash
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess
pip install yagmail==0.15.293
```

### 2. 配置邮箱（Gmail示例）

编辑 `.env` 文件：

```dotenv
# 邮件配置
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

#### 🔑 获取Gmail应用密码（推荐）

1. **登录 Google 账户** → 访问 https://myaccount.google.com/security
2. **开启两步验证**（如果未开启）
3. **生成应用密码**：
   - 访问：https://myaccount.google.com/apppasswords
   - 选择应用：`邮件`
   - 选择设备：`Windows电脑`
   - 点击"生成"
   - 复制16位密码（例如：`abcd efgh ijkl mnop`）
4. **粘贴到 .env**：
   ```dotenv
   SMTP_USER=yourname@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   ```

#### 📮 其他邮箱配置

**QQ邮箱**：
```dotenv
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USER=123456789@qq.com
SMTP_PASSWORD=your-qq-smtp-password  # 在QQ邮箱设置中获取授权码
```

**163邮箱**：
```dotenv
SMTP_SERVER=smtp.163.com
SMTP_PORT=25
SMTP_USER=yourname@163.com
SMTP_PASSWORD=your-163-smtp-password
```

**企业邮箱（腾讯企业邮）**：
```dotenv
SMTP_SERVER=smtp.exmail.qq.com
SMTP_PORT=465
SMTP_USER=admin@yourcompany.com
SMTP_PASSWORD=your-password
```

### 3. 测试邮件发送

#### 方法1: API测试（推荐）

1. 启动服务：
```bash
cd U:\BYSJ\yolov-door\yolov8-door\SmartAccess
python -m uvicorn app.main:app --reload
```

2. 访问API文档：http://localhost:8000/docs

3. 测试步骤：
   - **创建访客**：`POST /api/visitors/`
     ```json
     {
       "name": "张三",
       "email": "visitor@example.com",
       "phone": "13800138000",
       "company": "测试公司",
       "purpose": "业务洽谈",
       "max_duration_hours": 8
     }
     ```
   
   - **发送二维码**：`POST /api/visitors/{visitor_id}/send-qrcode?send_via=email`
     - 路径参数：`visitor_id` = 1（刚创建的访客ID）
     - 查询参数：`send_via` = `email`

4. 检查邮箱：访客邮箱应收到包含二维码的邮件

#### 方法2: 前端界面测试

1. 访问访客管理页面：http://localhost:8000/web/visitors

2. 点击"新增访客"按钮

3. 填写访客信息（包括邮箱）

4. 创建成功后，点击"发送二维码"按钮

5. 选择"邮件发送"

## 📱 访客使用流程

### 收到邮件后：

1. **打开邮件附件** - 查看二维码图片
2. **保存到手机** - 将二维码保存到相册（或直接用邮件附件）
3. **到达门口** - 将二维码对准摄像头/扫码设备
4. **验证通过** - 门禁自动开启

## 📧 邮件内容示例

访客收到的邮件包含：

```
主题：SmartAccess 访客二维码 - 张三

内容：
┌─────────────────────────────────┐
│  SmartAccess 访客通行证         │
├─────────────────────────────────┤
│ 访客信息                        │
│ 姓名：张三                      │
│ 公司：测试公司                  │
│ 访问目的：业务洽谈              │
│ 有效期至：2024-12-31 18:00      │
├─────────────────────────────────┤
│  ⬇️ 请使用下方二维码验证 ⬇️     │
│                                 │
│  [二维码图片 - 作为附件]        │
│                                 │
├─────────────────────────────────┤
│ 使用说明：                      │
│ 1. 查看附件中的二维码图片       │
│ 2. 保存到手机相册               │
│ 3. 到达门口对准摄像头           │
│ 4. 等待验证通过                 │
└─────────────────────────────────┘
```

## 🛠️ API文档

### 发送二维码邮件

**端点**：`POST /api/visitors/{visitor_id}/send-qrcode`

**参数**：
- `visitor_id` (路径参数): 访客ID
- `send_via` (查询参数): `email` 或 `sms`

**请求示例**：
```bash
curl -X POST "http://localhost:8000/api/visitors/1/send-qrcode?send_via=email"
```

**成功响应**：
```json
{
  "status": "success",
  "message": "二维码已成功发送到邮箱 visitor@example.com",
  "sent_to": "visitor@example.com",
  "qrcode_path": "static/qrcodes/visitor_20241231120000_abc123.png"
}
```

**错误响应**：
```json
{
  "detail": "访客未设置邮箱"
}
```

## 🔧 常见问题

### Q1: 邮件发送失败："Authentication failed"

**原因**：邮箱密码错误或未开启SMTP服务

**解决**：
- Gmail：使用应用专用密码，而非账户密码
- QQ/163：在邮箱设置中开启SMTP，并使用授权码

### Q2: 邮件进入垃圾箱

**解决**：
1. 访客将发件人加入白名单
2. 修改邮件内容，减少营销词汇
3. 使用企业邮箱发送（更可信）

### Q3: 二维码图片未生成

**原因**：`static/qrcodes/` 目录不存在

**解决**：
```bash
mkdir -p U:\BYSJ\yolov-door\yolov8-door\SmartAccess\static\qrcodes
```

### Q4: 想用其他邮箱服务（非Gmail）

**解决**：修改 `.env` 中的 `SMTP_SERVER` 和 `SMTP_PORT`
- 参考上方"其他邮箱配置"章节

## 🎯 优点总结

✅ **极简实现**：使用yagmail仅需5行代码  
✅ **零额外成本**：无需短信费用  
✅ **跨平台**：任何邮箱都能接收  
✅ **易于调试**：邮件可查看历史记录  
✅ **安全可靠**：二维码带加密token

## 📊 技术架构

```
访客创建 → 生成二维码(qrcode库) → 保存图片(static/qrcodes/)
    ↓
调用发送API → yagmail发送邮件 → 附件=二维码图片
    ↓
访客邮箱接收 → 手机查看附件 → 门口扫码验证(verify API)
```

## 🚀 下一步扩展

- [ ] 添加短信发送（需接入阿里云/腾讯云短信服务）
- [ ] 批量发送邮件
- [ ] 邮件模板自定义
- [ ] 发送记录查询
- [ ] 邮件送达率统计

---

**文档生成时间**：2024-12-31  
**适用版本**：SmartAccess v2.0

# SmartAccess 人脸识别集成使用指南

## 目录
1. [概述](#概述)
2. [功能说明](#功能说明)
3. [API 端点](#api-端点)
4. [使用示例](#使用示例)
5. [常见问题](#常见问题)
6. [故障排除](#故障排除)

## 概述

SmartAccess v2.0 已完整集成 face_access-v2 模块，实现了基于 YOLOv8 + InsightFace 的企业级人脸识别系统。本指南详细说明如何使用这些功能。

### 技术栈

| 组件 | 版本 | 功能 |
|------|------|------|
| YOLOv8 | 8.0.236 | 实时人脸检测 (纳米级，轻量级) |
| InsightFace | 0.7.3 | 人脸特征提取 (512维) |
| PyTorch | 2.1.2 | 深度学习框架，支持GPU |
| FastAPI | 0.104.1 | REST API 框架 |

### 核心特性

✅ **实时人脸检测** - YOLOv8 纳米模型，CPU 上也能流畅运行  
✅ **512维特征向量** - InsightFace 提供业界标准的人脸表示  
✅ **自动去重** - 上传时自动检测并防止重复注册相同的人  
✅ **离线识别** - 基于特征向量的快速离线匹配，无需上传至云端  
✅ **GPU/CPU 自适应** - 自动检测并利用 GPU，无 GPU 时降级到 CPU  
✅ **智能缓存** - 5秒内结果缓存，减少重复计算  

---

## 功能说明

### 1. 人脸上传与注册 - `POST /api/users/{user_id}/faces`

**功能描述:**
- 用户上传人脸照片
- 系统自动进行人脸检测、质量验证和特征提取
- 自动检测并防止重复注册相同人物的多张照片
- 将 512维特征向量存储到数据库

**智能验证流程:**

```
上传图片
   ↓
[YOLOv8 人脸检测] 
   ├─ 未检测到人脸 → 拒绝上传 ❌
   ├─ 检测到多张人脸 → 拒绝上传 ❌
   └─ 检测到单张人脸 → 继续 ✓
   ↓
[InsightFace 特征提取]
   ├─ 特征提取失败 → 拒绝上传 ❌
   └─ 成功提取 → 继续 ✓
   ↓
[重复检查]
   ├─ 相似度 > 85% → 拒绝上传 (防止重复) ❌
   └─ 相似度 < 85% → 继续 ✓
   ↓
[保存到数据库]
   ├─ embedding_data: 512维二进制向量
   ├─ image_path: 原始图片路径
   └─ is_primary: 是否主人脸标记
```

**请求参数:**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| user_id | integer | ✓ | 用户ID |
| file | file | ✓ | 人脸图片 (JPEG/PNG) |
| is_primary | boolean | ✗ | 是否设为主人脸 (默认 false) |
| permission_end_date | datetime | ✗ | 权限过期日期 |
| max_daily_uses | integer | ✗ | 每日最大使用次数 (默认 0 = 无限) |

**响应示例 - 成功 (200):**

```json
{
  "id": 15,
  "user_id": 3,
  "image_path": "/uploads/faces/face_3_15.jpg",
  "is_primary": true,
  "is_active": true,
  "embedding_data": "<binary>",
  "permission_start_date": "2024-01-15T10:30:00",
  "permission_end_date": "2025-01-15T10:30:00",
  "max_daily_uses": 100,
  "created_at": "2024-01-15T10:30:00"
}
```

**响应示例 - 失败 (400):**

```json
{
  "detail": "图片中未检测到人脸，请上传包含清晰人脸的照片"
}
```

### 2. 实时人脸识别 - `POST /api/users/{user_id}/faces/recognize-from-image`

**功能描述:**
- 上传一张包含人脸的图片
- 系统从图片中提取人脸特征
- 与指定用户已注册的所有人脸进行比对
- 返回所有相似度超过阈值的匹配结果

**识别流程:**

```
上传检查图片
   ↓
[YOLOv8 人脸检测]
   └─ 提取所有检测到的人脸 → 特征向量列表
   ↓
[逐一比对]
   ├─ 与用户人脸1 → 相似度 S1
   ├─ 与用户人脸2 → 相似度 S2
   └─ 与用户人脸N → 相似度 SN
   ↓
[过滤匹配]
   └─ 筛选相似度 >= threshold 的结果
   ↓
[返回排序结果]
   └─ 按相似度从高到低排列
```

**请求参数:**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| user_id | integer | ✓ | 要识别的用户ID |
| image | file | ✓ | 包含人脸的图片 (JPEG/PNG) |
| similarity_threshold | float | ✗ | 匹配阈值 0-1 (默认 0.7) |

**响应示例 - 有匹配 (200):**

```json
{
  "user_id": 3,
  "recognized": true,
  "total_detected_faces": 1,
  "message": "识别到 2 张匹配的人脸",
  "unmatched": false,
  "matched_faces": [
    {
      "face_id": 15,
      "similarity": 0.9234,
      "is_primary": true,
      "registered_at": "2024-01-15T10:30:00"
    },
    {
      "face_id": 16,
      "similarity": 0.8567,
      "is_primary": false,
      "registered_at": "2024-01-15T11:15:00"
    }
  ],
  "top_match": {
    "face_id": 15,
    "similarity": 0.9234,
    "is_primary": true
  }
}
```

**响应示例 - 无匹配 (200):**

```json
{
  "user_id": 3,
  "recognized": false,
  "total_detected_faces": 1,
  "message": "图片中的人脸未能与任何已注册的人脸匹配",
  "unmatched": true,
  "matched_faces": [],
  "top_match": null
}
```

### 3. 人脸权限检查（增强版）- `POST /api/users/{user_id}/faces/{face_id}/check-permission`

**功能描述:**
- 检查指定人脸的权限是否有效 (日期、时间、次数限制)
- 可选：通过上传新图片进行实时人脸识别验证

**检查流程:**

```
检查请求
   ↓
[权限有效性验证]
   ├─ 人脸是否被禁用? → 返回无效
   ├─ 权限是否过期? → 返回无效
   ├─ 当前时间是否在允许时间段? → 返回无效
   ├─ 今日使用次数是否超限? → 返回无效
   └─ 全部通过 → 继续
   ↓
[可选: 人脸识别验证]
   ├─ 若无图片 → 仅返回权限检查结果
   └─ 若有图片 → 进行特征比对
      ├─ 检测检查图片中的人脸
      ├─ 提取特征向量
      ├─ 与数据库存储的特征进行比对
      └─ 返回相似度和验证结果
   ↓
[返回综合结果]
```

**请求参数:**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| user_id | integer | ✓ | 用户ID |
| face_id | integer | ✓ | 人脸ID |
| check_image | file | ✗ | 验证图片 (JPEG/PNG)，可选 |

**响应示例 - 权限有效，无图片验证:**

```json
{
  "valid": true,
  "face_id": 15,
  "user_id": 3,
  "username": "zhangsan",
  "verified": false,
  "similarity_score": null
}
```

**响应示例 - 权限有效，图片验证通过:**

```json
{
  "valid": true,
  "face_id": 15,
  "user_id": 3,
  "username": "zhangsan",
  "verified": true,
  "similarity_score": 0.9234,
  "verification_reason": "人脸识别成功 (相似度: 92.34%)"
}
```

**响应示例 - 权限有效，图片验证失败:**

```json
{
  "valid": true,
  "face_id": 15,
  "user_id": 3,
  "username": "zhangsan",
  "verified": false,
  "similarity_score": 0.45,
  "verification_reason": "人脸不匹配 (相似度: 45%, 需要 >= 70%)"
}
```

---

## API 端点

### 人脸上传与管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/users/{user_id}/faces` | 上传人脸（自动识别和特征提取） |
| GET | `/api/users/{user_id}/faces` | 获取用户的所有人脸 |
| GET | `/api/users/{user_id}/faces/{face_id}` | 获取人脸详情 |
| PUT | `/api/users/{user_id}/faces/{face_id}` | 更新人脸信息（权限、时效等） |
| DELETE | `/api/users/{user_id}/faces/{face_id}` | 删除人脸 |
| POST | `/api/users/{user_id}/faces/{face_id}/check-permission` | **检查权限 + 可选人脸验证** |
| POST | `/api/users/{user_id}/faces/recognize-from-image` | **实时人脸识别** |

### 人脸识别服务（直接调用）

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/face-recognition/recognize` | 识别图片中的所有人脸 |
| GET | `/api/face-recognition/compare` | 比较两张人脸 |
| POST | `/api/face-recognition/register/{user_id}` | 为用户注册人脸 |
| GET | `/api/face-recognition/health` | 服务健康检查 |
| GET | `/api/face-recognition/info` | 获取设备信息（GPU/CPU） |

---

## 使用示例

### 示例 1: 完整的注册流程

```bash
# 1. 创建用户
curl -X POST "http://localhost:8000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "zhangsan",
    "password": "password123",
    "email": "zhangsan@example.com",
    "phone": "13800000001",
    "full_name": "张三"
  }'

# 响应: {"id": 3, "username": "zhangsan", ...}

# 2. 上传人脸照片（自动检测和特征提取）
curl -X POST "http://localhost:8000/api/users/3/faces" \
  -F "file=@/path/to/face.jpg" \
  -F "is_primary=true"

# 响应: {"id": 15, "user_id": 3, "embedding_data": "<binary>", ...}

# 3. 上传第二张人脸（不同角度）
curl -X POST "http://localhost:8000/api/users/3/faces" \
  -F "file=@/path/to/face_side.jpg"

# 响应: {"id": 16, "user_id": 3, ...}

# 4. 尝试上传相同人物的照片（会被拒绝）
curl -X POST "http://localhost:8000/api/users/3/faces" \
  -F "file=@/path/to/face_similar.jpg"

# 响应 (400): "检测到重复的人脸（相似度 92.34%），不需要重复上传同一个人的多张照片"
```

### 示例 2: 实时人脸识别

```bash
# 用一张人脸照片进行识别（识别是否为注册用户）
curl -X POST "http://localhost:8000/api/users/3/faces/recognize-from-image" \
  -F "image=@/path/to/check_face.jpg" \
  -F "similarity_threshold=0.7"

# 成功响应:
# {
#   "user_id": 3,
#   "recognized": true,
#   "matched_faces": [
#     {"face_id": 15, "similarity": 0.923, "is_primary": true},
#     {"face_id": 16, "similarity": 0.856, "is_primary": false}
#   ],
#   "top_match": {"face_id": 15, "similarity": 0.923}
# }
```

### 示例 3: 权限检查 + 人脸验证

```bash
# 仅检查权限有效性
curl -X POST "http://localhost:8000/api/users/3/faces/15/check-permission"

# 响应:
# {
#   "valid": true,
#   "face_id": 15,
#   "verified": false
# }

# 检查权限 + 通过新图片进行人脸识别验证
curl -X POST "http://localhost:8000/api/users/3/faces/15/check-permission" \
  -F "check_image=@/path/to/verification_face.jpg"

# 响应 (验证通过):
# {
#   "valid": true,
#   "verified": true,
#   "similarity_score": 0.924,
#   "verification_reason": "人脸识别成功 (相似度: 92.40%)"
# }
```

### 示例 4: 使用 Python 进行集成

```python
import requests
import json

BASE_URL = "http://localhost:8000/api"

# 1. 上传人脸
user_id = 3
with open("/path/to/face.jpg", "rb") as f:
    files = {"file": f}
    data = {"is_primary": True}
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/faces",
        files=files,
        data=data
    )
    face_data = response.json()
    print(f"人脸ID: {face_data['id']}")
    print(f"特征维度: 512")

# 2. 进行人脸识别
with open("/path/to/check_face.jpg", "rb") as f:
    files = {"image": f}
    params = {"similarity_threshold": 0.7}
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/faces/recognize-from-image",
        files=files,
        params=params
    )
    result = response.json()
    
    if result["recognized"]:
        top_match = result["top_match"]
        print(f"识别成功！")
        print(f"匹配的人脸ID: {top_match['face_id']}")
        print(f"相似度: {top_match['similarity']:.2%}")
    else:
        print(f"未识别到匹配的人脸")

# 3. 检查权限 + 验证
face_id = face_data["id"]
with open("/path/to/verification_face.jpg", "rb") as f:
    files = {"check_image": f}
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/faces/{face_id}/check-permission",
        files=files
    )
    result = response.json()
    
    if result["valid"] and result["verified"]:
        print(f"权限检查通过，人脸验证成功！")
        print(f"相似度: {result['similarity_score']:.2%}")
    elif result["valid"]:
        print(f"权限有效但未进行人脸验证")
    else:
        print(f"权限检查失败: {result['reason']}")
```

### 示例 5: 检查服务状态和设备信息

```bash
# 检查人脸识别服务是否可用
curl -X GET "http://localhost:8000/api/face-recognition/health"

# 响应:
# {
#   "status": "healthy",
#   "message": "Face recognition service is running"
# }

# 获取设备信息（GPU/CPU）
curl -X GET "http://localhost:8000/api/face-recognition/info"

# 响应:
# {
#   "device": "cuda",
#   "device_name": "NVIDIA GeForce RTX 3090",
#   "torch_version": "2.1.2",
#   "cuda_available": true,
#   "gpu_memory_allocated": 1024000000,
#   "models_loaded": {
#     "yolo": "yolov8n-face.pt",
#     "insightface": "buffalo_l"
#   }
# }
```

---

## 常见问题

### Q: 人脸特征向量 (embedding) 是什么？

**A:** 人脸特征向量是 InsightFace 模型从人脸图像中提取的 512 维数字表示。每张人脸都被转换为一个 512 个浮点数的向量，用于快速的人脸比对：

```
人脸图片 (500x500 px)
    ↓
[InsightFace 模型]
    ↓
特征向量 [f1, f2, f3, ..., f512]
每个 fi 是 -1 到 1 之间的浮点数
    ↓
比对: 计算两个向量的余弦相似度
结果范围: 0-1 (1 = 完全相同)
```

**优势:**
- 高效：比较两个向量只需计算一次 512 元向量的点积
- 隐私：存储特征向量而非图片
- 准确：InsightFace 在多个人脸识别基准测试中排名第一

### Q: 相似度阈值应该设置为多少？

**A:** 推荐值和应用场景：

| 阈值 | 应用场景 | 说明 |
|------|--------|------|
| 0.5-0.6 | 宽松匹配 | 用于推荐系统，找到相似的人脸 |
| 0.7 | **标准识别** | 适用于大多数应用（推荐值） |
| 0.8-0.85 | 严格匹配 | 高安全性应用 (门禁、金融) |
| 0.9+ | 极严格匹配 | 仅在需要完全匹配时使用 |

我们的实现：
- **上传检查 (防重复)**: 0.85 - 防止相同人物重复注册
- **权限验证 (认证)**: 0.7 - 标准人脸识别
- **API 参数**: 可自定义 (推荐 0.7)

### Q: 图片质量对识别有什么影响？

**A:** 图片质量直接影响特征提取和识别准确度：

**好的图片:**
✅ 人脸清晰，分辨率 ≥ 200x200 像素  
✅ 正面或接近正面 (偏转角 < 45°)  
✅ 光线均匀，没有强烈阴影  
✅ 完整的面部 (无遮挡或裁剪)  
✅ JPEG/PNG 格式，文件大小 < 5MB  

**不良的图片:**
❌ 人脸很小，分辨率 < 100x100 像素  
❌ 过度侧脸或向下看  
❌ 光线太暗或逆光  
❌ 眼睛被遮挡或闭眼  
❌ 图片模糊或压缩过度  

**系统行为:**
- 如果无法提取特征 → 拒绝上传，提示"无法提取人脸特征，请上传更清晰的照片"
- 如果图片质量导致识别失败 → 返回低相似度分数

### Q: 为什么上传两张相同人物的照片会被拒绝？

**A:** 这是**智能防重复功能**。我们在上传时设置 85% 的相似度阈值，如果新上传的人脸与现有人脸相似度 > 85%，系统会拒绝上传。

**原因:**
1. 避免冗余 - 相同人物的多张人脸数据不会提高识别准确度
2. 节省存储 - 每张人脸需要存储 512×4 = 2048 字节
3. 加速识别 - 人脸越少，识别越快

**处理方式:**
- 如果需要上传同一个人的**不同角度**人脸，确保侧脸角度 > 45°
- 如果确实需要多张人脸，可以调整重复检查的阈值 (需要修改代码)

### Q: 人脸识别服务需要网络连接吗？

**A:** 不需要。整个流程完全在本地进行：

```
上传人脸 → YOLOv8 检测 → InsightFace 特征 → 本地数据库
                (全部离线)
```

**完全离线的优势:**
- 🔒 隐私：人脸数据从不上传到云端
- ⚡ 速度：无网络延迟，毫秒级响应
- 💰 成本：无云服务费用
- 🛡️ 安全：完全的数据控制权

### Q: GPU 和 CPU 的性能差异是多少？

**A:** GPU 可以显著提升性能：

| 操作 | CPU (i7) | GPU (RTX 3090) |
|------|----------|----------------|
| 人脸检测 (640x480) | 150-200 ms | 10-20 ms |
| 特征提取 | 50-80 ms | 5-10 ms |
| 特征比对 (1 vs 1000) | 20-30 ms | 1-2 ms |
| **总耗时 (典型)** | **300 ms** | **30 ms** |

**加速倍数: 10 倍**

自动选择：
- 如果有 NVIDIA GPU (CUDA) → 自动使用 GPU
- 无 GPU → 自动降级到 CPU，仍可正常工作
- CPU 模式仍然可以进行实时识别 (约 3 FPS)

---

## 故障排除

### 问题 1: 上传人脸时报错 "图片中未检测到人脸"

**可能原因:**
- 图片分辨率过低 (< 100x100)
- 人脸被遮挡 (口罩、墨镜、长发遮挡)
- 图片过度裁剪，只有部分人脸
- 光线太暗

**解决方案:**
```bash
# 1. 尝试使用更清晰的图片
# 2. 确保人脸完整，分辨率 ≥ 200x200
# 3. 在光线良好的环境拍摄

# 检查图片分辨率:
python -c "from PIL import Image; img = Image.open('face.jpg'); print(img.size)"
# 输出应该 ≥ 200x200
```

### 问题 2: 人脸识别返回低相似度

**可能原因:**
- 上传时和检查时的光线差异大
- 人脸角度差异太大 (正面 vs 侧面)
- 人脸表情差异大 (笑脸 vs 严肃)
- 图片质量差异

**解决方案:**
```bash
# 1. 上传时和检查时在相同的光线条件
# 2. 确保人脸方向一致
# 3. 提高图片质量
# 4. 增加多张不同角度的人脸以提高鲁棒性

# 示例: 上传 3 张不同角度的人脸
# 正面、左45°、右45°
```

### 问题 3: GPU 未被检测到

**检查 GPU 状态:**
```bash
# 在 Python 中检查:
python -c "import torch; print(torch.cuda.is_available())"  # 应输出 True

# 获取 GPU 信息:
curl http://localhost:8000/api/face-recognition/info
# 检查响应中的 "cuda_available" 和 "device"
```

**解决方案:**
```bash
# 1. 安装 CUDA 和 cuDNN
# 2. 安装 PyTorch CUDA 版本:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 3. 验证安装:
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### 问题 4: 人脸特征向量为 None

**日志输出:**
```
ERROR: Failed to extract face embedding
```

**可能原因:**
- InsightFace 模型未正确加载
- 人脸裁剪区域为空
- 内存不足

**解决方案:**
```bash
# 1. 检查日志获取更详细的错误信息
# 2. 重启应用
# 3. 检查磁盘空间和内存

# 增加调试信息:
# 修改 logging level 为 DEBUG
# 在 main.py 中:
# logging.basicConfig(level=logging.DEBUG)
```

### 问题 5: 性能缓慢 (识别耗时 > 1 秒)

**可能原因:**
- 使用 CPU 而非 GPU
- 图片分辨率过高
- 数据库中人脸过多

**解决方案:**
```bash
# 1. 检查是否使用 GPU:
curl http://localhost:8000/api/face-recognition/info
# 如果 device 是 "cpu"，参考问题 3

# 2. 优化输入图片:
# 将输入图片resize到 640x480 或更小

# 3. 优化数据库查询:
# 在 users.py 中只查询 is_active=True 的人脸:
user_faces = db.query(FaceData).filter(
    FaceData.user_id == user_id,
    FaceData.is_active == True
).all()
```

---

## 最佳实践

### 1. 上传多张人脸以提高鲁棒性

```bash
# ✅ 推荐: 上传 3 张人脸
# - 正面 (face_front.jpg)
# - 左侧 (face_left.jpg)  
# - 右侧 (face_right.jpg)

for face_img in face_front.jpg face_left.jpg face_right.jpg; do
  curl -X POST "http://localhost:8000/api/users/3/faces" \
    -F "file=@$face_img"
done

# ❌ 不推荐: 上传 10+ 张非常相似的人脸
# 冗余数据、浪费存储、减慢识别
```

### 2. 定期更新人脸权限

```python
# 为用户的人脸设置权限期限 (如 1 年)
from datetime import datetime, timedelta

permission_end_date = datetime.now() + timedelta(days=365)

response = requests.put(
    f"http://localhost:8000/api/users/3/faces/15",
    json={"permission_end_date": permission_end_date.isoformat()}
)
```

### 3. 监控识别失败的情况

```python
# 在应用中记录识别失败
response = requests.post(
    f"http://localhost:8000/api/users/3/faces/recognize-from-image",
    files={"image": open("face.jpg", "rb")}
)

if not response.json()["recognized"]:
    # 记录失败，供后续分析
    logger.warning(f"Face recognition failed for user 3")
    # 可能需要上传更好的人脸照片
```

### 4. 合理设置相似度阈值

```python
# 根据安全级别调整:
# - 门禁系统: threshold = 0.8
# - 考勤打卡: threshold = 0.7  
# - 推荐系统: threshold = 0.6

requests.post(
    f"http://localhost:8000/api/users/3/faces/recognize-from-image",
    files={"image": open("face.jpg", "rb")},
    params={"similarity_threshold": 0.8}
)
```

### 5. 定期清理过期的人脸

```python
# 删除权限已过期的人脸
expired_faces = requests.get(
    f"http://localhost:8000/api/users/3/faces"
).json()

for face in expired_faces:
    if face["permission_end_date"] < datetime.now().isoformat():
        requests.delete(
            f"http://localhost:8000/api/users/3/faces/{face['id']}"
        )
```

---

## 总结

SmartAccess 的人脸识别集成提供了：

✅ **自动检测和验证** - YOLOv8 确保图片质量  
✅ **高效的特征提取** - InsightFace 512 维向量  
✅ **智能防重复** - 防止相同人物重复注册  
✅ **实时识别** - 毫秒级响应时间  
✅ **完全离线** - 无需云服务，保护隐私  
✅ **灵活的权限管理** - 支持日期、时间、次数限制  
✅ **GPU 加速** - 10 倍性能提升 (有 GPU 时)  

现在您已准备好在生产环境中使用这些功能！

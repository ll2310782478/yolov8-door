# 人脸识别模块集成指南

## 📌 概述

SmartAccess 已成功集成了 `face_access-v2` 的人脸识别模块，提供了完整的人脸识别功能，包括：

- ✅ 实时人脸检测（基于 YOLOv8）
- ✅ 人脸特征提取（基于 InsightFace）
- ✅ 人脸相似度计算
- ✅ 用户人脸注册
- ✅ 人脸识别缓存优化
- ✅ GPU/CPU 自适应

---

## 🏗️ 架构设计

### 模块结构

```
SmartAccess/
├── app/
│   ├── services/
│   │   ├── __init__.py
│   │   └── face_recognition.py      # 人脸识别服务类
│   │
│   ├── routers/
│   │   ├── face_recognition.py      # 人脸识别 API 端点
│   │   └── ...
│   │
│   ├── models.py                    # 数据库模型（新增 embedding_data 字段）
│   └── main.py                      # 注册人脸识别路由
│
├── requirements.txt                 # 新增依赖
└── ...
```

### 核心组件

#### 1. **FaceRecognitionService** (`app/services/face_recognition.py`)

人脸识别核心服务类，提供以下功能：

```python
class FaceRecognitionService:
    # 初始化服务
    __init__(config_path, model_path)
    
    # 人脸检测
    detect_faces(frame) -> List[Tuple[x1, y1, x2, y2]]
    
    # 特征提取
    extract_face_embedding(face_image) -> np.ndarray
    
    # 相似度计算
    compare_faces(embedding1, embedding2) -> float
    
    # 人脸识别
    recognize_face_in_frame(frame, known_embeddings) -> List[Dict]
    
    # 人脸注册
    register_face(frame, user_name) -> Tuple[bool, embedding, message]
    
    # 设备信息
    get_device_info() -> Dict
```

#### 2. **人脸识别 API** (`app/routers/face_recognition.py`)

RESTful API 端点，包括：

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/face-recognition/recognize` | 识别图像中的人脸 |
| POST | `/api/face-recognition/register/{user_id}` | 注册用户人脸 |
| POST | `/api/face-recognition/batch-register` | 批量注册人脸 |
| GET | `/api/face-recognition/info` | 获取设备信息 |
| POST | `/api/face-recognition/cache/clear` | 清空识别缓存 |
| GET | `/api/face-recognition/compare` | 对比两张人脸 |
| GET | `/api/face-recognition/health` | 健康检查 |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 更新 requirements.txt 已包含以下依赖：
pip install -r requirements.txt

# 或单独安装：
pip install ultralytics==8.0.236
pip install insightface==0.7.3
pip install torch==2.1.2
pip install torchvision==0.16.2
pip install opencv-python==4.8.1.78
```

### 2. 配置说明

#### 环境变量 (`.env`)

```ini
# 人脸识别配置
FACE_RECOGNITION_THRESHOLD=0.7        # 相似度阈值（0-1）
FACE_RECOGNITION_MODEL_PATH=yolov8n.pt # YOLO 模型路径
FACE_RECOGNITION_GPU=true             # 是否使用 GPU
```

#### 配置文件 (`app/services/face_recognition.py`)

服务会自动从 `api_config.json` 读取配置：

```json
{
    "threshold": 0.9,
    "api_url": "http://127.0.0.1:8000/api/access/log",
    "model_confidence": 0.6
}
```

### 3. 启动应用

```bash
cd SmartAccess
python -m uvicorn app.main:app --reload
```

应用启动时会自动初始化人脸识别服务。

---

## 📖 使用示例

### 示例 1：识别图像中的人脸

```python
import requests
import cv2

# 从摄像头捕获图像
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
cv2.imwrite('test_face.jpg', frame)

# 调用 API 识别人脸
with open('test_face.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/face-recognition/recognize',
        files={'file': f}
    )

results = response.json()
for result in results:
    print(f"姓名: {result['name']}")
    print(f"相似度: {result['similarity']:.2f}")
    print(f"状态: {result['status']}")
```

### 示例 2：注册用户人脸

```python
# 注册用户 ID 为 1 的人脸
with open('user_face.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/face-recognition/register/1',
        files={'file': f}
    )

result = response.json()
print(f"注册结果: {result['message']}")
```

### 示例 3：批量注册人脸

```python
# 批量注册用户 ID 为 1 的多张人脸
files = [
    ('files', open('face1.jpg', 'rb')),
    ('files', open('face2.jpg', 'rb')),
    ('files', open('face3.jpg', 'rb')),
]

response = requests.post(
    'http://localhost:8000/api/face-recognition/batch-register?user_id=1',
    files=files
)

result = response.json()
print(f"批量注册结果: {result['message']}")
```

### 示例 4：对比两张人脸

```python
# 对比两张人脸的相似度
with open('face1.jpg', 'rb') as f1, open('face2.jpg', 'rb') as f2:
    response = requests.get(
        'http://localhost:8000/api/face-recognition/compare',
        files={'file1': f1, 'file2': f2}
    )

result = response.json()
print(f"相似度: {result['similarity']:.2f}")
print(f"是否同一人: {result['is_same_person']}")
```

### 示例 5：获取设备信息

```python
response = requests.get(
    'http://localhost:8000/api/face-recognition/info'
)

info = response.json()
print(f"设备: {info['device']}")
print(f"识别阈值: {info['threshold']}")
print(f"缓存大小: {info['cache_size']}")

if info.get('gpu_name'):
    print(f"GPU 型号: {info['gpu_name']}")
    print(f"GPU 显存: {info['gpu_memory']}")
```

---

## 🔧 工作流程

### 人脸注册流程

```
上传图像
  ↓
YOLO 人脸检测
  ↓
InsightFace 特征提取
  ↓
保存到数据库
  ↓
✅ 注册完成
```

### 人脸识别流程

```
上传图像/摄像头输入
  ↓
YOLO 人脸检测
  ↓
检查缓存 ─→ 缓存命中 → 返回缓存结果
  ↓
InsightFace 特征提取
  ↓
与已知人脸特征对比
  ↓
计算相似度
  ↓
更新缓存
  ↓
✅ 返回识别结果
```

---

## 🎯 关键特性

### 1. **高效的缓存机制**

- 识别结果缓存 5 秒，减少重复计算
- 自动过期清理
- 支持手动清空缓存

### 2. **GPU 自适应**

- 自动检测 GPU 可用性
- GPU 不可用时自动降级到 CPU
- 性能监控和输出

### 3. **批量处理**

- 支持批量注册多张人脸
- 支持一次性识别多个人脸
- 返回详细的处理结果

### 4. **灵活的相似度阈值**

- 可配置的相似度阈值（0-1）
- 支持动态调整
- 阈值过低会增加误识率，过高会降低识别率

### 5. **完整的错误处理**

- 无效图像检测
- 人脸检测失败处理
- 特征提取失败处理
- 详细的错误信息返回

---

## 📊 性能优化

### 优化措施

1. **模型选择**
   - 使用 YOLOv8 nano 版本（轻量级）
   - 推理尺寸设为 320x320

2. **缓存策略**
   - 5 秒结果缓存
   - 减少重复识别

3. **GPU 优化**
   - 使用 CUDA 加速
   - 自动显存管理

4. **图像处理**
   - 自动调整图像尺寸
   - 减少不必要的处理

### 性能指标

| 指标 | CPU | GPU |
|------|-----|-----|
| 单帧识别时间 | 200-300ms | 50-100ms |
| 最大 FPS | 3-5 | 10-20 |
| 内存占用 | 500MB | 1GB+ |

---

## 🔐 安全建议

### 1. **数据安全**

- 人脸图像存储在安全的目录中
- 特征向量存储在数据库中，不是原始图像
- 支持加密存储（可自行实现）

### 2. **隐私保护**

- 不存储人脸原始图像（仅存储特征向量）
- 访问日志记录
- 定期清理过期数据

### 3. **相似度阈值调整**

- 生产环境建议设置阈值为 0.8-0.9
- 定期评估误识率和漏识率
- 根据实际情况调整

---

## 🐛 故障排除

### 问题 1：导入错误

**错误信息**: `ImportError: No module named 'insightface'`

**解决方案**:
```bash
pip install insightface==0.7.3
```

### 问题 2：CUDA 错误

**错误信息**: `CUDA out of memory`

**解决方案**:
```python
# 在 .env 中设置
FACE_RECOGNITION_GPU=false  # 改用 CPU
```

### 问题 3：识别准确率低

**原因可能**:
- 相似度阈值设置过低
- 注册时的人脸质量差
- 光线不足

**解决方案**:
- 提高相似度阈值（0.8-0.9）
- 注册时使用高质量图像
- 改善照明条件

### 问题 4：模型文件未找到

**错误信息**: `FileNotFoundError: 未找到 yolov8n.pt`

**解决方案**:
```bash
# 手动下载模型文件到项目目录
# 或在配置中指定正确的路径
FACE_RECOGNITION_MODEL_PATH=/path/to/yolov8n.pt
```

---

## 📚 API 参考

### POST /api/face-recognition/recognize

**请求**:
```json
Content-Type: multipart/form-data
file: <image_file>
```

**响应**:
```json
[
  {
    "name": "张三",
    "similarity": 0.95,
    "status": "recognized",
    "box": [100, 50, 300, 280]
  }
]
```

### POST /api/face-recognition/register/{user_id}

**请求**:
```json
Content-Type: multipart/form-data
file: <image_file>
```

**响应**:
```json
{
  "success": true,
  "message": "✅ 张三 人脸注册成功",
  "user_id": 1,
  "username": "张三"
}
```

### GET /api/face-recognition/info

**响应**:
```json
{
  "device": "cuda",
  "threshold": 0.7,
  "cache_size": 5,
  "gpu_name": "NVIDIA GeForce RTX 3060",
  "gpu_memory": "12.00 GB"
}
```

### POST /api/face-recognition/cache/clear

**响应**:
```json
{
  "success": true,
  "message": "✅ 识别缓存已清空"
}
```

---

## 🔄 与旧模块的兼容性

新的人脸识别模块与旧的 `face_access-v2` 模块兼容：

- 旧的 `face_encoding` 字段保留
- 新增 `embedding_data` 字段用于 InsightFace
- 可以并行使用两种特征向量

---

## 📝 配置参考

### FaceRecognitionService 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|-------|------|
| `threshold` | float | 0.7 | 相似度阈值（0-1） |
| `model_confidence` | float | 0.6 | YOLO 检测置信度 |
| `cache_duration` | int | 5 | 缓存时间（秒） |

---

## 💡 最佳实践

1. **使用高质量的注册图像**
   - 明亮的光线
   - 清晰的人脸
   - 不同角度的多张照片

2. **定期评估准确率**
   - 监控误识率
   - 监控漏识率
   - 根据反馈调整阈值

3. **缓存管理**
   - 定期清空缓存
   - 避免长期累积

4. **资源监控**
   - 监控 GPU 使用情况
   - 监控内存占用
   - 监控识别延迟

5. **数据备份**
   - 定期备份人脸特征向量
   - 定期备份数据库
   - 维护历史日志

---

## 📞 获取帮助

遇到问题？请按以下步骤：

1. 查看本文档的故障排除部分
2. 检查应用日志
3. 查看 API 文档 (`http://localhost:8000/docs`)
4. 查看源代码注释

---

## 📚 相关文档

- [README.md](README.md) - 项目概述
- [INSTALL.md](INSTALL.md) - 详细安装指南
- [face_access-v2 原始项目](../face_access-v2/) - 原始人脸识别模块

---

**版本**: 1.0.0 | **更新日期**: 2024 年 12 月

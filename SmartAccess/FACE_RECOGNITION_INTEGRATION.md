# SmartAccess 外部接口集成指南

## 概述

SmartAccess 不直接实现人脸识别算法，而是通过**调用外部接口**来实现人脸识别功能。这样设计的优势：

- ✅ 应用保持轻量级
- ✅ 可灵活更换识别引擎
- ✅ 利用专业的识别服务
- ✅ 降低硬件要求

---

## 支持的外部接口类型

### 1. 云端人脸识别服务

#### 🔷 百度人脸识别 API
```
服务网址: https://ai.baidu.com/ai-doc/FACE/
调用方式: REST API
特点: 功能完整、识别速度快、国内化部署

主要功能:
  • 人脸检测 (detect)
  • 人脸识别 (match)
  • 人脸搜索 (search)
  • 活体检测 (liveness)
```

#### 🔷 阿里云人脸识别
```
服务网址: https://www.aliyun.com/product/face
调用方式: REST API / SDK
特点: 企业级服务、可靠性高、支持离线部署

主要功能:
  • 人脸检测
  • 人脸对比
  • 人脸搜索
  • 活体检测
```

#### 🔷 腾讯云人脸识别
```
服务网址: https://cloud.tencent.com/product/fr
调用方式: REST API / SDK
特点: 国内化、文档完整、支持离线API

主要功能:
  • 人脸检测
  • 人脸对比
  • 人脸搜索
  • 活体检测
  • 人脸美颜
```

#### 🔷 Microsoft Azure Face API
```
服务网址: https://azure.microsoft.com/en-us/services/cognitive-services/face/
调用方式: REST API
特点: 国际化、功能全、文档详细

主要功能:
  • 人脸检测
  • 人脸验证
  • 人脸查找
  • 人脸分组
  • 人脸列表管理
```

#### 🔷 Google Cloud Vision API
```
服务网址: https://cloud.google.com/vision
调用方式: REST API / gRPC
特点: 功能强大、准确率高

主要功能:
  • 人脸检测
  • 人脸属性识别
  • 标签检测
  • Logo 检测
```

### 2. 本地部署方案

#### 🟢 Face++ (旷视)
```
部署方式: 本地 Docker
GitHub: https://github.com/deepinsight/insightface
特点: 开源免费、准确率高

支持功能:
  • 人脸检测
  • 人脸特征提取
  • 人脸对比
  • 活体检测
```

#### 🟢 SenseTime OpenIoT
```
部署方式: 本地服务
特点: 企业级方案、可靠性高

支持功能:
  • 人脸检测
  • 人脸识别
  • 行为识别
```

#### 🟢 OpenCV + DeepFace (Python)
```
部署方式: Python 本地库
GitHub: https://github.com/serengp/deepface
特点: 开源免费、易于集成

支持库:
  • OpenCV (cv2)
  • DeepFace
  • FaceNet
  • VGGFace2
```

---

## 集成方案

### 方案 A：云服务 API 调用

#### 适用场景
- ✅ 小型项目（初期）
- ✅ 用户量较小
- ✅ 对部署复杂度敏感
- ✅ 需要最高识别准确率

#### 优点
- 无需维护本地服务
- 自动更新升级
- 识别准确率最高
- 成本可控

#### 缺点
- 需要网络连接
- 每次调用产生费用
- 响应速度取决于网络
- 数据安全性考虑

#### 实现示例（以百度为例）

创建文件 `app/services/baidu_face.py`:
```python
import requests
import base64
from typing import Tuple, Dict
import json

class BaiduFaceAPI:
    """百度人脸识别 API 接口"""
    
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.token = self._get_access_token()
    
    def _get_access_token(self) -> str:
        """获取百度 API 令牌"""
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret_key
        }
        response = requests.get(url, params=params)
        return response.json()['access_token']
    
    def detect_face(self, image_path: str) -> Dict:
        """检测人脸"""
        url = f"https://aip.baidubce.com/rest/2.0/face/v3/detect?access_token={self.token}"
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()
        
        data = {
            'image': image_data,
            'image_type': 'BASE64',
            'max_face_num': 10,
            'face_type': 'LIVE',
            'quality_control': 'NORMAL'
        }
        
        response = requests.post(url, data=json.dumps(data),
                               headers={'Content-Type': 'application/json'})
        return response.json()
    
    def match_faces(self, image1_path: str, image2_path: str) -> Tuple[bool, float]:
        """对比两张人脸"""
        url = f"https://aip.baidubce.com/rest/2.0/face/v3/match?access_token={self.token}"
        
        def encode_image(path):
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        
        data = {
            'image_type': 'BASE64',
            'images': [
                {
                    'image': encode_image(image1_path),
                    'image_type': 'BASE64'
                },
                {
                    'image': encode_image(image2_path),
                    'image_type': 'BASE64'
                }
            ]
        }
        
        response = requests.post(url, data=json.dumps(data),
                               headers={'Content-Type': 'application/json'})
        result = response.json()
        
        if result['result'] and 'score' in result['result']:
            score = result['result']['score']  # 0-100 分
            return score >= 80, score  # 80 分以上判定为同一人
        
        return False, 0
```

在 `app/routers/users.py` 中使用：
```python
from app.services.baidu_face import BaiduFaceAPI
from os import getenv

baidu_api = BaiduFaceAPI(
    api_key=getenv('BAIDU_API_KEY'),
    secret_key=getenv('BAIDU_SECRET_KEY')
)

@router.post("/api/users/{user_id}/faces/verify")
async def verify_face(user_id: int, file: UploadFile, db: Session = Depends(get_db)):
    """验证人脸是否属于用户"""
    # 保存上传的图片
    uploaded_path = save_file(file, "uploads/faces")
    
    # 获取用户的主人脸
    user = db.query(User).filter(User.id == user_id).first()
    face = db.query(FaceData).filter(
        FaceData.user_id == user_id,
        FaceData.is_primary == True
    ).first()
    
    if not face:
        raise HTTPException(status_code=400, detail="用户未设置主人脸")
    
    # 调用百度 API 进行人脸对比
    is_match, score = baidu_api.match_faces(face.image_path, uploaded_path)
    
    return {
        "is_match": is_match,
        "score": score,
        "message": "人脸匹配" if is_match else "人脸不匹配"
    }
```

在 `.env` 中添加配置：
```env
# 百度人脸识别配置
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret_key
```

### 方案 B：本地服务部署

#### 适用场景
- ✅ 大型项目
- ✅ 用户量大
- ✅ 对延迟敏感
- ✅ 数据隐私要求高

#### 优点
- 完全离线运行
- 无调用费用
- 低延迟
- 数据不上传云端

#### 缺点
- 需要部署维护
- 硬件要求较高
- 识别准确率可能较低
- 需要GPU支持

#### 实现示例（使用 DeepFace）

安装依赖：
```bash
pip install deepface opencv-python tensorflow
```

创建文件 `app/services/deepface_local.py`:
```python
from deepface import DeepFace
import cv2
from typing import Tuple
import numpy as np

class LocalFaceRecognition:
    """本地人脸识别服务"""
    
    def __init__(self, model_name: str = "VGGFace2", metric: str = "cosine"):
        """
        初始化本地人脸识别
        
        model_name: VGGFace2, ArcFace, Facenet, 等
        metric: cosine, euclidean
        """
        self.model_name = model_name
        self.metric = metric
    
    def detect_face(self, image_path: str) -> bool:
        """检测图像中是否有人脸"""
        try:
            img = cv2.imread(image_path)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = face_cascade.detectMultiScale(img, 1.3, 5)
            return len(faces) > 0
        except Exception as e:
            print(f"人脸检测失败: {e}")
            return False
    
    def extract_face_encoding(self, image_path: str) -> np.ndarray:
        """提取人脸特征向量"""
        try:
            embedding = DeepFace.represent(
                image_path,
                model_name=self.model_name,
                enforce_detection=True
            )[0]['embedding']
            return np.array(embedding)
        except Exception as e:
            print(f"人脸特征提取失败: {e}")
            return None
    
    def match_faces(self, image1_path: str, image2_path: str, threshold: float = 0.6) -> Tuple[bool, float]:
        """对比两张人脸"""
        try:
            result = DeepFace.verify(
                image1_path,
                image2_path,
                model_name=self.model_name,
                metric=self.metric,
                enforce_detection=True
            )
            
            is_match = result['verified']
            distance = result['distance']
            
            return is_match, 1 - distance  # 转换为相似度 (0-1)
        except Exception as e:
            print(f"人脸对比失败: {e}")
            return False, 0
    
    def find_faces(self, query_image: str, database_path: str, threshold: float = 0.6) -> list:
        """在数据库中搜索相似人脸"""
        results = DeepFace.find(
            query_image,
            db_path=database_path,
            model_name=self.model_name,
            metric=self.metric,
            enforce_detection=True
        )
        return results
```

在 `app/routers/users.py` 中使用：
```python
from app.services.deepface_local import LocalFaceRecognition

face_recognition = LocalFaceRecognition(model_name="VGGFace2")

@router.post("/api/users/{user_id}/faces/verify")
async def verify_face(user_id: int, file: UploadFile, db: Session = Depends(get_db)):
    """验证人脸是否属于用户"""
    # 保存上传的图片
    uploaded_path = save_file(file, "uploads/faces")
    
    # 获取用户的主人脸
    face = db.query(FaceData).filter(
        FaceData.user_id == user_id,
        FaceData.is_primary == True
    ).first()
    
    if not face:
        raise HTTPException(status_code=400, detail="用户未设置主人脸")
    
    # 调用本地人脸识别服务
    is_match, similarity = face_recognition.match_faces(
        face.image_path,
        uploaded_path
    )
    
    return {
        "is_match": is_match,
        "similarity": float(similarity),
        "message": "人脸匹配" if is_match else "人脸不匹配"
    }
```

### 方案 C：硬件设备集成

#### 适用场景
- ✅ 专业人脸识别设备
- ✅ 需要高可靠性
- ✅ 实时人脸检测

#### 实现方式

创建文件 `app/services/hardware_face_device.py`:
```python
import requests
from typing import Tuple, Dict
from datetime import datetime

class HardwareFaceDevice:
    """硬件人脸识别设备接口"""
    
    def __init__(self, device_ip: str, device_port: int = 8000):
        """
        连接硬件人脸识别设备
        
        Args:
            device_ip: 设备 IP 地址
            device_port: 设备端口（默认 8000）
        """
        self.base_url = f"http://{device_ip}:{device_port}"
        self.timeout = 30
    
    def register_face(self, user_id: int, image_path: str, name: str) -> Dict:
        """向设备注册新人脸"""
        with open(image_path, 'rb') as f:
            files = {'image': f}
            data = {
                'user_id': user_id,
                'name': name,
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.base_url}/api/face/register",
                files=files,
                data=data,
                timeout=self.timeout
            )
            
            return response.json()
    
    def recognize_face(self, image_path: str) -> Dict:
        """识别人脸"""
        with open(image_path, 'rb') as f:
            files = {'image': f}
            
            response = requests.post(
                f"{self.base_url}/api/face/recognize",
                files=files,
                timeout=self.timeout
            )
            
            return response.json()
    
    def delete_face(self, user_id: int, face_id: int) -> Dict:
        """删除已注册的人脸"""
        response = requests.delete(
            f"{self.base_url}/api/face/{user_id}/{face_id}",
            timeout=self.timeout
        )
        
        return response.json()
    
    def get_device_status(self) -> Dict:
        """获取设备状态"""
        response = requests.get(
            f"{self.base_url}/api/device/status",
            timeout=self.timeout
        )
        
        return response.json()
```

在 `.env` 中添加配置：
```env
# 硬件人脸识别设备
HARDWARE_FACE_DEVICE_IP=192.168.1.100
HARDWARE_FACE_DEVICE_PORT=8000
```

在 `app/routers/hardware.py` 中使用：
```python
@router.post("/api/hardware/face/recognize")
async def recognize_face(file: UploadFile, db: Session = Depends(get_db)):
    """通过硬件设备识别人脸"""
    
    hardware_ip = getenv('HARDWARE_FACE_DEVICE_IP')
    device = HardwareFaceDevice(hardware_ip)
    
    # 保存上传的图片
    uploaded_path = save_file(file, "uploads/faces")
    
    # 调用硬件设备识别
    result = device.recognize_face(uploaded_path)
    
    if result['success']:
        user_id = result['user_id']
        confidence = result['confidence']
        
        # 查询用户并检查权限
        user = db.query(User).filter(User.id == user_id).first()
        
        if user and check_permission_valid(user, 'face_recognition', db):
            # 记录访问日志
            log = AccessLog(
                user_id=user_id,
                access_type='face',
                status='success',
                detail=f"confidence: {confidence}"
            )
            db.add(log)
            db.commit()
            
            return {
                "success": True,
                "user_id": user_id,
                "username": user.username,
                "confidence": confidence,
                "message": "人脸识别成功"
            }
    
    return {
        "success": False,
        "message": "人脸识别失败"
    }
```

---

## 配置对比

| 方案 | 成本 | 准确率 | 延迟 | 部署 | 推荐 |
|------|------|-------|------|------|------|
| **百度云 API** | 按量付费 | 95%+ | 中等 | 最简单 | ⭐ 初期 |
| **阿里云 API** | 按量付费 | 95%+ | 中等 | 简单 | ⭐ 初期 |
| **腾讯云 API** | 按量付费 | 95%+ | 中等 | 简单 | ⭐ 初期 |
| **Azure API** | 按量付费 | 95%+ | 中等 | 中等 | ⭐ 国际 |
| **DeepFace** | 免费 | 90%+ | 快 | 中等 | ⭐ 本地 |
| **硬件设备** | 高 | 98%+ | 快 | 复杂 | ⭐ 企业 |

---

## 推荐方案

### 初期（用户量小）
**推荐**: 百度或腾讯云 API
- 快速上线
- 识别准确率高
- 成本低
- 无需维护

### 中期（用户量中等）
**推荐**: DeepFace 本地部署 + 云 API 备用
- 平衡成本和性能
- 减少云 API 调用
- 提高响应速度

### 后期（用户量大）
**推荐**: 硬件设备 + 本地服务
- 最高性能
- 完全离线
- 最高可靠性

---

## 总结

**SmartAccess 的设计理念**：
- 💡 不实现人脸识别算法本身
- 💡 通过接口调用专业的识别服务
- 💡 支持多种集成方案
- 💡 灵活选择和切换

这样的设计让 SmartAccess 可以：
- ✅ 保持代码轻量级
- ✅ 利用专业的识别引擎
- ✅ 降低维护成本
- ✅ 支持快速迭代升级

**您可以根据项目实际情况，选择最合适的外部接口方案！**

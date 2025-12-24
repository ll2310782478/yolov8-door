"""
人脸识别服务模块 - 集成 face_access-v2

功能：
  1. 人脸特征提取（使用 InsightFace）
  2. 人脸相似度计算和对比
  3. 实时人脸识别（调用摄像头）
  4. 注册新人脸
  5. 人脸识别结果缓存

依赖：
  - ultralytics（YOLO）
  - opencv-python（OpenCV）
  - insightface（人脸识别）
  - numpy
  - torch
"""

import os
import json
import cv2
import numpy as np
import torch
import time
import logging
from typing import Dict, List, Tuple, Optional
from ultralytics import YOLO
import warnings

# 懒加载 insightface（解决导入问题）
insightface = None

# 抑制警告
warnings.filterwarnings('ignore', category=UserWarning)

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """人脸识别服务类"""

    def __init__(self, config_path: Optional[str] = None, model_path: Optional[str] = None):
        """
        初始化人脸识别服务

        参数:
            config_path: 配置文件路径
            model_path: YOLO 模型路径
        """
        # 初始化设备
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"🚀 使用设备: {self.device}")

        # 加载配置
        self.config = self._load_config(config_path)
        self.threshold = self.config.get("threshold", 0.7)

        # 初始化模型
        self.model = self._init_yolo_model(model_path)
        self.face_app = self._init_insightface()

        # 人脸识别缓存
        self.recognition_cache = {}
        self.cache_duration = 5  # 缓存5秒

        logger.info("✅ 人脸识别服务初始化完成")

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ 加载配置文件失败: {e}，使用默认配置")

        return {
            "threshold": 0.7,
            "api_url": "",
            "model_confidence": 0.6
        }

    def _init_yolo_model(self, model_path: Optional[str] = None) -> YOLO:
        """初始化 YOLO 人脸检测模型"""
        try:
            if model_path is None:
                # 查找 yolov8n.pt 模型文件
                possible_paths = [
                    os.path.join(os.path.dirname(__file__), '../../yolov8n.pt'),
                    'yolov8n.pt',
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        model_path = path
                        break

                if model_path is None:
                    raise FileNotFoundError("未找到 yolov8n.pt 模型文件")

            model = YOLO(model_path)
            model.to(self.device)
            logger.info("✅ YOLO 模型加载完成")
            return model
        except Exception as e:
            logger.error(f"❌ YOLO 模型加载失败: {e}")
            raise

    def _init_insightface(self):
        """初始化 InsightFace 人脸识别引擎"""
        global insightface
        try:
            # 懒加载 insightface
            if insightface is None:
                import insightface as _insightface
                insightface = _insightface
            
            face_app = insightface.app.FaceAnalysis()
            ctx_id = 0 if self.device == 'cuda' else -1
            face_app.prepare(ctx_id=ctx_id, det_size=(320, 320))
            logger.info(f"✅ InsightFace 模型加载完成（{'GPU' if ctx_id == 0 else 'CPU'} 模式）")
            return face_app
        except Exception as e:
            logger.error(f"❌ InsightFace 初始化失败: {e}")
            raise

    def extract_face_embedding(self, face_image: np.ndarray) -> Optional[np.ndarray]:
        """
        从图像中提取人脸特征向量

        参数:
            face_image: 人脸图像（OpenCV 格式）

        返回:
            特征向量（512维） 或 None（未检测到人脸）
        """
        try:
            faces = self.face_app.get(face_image)
            if len(faces) > 0:
                return faces[0].embedding
            return None
        except Exception as e:
            logger.error(f"❌ 特征提取失败: {e}")
            return None

    def compare_faces(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        计算两个人脸特征的相似度

        参数:
            embedding1: 第一个人脸特征向量
            embedding2: 第二个人脸特征向量

        返回:
            相似度（0-1 之间）
        """
        try:
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            logger.error(f"❌ 相似度计算失败: {e}")
            return 0.0

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        在图像中检测人脸

        参数:
            frame: 输入图像

        返回:
            人脸边界框列表 [(x1, y1, x2, y2), ...]
        """
        try:
            with torch.no_grad():
                results = self.model(frame, verbose=False, imgsz=320)

            boxes = []
            if len(results[0].boxes) > 0:
                xyxy = results[0].boxes.xyxy.cpu().numpy()
                conf = results[0].boxes.conf.cpu().numpy()

                for box, confidence in zip(xyxy, conf):
                    if confidence >= self.config.get("model_confidence", 0.6):
                        x1, y1, x2, y2 = map(int, box)
                        # 确保边界在图像范围内
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

                        if x2 > x1 and y2 > y1:
                            boxes.append((x1, y1, x2, y2))

            return boxes
        except Exception as e:
            logger.error(f"❌ 人脸检测失败: {e}")
            return []

    def recognize_face_in_frame(
        self,
        frame: np.ndarray,
        known_embeddings: Dict[str, np.ndarray]
    ) -> List[Dict]:
        """
        识别图像中的所有人脸

        参数:
            frame: 输入图像
            known_embeddings: 已知用户的特征向量 {用户名: 特征向量}

        返回:
            识别结果列表 [
                {
                    'name': '用户名',
                    'similarity': 0.95,
                    'box': (x1, y1, x2, y2),
                    'status': 'recognized' | 'unknown'
                }
            ]
        """
        results = []
        current_time = time.time()

        # 检测人脸
        boxes = self.detect_faces(frame)

        for box in boxes:
            x1, y1, x2, y2 = box
            face_crop = frame[y1:y2, x1:x2]

            if face_crop.size == 0:
                continue

            # 提取特征
            embedding = self.extract_face_embedding(face_crop)
            if embedding is None:
                results.append({
                    'name': 'Unknown',
                    'similarity': 0.0,
                    'box': box,
                    'status': 'no_features'
                })
                continue

            # 检查缓存
            cache_key = f"{x1}_{y1}_{x2}_{y2}"
            cached_result = self.recognition_cache.get(cache_key, {})

            if cached_result and (current_time - cached_result.get('time', 0)) < self.cache_duration:
                # 使用缓存结果
                results.append({
                    'name': cached_result['name'],
                    'similarity': cached_result['similarity'],
                    'box': box,
                    'status': 'recognized' if cached_result['similarity'] >= self.threshold else 'unknown'
                })
            else:
                # 对比已知人脸
                best_name = 'Unknown'
                best_similarity = 0.0

                for user_name, known_emb in known_embeddings.items():
                    similarity = self.compare_faces(embedding, known_emb)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        if similarity >= self.threshold:
                            best_name = user_name

                # 更新缓存
                self.recognition_cache[cache_key] = {
                    'name': best_name,
                    'similarity': best_similarity,
                    'time': current_time
                }

                results.append({
                    'name': best_name,
                    'similarity': best_similarity,
                    'box': box,
                    'status': 'recognized' if best_similarity >= self.threshold else 'unknown'
                })

        return results

    def register_face(
        self,
        frame: np.ndarray,
        user_name: str
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        从图像中注册用户人脸

        参数:
            frame: 输入图像
            user_name: 用户名

        返回:
            (成功标志, 特征向量, 消息)
        """
        try:
            # 检测人脸
            boxes = self.detect_faces(frame)
            if len(boxes) == 0:
                return False, None, "未检测到人脸"

            # 只使用第一个人脸
            x1, y1, x2, y2 = boxes[0]
            face_crop = frame[y1:y2, x1:x2]

            # 提取特征
            embedding = self.extract_face_embedding(face_crop)
            if embedding is None:
                return False, None, "无法提取人脸特征"

            return True, embedding, f"✅ {user_name} 人脸注册成功"
        except Exception as e:
            logger.error(f"❌ 人脸注册失败: {e}")
            return False, None, f"人脸注册失败: {e}"

    def clear_cache(self):
        """清空识别缓存"""
        self.recognition_cache.clear()
        logger.info("✅ 识别缓存已清空")

    def get_device_info(self) -> Dict:
        """获取设备信息"""
        info = {
            'device': self.device,
            'threshold': self.threshold,
            'cache_size': len(self.recognition_cache)
        }

        if self.device == 'cuda':
            info['gpu_name'] = torch.cuda.get_device_name(0)
            info['gpu_memory'] = f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB"

        return info

    def cleanup(self):
        """清理资源"""
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        logger.info("✅ 资源已清理")


# 全局服务实例（单例模式）
_face_service = None


def get_face_service(
    config_path: Optional[str] = None,
    model_path: Optional[str] = None
) -> FaceRecognitionService:
    """
    获取全局人脸识别服务实例

    参数:
        config_path: 配置文件路径
        model_path: YOLO 模型路径

    返回:
        人脸识别服务实例
    """
    global _face_service

    if _face_service is None:
        _face_service = FaceRecognitionService(config_path, model_path)

    return _face_service


if __name__ == "__main__":
    """测试脚本"""
    import sys

    # 创建服务实例
    service = FaceRecognitionService()

    # 打印设备信息
    print("\n设备信息:")
    for key, value in service.get_device_info().items():
        print(f"  {key}: {value}")

    # 初始化摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        sys.exit(1)

    print("\n✅ 摄像头已打开")
    print("按 'Q' 键退出\n")

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # 每 5 帧处理一次
            if frame_count % 5 != 0:
                continue

            # 检测人脸
            boxes = service.detect_faces(frame)
            frame_display = frame.copy()

            for box in boxes:
                x1, y1, x2, y2 = box
                cv2.rectangle(frame_display, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 显示 FPS
            fps = frame_count / (time.time() - start_time)
            cv2.putText(
                frame_display,
                f"FPS: {fps:.1f} | Faces: {len(boxes)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            cv2.imshow("Face Recognition Service", frame_display)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        service.cleanup()
        print("\n✅ 程序已退出")

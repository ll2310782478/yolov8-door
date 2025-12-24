import os
import json
import cv2
import numpy as np
import requests
from ultralytics import YOLO
import insightface
from db_config import load_all_users
import torch
import time

# —— 获取脚本所在目录 —— #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "api_config.json")

# —— 读取配置文件 —— #
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"配置文件未找到: {CONFIG_PATH}")

with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)

THRESHOLD = cfg.get("threshold", 0.7)
API_URL = cfg.get("api_url", "")

# —— 检查GPU可用性 —— #
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🚀 使用设备: {device}")
if device == 'cuda':
    print(f"📊 GPU信息: {torch.cuda.get_device_name()}")

# —— 初始化模型（性能优化版）—— #
try:
    # 使用更小的模型尺寸提升速度
    model = YOLO(os.path.join(BASE_DIR, "yolov8n.pt"))
    model.to(device)
    print("✅ YOLO模型加载完成")
except Exception as e:
    print(f"❌ YOLO模型加载失败: {e}")
    exit(1)

# InsightFace配置 - 抑制警告
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

try:
    face_app = insightface.app.FaceAnalysis()
    face_app.prepare(ctx_id=0, det_size=(320, 320))  # 减小检测尺寸提升速度
    print("✅ InsightFace模型加载完成（GPU模式）")
except Exception as e:
    print(f"❌ InsightFace初始化失败: {e}")
    exit(1)

# —— 加载数据库人脸 —— #
known_users = load_all_users()
print(f"✅ 已加载 {len(known_users)} 个用户人脸")

# 预计算优化
known_embeddings = []
known_names = []
known_norms = []

for name, emb in known_users.items():
    known_embeddings.append(emb)
    known_names.append(name)
    known_norms.append(np.linalg.norm(emb))

if known_embeddings:
    known_embeddings = np.array(known_embeddings)
    known_norms = np.array(known_norms)
else:
    known_embeddings = np.array([])
    known_norms = np.array([])

# —— 打开摄像头 —— #
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("无法打开摄像头")

# 设置摄像头分辨率降低以提升性能
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

print("按 Q 键退出识别")

# 性能监控
frame_count = 0
start_time = time.time()
last_log_time = time.time()

# 识别结果缓存（减少重复识别）
recognition_cache = {}
cache_duration = 5  # 缓存5秒

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ 无法读取摄像头画面")
            break

        frame_count += 1
        current_time = time.time()

        # 每0.5秒处理一帧，大幅提升响应速度
        if current_time - last_log_time < 0.2:  # 限制处理频率
            continue

        # 调整图像尺寸提升处理速度
        small_frame = cv2.resize(frame, (640, 480))
        frame_disp = small_frame.copy()

        # YOLO人脸检测（使用更小的图像尺寸）
        with torch.no_grad():
            results = model(small_frame, verbose=False, imgsz=320)  # 减小推理尺寸

        recognized_names = set()

        # 处理检测到的人脸
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()

            for i, box in enumerate(boxes):
                if confidences[i] < 0.6:  # 提高置信度阈值
                    continue

                x1, y1, x2, y2 = map(int, box)

                # 确保边界在图像范围内
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(small_frame.shape[1], x2), min(small_frame.shape[0], y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                face_crop = small_frame[y1:y2, x1:x2]

                if face_crop.size == 0:
                    continue

                # 检查缓存
                cache_key = f"{x1}_{y1}_{x2}_{y2}"
                current_cache = recognition_cache.get(cache_key, {})

                if current_cache and (current_time - current_cache.get('time', 0)) < cache_duration:
                    # 使用缓存结果
                    best_name = current_cache['name']
                    best_sim = current_cache['similarity']
                else:
                    # InsightFace特征提取
                    faces = face_app.get(face_crop)

                    if len(faces) == 0:
                        color = (0, 255, 255)
                        cv2.rectangle(frame_disp, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(frame_disp, "No Features", (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        continue

                    emb = faces[0].embedding
                    emb_norm = np.linalg.norm(emb)

                    # 批量相似度计算
                    best_name = "Unknown"
                    best_sim = 0.0

                    if len(known_embeddings) > 0:
                        similarities = np.dot(known_embeddings, emb) / (known_norms * emb_norm)
                        best_idx = np.argmax(similarities)
                        best_sim = similarities[best_idx]
                        if best_sim >= THRESHOLD:
                            best_name = known_names[best_idx]

                    # 更新缓存
                    recognition_cache[cache_key] = {
                        'name': best_name,
                        'similarity': best_sim,
                        'time': current_time
                    }

                # 识别成功
                if best_sim >= THRESHOLD:
                    color = (0, 255, 0)
                    text = f"{best_name} {best_sim:.2f}"

                    if best_name not in recognized_names:
                        recognized_names.add(best_name)
                        print(f"✅ 识别成功：{best_name}（相似度：{best_sim:.2f}）")

                        if API_URL:
                            try:
                                requests.post(API_URL,
                                              json={"user": best_name, "similarity": float(best_sim)},
                                              timeout=0.5)  # 更短的超时
                            except:
                                pass  # 静默失败，不阻塞主线程
                else:
                    color = (0, 0, 255)
                    text = f"Unknown"

                # 绘制结果
                cv2.rectangle(frame_disp, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame_disp, text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 显示FPS
        fps = frame_count / (current_time - start_time)
        cv2.putText(frame_disp, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame_disp, f"GPU: {device}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow("Face Recognition - Optimized", frame_disp)
        last_log_time = current_time

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("🛑 退出识别")
            break

except KeyboardInterrupt:
    print("🛑 用户中断程序")
except Exception as e:
    print(f"❌ 程序运行错误: {e}")
finally:
    cap.release()
    cv2.destroyAllWindows()

    if device == 'cuda':
        torch.cuda.empty_cache()

    total_time = time.time() - start_time
    print(f"📊 性能统计: 处理 {frame_count} 帧, 平均FPS: {frame_count / total_time:.1f}")
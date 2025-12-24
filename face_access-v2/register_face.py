from ultralytics import YOLO
import cv2
import insightface
from db_config import create_tables, insert_user
import numpy as np

# 初始化数据库
create_tables()

# 初始化 YOLOv8 模型（检测人脸）
model = YOLO("yolov8n.pt")

# 初始化 InsightFace
face_app = insightface.app.FaceAnalysis()
# ctx_id=-1 强制 CPU，ctx_id=0 使用 GPU（如果可用）
face_app.prepare(ctx_id=-1)

# 输入用户名
name = input("请输入录入人脸的用户名：")
cap = cv2.VideoCapture(0)

print("✅ 摄像头已打开，请按 'S' 键拍照录入，按 'Q' 键退出。")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ 无法读取摄像头画面")
        break

    results = model(frame, verbose=False)

    # 绘制检测框
    for box in results[0].boxes.xyxy.cpu().numpy():
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

    cv2.imshow("Register Face", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        if len(results[0].boxes.xyxy) == 0:
            print("❌ 未检测到人脸，请重试。")
            continue

        x1, y1, x2, y2 = map(int, results[0].boxes.xyxy[0].cpu().numpy())
        face_crop = frame[y1:y2, x1:x2]

        faces = face_app.get(face_crop)
        if len(faces) > 0:
            emb = faces[0].embedding  # numpy array
            insert_user(name, emb)
            print(f"✅ {name} 人脸录入成功！")
        else:
            print("❌ 未检测到有效人脸，请重试。")

    elif key == ord('q'):
        print("🛑 退出程序")
        break

cap.release()
cv2.destroyAllWindows()

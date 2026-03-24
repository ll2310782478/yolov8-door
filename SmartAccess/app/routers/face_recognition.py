"""
人脸识别 API 端点

功能：
  1. 上传人脸图像进行识别
  2. 获取人脸识别统计信息
  3. 清空识别缓存
  4. 获取设备信息
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from pydantic import BaseModel
import io
import cv2
import numpy as np
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, FaceData
from app.services.face_recognition import get_face_service
from app.services.qrcode_service import verify_qrcode_token
from app.auth import get_current_user, require_role, TokenData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/face-recognition", tags=["Face Recognition"])

# 复用 QR 检测器实例，避免每次请求重新创建
_qr_detector = cv2.QRCodeDetector()


# ================== Pydantic 模型 ==================

class FaceRecognitionRequest(BaseModel):
    """人脸识别请求"""
    user_id: int


class FaceRecognitionResult(BaseModel):
    """人脸识别结果"""
    name: str
    similarity: float
    status: str  # 'recognized' | 'unknown' | 'no_features' | 'no_face' | 'no_registered'
    box: tuple
    access_level: Optional[str] = "door1"
    source: Optional[str] = "face"  # 'face' | 'qrcode'
    visitor_id: Optional[int] = None  # 访客 QR 识别时携带


class FaceDeviceInfo(BaseModel):
    """人脸识别设备信息"""
    device: str
    threshold: float
    cache_size: int
    gpu_name: Optional[str] = None
    gpu_memory: Optional[str] = None


# ================== API 端点 ==================

@router.post("/recognize", response_model=List[FaceRecognitionResult])
async def recognize_faces(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    识别图像中的所有人脸

    参数:
        file: 上传的图像文件

    返回:
        识别结果列表
    """
    try:
        # 读取上传的图像
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="无效的图像文件")

        results = []
        user_access_map = {}

        # =============================================
        # 第一阶段：QR 码快速检测（优先，速度极快 ~5ms）
        # =============================================
        qr_recognized = False
        try:
            qr_data, qr_bbox, _ = _qr_detector.detectAndDecode(frame)
            if qr_data and qr_bbox is not None:
                is_valid, verify_result = verify_qrcode_token(qr_data, db, device_id="face_gate")
                if is_valid:
                    points = qr_bbox[0]
                    box = (
                        int(min(p[0] for p in points)),
                        int(min(p[1] for p in points)),
                        int(max(p[0] for p in points)),
                        int(max(p[1] for p in points)),
                    )
                    results.append({
                        "name": verify_result["visitor_name"],
                        "similarity": 1.0,
                        "status": "recognized",
                        "box": box,
                        "access_level": verify_result.get("access_level", "door1"),
                        "source": "qrcode",
                        "visitor_id": verify_result.get("visitor_id")
                    })
                    qr_recognized = True
                    logger.info(f"QR 快速识别成功: {verify_result['visitor_name']}")
                else:
                    logger.info(f"QR 验证失败: {verify_result.get('message', '')}")
        except Exception as e:
            logger.warning(f"QR 检测异常: {e}")

        # QR 码已识别成功时跳过耗时的人脸识别
        if qr_recognized:
            return [FaceRecognitionResult(
                name=results[0]['name'],
                similarity=1.0,
                status='recognized',
                box=results[0]['box'],
                access_level=results[0]['access_level'],
                source='qrcode',
                visitor_id=results[0].get('visitor_id')
            )]

        # =============================================
        # 第二阶段：人脸识别（耗时较长 ~200ms+）
        # =============================================
        face_service = get_face_service()

        # 加载已知的人脸特征
        known_embeddings = {}
        face_records = db.query(FaceData).filter(FaceData.is_active == True).all()

        for face_record in face_records:
            if face_record.embedding_data:
                user = db.query(User).filter(User.id == face_record.user_id).first()
                if user and face_record.embedding_data:
                    try:
                        embedding = np.frombuffer(face_record.embedding_data, dtype=np.float32)
                        known_embeddings[user.username] = embedding
                        user_access_map[user.username] = face_record.access_level
                    except Exception as e:
                        logger.warning(f"无法加载用户 {user.username} 的人脸特征: {e}")

        if not known_embeddings:
            return [FaceRecognitionResult(
                name='无已注册人脸',
                similarity=0.0,
                status='no_registered',
                box=(0, 0, 0, 0),
                access_level=None
            )]

        results = face_service.recognize_face_in_frame(frame, known_embeddings)

        if not results:
            return [FaceRecognitionResult(
                name='未检测到人脸',
                similarity=0.0,
                status='no_face',
                box=(0, 0, 0, 0),
                access_level=None
            )]

        # 转换为 API 响应格式
        final_results = []
        for r in results:
            access_lvl = r.get('access_level')
            if not access_lvl and r['status'] == 'recognized':
                access_lvl = user_access_map.get(r['name'], "door1")
            
            final_results.append(FaceRecognitionResult(
                name=r['name'],
                similarity=r['similarity'],
                status=r['status'],
                box=r['box'],
                access_level=access_lvl
            ))
            
        return final_results

    except Exception as e:
        logger.error(f"❌ 人脸识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"人脸识别失败: {e}")


@router.post("/register/{user_id}")
async def register_user_face(
    user_id: int,
    access_level: str = Form("door1"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """
    注册用户人脸

    参数:
        user_id: 用户 ID
        access_level: 门禁权限 (door1, door2, all)
        file: 人脸图像文件

    返回:
        注册结果
    """
    try:
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 读取上传的图像
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(status_code=400, detail="无效的图像文件")

        # 获取人脸服务
        face_service = get_face_service()

        # 注册人脸
        success, embedding, message = face_service.register_face(frame, user.username)

        if not success:
            raise HTTPException(status_code=400, detail=message)

        # 保存到数据库
        face_record = FaceData(
            user_id=user_id,
            image_path=f"faces/{user_id}_{file.filename}",
            is_primary=True,
            is_active=True,
            embedding_data=embedding.astype(np.float32).tobytes(),
            access_level=access_level
        )
        db.add(face_record)
        db.commit()

        logger.info(f"✅ 用户 {user.username} 的人脸已注册")

        return {
            "success": True,
            "message": message,
            "user_id": user_id,
            "username": user.username
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 人脸注册失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"人脸注册失败: {e}")


@router.get("/info", response_model=FaceDeviceInfo)
async def get_device_info(current_user: TokenData = Depends(require_role("admin"))):
    """
    获取人脸识别设备信息

    返回:
        设备信息（GPU/CPU、识别阈值、缓存大小等）
    """
    try:
        face_service = get_face_service()
        info = face_service.get_device_info()

        return FaceDeviceInfo(**info)

    except Exception as e:
        logger.error(f"❌ 获取设备信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取设备信息失败: {e}")


@router.post("/cache/clear")
async def clear_recognition_cache(current_user: TokenData = Depends(require_role("admin"))):
    """
    清空识别缓存

    返回:
        操作结果
    """
    try:
        face_service = get_face_service()
        face_service.clear_cache()

        return {
            "success": True,
            "message": "✅ 识别缓存已清空"
        }

    except Exception as e:
        logger.error(f"❌ 清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空缓存失败: {e}")


@router.post("/compare")
async def compare_two_faces(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    current_user: TokenData = Depends(require_role("admin")),
):
    """
    对比两张人脸的相似度

    参数:
        file1: 第一张人脸图像
        file2: 第二张人脸图像

    返回:
        相似度对比结果
    """
    try:
        face_service = get_face_service()

        # 读取第一张图像
        content1 = await file1.read()
        nparr1 = np.frombuffer(content1, np.uint8)
        frame1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)

        if frame1 is None:
            raise HTTPException(status_code=400, detail="第一张图像无效")

        # 读取第二张图像
        content2 = await file2.read()
        nparr2 = np.frombuffer(content2, np.uint8)
        frame2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)

        if frame2 is None:
            raise HTTPException(status_code=400, detail="第二张图像无效")

        # 提取特征
        emb1 = face_service.extract_face_embedding(frame1)
        emb2 = face_service.extract_face_embedding(frame2)

        if emb1 is None or emb2 is None:
            raise HTTPException(status_code=400, detail="无法提取人脸特征")

        # 计算相似度
        similarity = face_service.compare_faces(emb1, emb2)

        return {
            "similarity": float(similarity),
            "is_same_person": similarity >= face_service.threshold,
            "threshold": face_service.threshold
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 人脸对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"人脸对比失败: {e}")


@router.post("/batch-register")
async def batch_register_faces(
    user_id: int,
    access_level: str = Form("door1"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin"))
):
    """
    批量注册用户人脸

    参数:
        user_id: 用户 ID
        access_level: 门禁权限 (door1, door2, all)
        files: 多张人脸图像文件

    返回:
        批量注册结果
    """
    try:
        # 检查用户是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        face_service = get_face_service()
        results = []

        for idx, file in enumerate(files):
            try:
                # 读取图像
                content = await file.read()
                nparr = np.frombuffer(content, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is None:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "message": "无效的图像文件"
                    })
                    continue

                # 注册人脸
                success, embedding, message = face_service.register_face(frame, user.username)

                if success:
                    # 保存到数据库
                    face_record = FaceData(
                        user_id=user_id,
                        image_path=f"faces/{user_id}_{file.filename}",
                        is_primary=idx == 0,  # 第一张设为主人脸
                        is_active=True,
                        embedding_data=embedding.astype(np.float32).tobytes(),
                        access_level=access_level
                    )
                    db.add(face_record)

                    results.append({
                        "filename": file.filename,
                        "success": True,
                        "message": message
                    })
                else:
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "message": message
                    })

            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": f"处理失败: {e}"
                })

        db.commit()

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)

        logger.info(f"✅ 用户 {user.username} 批量注册完成: {success_count}/{total_count}")

        return {
            "success": success_count > 0,
            "message": f"批量注册完成: {success_count}/{total_count} 张人脸注册成功",
            "user_id": user_id,
            "username": user.username,
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 批量注册失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量注册失败: {e}")


@router.get("/health")
async def health_check():
    """
    检查人脸识别服务健康状态

    返回:
        健康状态信息
    """
    try:
        face_service = get_face_service()
        info = face_service.get_device_info()

        return {
            "status": "healthy",
            "message": "人脸识别服务运行正常",
            "device_info": info
        }

    except Exception as e:
        logger.error(f"❌ 服务检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务检查失败: {e}")

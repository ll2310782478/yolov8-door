"""用户/人脸/权限管理路由 - 增强版（集成 face_access-v2）"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, FaceData, Role, UserPermission
from app.utils import (
    check_permission_valid, check_time_period_valid, check_daily_limit,
    save_file, delete_file
)
from app.auth import get_password_hash
from app.services.face_recognition import get_face_service
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
import numpy as np
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)


# ==================== Pydantic 模型 ====================

class UserCreate(BaseModel):
    username: str
    password: str
    email: str = None
    phone: str = None
    full_name: str = None


class UserUpdate(BaseModel):
    email: str = None
    phone: str = None
    full_name: str = None
    is_active: bool = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str = None
    phone: str = None
    full_name: str = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FaceDataCreate(BaseModel):
    is_primary: bool = False
    permission_end_date: Optional[datetime] = None
    time_periods: Optional[str] = None
    max_daily_uses: int = 0


class FaceDataUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    permission_start_date: Optional[datetime] = None
    permission_end_date: Optional[datetime] = None
    time_periods: Optional[str] = None
    max_daily_uses: Optional[int] = None


class FaceDataResponse(BaseModel):
    id: int
    user_id: int
    image_path: str
    is_primary: bool
    is_active: bool
    created_at: datetime
    permission_start_date: datetime
    permission_end_date: Optional[datetime]
    max_daily_uses: int
    daily_use_count: int

    class Config:
        from_attributes = True


class UserPermissionResponse(BaseModel):
    id: int
    user_id: int
    permission_type: str
    is_enabled: bool
    start_date: datetime
    end_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 用户管理端点 ====================

@router.get("/", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    query = db.query(User)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    users = query.offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """创建用户"""
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    db_user = User(
        username=user.username,
        password_hash=get_password_hash(user.password),
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
    )
    db.add(db_user)
    db.flush()
    
    # 初始化用户权限
    permission_types = ["face_recognition", "nfc", "bluetooth", "qrcode"]
    for perm_type in permission_types:
        perm = UserPermission(
            user_id=db_user.id,
            permission_type=perm_type,
            is_enabled=True
        )
        db.add(perm)
    
    db.commit()
    db.refresh(db_user)
    return db_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """更新用户信息"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if user_update.email:
        db_user.email = user_update.email
    if user_update.phone:
        db_user.phone = user_update.phone
    if user_update.full_name:
        db_user.full_name = user_update.full_name
    if user_update.is_active is not None:
        db_user.is_active = user_update.is_active
    
    db.commit()
    db.refresh(db_user)
    return db_user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """删除用户"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 删除用户的人脸图片文件
    for face in db_user.faces:
        delete_file(face.image_path)
    
    db.delete(db_user)
    db.commit()
    return {"message": "用户已删除"}


# ==================== 人脸管理端点 ====================

@router.post("/{user_id}/faces", response_model=FaceDataResponse)
async def upload_face(
    user_id: int,
    file: UploadFile = File(...),
    is_primary: bool = False,
    permission_end_date: Optional[datetime] = None,
    max_daily_uses: int = 0,
    db: Session = Depends(get_db)
):
    """上传用户人脸 - 集成 face_access-v2 人脸识别
    
    使用 YOLOv8 + InsightFace 进行：
    1. 人脸检测 - 确保图片中存在人脸
    2. 特征提取 - 提取 512 维人脸特征向量
    3. 重复检查 - 防止上传相同人物的人脸
    4. 质量验证 - 确保人脸清晰可识别
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 检查人脸数量限制
    face_count = db.query(FaceData).filter(FaceData.user_id == user_id).count()
    import os
    max_faces = int(os.getenv("MAX_FACE_UPLOADS_PER_USER", "5"))
    if face_count >= max_faces:
        raise HTTPException(status_code=400, detail=f"每个用户最多上传 {max_faces} 张人脸照片")
    
    try:
        # 保存文件
        file_path = save_file(file)
        logger.info(f"用户 {user_id} 上传人脸文件: {file_path}")
        
        # 使用 face_access-v2 进行人脸识别和特征提取
        face_service = get_face_service()
        
        # 读取图片文件
        import cv2
        image = cv2.imread(file_path)
        if image is None:
            raise HTTPException(status_code=400, detail="无法读取图片文件")
        
        # 步骤 1: 使用 YOLOv8 检测人脸
        faces = face_service.detect_faces(image)
        if not faces or len(faces) == 0:
            logger.warning(f"用户 {user_id} 上传的图片中未检测到人脸: {file_path}")
            delete_file(file_path)
            raise HTTPException(
                status_code=400, 
                detail="图片中未检测到人脸，请上传包含清晰人脸的照片"
            )
        
        if len(faces) > 1:
            logger.warning(f"用户 {user_id} 上传的图片中检测到多张人脸: {len(faces)}")
            delete_file(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"检测到 {len(faces)} 张人脸，请上传仅包含一张人脸的照片"
            )
        
        # 步骤 2: 提取人脸特征向量
        x1, y1, x2, y2 = faces[0]
        face_crop = image[y1:y2, x1:x2]
        
        if face_crop.size == 0:
            logger.error(f"人脸裁剪失败，尺寸异常")
            delete_file(file_path)
            raise HTTPException(status_code=400, detail="人脸检测失败，请重试")
        
        # 使用 InsightFace 提取 512 维特征向量
        embedding = face_service.extract_face_embedding(face_crop)
        if embedding is None:
            logger.error(f"用户 {user_id} 人脸特征提取失败")
            delete_file(file_path)
            raise HTTPException(status_code=400, detail="无法提取人脸特征，请上传更清晰的照片")
        
        logger.info(f"成功提取用户 {user_id} 的人脸特征: {embedding.shape}")
        
        # 步骤 3: 检查用户现有人脸中是否已有相同的人
        user_faces = db.query(FaceData).filter(FaceData.user_id == user_id).all()
        for existing_face in user_faces:
            if existing_face.embedding_data:
                try:
                    existing_embedding = np.frombuffer(existing_face.embedding_data, dtype=np.float32)
                    similarity = face_service.compare_faces(embedding, existing_embedding)
                    
                    if similarity > 0.85:  # 高相似度阈值用于检测是否为同一个人
                        logger.warning(
                            f"用户 {user_id} 的新人脸与现有人脸相似度为 {similarity:.2%}，"
                            f"可能是同一个人"
                        )
                        delete_file(file_path)
                        raise HTTPException(
                            status_code=400,
                            detail=f"检测到重复的人脸（相似度 {similarity:.2%}），"
                            f"不需要重复上传同一个人的多张照片"
                        )
                except Exception as e:
                    logger.error(f"比对人脸特征时出错: {str(e)}")
        
        # 如果这是第一张人脸，自动设为主人脸
        is_primary = is_primary or (len(user.faces) == 0)
        
        # 将特征向量转换为二进制格式存储
        embedding_bytes = embedding.astype(np.float32).tobytes()
        
        # 步骤 4: 保存到数据库
        face_data = FaceData(
            user_id=user_id,
            image_path=file_path,
            embedding_data=embedding_bytes,  # 存储 InsightFace 特征向量
            is_primary=is_primary,
            permission_start_date=datetime.utcnow(),
            permission_end_date=permission_end_date,
            max_daily_uses=max_daily_uses,
        )
        db.add(face_data)
        db.commit()
        db.refresh(face_data)
        
        logger.info(
            f"用户 {user_id} 成功上传人脸，"
            f"ID: {face_data.id}, "
            f"是否主人脸: {is_primary}, "
            f"特征维度: {embedding.shape[0]}"
        )
        
        return face_data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"上传人脸时出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/{user_id}/faces", response_model=List[FaceDataResponse])
def list_user_faces(user_id: int, db: Session = Depends(get_db)):
    """获取用户的所有人脸"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    faces = db.query(FaceData).filter(FaceData.user_id == user_id).all()
    return faces


@router.get("/face/{face_id}", response_model=FaceDataResponse)
def get_face(face_id: int, db: Session = Depends(get_db)):
    """获取人脸详情"""
    face = db.query(FaceData).filter(FaceData.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="人脸不存在")
    return face


@router.put("/face/{face_id}", response_model=FaceDataResponse)
def update_face(face_id: int, face_update: FaceDataUpdate, db: Session = Depends(get_db)):
    """更新人脸信息（权限、时效等）"""
    face = db.query(FaceData).filter(FaceData.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="人脸不存在")
    
    if face_update.is_active is not None:
        face.is_active = face_update.is_active
    if face_update.is_primary is not None:
        if face_update.is_primary:
            # 取消其他人脸的主要标记
            db.query(FaceData).filter(
                FaceData.user_id == face.user_id,
                FaceData.is_primary == True,
                FaceData.id != face_id
            ).update({"is_primary": False})
        face.is_primary = face_update.is_primary
    if face_update.permission_start_date is not None:
        face.permission_start_date = face_update.permission_start_date
    if face_update.permission_end_date is not None:
        face.permission_end_date = face_update.permission_end_date
    if face_update.time_periods is not None:
        face.time_periods = face_update.time_periods
    if face_update.max_daily_uses is not None:
        face.max_daily_uses = face_update.max_daily_uses
    
    db.commit()
    db.refresh(face)
    return face


@router.delete("/{user_id}/faces/{face_id}")
def delete_face(user_id: int, face_id: int, db: Session = Depends(get_db)):
    """删除人脸"""
    face = db.query(FaceData).filter(
        FaceData.id == face_id,
        FaceData.user_id == user_id
    ).first()
    
    if not face:
        raise HTTPException(status_code=404, detail="人脸不存在")
    
    delete_file(face.image_path)
    
    db.delete(face)
    db.commit()
    return {"message": "人脸已删除"}


@router.post("/{user_id}/faces/{face_id}/check-permission")
async def check_face_permission(
    user_id: int, 
    face_id: int,
    check_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """检查人脸权限是否有效 - 支持实时人脸识别验证
    
    两种使用方式：
    1. 仅检查权限有效性 (无图片): 检查日期、时间、使用次数限制
    2. 实时识别验证 (有图片): 用新图片与存储的人脸进行比对验证
    
    参数:
    - check_image: 可选的检查图片 (JPEG/PNG)，用于实时人脸识别验证
    """
    face = db.query(FaceData).filter(
        FaceData.id == face_id,
        FaceData.user_id == user_id
    ).first()
    
    if not face:
        raise HTTPException(status_code=404, detail="人脸不存在")
    
    # 步骤 1: 检查基本权限有效性
    if not face.is_active:
        return {
            "valid": False, 
            "reason": "人脸已被禁用", 
            "face_id": face_id,
            "verified": False
        }
    
    if not check_permission_valid(face.permission_start_date, face.permission_end_date):
        return {
            "valid": False, 
            "reason": "权限已过期", 
            "face_id": face_id,
            "verified": False
        }
    
    if not check_time_period_valid(face.time_periods):
        return {
            "valid": False, 
            "reason": "不在允许的时间段内", 
            "face_id": face_id,
            "verified": False
        }
    
    if not check_daily_limit(face.max_daily_uses, face.daily_use_count, face.last_use_date):
        return {
            "valid": False, 
            "reason": "今日使用次数已达限制", 
            "face_id": face_id,
            "verified": False
        }
    
    # 步骤 2: 如果提供了检查图片，进行实时人脸识别验证
    verification_result = {
        "valid": True,
        "face_id": face_id,
        "user_id": user_id,
        "username": face.user.username,
        "verified": False,  # 是否通过人脸识别验证
        "similarity_score": None,  # 人脸相似度评分
    }
    
    if check_image is not None and face.embedding_data is not None:
        try:
            logger.info(f"执行人脸识别验证: 用户 {user_id}, 人脸 ID {face_id}")
            
            # 保存临时检查图片
            import tempfile
            import os as os_module
            temp_dir = tempfile.gettempdir()
            temp_path = os_module.join(temp_dir, f"face_check_{user_id}_{face_id}.jpg")
            
            # 从上传的文件读取内容
            content = await check_image.read()
            with open(temp_path, 'wb') as f:
                f.write(content)
            
            # 读取并处理图片
            import cv2
            check_frame = cv2.imread(temp_path)
            if check_frame is None:
                logger.error(f"无法读取检查图片: {temp_path}")
                raise HTTPException(status_code=400, detail="无法读取检查图片")
            
            # 使用 face_access-v2 进行人脸识别
            face_service = get_face_service()
            
            # 检测检查图片中的人脸
            check_faces = face_service.detect_faces(check_frame)
            if not check_faces:
                logger.warning(f"检查图片中未检测到人脸")
                # 清理临时文件
                try:
                    os_module.remove(temp_path)
                except:
                    pass
                verification_result["verified"] = False
                verification_result["verification_reason"] = "检查图片中未检测到人脸"
                return verification_result
            
            # 提取检查图片中的人脸特征
            x1, y1, x2, y2 = check_faces[0]
            check_face_crop = check_frame[y1:y2, x1:x2]
            check_embedding = face_service.extract_face_embedding(check_face_crop)
            
            if check_embedding is None:
                logger.error(f"无法提取检查图片的人脸特征")
                # 清理临时文件
                try:
                    os_module.remove(temp_path)
                except:
                    pass
                verification_result["verified"] = False
                verification_result["verification_reason"] = "无法提取人脸特征"
                return verification_result
            
            # 从数据库恢复存储的人脸特征向量
            stored_embedding = np.frombuffer(face.embedding_data, dtype=np.float32)
            
            # 步骤 3: 比对两个特征向量
            similarity = face_service.compare_faces(check_embedding, stored_embedding)
            logger.info(f"人脸识别结果: 相似度 = {similarity:.4f}")
            
            verification_result["similarity_score"] = float(similarity)
            
            # 判断是否匹配 (使用 0.7 作为识别阈值)
            RECOGNITION_THRESHOLD = 0.7
            if similarity >= RECOGNITION_THRESHOLD:
                verification_result["verified"] = True
                verification_result["verification_reason"] = (
                    f"人脸识别成功 (相似度: {similarity:.2%})"
                )
                logger.info(f"用户 {user_id} 人脸识别验证通过")
            else:
                verification_result["verified"] = False
                verification_result["verification_reason"] = (
                    f"人脸不匹配 (相似度: {similarity:.2%}，需要 >= {RECOGNITION_THRESHOLD:.0%})"
                )
                logger.warning(f"用户 {user_id} 人脸识别验证失败")
            
            # 清理临时文件
            try:
                os_module.remove(temp_path)
            except:
                pass
                
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"人脸识别验证过程中出错: {str(e)}", exc_info=True)
            verification_result["verified"] = False
            verification_result["verification_reason"] = f"验证过程出错: {str(e)}"
    
@router.post("/{user_id}/faces/recognize-from-image")
async def recognize_face_from_image(
    user_id: int,
    image: UploadFile = File(...),
    similarity_threshold: float = 0.7,
    db: Session = Depends(get_db)
):
    """使用 face_access-v2 进行实时人脸识别 - 识别指定用户上传的人脸
    
    流程:
    1. 上传一张包含人脸的图片
    2. 提取该图片中的人脸特征
    3. 与用户的所有已注册人脸进行比对
    4. 返回匹配的人脸及相似度评分
    
    参数:
    - user_id: 要识别的用户 ID
    - image: 包含人脸的图片文件 (JPEG/PNG)
    - similarity_threshold: 相似度阈值 (0-1)，超过此值认为是匹配 (默认 0.7)
    
    返回:
    - matched_faces: 匹配的人脸列表 (按相似度降序排列)
    - unmatched: 是否为未注册的人脸
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    try:
        logger.info(f"开始识别用户 {user_id} 的人脸，阈值: {similarity_threshold}")
        
        # 保存临时图片文件
        import tempfile
        import os as os_module
        temp_dir = tempfile.gettempdir()
        temp_path = os_module.path.join(temp_dir, f"recognize_{user_id}.jpg")
        
        content = await image.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # 读取图片
        import cv2
        frame = cv2.imread(temp_path)
        if frame is None:
            raise HTTPException(status_code=400, detail="无法读取图片文件")
        
        # 使用 face_access-v2 的人脸检测和识别
        face_service = get_face_service()
        
        # 步骤 1: 检测图片中的所有人脸
        detected_faces = face_service.detect_faces(frame)
        if not detected_faces:
            logger.info(f"图片中未检测到人脸")
            # 清理临时文件
            try:
                os_module.remove(temp_path)
            except:
                pass
            return {
                "user_id": user_id,
                "recognized": False,
                "message": "图片中未检测到人脸",
                "matched_faces": [],
                "unmatched": True
            }
        
        logger.info(f"检测到 {len(detected_faces)} 张人脸")
        
        # 步骤 2: 对于每一张检测到的人脸，提取特征并比对
        results = {
            "user_id": user_id,
            "recognized": False,
            "total_detected_faces": len(detected_faces),
            "matched_faces": [],
            "unmatched": True,
        }
        
        # 获取用户的所有已注册人脸
        user_faces = db.query(FaceData).filter(
            FaceData.user_id == user_id,
            FaceData.is_active == True,
            FaceData.embedding_data is not None
        ).all()
        
        if not user_faces:
            logger.warning(f"用户 {user_id} 未注册任何人脸")
            # 清理临时文件
            try:
                os_module.remove(temp_path)
            except:
                pass
            results["message"] = "用户未注册任何人脸"
            return results
        
        logger.info(f"用户已注册 {len(user_faces)} 张人脸")
        
        # 对检测到的每张人脸进行识别
        for face_idx, (x1, y1, x2, y2) in enumerate(detected_faces):
            try:
                # 提取人脸特征
                face_crop = frame[y1:y2, x1:x2]
                if face_crop.size == 0:
                    continue
                
                embedding = face_service.extract_face_embedding(face_crop)
                if embedding is None:
                    continue
                
                # 与用户的每张已注册人脸比对
                face_matches = []
                for db_face in user_faces:
                    stored_embedding = np.frombuffer(db_face.embedding_data, dtype=np.float32)
                    similarity = face_service.compare_faces(embedding, stored_embedding)
                    
                    if similarity >= similarity_threshold:
                        face_matches.append({
                            "face_id": db_face.id,
                            "similarity": float(similarity),
                            "is_primary": db_face.is_primary,
                            "registered_at": db_face.created_at.isoformat() if db_face.created_at else None,
                        })
                
                # 按相似度排序
                face_matches.sort(key=lambda x: x["similarity"], reverse=True)
                
                if face_matches:
                    results["matched_faces"].extend(face_matches)
                    results["recognized"] = True
                    results["unmatched"] = False
                    logger.info(f"检测的人脸 {face_idx} 匹配，最高相似度: {face_matches[0]['similarity']:.4f}")
                else:
                    logger.warning(f"检测的人脸 {face_idx} 未匹配任何已注册的人脸")
                    
            except Exception as e:
                logger.error(f"处理检测的人脸 {face_idx} 时出错: {str(e)}")
                continue
        
        # 对匹配结果按相似度排序 (全局)
        results["matched_faces"].sort(key=lambda x: x["similarity"], reverse=True)
        
        if results["matched_faces"]:
            results["message"] = f"识别到 {len(results['matched_faces'])} 张匹配的人脸"
            results["top_match"] = results["matched_faces"][0]
        else:
            results["message"] = "图片中的人脸未能与任何已注册的人脸匹配"
        
        logger.info(f"用户 {user_id} 人脸识别完成: {results['message']}")
        
        # 清理临时文件
        try:
            os_module.remove(temp_path)
        except:
            pass
        
        return results
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"人脸识别过程中出错: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


# ==================== 权限管理端点 ====================

@router.get("/{user_id}/permissions", response_model=List[UserPermissionResponse])
def get_user_permissions(user_id: int, db: Session = Depends(get_db)):
    """获取用户权限列表"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    permissions = db.query(UserPermission).filter(UserPermission.user_id == user_id).all()
    return permissions


@router.put("/permission/{permission_id}")
def update_permission(
    permission_id: int,
    is_enabled: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    time_periods: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """更新用户权限"""
    perm = db.query(UserPermission).filter(UserPermission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="权限不存在")
    
    if is_enabled is not None:
        perm.is_enabled = is_enabled
    if start_date is not None:
        perm.start_date = start_date
    if end_date is not None:
        perm.end_date = end_date
    if time_periods is not None:
        perm.time_periods = time_periods
    
    db.commit()
    db.refresh(perm)
    return perm


@router.post("/{user_id}/permissions/batch-update")
def batch_update_permissions(
    user_id: int,
    permission_updates: dict,
    db: Session = Depends(get_db)
):
    """批量更新用户权限"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    updated = []
    for perm_type, updates in permission_updates.items():
        perm = db.query(UserPermission).filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_type == perm_type
        ).first()
        
        if perm:
            if "is_enabled" in updates:
                perm.is_enabled = updates["is_enabled"]
            if "end_date" in updates:
                perm.end_date = updates["end_date"]
            db.commit()
            updated.append(perm_type)
    
    return {
        "message": "权限已更新",
        "updated_count": len(updated),
        "updated_types": updated
    }

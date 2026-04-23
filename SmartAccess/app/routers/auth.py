"""认证路由 - 管理员登录"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, noload
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import User
from app.auth import (
    LoginRequest, LoginResponse, Token, TokenData,
    verify_password, create_access_token,
    decode_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    get_password_hash, get_current_user, require_role
)

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    password: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None


class RegisterResponse(BaseModel):
    """注册响应模型"""
    code: int
    message: str
    data: Optional[dict] = None


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    管理员登录端点
    
    需要提供用户名和密码，返回 JWT 访问令牌
    
    ```json
    {
      "username": "admin",
      "password": "admin@123456"
    }
    ```
    """
    username = request.username
    password = request.password
    # 查询用户（防止加载包含二进制数据的关系）
    user = db.query(User).options(noload(User.faces)).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码（支持 bcrypt hash 及明文兜底）
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "role": user.user_role},
        expires_delta=access_token_expires
    )
    
    # 直接返回JSON而不使用response_model以避免Pydantic序列化问题
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "登录成功",
            "data": {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "username": user.username
            }
        }
    )


@router.post("/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    用户注册端点（公开）

    通过用户名/密码注册账户，可选填写邮箱、电话和姓名。
    注册后账户默认为待审核状态（is_active=False），需管理员审核激活并分配角色。
    """
    # 用户名重复检查
    existing_user = db.query(User).options(noload(User.faces)).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被占用"
        )

    # 邮箱重复检查（如果填写）
    if request.email:
        email_used = db.query(User).options(noload(User.faces)).filter(User.email == request.email).first()
        if email_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

    db_user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        email=request.email,
        phone=request.phone,
        full_name=request.full_name,
        is_active=False,
        user_role="access_user",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return RegisterResponse(
        code=200,
        message="注册成功，请等待管理员审核激活",
        data={"user_id": db_user.id, "username": db_user.username}
    )


@router.post("/logout")
async def logout():
    """
    注销端点
    
    前端应删除本地保存的令牌
    """
    return {
        "code": 200,
        "message": "注销成功"
    }


@router.get("/me")
async def get_me(request: Request, db: Session = Depends(get_db)):
    """
    获取当前登录用户信息
    
    需要在请求头中提供令牌：Authorization: Bearer <token>
    """
    # 从 Authorization header 提取 Bearer token
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_token(token)
    if token_data is None or token_data.username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).options(noload(User.faces)).filter(User.username == token_data.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "role": user.user_role,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }

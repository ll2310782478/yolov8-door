"""应用启动入口"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database import engine, Base, get_db, init_db
from app.models import User, Role, UserPermission
from app.routers import users, hardware, visitors, face_recognition, auth, web

# 加载环境变量
load_dotenv()

# 创建数据库表
init_db()

# 创建 FastAPI 应用
app = FastAPI(
    title=os.getenv("APP_NAME", "SmartAccess"),
    description="智能人脸识别门禁系统 API - 支持人脸、NFC、蓝牙、二维码多种门禁方式",
    version="2.0.0",
)

# 挂载静态文件（包含CSS/JS和上传文件）
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# 挂载上传文件目录（二维码、人脸图片等）
app.mount("/uploads", StaticFiles(directory="static"), name="uploads")

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(hardware.router)
app.include_router(visitors.router)
app.include_router(face_recognition.router)
app.include_router(web.router)


# ==================== 网页路由 ====================

@app.get("/", response_class=HTMLResponse)
def read_root():
    """系统首页 - 直接显示登录页"""
    template_path = Path(__file__).parent / "templates" / "auth.html"
    if template_path.exists():
        return HTMLResponse(template_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Error: auth.html not found</h1>", status_code=404)


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "message": "SmartAccess is running", "version": "2.0.0"}


# ==================== 初始化事件 ====================

@app.on_event("startup")
def startup_event():
    """应用启动事件"""
    # 注意：启动事件中 bcrypt 可能有兼容性问题，因此禁用自动创建默认用户
    # 生产环境应手动创建管理员账户或使用数据库迁移工具
    
    print("✅ SmartAccess v2.0 应用已启动")
    print("📖 API 文档: http://localhost:8000/docs")
    print("🔗 数据库: " + os.getenv("DATABASE_URL", "sqlite:///./smartaccess.db"))
    print("⚠️  首次运行时，请访问 /api/docs 查看 API 文档并创建用户")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "False") == "True",
    )

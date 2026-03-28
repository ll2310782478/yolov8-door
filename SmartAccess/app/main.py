"""应用启动入口"""

import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import traceback

from app.database import engine, Base, get_db, init_db
from app.models import User, Role, UserPermission
from app.routers import users, hardware, visitors, face_recognition, auth, web, system

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
app.include_router(system.router)


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


# ==================== 全局异常处理 ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "HTTPException"
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常（422 错误）"""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": 422,
                "message": "请求参数验证失败",
                "type": "RequestValidationError",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """处理 500 内部服务器错误"""
    # 记录详细错误日志
    error_trace = traceback.format_exc()
    print(f"❌ Internal Server Error: {error_trace}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": "服务器内部错误，请稍后重试",
                "type": "InternalServerError"
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理其他所有未捕获的异常"""
    # 记录详细错误日志
    error_trace = traceback.format_exc()
    print(f"❌ Unhandled Exception: {error_trace}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": f"发生未知错误：{str(exc)}",
                "type": "GeneralException"
            }
        }
    )


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


@app.on_event("shutdown")
def shutdown_event():
    """应用关闭事件"""
    pass


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "False") == "True",
    )

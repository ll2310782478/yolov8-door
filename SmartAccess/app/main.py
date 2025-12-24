"""应用启动入口"""

import os
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

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    """系统首页"""
    return """
    <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SmartAccess - 智能人脸识别门禁系统</title>
            <style>
                body { 
                    font-family: 'Microsoft YaHei', Arial, sans-serif; 
                    margin: 0;
                    padding: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }
                .navbar {
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 1rem 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .navbar h1 {
                    margin: 0;
                    font-size: 1.5rem;
                }
                .nav-links {
                    display: flex;
                    gap: 2rem;
                    list-style: none;
                }
                .nav-links a {
                    color: white;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                    transition: background 0.3s;
                }
                .nav-links a:hover {
                    background: rgba(255,255,255,0.2);
                }
                .container {
                    max-width: 1200px;
                    margin: 3rem auto;
                    padding: 0 2rem;
                }
                .hero {
                    background: white;
                    border-radius: 8px;
                    padding: 3rem;
                    text-align: center;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                .hero h1 {
                    color: #333;
                    font-size: 2rem;
                    margin-bottom: 1rem;
                }
                .hero p {
                    color: #666;
                    font-size: 1.1rem;
                    margin-bottom: 2rem;
                }
                .buttons {
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    flex-wrap: wrap;
                }
                .btn {
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 1rem;
                    text-decoration: none;
                    transition: transform 0.2s;
                }
                .btn:hover {
                    transform: translateY(-2px);
                }
                .btn-primary {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .btn-secondary {
                    background: #f0f0f0;
                    color: #333;
                }
                .features {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 2rem;
                    margin-top: 3rem;
                }
                .feature-card {
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    text-align: center;
                }
                .feature-card h3 {
                    color: #667eea;
                    margin-bottom: 1rem;
                }
                .feature-card p {
                    color: #666;
                    line-height: 1.6;
                }
                footer {
                    background: rgba(0,0,0,0.8);
                    color: white;
                    text-align: center;
                    padding: 2rem;
                    margin-top: 4rem;
                }
            </style>
        </head>
        <body>
            <div class="navbar">
                <h1>🔐 SmartAccess</h1>
                <ul class="nav-links">
                    <li><a href="/">首页</a></li>
                    <li><a href="/web/auth">登录/注册</a></li>
                    <li><a href="/docs">API 文档</a></li>
                </ul>
            </div>
            
            <div class="container">
                <div class="hero">
                    <h1>SmartAccess</h1>
                    <p>智能人脸识别门禁系统 v2.0 - 支持多种门禁方式</p>
                    
                    <div class="buttons">
                        <a href="/web/auth" class="btn btn-primary">🔐 登录 / 注册</a>
                        <a href="/web/dashboard" class="btn btn-secondary">🖥️ 管理界面</a>
                        <a href="/docs" class="btn btn-secondary">📖 API 文档</a>
                        <a href="/redoc" class="btn btn-secondary">📚 ReDoc</a>
                    </div>
                </div>
                
                <div class="features">
                    <div class="feature-card">
                        <h3>👥 用户管理</h3>
                        <p>完整的用户生命周期管理，支持人脸注册和权限分配</p>
                    </div>
                    <div class="feature-card">
                        <h3>🔍 人脸识别</h3>
                        <p>高精度人脸识别，支持权限时效和每日使用限制</p>
                    </div>
                    <div class="feature-card">
                        <h3>🏷️ NFC 卡片</h3>
                        <p>NFC 卡片管理，支持权限时效、时间段限制</p>
                    </div>
                    <div class="feature-card">
                        <h3>🔵 蓝牙设备</h3>
                        <p>蓝牙设备配对和远程开锁，实时状态同步</p>
                    </div>
                    <div class="feature-card">
                        <h3>👤 访客管理</h3>
                        <p>访客二维码快速登记，邮件/短信发送权限</p>
                    </div>
                    <div class="feature-card">
                        <h3>📝 完整日志</h3>
                        <p>详细记录每次访问，支持多维度统计分析</p>
                    </div>
                </div>
            </div>
            
            <footer>
                <p>&copy; 2024 SmartAccess. All rights reserved.</p>
                <p>数据库类型: MySQL | 版本: 2.0.0</p>
            </footer>
        </body>
    </html>
    """


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

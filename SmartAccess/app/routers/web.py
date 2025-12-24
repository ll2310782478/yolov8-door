"""简单的网页路由，用于提供基于表单的登录/注册入口和管理界面"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter(
    prefix="/web",
    tags=["web"],
)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def load_template(filename: str) -> HTMLResponse:
    """读取模板文件并返回 HTML 响应"""
    path = TEMPLATE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="页面不存在")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/auth", response_class=HTMLResponse)
def web_auth_page():
    """登录/注册页面"""
    return load_template("auth.html")


@router.get("/dashboard", response_class=HTMLResponse)
def web_dashboard():
    """登录后控制台按钮页"""
    return load_template("dashboard.html")


@router.get("/users", response_class=HTMLResponse)
def web_users():
    """用户管理页面"""
    return load_template("users.html")


@router.get("/visitors", response_class=HTMLResponse)
def web_visitors():
    """访客管理页面"""
    return load_template("visitors.html")


@router.get("/face", response_class=HTMLResponse)
def web_face():
    """人脸识别管理页面"""
    return load_template("face.html")


@router.get("/hardware", response_class=HTMLResponse)
def web_hardware():
    """硬件管理页面"""
    return load_template("hardware.html")


@router.get("/nfc", response_class=HTMLResponse)
def web_nfc():
    """NFC 管理页面"""
    return load_template("nfc.html")


@router.get("/logs", response_class=HTMLResponse)
def web_logs():
    """访问日志页面"""
    return load_template("logs.html")


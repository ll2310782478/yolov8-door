"""修复auth.py中的 /me端点以支持Authorization Header"""

with open(r'app\routers\auth.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 定义要插入的新代码（在router 定义之后）
new_dependency = '''

async def get_current_user_from_header(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """
    从Authorization头部获取当前用户
    
    期望格式：Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 提取 Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证格式错误，应为：Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    token_data = decode_token(token)
    
    if token_data is None or token_data.username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    return user

'''

# 找到router定义的位置，在其后插入新函数
marker = 'responses={404: {"description": "Not found"}},\n)'
if marker in content:
    content = content.replace(marker, marker + '\n' + new_dependency.strip())
else:
    print(f"警告：未找到标记 '{marker}'")

# 替换旧的 /me端点实现
old_me_endpoint = '''@router.get("/me")
async def get_current_user(token: str = None, db: Session = Depends(get_db)):
    """
    获取当前登录用户信息
    
    需要在请求头中提供令牌：Authorization: Bearer <token>
    """
    if not token:
        # 尝试从请求头获取
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
    
    user = db.query(User).filter(User.username == token_data.username).first()
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
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }'''

new_me_endpoint = '''@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user_from_header)):
    """
    获取当前登录用户信息
    
    需要在请求头中提供令牌：Authorization: Bearer <token>
    """
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "phone": current_user.phone,
            "full_name": current_user.full_name,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        }
    }'''

if old_me_endpoint in content:
    content = content.replace(old_me_endpoint, new_me_endpoint)
    print("✓ 已更新 /me端点")
else:
    print("✗ 未找到旧的 /me端点代码")

with open(r'app\routers\auth.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ auth.py修复完成！")

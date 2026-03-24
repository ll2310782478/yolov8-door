#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix /me endpoint in auth.py to support Authorization Header"""

filepath = 'app/routers/auth.py'

with open(filepath, 'r', encoding='latin-1') as f:
    content = f.read()

# Add Optional import if not present
if 'from typing import Optional' not in content and 'Optional' not in content:
    # Find existing imports and add Optional
    if 'from fastapi import' in content:
        content = content.replace(
            'from fastapi import APIRouter, Depends, HTTPException, status, Header',
            'from fastapi import APIRouter, Depends, HTTPException, status, Header\nfrom typing import Optional'
        )

# New dependency function
new_func = '''

async def get_current_user_from_header(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息", headers={"WWW-Authenticate": "Bearer"})
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证格式错误", headers={"WWW-Authenticate": "Bearer"})
    
    token = parts[1]
    token_data = decode_token(token)
    
    if token_data is None or token_data.username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌", headers={"WWW-Authenticate": "Bearer"})
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")
    
    return user

'''

# Insert after router definition
if '@router.get("/me")' in content and 'get_current_user_from_header' not in content:
    marker = 'responses={404: {"description": "Not found"}},\n)'
    if marker in content:
        idx = content.find(marker) + len(marker)
        content = content[:idx] + '\n' + new_func + content[idx:]

# Replace old /me endpoint
old_pattern = '''@router.get("/me")
async def get_current_user(token: str = None, db: Session = Depends(get_db)):'''

new_pattern = '''@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user_from_header)):'''

if old_pattern in content:
    # Extract just the signature replacement
    content = content.replace(old_pattern, new_pattern)
    
    # Now remove the manual token checking code - find everything between signature and return statement
    lines = content.split('\n')
    new_lines = []
    skip_until_return = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if '@router.get("/me")' in line or 'async def get_me(' in line:
            new_lines.append(line)
            skip_until_return = True
            i += 1
            continue
        
        if skip_until_return:
            # Skip until we find the return statement with user data
            if 'return {' in line and '"code": 200' in line:
                skip_until_return = False
                # Add the return block
                new_lines.append('    return {')
                new_lines.append('        "code": 200,')
                new_lines.append('        "message": "获取成功",')
                new_lines.append('        "data": {')
                new_lines.append('            "id": current_user.id,')
                new_lines.append('            "username": current_user.username,')
                new_lines.append('            "email": current_user.email,')
                new_lines.append('            "phone": current_user.phone,')
                new_lines.append('            "full_name": current_user.full_name,')
                new_lines.append('            "is_active": current_user.is_active,')
                new_lines.append('            "created_at": current_user.created_at.isoformat() if current_user.created_at else None')
                new_lines.append('        }')
                new_lines.append('    }')
                
                # Skip ahead past the old return block
                brace_count = 1
                i += 1
                while i < len(lines) and brace_count > 0:
                    if '{' in lines[i]:
                        brace_count += lines[i].count('{')
                    if '}' in lines[i]:
                        brace_count -= lines[i].count('}')
                    i += 1
                continue
            else:
                i += 1
                continue
        
        new_lines.append(line)
        i += 1
    
    content = '\n'.join(new_lines)

with open(filepath, 'w', encoding='latin-1') as f:
    f.write(content)

print("✓ auth.py fixed!")

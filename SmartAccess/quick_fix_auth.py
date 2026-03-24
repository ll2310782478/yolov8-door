#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simple fix for /me endpoint"""

filepath = 'app/routers/auth.py'

with open(filepath, 'r', encoding='latin-1') as f:
    content = f.read()

# Add Optional import if needed
if 'Optional' not in content:
    content = content.replace(
        'from fastapi import APIRouter, Depends, HTTPException, status, Header',
        'from fastapi import APIRouter, Depends, HTTPException, status, Header\nfrom typing import Optional'
    )

# New dependency function to add
new_func = '''

async def get_current_user_from_header(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth", headers={"WWW-Authenticate": "Bearer"})
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid format", headers={"WWW-Authenticate": "Bearer"})
    token = parts[1]
    token_data = decode_token(token)
    if token_data is None or token_data.username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"})
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    return user

'''

# Insert after router definition
marker = 'responses={404: {"description": "Not found"}},'
if marker in content and 'get_current_user_from_header' not in content:
    idx = content.find(marker) + len(marker)
    # Skip the closing paren and newline
    while idx < len(content) and content[idx] in ['\n', ')']:
        idx += 1
    content = content[:idx] + '\n' + new_func + content[idx:]

# Replace old signature with new one
old_sig = '@router.get("/me")\nasync def get_current_user(token: str = None, db: Session = Depends(get_db)):'
new_sig = '@router.get("/me")\nasync def get_me(current_user: User = Depends(get_current_user_from_header)):'

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    
    # Simplify body - remove manual token checks, use current_user directly
    # Find the function body and simplify it
    start_marker = 'async def get_me(current_user: User = Depends(get_current_user_from_header)):'
    end_marker = 'return {\n        "code": 200,'
    
    if start_marker in content and end_marker in content:
        start_idx = content.find(start_marker) + len(start_marker)
        end_idx = content.find(end_marker)
        
        # Everything between start and end should be replaced with just docstring
        new_body = '''\n    """Get current logged-in user info."""\n    '''
        content = content[:start_idx] + new_body + content[end_idx:]

with open(filepath, 'w', encoding='latin-1', errors='replace') as f:
    f.write(content)

print("Done! auth.py updated.")

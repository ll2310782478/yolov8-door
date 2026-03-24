#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix duplicate else statements in logs.html"""

FILE_PATH = 'app/templates/logs.html'

def main():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the duplicate else statement
    old_code = """if (!token) { window.location.href = '/web/auth'; }
        else {
            document.getElementById('welcome').textContent = username ? `你好，${username}` : '已登录';
            initDatePickers();  // 初始化日期选择器
        }
        else { document.getElementById('welcome').textContent = username ? `你好，${username}` : '已登录'; }"""
    
    new_code = """if (!token) { 
            window.location.href = '/web/auth'; 
        } else {
            document.getElementById('welcome').textContent = username ? `你好，${username}` : '已登录';
            initDatePickers();  // 初始化日期选择器
        }"""
    
    content = content.replace(old_code, new_code)
    
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Successfully fixed {FILE_PATH}')

if __name__ == '__main__':
    main()

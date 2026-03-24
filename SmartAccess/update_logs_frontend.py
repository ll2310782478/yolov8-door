#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update logs.html to add date range picker"""

FILE_PATH = 'app/templates/logs.html'

def main():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the days input with date range pickers
    old_html = '''                <div>
                    <label>天数</label>
                    <input id="daysInput" type="number" min="1" max="30" value="7" style="width:90px;" 
                           onchange="validateDaysInput()" oninput="validateDaysInput()">
                </div>'''
    
    new_html = '''                <div>
                    <label>开始日期</label>
                    <input id="startDateInput" type="date" style="width:140px;">
                </div>
                <div>
                    <label>结束日期</label>
                    <input id="endDateInput" type="date" style="width:140px;">
                </div>'''
    
    content = content.replace(old_html, new_html)
    
    # Update the loadLogs function to use date parameters
    old_load = '''        async function loadLogs() {
            const type = document.getElementById('typeFilter').value;
            const statusF = document.getElementById('statusFilter').value;
            const days = validateDaysInput();  // 使用验证后的值
            const params = new URLSearchParams();
            params.set('days', days);
            if (type) params.set('access_type', type);
            if (statusF) params.set('status', statusF);'''
    
    new_load = '''        async function loadLogs() {
            const type = document.getElementById('typeFilter').value;
            const statusF = document.getElementById('statusFilter').value;
            const startDate = document.getElementById('startDateInput').value;
            const endDate = document.getElementById('endDateInput').value;
            const params = new URLSearchParams();
            if (startDate) params.set('start_date', startDate);
            if (endDate) params.set('end_date', endDate);
            if (type) params.set('access_type', type);
            if (statusF) params.set('status', statusF);'''
    
    content = content.replace(old_load, new_load)
    
    # Remove or comment out the validateDaysInput function since we no longer need it
    old_validate = '''        /**
         * 验证天数输入
         */
        function validateDaysInput() {
            const input = document.getElementById('daysInput');
            let value = parseInt(input.value);
            
            if (isNaN(value) || value < 1) {
                value = 1;
            } else if (value > 30) {
                value = 30;
            }
            
            if (input.value !== value.toString()) {
                input.value = value;
                showToast('天数范围：1-30天', 'warning');
            }
            
            return value;
        }
        '''
    
    new_validate = '''        /**
         * 初始化日期选择器的默认值
         */
        function initDatePickers() {
            const today = new Date();
            const sevenDaysAgo = new Date(today);
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            
            const startDateInput = document.getElementById('startDateInput');
            const endDateInput = document.getElementById('endDateInput');
            
            // 设置默认值：最近7 天
            endDateInput.value = today.toISOString().split('T')[0];
            startDateInput.value = sevenDaysAgo.toISOString().split('T')[0];
        }
        
        /**
         * 验证旧的days 输入（保留以兼容旧代码引用）
         */
        function validateDaysInput() {
            return 7;  // 默认值，实际不再使用
        }
        '''
    
    content = content.replace(old_validate, new_validate)
    
    # Initialize date pickers when page loads
    old_init = "if (!token) { window.location.href = '/web/auth'; }"
    new_init = """if (!token) { window.location.href = '/web/auth'; }
        else {
            document.getElementById('welcome').textContent = username ? `你好，${username}` : '已登录';
            initDatePickers();  // 初始化日期选择器
        }"""
    
    content = content.replace(old_init, new_init)
    
    # Also update exportCsv function to use date parameters
    old_export = '''        async function exportCsv() {
            const type = document.getElementById('typeFilter').value;
            const statusF = document.getElementById('statusFilter').value;
            const days = validateDaysInput();  // 使用验证后的值
            const params = new URLSearchParams();
            params.set('days', days);
            if (type) params.set('access_type', type);
            if (statusF) params.set('status', statusF);'''
    
    new_export = '''        async function exportCsv() {
            const type = document.getElementById('typeFilter').value;
            const statusF = document.getElementById('statusFilter').value;
            const startDate = document.getElementById('startDateInput').value;
            const endDate = document.getElementById('endDateInput').value;
            const params = new URLSearchParams();
            if (startDate) params.set('start_date', startDate);
            if (endDate) params.set('end_date', endDate);
            if (type) params.set('access_type', type);
            if (statusF) params.set('status', statusF);'''
    
    content = content.replace(old_export, new_export)
    
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Successfully updated {FILE_PATH}')

if __name__ == '__main__':
    main()

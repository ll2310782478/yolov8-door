#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add initDatePickers function to logs.html"""

FILE_PATH = 'app/templates/logs.html'

def main():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the initDatePickers function before loadLogs
    old_script = """        async function loadLogs() {"""
    
    new_script = """        /**
         * 初始化日期选择器的默认值（最近 7 天）
         */
        function initDatePickers() {
            const today = new Date();
            const sevenDaysAgo = new Date(today);
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            
            const startDateInput = document.getElementById('startDateInput');
            const endDateInput = document.getElementById('endDateInput');
            
            // 设置默认值：最近 7天
            endDateInput.value = today.toISOString().split('T')[0];
            startDateInput.value = sevenDaysAgo.toISOString().split('T')[0];
        }
        
        async function loadLogs() {"""
    
    content = content.replace(old_script, new_script)
    
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Successfully added initDatePickers function to {FILE_PATH}')

if __name__ == '__main__':
    main()

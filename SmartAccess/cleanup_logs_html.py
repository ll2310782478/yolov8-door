#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Clean up logs.html - remove obsolete validateDaysInput function"""

FILE_PATH = 'app/templates/logs.html'

def main():
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove the old validateDaysInput function completely
    old_function = """        
        /**
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
                showToast('天数范围：1-30 天', 'warning');
            }
            
            return value;
        }
        """
    
    # Replace with empty string to remove it
    content = content.replace(old_function, '')
    
    # Also fix any remaining references to validateDaysInput in comments
    content = content.replace('// 使用验证后的值', '// 使用日期范围参数')
    
    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'Successfully cleaned up {FILE_PATH}')

if __name__ == '__main__':
    main()

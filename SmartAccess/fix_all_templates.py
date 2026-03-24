import os
from pathlib import Path

# Fix localStorage key inconsistency in ALL HTML files
template_dir = Path('app/templates')
all_html_files = list(template_dir.glob('*.html'))

fixed_count = 0

for file_path in all_html_files:
    # Skip backup/corrupted files
    if 'backup' in str(file_path) or 'old' in str(file_path) or 'broken' in str(file_path):
        print(f"⚠️  Skipping backup/broken file: {file_path.name}")
        continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace smartaccess_token with token
    old_content = content
    content = content.replace("'smartaccess_token'", "'token'")
    content = content.replace('"smartaccess_token"', '"token"')
    content = content.replace("'smartaccess_username'", "'username'")
    content = content.replace('"smartaccess_username"', '"username"')
    
    if old_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed: {file_path.name}")
        fixed_count += 1
    else:
        print(f"ℹ️  OK: {file_path.name}")

print(f"\n{'='*60}")
print(f"✅ COMPLETED: Fixed {fixed_count} file(s)")
print("   All active templates now use:")
print("   - localStorage.getItem('token')")
print("   - localStorage.setItem('token', ...)")

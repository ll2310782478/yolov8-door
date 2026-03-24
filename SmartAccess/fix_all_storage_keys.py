import os
from pathlib import Path

# Fix localStorage key inconsistency in all HTML files
template_dir = Path('app/templates')
files_to_fix = ['logs.html', 'face_gate.html']

for filename in files_to_fix:
    file_path = template_dir / filename
    
    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        continue
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace smartaccess_token with token
    old_content = content
    content = content.replace("'smartaccess_token'", "'token'")
    content = content.replace("'smartaccess_username'", "'username'")
    
    if old_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed localStorage keys in {file_path}")
    else:
        print(f"ℹ️  No changes needed for {file_path}")

print("\n✅ All files updated!")
print("   Changed 'smartaccess_token' → 'token'")
print("   Changed 'smartaccess_username' → 'username'")

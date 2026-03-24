import os

# Fix localStorage key inconsistency in auth.html
file_path = 'app/templates/auth.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace smartaccess_token with token
content = content.replace("'smartaccess_token'", "'token'")
content = content.replace("'smartaccess_username'", "'username'")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Fixed localStorage keys in {file_path}")
print("   Changed 'smartaccess_token' → 'token'")
print("   Changed 'smartaccess_username' → 'username'")

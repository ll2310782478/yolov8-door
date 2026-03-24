"""Add user_role column to users table and set admin role"""
from sqlalchemy import create_engine, text

engine = create_engine('mysql+pymysql://root:123456@localhost:3306/smartaccess')
with engine.connect() as conn:
    # Check if column exists
    result = conn.execute(text("SHOW COLUMNS FROM users LIKE 'user_role'"))
    if result.fetchone():
        print('Column user_role already exists')
    else:
        conn.execute(text("ALTER TABLE users ADD COLUMN user_role VARCHAR(20) NOT NULL DEFAULT 'access_user'"))
        conn.commit()
        print('Added user_role column')
    
    # Set admin role
    conn.execute(text("UPDATE users SET user_role = 'admin' WHERE username = 'admin'"))
    conn.commit()
    print('Set admin user role to admin')
    
    # Verify
    result = conn.execute(text('SELECT id, username, user_role FROM users'))
    for row in result:
        print(f'  User: {row[1]}, Role: {row[2]}')

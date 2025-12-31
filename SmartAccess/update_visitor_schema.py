import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "smartaccess")

def update_schema():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        
        print("Updating database schema...")

        # 1. Add qr_code_image to visitors
        try:
            cursor.execute("ALTER TABLE visitors ADD COLUMN qr_code_image LONGBLOB")
            print("Added qr_code_image to visitors")
        except pymysql.err.OperationalError as e:
            if "Duplicate column" in str(e):
                print("Column qr_code_image already exists in visitors")
            else:
                print(f"Error adding qr_code_image: {e}")

        # 2. Add start_time to visitor_permissions
        try:
            cursor.execute("ALTER TABLE visitor_permissions ADD COLUMN start_time DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("Added start_time to visitor_permissions")
        except pymysql.err.OperationalError as e:
            if "Duplicate column" in str(e):
                print("Column start_time already exists in visitor_permissions")
            else:
                print(f"Error adding start_time: {e}")

        # 3. Add max_uses to visitor_permissions
        try:
            cursor.execute("ALTER TABLE visitor_permissions ADD COLUMN max_uses INT DEFAULT 1")
            print("Added max_uses to visitor_permissions")
        except pymysql.err.OperationalError as e:
            if "Duplicate column" in str(e):
                print("Column max_uses already exists in visitor_permissions")
            else:
                print(f"Error adding max_uses: {e}")

        # 4. Create system_configs table
        create_config_table_sql = """
        CREATE TABLE IF NOT EXISTS system_configs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `key` VARCHAR(50) NOT NULL UNIQUE,
            value TEXT,
            description VARCHAR(255),
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_key (`key`)
        )
        """
        cursor.execute(create_config_table_sql)
        print("Created system_configs table")

        conn.commit()
        print("Schema update completed successfully.")
        
    except Exception as e:
        print(f"Failed to update schema: {e}")
    finally:
        if 'conn' in locals() and conn.open:
            conn.close()

if __name__ == "__main__":
    update_schema()

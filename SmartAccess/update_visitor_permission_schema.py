import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def update_schema():
    print("Updating database schema for access_level...")
    
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "123456"),
            database=os.getenv("DB_NAME", "smartaccess")
        )
        cursor = conn.cursor()
        
        # Check if access_level column exists in visitor_permissions
        cursor.execute("SHOW COLUMNS FROM visitor_permissions LIKE 'access_level'")
        result = cursor.fetchone()
        
        if not result:
            print("Adding access_level column to visitor_permissions...")
            cursor.execute("ALTER TABLE visitor_permissions ADD COLUMN access_level VARCHAR(50) DEFAULT 'door1'")
            conn.commit()
            print("Column access_level added successfully.")
        else:
            print("Column access_level already exists in visitor_permissions.")
            
        cursor.close()
        conn.close()
        print("Schema update completed successfully.")
        
    except Exception as e:
        print(f"Error updating schema: {e}")

if __name__ == "__main__":
    update_schema()

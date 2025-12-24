import pymysql
import numpy as np

# 数据库配置
DB_HOST = '127.0.0.1'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = '123456'
DB_NAME = 'face_access'

def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            embedding LONGBLOB NOT NULL
        )
        """
        cursor.execute(sql)
        conn.commit()
        print("✅ 数据表初始化完成")
    finally:
        cursor.close()
        conn.close()

def insert_user(name, embedding):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        emb_bytes = embedding.tobytes()
        sql = "INSERT INTO users (name, embedding) VALUES (%s, %s)"
        cursor.execute(sql, (name, emb_bytes))
        conn.commit()
        print(f"✅ {name} 数据已写入数据库")
    finally:
        cursor.close()
        conn.close()

def load_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    users = {}
    try:
        cursor.execute("SELECT name, embedding FROM users")
        for name, emb_blob in cursor.fetchall():
            emb = np.frombuffer(emb_blob, dtype=np.float32)
            users[name] = emb
    finally:
        cursor.close()
        conn.close()
    return users

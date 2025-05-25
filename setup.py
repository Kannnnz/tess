import sqlite3
import os
from datetime import datetime

def setup_database():
    """Setup database with proper schema"""
    
    # Remove existing database if exists
    if os.path.exists('database.db'):
        os.remove('database.db')
        print("Removed existing database.db")
    
    # Create new database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create users table with proper schema
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Create documents table
    cursor.execute('''
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_text TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create chat_sessions table
    cursor.execute('''
        CREATE TABLE chat_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create chat_messages table
    cursor.execute('''
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            document_ids TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create admin logs table
    cursor.execute('''
        CREATE TABLE admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users (id),
            FOREIGN KEY (target_user_id) REFERENCES users (id)
        )
    ''')
    
    # Insert default admin user
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin_password_hash = pwd_context.hash("admin123")
    
    cursor.execute('''
        INSERT INTO users (username, password_hash, email, role) 
        VALUES (?, ?, ?, ?)
    ''', ("admin", admin_password_hash, "admin@mail.unnes.ac.id", "admin"))
    
    # Insert test dosen
    dosen_password_hash = pwd_context.hash("dosen123")
    cursor.execute('''
        INSERT INTO users (username, password_hash, email, role) 
        VALUES (?, ?, ?, ?)
    ''', ("testdosen", dosen_password_hash, "dosen@mail.unnes.ac.id", "dosen"))
    
    # Insert test mahasiswa
    mahasiswa_password_hash = pwd_context.hash("mahasiswa123")
    cursor.execute('''
        INSERT INTO users (username, password_hash, email, role) 
        VALUES (?, ?, ?, ?)
    ''', ("testmahasiswa", mahasiswa_password_hash, "mahasiswa@students.unnes.ac.id", "mahasiswa"))
    
    conn.commit()
    conn.close()
    
    print("Database setup completed successfully!")
    print("Default admin: username=admin, password=admin123")
    print("Test dosen: username=testdosen, password=dosen123") 
    print("Test mahasiswa: username=testmahasiswa, password=mahasiswa123")

def create_uploads_directory():
    """Create uploads directory if it doesn't exist"""
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
        print("Created uploads directory")

if __name__ == "__main__":
    setup_database()
    create_uploads_directory()
    print("Setup completed!")

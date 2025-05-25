import sqlite3
import hashlib
from datetime import datetime
import os

def create_database():
    """Create database and tables"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin')),
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    ''')
    
    # Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            file_size INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            document_ids TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # System logs table (for admin monitoring)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history (user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history (timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs (timestamp)')
    
    conn.commit()
    return conn

def create_default_admin():
    """Create default admin user"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Create default admin
            admin_username = "admin"
            admin_password = "admin123"  # Change this in production!
            admin_email = "admin@unnes.ac.id"
            
            password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, role, is_active, created_at)
                VALUES (?, ?, ?, 'admin', 1, ?)
            ''', (admin_username, password_hash, admin_email, datetime.now().isoformat()))
            
            conn.commit()
            print(f"✅ Default admin created:")
            print(f"   Username: {admin_username}")
            print(f"   Password: {admin_password}")
            print(f"   Email: {admin_email}")
            print("   ⚠️  CHANGE THE DEFAULT PASSWORD IMMEDIATELY!")
        else:
            print("✅ Admin user already exists")
    
    except Exception as e:
        print(f"❌ Error creating admin: {str(e)}")
    finally:
        conn.close()

def create_sample_data():
    """Create sample data for testing"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        # Check if sample user exists
        cursor.execute("SELECT id FROM users WHERE username = 'testuser'")
        if not cursor.fetchone():
            # Create sample user
            test_password = hashlib.sha256("test123".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, role, is_active, created_at)
                VALUES (?, ?, ?, 'user', 1, ?)
            ''', ("testuser", test_password, "test@student.unnes.ac.id", datetime.now().isoformat()))
            
            conn.commit()
            print("✅ Sample user created:")
            print("   Username: testuser")
            print("   Password: test123")
    
    except Exception as e:
        print(f"❌ Error creating sample data: {str(e)}")
    finally:
        conn.close()

def setup_directories():
    """Create necessary directories"""
    directories = ['uploads', 'logs', 'backups']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'pyjwt',
        'requests',
        'pypdf2',
        'python-docx',
        'python-multipart'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    else:
        print("✅ All required packages are installed")
        return True

def test_lm_studio_connection():
    """Test connection to LM Studio"""
    import requests
    
    try:
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=5)
        if response.status_code == 200:
            models = response.json()
            print("✅ LM Studio connection successful")
            print(f"   Available models: {len(models.get('data', []))}")
            return True
        else:
            print("❌ LM Studio connection failed")
            return False
    except Exception as e:
        print("❌ LM Studio not running or not accessible")
        print("   Make sure LM Studio is running on http://127.0.0.1:1234")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Document Summarizer...")
    print("=" * 50)
    
    # Check requirements
    print("\n1. Checking requirements...")
    if not check_requirements():
        print("❌ Setup failed. Please install missing packages first.")
        return
    
    # Setup directories
    print("\n2. Setting up directories...")
    setup_directories()
    
    # Create database
    print("\n3. Setting up database...")
    try:
        conn = create_database()
        conn.close()
        print("✅ Database created successfully")
    except Exception as e:
        print(f"❌ Database setup failed: {str(e)}")
        return
    
    # Create admin user
    print("\n4. Creating admin user...")
    create_default_admin()
    
    # Create sample data
    print("\n5. Creating sample data...")
    create_sample_data()
    
    # Test LM Studio
    print("\n6. Testing LM Studio connection...")
    lm_studio_ok = test_lm_studio_connection()
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Start LM Studio and load mistral-nemo-instruct-2407 model" + ("" if lm_studio_ok else " ⚠️"))
    print("2. Change default admin password")
    print("3. Run the application: python app.py")
    print("4. Access API documentation: http://localhost:8000/docs")
    
    print("\nDefault credentials:")
    print("Admin - Username: admin, Password: admin123")
    print("Test User - Username: testuser, Password: test123")
    
    if not lm_studio_ok:
        print("\n⚠️  Warning: LM Studio is not running!")
        print("   Please start LM Studio and load the model before using the application.")

if __name__ == "__main__":
    main()
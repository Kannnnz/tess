import sqlite3
import os
import sys
import subprocess
import pkg_resources

def check_package_installed(package_name):
    """Check if a package is installed using pkg_resources"""
    try:
        # Handle special cases for package names
        check_name = package_name
        if package_name == 'passlib[bcrypt]':
            check_name = 'passlib'
        
        pkg_resources.get_distribution(check_name)
        return True
    except pkg_resources.DistributionNotFound:
        return False
    except Exception:
        # Fallback to import check
        try:
            import_name = package_name
            if package_name == 'pyjwt':
                import_name = 'jwt'
            elif package_name == 'pypdf2':
                import_name = 'PyPDF2'
            elif package_name == 'python-docx':
                import_name = 'docx'
            elif package_name == 'python-multipart':
                import_name = 'multipart'
            elif package_name == 'passlib[bcrypt]':
                import_name = 'passlib'
            
            __import__(import_name)
            return True
        except ImportError:
            return False

def install_package(package_name):
    """Install a single package"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError:
        return False

def check_and_install_packages():
    """Check and install required packages"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'python-multipart',
        'pyjwt',
        'pypdf2',
        'python-docx',
        'requests',
        'passlib[bcrypt]'
    ]
    
    print("1. Checking and installing required packages...")
    
    missing_packages = []
    for package in required_packages:
        if not check_package_installed(package):
            missing_packages.append(package)
    
    if missing_packages:
        print(f"📦 Installing missing packages: {', '.join(missing_packages)}")
        
        for package in missing_packages:
            print(f"   Installing {package}...")
            if install_package(package):
                print(f"   ✅ {package} installed successfully")
            else:
                print(f"   ❌ Failed to install {package}")
                return False
        
        # Verify installation after installing
        print("   Verifying installation...")
        still_missing = []
        for package in missing_packages:
            if not check_package_installed(package):
                still_missing.append(package)
        
        if still_missing:
            print(f"❌ Some packages still missing after installation: {', '.join(still_missing)}")
            print("Attempting direct import test...")
            
            # Direct import test as final check
            import_tests = {
                'fastapi': 'fastapi',
                'uvicorn': 'uvicorn',
                'python-multipart': 'multipart',
                'pyjwt': 'jwt',
                'pypdf2': 'PyPDF2',
                'python-docx': 'docx',
                'requests': 'requests',
                'passlib[bcrypt]': 'passlib'
            }
            
            final_missing = []
            for package in still_missing:
                try:
                    __import__(import_tests[package])
                    print(f"   ✅ {package} is actually available")
                except ImportError:
                    final_missing.append(package)
                    print(f"   ❌ {package} is truly missing")
            
            if final_missing:
                print(f"Please try installing manually:")
                print(f"pip install {' '.join(final_missing)}")
                return False
    
    print("✅ All required packages are available")
    return True

def create_database():
    """Create and setup database tables"""
    print("\n2. Setting up database...")
    
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create documents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create chat_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                document_ids TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash("admin123")
            
            cursor.execute('''
                INSERT INTO users (username, hashed_password, is_admin) 
                VALUES (?, ?, ?)
            ''', ("admin", hashed_password, True))
            
            print("✅ Default admin user created:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   ⚠️  Please change the admin password after first login!")
        
        conn.commit()
        conn.close()
        
        print("✅ Database setup completed")
        return True
        
    except Exception as e:
        print(f"❌ Database setup failed: {str(e)}")
        return False

def create_directories():
    """Create necessary directories"""
    print("\n3. Creating directories...")
    
    directories = ['uploads']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Directory '{directory}' created/verified")
        except Exception as e:
            print(f"❌ Failed to create directory '{directory}': {str(e)}")
            return False
    
    return True

def test_lm_studio_connection():
    """Test connection to LM Studio"""
    print("\n4. Testing LM Studio connection...")
    
    try:
        import requests
        
        # Test if LM Studio is running
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=5)
        
        if response.status_code == 200:
            models = response.json()
            if models.get('data'):
                model_name = models['data'][0]['id']
                print(f"✅ LM Studio connected successfully")
                print(f"   Active model: {model_name}")
                return True
            else:
                print("⚠️  LM Studio is running but no model is loaded")
                print("   Please load the mistral-nemo-instruct-2407 model in LM Studio")
                return False
        else:
            print("❌ LM Studio connection failed")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Cannot connect to LM Studio")
        print("   Please make sure:")
        print("   1. LM Studio is installed and running")
        print("   2. Local server is started on port 1234")
        print("   3. mistral-nemo-instruct-2407 model is loaded")
        return False
    except Exception as e:
        print(f"❌ Error testing LM Studio: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("=== Document Summarizer Setup ===\n")
    
    # Check and install packages
    if not check_and_install_packages():
        print("\n❌ Setup failed. Please resolve package installation issues.")
        return False
    
    # Create database
    if not create_database():
        print("\n❌ Setup failed. Database creation failed.")
        return False
    
    # Create directories
    if not create_directories():
        print("\n❌ Setup failed. Directory creation failed.")
        return False
    
    # Test LM Studio (optional, won't fail setup)
    test_lm_studio_connection()
    
    print("\n✅ Setup completed successfully!")
    print("\nNext steps:")
    print("1. Make sure LM Studio is running with mistral-nemo-instruct-2407 model")
    print("2. Run the application: python app.py")
    print("3. Access the API at: http://localhost:8000")
    print("\nDefault admin credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    print("   ⚠️  Please change the password after first login!")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)

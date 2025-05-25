import os
import sys
from werkzeug.security import generate_password_hash

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_database():
    """Setup database and create initial users"""
    try:
        # Import after setting up path
        from app import app, db, User
        
        print("Setting up database...")
        
        with app.app_context():
            # Drop all tables and recreate (for clean setup)
            db.drop_all()
            db.create_all()
            
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@unnes.ac.id',
                role='admin'
            )
            admin_user.set_password('admin123')
            
            # Create test dosen
            dosen_user = User(
                username='testdosen',
                email='dosen@unnes.ac.id',
                role='dosen'
            )
            dosen_user.set_password('dosen123')
            
            # Create test mahasiswa
            mahasiswa_user = User(
                username='testmahasiswa',
                email='mahasiswa@student.unnes.ac.id',
                role='user'
            )
            mahasiswa_user.set_password('mahasiswa123')
            
            # Add users to database
            db.session.add(admin_user)
            db.session.add(dosen_user)
            db.session.add(mahasiswa_user)
            
            try:
                db.session.commit()
                print("Database setup completed successfully!")
                print("Default admin: username=admin, password=admin123")
                print("Test dosen: username=testdosen, password=dosen123")
                print("Test mahasiswa: username=testmahasiswa, password=mahasiswa123")
            except Exception as e:
                db.session.rollback()
                print(f"Error creating users: {e}")
                return False
                
        return True
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please make sure all required packages are installed:")
        print("pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"Setup error: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ['uploads', 'instance']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def main():
    print("Starting setup process...")
    
    # Create necessary directories
    create_directories()
    
    # Setup database
    if setup_database():
        print("Setup completed successfully!")
        print("\nYou can now run the application with:")
        print("python app.py")
        print("\nTest accounts:")
        print("1. Admin - username: admin, password: admin123")
        print("2. Dosen - username: testdosen, password: dosen123")
        print("3. Mahasiswa - username: testmahasiswa, password: mahasiswa123")
    else:
        print("Setup failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

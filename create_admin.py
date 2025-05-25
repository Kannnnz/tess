#!/usr/bin/env python3
"""
Script to create admin user for Document Summarizer
Usage: python create_admin.py
"""

import sqlite3
import hashlib
import getpass
from datetime import datetime

def create_admin_user():
    """Interactive admin user creation"""
    print("🔐 Admin User Creation")
    print("=" * 30)
    
    # Get admin details
    username = input("Enter admin username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return False
    
    email = input("Enter admin email: ").strip()
    
    # Get password securely
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 6:
            print("❌ Password must be at least 6 characters")
            continue
        
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("❌ Passwords do not match")
            continue
        
        break
    
    # Connect to database
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Check if admin already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            print(f"❌ User '{username}' already exists")
            return False
        
        # Create admin user
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('''
            INSERT INTO users (username, password_hash, email, role, is_active, created_at)
            VALUES (?, ?, ?, 'admin', 1, ?)
        ''', (username, password_hash, email, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        print("✅ Admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print("   Role: admin")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin: {str(e)}")
        return False

def list_existing_admins():
    """List existing admin users"""
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, email, created_at, last_login, is_active
            FROM users 
            WHERE role = 'admin'
            ORDER BY created_at
        """)
        
        admins = cursor.fetchall()
        conn.close()
        
        if admins:
            print("\n📋 Existing Admin Users:")
            print("-" * 50)
            for admin in admins:
                status = "✅ Active" if admin[4] else "❌ Inactive"
                last_login = admin[3] if admin[3] else "Never"
                print(f"Username: {admin[0]}")
                print(f"Email: {admin[1]}")
                print(f"Created: {admin[2]}")
                print(f"Last Login: {last_login}")
                print(f"Status: {status}")
                print("-" * 30)
        else:
            print("\n📋 No admin users found")
            
    except Exception as e:
        print(f"❌ Error listing admins: {str(e)}")

def change_admin_password():
    """Change existing admin password"""
    print("\n🔑 Change Admin Password")
    print("=" * 30)
    
    username = input("Enter admin username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return False
    
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (username,))
        admin = cursor.fetchone()
        
        if not admin:
            print(f"❌ Admin user '{username}' not found")
            return False
        
        # Get new password
        while True:
            new_password = getpass.getpass("Enter new password: ")
            if len(new_password) < 6:
                print("❌ Password must be at least 6 characters")
                continue
            
            confirm_password = getpass.getpass("Confirm new password: ")
            if new_password != confirm_password:
                print("❌ Passwords do not match")
                continue
            
            break
        
        # Update password
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Password changed successfully for admin '{username}'")
        return True
        
    except Exception as e:
        print(f"❌ Error changing password: {str(e)}")
        return False

def main():
    """Main function"""
    while True:
        print("\n" + "=" * 40)
        print("🛠️  Document Summarizer Admin Management")
        print("=" * 40)
        print("1. Create new admin user")
        print("2. List existing admins")
        print("3. Change admin password")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ").strip()
        
        if choice == '1':
            create_admin_user()
        elif choice == '2':
            list_existing_admins()
        elif choice == '3':
            change_admin_password()
        elif choice == '4':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid option. Please select 1-4.")

if __name__ == "__main__":
    main()
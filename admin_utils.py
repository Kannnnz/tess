import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import secrets

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_admin_user(username: str, password: str, email: str) -> Dict:
    """Create admin user"""
    conn = get_db_connection()
    try:
        # Check if admin already exists
        cursor = conn.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (username,))
        if cursor.fetchone():
            return {"success": False, "message": "Admin user already exists"}
        
        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Create admin user
        conn.execute("""
            INSERT INTO users (username, password_hash, email, role, is_active, created_at)
            VALUES (?, ?, ?, 'admin', 1, ?)
        """, (username, password_hash, email, datetime.now().isoformat()))
        
        conn.commit()
        return {"success": True, "message": f"Admin user '{username}' created successfully"}
    
    except Exception as e:
        return {"success": False, "message": f"Error creating admin: {str(e)}"}
    finally:
        conn.close()

def get_all_users() -> List[Dict]:
    """Get all users for admin dashboard"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, username, email, role, is_active, created_at, last_login
            FROM users
            ORDER BY created_at DESC
        """)
        users = []
        for row in cursor.fetchall():
            users.append({
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
                "last_login": row["last_login"]
            })
        return users
    finally:
        conn.close()

def toggle_user_status(user_id: int) -> Dict:
    """Toggle user active/inactive status"""
    conn = get_db_connection()
    try:
        # Get current status
        cursor = conn.execute("SELECT is_active, username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        new_status = 0 if user["is_active"] else 1
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        
        status_text = "activated" if new_status else "deactivated"
        return {"success": True, "message": f"User '{user['username']}' {status_text} successfully"}
    
    except Exception as e:
        return {"success": False, "message": f"Error updating user status: {str(e)}"}
    finally:
        conn.close()

def delete_user(user_id: int) -> Dict:
    """Delete user and all related data"""
    conn = get_db_connection()
    try:
        # Get username first
        cursor = conn.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        if user["role"] == "admin":
            return {"success": False, "message": "Cannot delete admin user"}
        
        # Delete related data
        conn.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        return {"success": True, "message": f"User '{user['username']}' deleted successfully"}
    
    except Exception as e:
        return {"success": False, "message": f"Error deleting user: {str(e)}"}
    finally:
        conn.close()

def get_system_stats() -> Dict:
    """Get system statistics for admin dashboard"""
    conn = get_db_connection()
    try:
        stats = {}
        
        # Total users
        cursor = conn.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user'")
        stats["total_users"] = cursor.fetchone()["count"]
        
        # Active users
        cursor = conn.execute("SELECT COUNT(*) as count FROM users WHERE role = 'user' AND is_active = 1")
        stats["active_users"] = cursor.fetchone()["count"]
        
        # Total documents
        cursor = conn.execute("SELECT COUNT(*) as count FROM documents")
        stats["total_documents"] = cursor.fetchone()["count"]
        
        # Total chats
        cursor = conn.execute("SELECT COUNT(*) as count FROM chat_history")
        stats["total_chats"] = cursor.fetchone()["count"]
        
        # Recent registrations (last 7 days)
        cursor = conn.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE created_at >= date('now', '-7 days')
        """)
        stats["recent_registrations"] = cursor.fetchone()["count"]
        
        # Most active users
        cursor = conn.execute("""
            SELECT u.username, COUNT(ch.id) as chat_count
            FROM users u
            LEFT JOIN chat_history ch ON u.id = ch.user_id
            WHERE u.role = 'user'
            GROUP BY u.id, u.username
            ORDER BY chat_count DESC
            LIMIT 5
        """)
        stats["most_active_users"] = [{"username": row["username"], "chat_count": row["chat_count"]} 
                                     for row in cursor.fetchall()]
        
        return stats
    finally:
        conn.close()

def get_all_documents() -> List[Dict]:
    """Get all documents for admin management"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT d.id, d.filename, d.file_path, d.uploaded_at, u.username
            FROM documents d
            JOIN users u ON d.user_id = u.id
            ORDER BY d.uploaded_at DESC
        """)
        documents = []
        for row in cursor.fetchall():
            documents.append({
                "id": row["id"],
                "filename": row["filename"],
                "file_path": row["file_path"],
                "uploaded_at": row["uploaded_at"],
                "username": row["username"]
            })
        return documents
    finally:
        conn.close()

def delete_document(doc_id: int) -> Dict:
    """Delete document"""
    conn = get_db_connection()
    try:
        import os
        
        # Get document info
        cursor = conn.execute("SELECT filename, file_path FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        
        if not doc:
            return {"success": False, "message": "Document not found"}
        
        # Delete file from filesystem
        if os.path.exists(doc["file_path"]):
            os.remove(doc["file_path"])
        
        # Delete from database
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        
        return {"success": True, "message": f"Document '{doc['filename']}' deleted successfully"}
    
    except Exception as e:
        return {"success": False, "message": f"Error deleting document: {str(e)}"}
    finally:
        conn.close()

def get_chat_history_all() -> List[Dict]:
    """Get all chat history for admin monitoring"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT ch.id, ch.message, ch.response, ch.timestamp, u.username
            FROM chat_history ch
            JOIN users u ON ch.user_id = u.id
            ORDER BY ch.timestamp DESC
            LIMIT 100
        """)
        chats = []
        for row in cursor.fetchall():
            chats.append({
                "id": row["id"],
                "username": row["username"],
                "message": row["message"],
                "response": row["response"],
                "timestamp": row["timestamp"]
            })
        return chats
    finally:
        conn.close()

def cleanup_old_data(days: int = 30) -> Dict:
    """Cleanup old chat history and unused documents"""
    conn = get_db_connection()
    try:
        # Delete old chat history
        cursor = conn.execute("""
            DELETE FROM chat_history 
            WHERE timestamp < date('now', '-{} days')
        """.format(days))
        deleted_chats = cursor.rowcount
        
        conn.commit()
        
        return {
            "success": True, 
            "message": f"Cleaned up {deleted_chats} old chat records"
        }
    
    except Exception as e:
        return {"success": False, "message": f"Error during cleanup: {str(e)}"}
    finally:
        conn.close()

def change_user_role(user_id: int, new_role: str) -> Dict:
    """Change user role (admin/user)"""
    conn = get_db_connection()
    try:
        if new_role not in ["admin", "user"]:
            return {"success": False, "message": "Invalid role"}
        
        cursor = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()
        
        return {"success": True, "message": f"User '{user['username']}' role changed to {new_role}"}
    
    except Exception as e:
        return {"success": False, "message": f"Error changing user role: {str(e)}"}
    finally:
        conn.close()

def reset_user_password(user_id: int) -> Dict:
    """Reset user password to default"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        password_hash = hashlib.sha256(temp_password.encode()).hexdigest()
        
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        
        return {
            "success": True, 
            "message": f"Password reset for '{user['username']}'",
            "temp_password": temp_password
        }
    
    except Exception as e:
        return {"success": False, "message": f"Error resetting password: {str(e)}"}
    finally:
        conn.close()
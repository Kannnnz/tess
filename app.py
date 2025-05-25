from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import hashlib
import jwt
import os
import uuid
import json
import requests
from datetime import datetime, timedelta
from passlib.context import CryptContext
import PyPDF2
import docx
from io import BytesIO

# Security
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
security = HTTPBearer()

app = FastAPI(title="Document Summarizer API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str
    email: str  # Required untuk validasi domain UNNES

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    created_at: str
    is_active: bool

class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: Dict[str, Any]

class ChatMessage(BaseModel):
    message: str
    document_ids: Optional[List[str]] = []
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    message_id: int

class AdminUserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None

# Database functions
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_username(username: str):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id: int):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def validate_unnes_email(email: str) -> str:
    """Validate UNNES email and determine role"""
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    email = email.lower().strip()
    
    if email.endswith("@students.unnes.ac.id"):
        return "mahasiswa"
    elif email.endswith("@mail.unnes.ac.id"):
        return "dosen"
    else:
        raise HTTPException(
            status_code=400, 
            detail="Email harus menggunakan domain UNNES (@students.unnes.ac.id untuk mahasiswa atau @mail.unnes.ac.id untuk dosen)"
        )

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = get_user_by_username(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_admin_user(current_user = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Text extraction functions
def extract_text_from_pdf(file_content: bytes) -> str:
    try:
        pdf_file = BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error extracting PDF: {str(e)}")

def extract_text_from_docx(file_content: bytes) -> str:
    try:
        doc_file = BytesIO(file_content)
        doc = docx.Document(doc_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error extracting DOCX: {str(e)}")

def extract_text_from_txt(file_content: bytes) -> str:
    try:
        return file_content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error extracting TXT: {str(e)}")

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    file_extension = filename.lower().split('.')[-1]
    
    if file_extension == 'pdf':
        return extract_text_from_pdf(file_content)
    elif file_extension == 'docx':
        return extract_text_from_docx(file_content)
    elif file_extension == 'txt':
        return extract_text_from_txt(file_content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format")

# LM Studio API function
def query_lm_studio(prompt: str, context: str = "") -> str:
    try:
        full_prompt = f"""Context: {context}

Question: {prompt}

Please answer based on the provided context. If the question is not related to academic papers, research, or Universitas Negeri Semarang (UNNES), respond with: "Maaf, tolong berikan pertanyaan yang relevan dengan paper atau Universitas Negeri Semarang."

Answer:"""

        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json={
                "model": "mistral-nemo-instruct-2407",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that answers questions about academic papers and Universitas Negeri Semarang (UNNES). Only answer questions related to these topics."},
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return "Maaf, terjadi kesalahan dalam memproses pertanyaan Anda."
            
    except requests.exceptions.RequestException:
        return "Maaf, tidak dapat terhubung ke AI model. Pastikan LM Studio berjalan."

def is_relevant_question(question: str) -> bool:
    """Check if question is relevant to papers or UNNES"""
    relevant_keywords = [
        'paper', 'penelitian', 'skripsi', 'jurnal', 'artikel', 'study', 'research',
        'unnes', 'universitas negeri semarang', 'semarang', 'metode', 'metodologi',
        'hasil', 'kesimpulan', 'analisis', 'pembahasan', 'teori', 'landasan',
        'penulis', 'author', 'tahun', 'publikasi', 'abstrak', 'abstract'
    ]
    
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in relevant_keywords)

# API Endpoints

@app.post("/register", response_model=dict)
async def register(user: UserCreate):
    # Validate UNNES email and get role
    role = validate_unnes_email(user.email)
    
    # Check if username already exists
    if get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    conn = get_db_connection()
    existing_email = conn.execute('SELECT id FROM users WHERE email = ?', (user.email.lower(),)).fetchone()
    if existing_email:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = get_password_hash(user.password)
    
    # Insert user with determined role
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)',
            (user.username, hashed_password, user.email.lower(), role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        return {
            "message": "User registered successfully", 
            "user_id": user_id,
            "role": role,
            "email": user.email.lower()
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    
    if not user or not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    if not user['is_active']:
        raise HTTPException(status_code=401, detail="Account is deactivated")
    
    access_token = create_access_token(data={"sub": user['username']})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        }
    }

@app.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user)
):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed")
    
    uploaded_files = []
    conn = get_db_connection()
    
    try:
        for file in files:
            # Read file content
            file_content = await file.read()
            
            # Extract text
            extracted_text = extract_text_from_file(file_content, file.filename)
            
            # Generate unique document ID
            doc_id = str(uuid.uuid4())
            
            # Save file
            file_path = f"uploads/{doc_id}_{file.filename}"
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Save to database
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents (id, user_id, filename, file_path, file_size, content_text)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (doc_id, current_user['id'], file.filename, file_path, len(file_content), extracted_text))
            
            uploaded_files.append({
                "document_id": doc_id,
                "filename": file.filename,
                "size": len(file_content)
            })
        
        conn.commit()
        conn.close()
        
        return {"message": "Files uploaded successfully", "documents": uploaded_files}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatMessage,
    current_user = Depends(get_current_user)
):
    # Check if question is relevant
    if not is_relevant_question(chat_request.message):
        return ChatResponse(
            response="Maaf, tolong berikan pertanyaan yang relevan dengan paper atau Universitas Negeri Semarang.",
            session_id=chat_request.session_id or str(uuid.uuid4()),
            message_id=0
        )
    
    # Get document context
    context = ""
    if chat_request.document_ids:
        conn = get_db_connection()
        for doc_id in chat_request.document_ids:
            doc = conn.execute(
                'SELECT content_text FROM documents WHERE id = ? AND user_id = ?',
                (doc_id, current_user['id'])
            ).fetchone()
            if doc:
                context += doc['content_text'] + "\n\n"
        conn.close()
    
    # Get AI response
    ai_response = query_lm_studio(chat_request.message, context)
    
    # Create or use existing session
    session_id = chat_request.session_id or str(uuid.uuid4())
    
    # Save chat message
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create session if new
    if not chat_request.session_id:
        cursor.execute(
            'INSERT INTO chat_sessions (id, user_id, title) VALUES (?, ?, ?)',
            (session_id, current_user['id'], chat_request.message[:50] + "...")
        )
    
    # Save message
    cursor.execute('''
        INSERT INTO chat_messages (session_id, user_id, message, response, document_ids)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, current_user['id'], chat_request.message, ai_response, 
          json.dumps(chat_request.document_ids) if chat_request.document_ids else None))
    
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return ChatResponse(
        response=ai_response,
        session_id=session_id,
        message_id=message_id
    )

@app.get("/documents")
async def get_user_documents(current_user = Depends(get_current_user)):
    conn = get_db_connection()
    documents = conn.execute('''
        SELECT id, filename, file_size, upload_date 
        FROM documents 
        WHERE user_id = ? 
        ORDER BY upload_date DESC
    ''', (current_user['id'],)).fetchall()
    conn.close()
    
    return [dict(doc) for doc in documents]

@app.get("/chat-history")
async def get_chat_history(current_user = Depends(get_current_user)):
    conn = get_db_connection()
    sessions = conn.execute('''
        SELECT id, title, created_at 
        FROM chat_sessions 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (current_user['id'],)).fetchall()
    conn.close()
    
    return [dict(session) for session in sessions]

@app.get("/chat-messages/{session_id}")
async def get_chat_messages(session_id: str, current_user = Depends(get_current_user)):
    conn = get_db_connection()
    messages = conn.execute('''
        SELECT message, response, timestamp 
        FROM chat_messages 
        WHERE session_id = ? AND user_id = ? 
        ORDER BY timestamp ASC
    ''', (session_id, current_user['id'])).fetchall()
    conn.close()
    
    return [dict(message) for message in messages]

# Admin endpoints (Only Admin)
@app.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(admin_user = Depends(get_admin_user)):
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return [UserResponse(**dict(user)) for user in users]

# Dosen can also view users (but limited actions)
@app.get("/dosen/users", response_model=List[UserResponse])
async def get_users_for_dosen(dosen_user = Depends(get_admin_or_dosen_user)):
    conn = get_db_connection()
    # Dosen can only see mahasiswa
    if dosen_user['role'] == 'dosen':
        users = conn.execute('SELECT * FROM users WHERE role = "mahasiswa" ORDER BY created_at DESC').fetchall()
    else:  # admin
        users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return [UserResponse(**dict(user)) for user in users]

@app.put("/admin/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: AdminUserUpdate,
    admin_user = Depends(get_admin_user)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build update query dynamically
    updates = []
    params = []
    
    if update_data.is_active is not None:
        updates.append("is_active = ?")
        params.append(update_data.is_active)
    
    if update_data.role is not None:
        updates.append("role = ?")
        params.append(update_data.role)
    
    if updates:
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        params.append(user_id)
        cursor.execute(query, params)
        
        # Log admin action
        cursor.execute('''
            INSERT INTO admin_logs (admin_id, action, target_user_id, details)
            VALUES (?, ?, ?, ?)
        ''', (admin_user['id'], "UPDATE_USER", user_id, json.dumps(update_data.dict())))
        
        conn.commit()
    
    conn.close()
    return {"message": "User updated successfully"}

@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, admin_user = Depends(get_admin_user)):
    if user_id == admin_user['id']:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete user and related data
    cursor.execute('DELETE FROM chat_messages WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM chat_sessions WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM documents WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
    
    # Log admin action
    cursor.execute('''
        INSERT INTO admin_logs (admin_id, action, target_user_id, details)
        VALUES (?, ?, ?, ?)
    ''', (admin_user['id'], "DELETE_USER", user_id, f"Deleted user ID {user_id}"))
    
    conn.commit()
    conn.close()
    
    return {"message": "User deleted successfully"}

@app.get("/admin/stats")
async def get_admin_stats(admin_user = Depends(get_admin_user)):
    conn = get_db_connection()
    
    # Get various statistics
    total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
    total_mahasiswa = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "mahasiswa"').fetchone()['count']
    total_dosen = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "dosen"').fetchone()['count']
    total_documents = conn.execute('SELECT COUNT(*) as count FROM documents').fetchone()['count']
    total_chats = conn.execute('SELECT COUNT(*) as count FROM chat_messages').fetchone()['count']
    active_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1').fetchone()['count']
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_mahasiswa": total_mahasiswa,
        "total_dosen": total_dosen,
        "active_users": active_users,
        "total_documents": total_documents,
        "total_chat_messages": total_chats
    }

@app.get("/predefined-questions")
async def get_predefined_questions():
    """Get list of predefined questions"""
    questions = [
        "Apa metode penelitian yang digunakan dalam paper ini?",
        "Siapa penulis dan kapan paper ini dibuat?",
        "Apa hasil utama dari penelitian ini?",
        "Apa kesimpulan dari paper ini?",
        "Apa landasan teori yang digunakan?",
        "Bagaimana metodologi yang diterapkan?",
        "Apa saja temuan penting dalam penelitian ini?",
        "Bagaimana analisis data dilakukan?",
        "Apa kontribusi penelitian ini terhadap ilmu pengetahuan?",
        "Apa saran untuk penelitian selanjutnya?",
        "Bagaimana cara mendaftar di UNNES?",
        "Apa saja fakultas yang ada di UNNES?",
        "Bagaimana sistem perkuliahan di UNNES?",
        "Apa visi misi UNNES?"
    ]
    return {"questions": questions}

@app.get("/profile")
async def get_user_profile(current_user = Depends(get_current_user)):
    """Get current user profile information"""
    return {
        "id": current_user['id'],
        "username": current_user['username'],
        "email": current_user['email'],
        "role": current_user['role'],
        "created_at": current_user['created_at'],
        "is_active": current_user['is_active']
    }

@app.get("/role-info")
async def get_role_info():
    """Get information about different roles in the system"""
    return {
        "roles": {
            "mahasiswa": {
                "description": "Mahasiswa UNNES",
                "email_domain": "@students.unnes.ac.id",
                "permissions": [
                    "Upload dokumen penelitian",
                    "Chat dengan AI tentang paper/UNNES", 
                    "Melihat riwayat chat sendiri",
                    "Mengelola dokumen sendiri"
                ]
            },
            "dosen": {
                "description": "Dosen UNNES",
                "email_domain": "@mail.unnes.ac.id", 
                "permissions": [
                    "Semua fitur mahasiswa",
                    "Melihat daftar mahasiswa",
                    "Akses ke statistik terbatas"
                ]
            },
            "admin": {
                "description": "Administrator Sistem",
                "email_domain": "@mail.unnes.ac.id",
                "permissions": [
                    "Semua fitur sistem",
                    "Mengelola semua user",
                    "Melihat statistik lengkap",
                    "Mengaktifkan/menonaktifkan akun",
                    "Menghapus user dan data"
                ]
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

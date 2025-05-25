from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import hashlib
import sqlite3
import requests
import json
from datetime import datetime, timedelta
from typing import List, Optional
import jwt
import PyPDF2
from docx import Document
import io
from admin_utils import *

app = FastAPI(title="Document Summarizer API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"

# LM Studio configuration
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class ChatMessage(BaseModel):
    message: str
    document_ids: Optional[List[str]] = []

class AdminUserCreate(BaseModel):
    username: str
    password: str
    email: str

class UserRoleUpdate(BaseModel):
    user_id: int
    new_role: str

# Database functions
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload

def authenticate_user(username: str, password: str):
    conn = get_db_connection()
    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor = conn.execute(
            "SELECT id, username, role, is_active FROM users WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        )
        user = cursor.fetchone()
        if user and user["is_active"]:
            # Update last login
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), user["id"])
            )
            conn.commit()
            return dict(user)
        return None
    finally:
        conn.close()

def is_question_relevant(question: str) -> bool:
    """Check if question is relevant to paper/research or UNNES"""
    paper_keywords = [
        "paper", "penelitian", "skripsi", "jurnal", "artikel", "study", "metode", 
        "hasil", "kesimpulan", "abstrak", "literatur", "referensi", "analisis",
        "data", "sampel", "populasi", "hipotesis", "teori", "diskusi", "pembahasan"
    ]
    
    unnes_keywords = [
        "unnes", "universitas negeri semarang", "semarang", "kampus", "fakultas",
        "jurusan", "program studi", "akademik", "mahasiswa", "dosen"
    ]
    
    question_lower = question.lower()
    
    # Check for paper/research keywords
    for keyword in paper_keywords:
        if keyword in question_lower:
            return True
    
    # Check for UNNES keywords
    for keyword in unnes_keywords:
        if keyword in question_lower:
            return True
    
    return False

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extract text from uploaded file"""
    try:
        if filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        
        elif filename.endswith('.docx'):
            doc = Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        
        elif filename.endswith('.txt'):
            return file_content.decode('utf-8')
        
        else:
            return ""
    
    except Exception as e:
        print(f"Error extracting text from {filename}: {str(e)}")
        return ""

def call_lm_studio(prompt: str) -> str:
    """Call LM Studio API"""
    try:
        payload = {
            "model": "mistral-nemo-instruct-2407",
            "messages": [
                {
                    "role": "system",
                    "content": "Anda adalah asisten AI yang membantu menganalisis dokumen penelitian dan menjawab pertanyaan tentang Universitas Negeri Semarang (UNNES). Berikan jawaban yang akurat, relevan, dan berdasarkan konten dokumen yang diberikan."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return "Maaf, terjadi kesalahan pada sistem AI. Silakan coba lagi."
    
    except Exception as e:
        print(f"Error calling LM Studio: {str(e)}")
        return "Maaf, sistem AI sedang tidak tersedia. Silakan coba lagi nanti."

# User endpoints
@app.post("/register")
async def register(user: UserCreate):
    conn = get_db_connection()
    try:
        # Check if user exists
        cursor = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # Hash password
        password_hash = hashlib.sha256(user.password.encode()).hexdigest()
        
        # Create user
        conn.execute("""
            INSERT INTO users (username, password_hash, email, role, is_active, created_at)
            VALUES (?, ?, ?, 'user', 1, ?)
        """, (user.username, password_hash, user.email, datetime.now().isoformat()))
        
        conn.commit()
        return {"message": "User registered successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        conn.close()

@app.post("/token")
async def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "user_id": user["id"]}
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}

@app.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...), current_user: dict = Depends(verify_token)):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed")
    
    uploaded_files = []
    conn = get_db_connection()
    
    try:
        for file in files:
            if not file.filename.endswith(('.pdf', '.docx', '.txt')):
                raise HTTPException(status_code=400, detail=f"File type not supported: {file.filename}")
            
            # Create uploads directory if not exists
            os.makedirs("uploads", exist_ok=True)
            
            # Save file
            file_path = f"uploads/{current_user['user_id']}_{file.filename}"
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Save to database
            conn.execute("""
                INSERT INTO documents (user_id, filename, file_path, uploaded_at)
                VALUES (?, ?, ?, ?)
            """, (current_user["user_id"], file.filename, file_path, datetime.now().isoformat()))
            
            uploaded_files.append({"filename": file.filename, "file_path": file_path})
        
        conn.commit()
        return {"message": f"{len(uploaded_files)} files uploaded successfully", "files": uploaded_files}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        conn.close()

@app.post("/chat")
async def chat(message: ChatMessage, current_user: dict = Depends(verify_token)):
    # Check question relevance
    if not is_question_relevant(message.message):
        response_text = "Maaf, tolong berikan pertanyaan yang relevan dengan paper atau universitas negeri semarang"
        
        # Save to chat history
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO chat_history (user_id, message, response, timestamp)
                VALUES (?, ?, ?, ?)
            """, (current_user["user_id"], message.message, response_text, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
        
        return {"response": response_text}
    
    # Get documents content
    documents_content = ""
    if message.document_ids:
        conn = get_db_connection()
        try:
            for doc_id in message.document_ids:
                cursor = conn.execute(
                    "SELECT file_path, filename FROM documents WHERE id = ? AND user_id = ?",
                    (doc_id, current_user["user_id"])
                )
                doc = cursor.fetchone()
                
                if doc:
                    with open(doc["file_path"], "rb") as f:
                        file_content = f.read()
                    
                    text = extract_text_from_file(file_content, doc["filename"])
                    documents_content += f"\n--- {doc['filename']} ---\n{text}\n"
        finally:
            conn.close()
    
    # Prepare prompt
    if documents_content:
        prompt = f"""
        Berdasarkan dokumen berikut:
        {documents_content}
        
        Pertanyaan: {message.message}
        
        Tolong berikan jawaban yang akurat berdasarkan konten dokumen di atas.
        """
    else:
        prompt = f"""
        Pertanyaan tentang penelitian/paper atau Universitas Negeri Semarang: {message.message}
        
        Berikan jawaban yang informatif dan akurat.
        """
    
    # Get AI response
    ai_response = call_lm_studio(prompt)
    
    # Save to chat history
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO chat_history (user_id, message, response, timestamp)
            VALUES (?, ?, ?, ?)
        """, (current_user["user_id"], message.message, ai_response, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    
    return {"response": ai_response}

@app.get("/chat/history")
async def get_chat_history(current_user: dict = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT message, response, timestamp
            FROM chat_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (current_user["user_id"],))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "message": row["message"],
                "response": row["response"],
                "timestamp": row["timestamp"]
            })
        
        return {"history": history}
    finally:
        conn.close()

@app.get("/documents")
async def get_user_documents(current_user: dict = Depends(verify_token)):
    conn = get_db_connection()
    try:
        cursor = conn.execute("""
            SELECT id, filename, uploaded_at
            FROM documents
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
        """, (current_user["user_id"],))
        
        documents = []
        for row in cursor.fetchall():
            documents.append({
                "id": row["id"],
                "filename": row["filename"],
                "uploaded_at": row["uploaded_at"]
            })
        
        return {"documents": documents}
    finally:
        conn.close()

# Admin endpoints
@app.post("/admin/create-admin")
async def create_admin_endpoint(admin_data: AdminUserCreate, current_user: dict = Depends(verify_admin_token)):
    result = create_admin_user(admin_data.username, admin_data.password, admin_data.email)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/admin/users")
async def get_all_users_endpoint(current_user: dict = Depends(verify_admin_token)):
    users = get_all_users()
    return {"users": users}

@app.post("/admin/users/{user_id}/toggle-status")
async def toggle_user_status_endpoint(user_id: int, current_user: dict = Depends(verify_admin_token)):
    result = toggle_user_status(user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.delete("/admin/users/{user_id}")
async def delete_user_endpoint(user_id: int, current_user: dict = Depends(verify_admin_token)):
    result = delete_user(user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/admin/stats")
async def get_system_stats_endpoint(current_user: dict = Depends(verify_admin_token)):
    stats = get_system_stats()
    return {"stats": stats}

@app.get("/admin/documents")
async def get_all_documents_endpoint(current_user: dict = Depends(verify_admin_token)):
    documents = get_all_documents()
    return {"documents": documents}

@app.delete("/admin/documents/{doc_id}")
async def delete_document_endpoint(doc_id: int, current_user: dict = Depends(verify_admin_token)):
    result = delete_document(doc_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/admin/chats")
async def get_all_chats_endpoint(current_user: dict = Depends(verify_admin_token)):
    chats = get_chat_history_all()
    return {"chats": chats}

@app.post("/admin/cleanup")
async def cleanup_old_data_endpoint(days: int = 30, current_user: dict = Depends(verify_admin_token)):
    result = cleanup_old_data(days)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/admin/users/change-role")
async def change_user_role_endpoint(role_update: UserRoleUpdate, current_user: dict = Depends(verify_admin_token)):
    result = change_user_role(role_update.user_id, role_update.new_role)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/admin/users/{user_id}/reset-password")
async def reset_user_password_endpoint(user_id: int, current_user: dict = Depends(verify_admin_token)):
    result = reset_user_password(user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.get("/")
async def root():
    return {
        "message": "Document Summarizer API",
        "version": "1.0.0",
        "endpoints": {
            "user": ["/register", "/token", "/upload", "/chat", "/chat/history", "/documents"],
            "admin": ["/admin/users", "/admin/stats", "/admin/documents", "/admin/chats", "/admin/cleanup"]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
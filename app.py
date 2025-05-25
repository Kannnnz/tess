from flask import Flask, request, jsonify, session, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import requests
import PyPDF2
from docx import Document
import io
import json
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///document_summarizer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user', 'admin', 'dosen'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    document_ids = db.Column(db.String(500))  # Store as comma-separated IDs

# LM Studio Configuration
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_admin_or_dosen_user():
    """Helper function to get current user if they are admin or dosen"""
    if 'user_id' not in session:
        return None
    
    user = User.query.get(session['user_id'])
    if user and user.role in ['admin', 'dosen']:
        return user
    return None

def admin_or_dosen_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_admin_or_dosen_user()
        if not user:
            return jsonify({'error': 'Admin or Dosen access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# File processing functions
def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
    except Exception as e:
        print(f"Error extracting PDF: {e}")
    return text

def extract_text_from_docx(file_path):
    text = ""
    try:
        doc = Document(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
    return text

def extract_text_from_txt(file_path):
    text = ""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
    except Exception as e:
        print(f"Error extracting TXT: {e}")
    return text

def extract_text_from_file(file_path, filename):
    """Extract text based on file extension"""
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['doc', 'docx']:
        return extract_text_from_docx(file_path)
    elif ext == 'txt':
        return extract_text_from_txt(file_path)
    else:
        return ""

def is_relevant_query(query):
    """Check if query is relevant to papers or UNNES"""
    query_lower = query.lower()
    paper_keywords = ['paper', 'skripsi', 'penelitian', 'jurnal', 'artikel', 'studi', 'analisis', 'metode', 'hasil', 'kesimpulan', 'abstrak', 'penulis', 'author']
    unnes_keywords = ['unnes', 'universitas negeri semarang', 'semarang', 'negeri semarang']
    
    # Check if query contains paper-related keywords
    for keyword in paper_keywords:
        if keyword in query_lower:
            return True
    
    # Check if query contains UNNES-related keywords
    for keyword in unnes_keywords:
        if keyword in query_lower:
            return True
    
    return False

def query_lm_studio(messages, max_tokens=1000):
    """Query LM Studio API"""
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        response = requests.post(LM_STUDIO_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Error: LM Studio returned status code {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return f"Error connecting to LM Studio: {str(e)}"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not all(k in data for k in ('username', 'email', 'password')):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        role=data.get('role', 'user')  # Default to 'user' if role not specified
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not all(k in data for k in ('username', 'password')):
        return jsonify({'error': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if user and user.check_password(data['password']):
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role
            }
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/upload', methods=['POST'])
@login_required
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if len(files) > 5:
        return jsonify({'error': 'Maximum 5 files allowed'}), 400
    
    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'No files selected'}), 400
    
    uploaded_files = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to prevent filename conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            file.save(file_path)
            
            # Extract text content
            content = extract_text_from_file(file_path, file.filename)
            
            # Save to database
            document = Document(
                filename=filename,
                original_filename=file.filename,
                file_path=file_path,
                content=content,
                user_id=session['user_id']
            )
            db.session.add(document)
            db.session.commit()
            
            uploaded_files.append({
                'id': document.id,
                'filename': file.filename,
                'size': len(content)
            })
    
    return jsonify({
        'message': f'{len(uploaded_files)} files uploaded successfully',
        'files': uploaded_files
    })

@app.route('/predefined-questions', methods=['GET'])
def get_predefined_questions():
    questions = [
        "Metode apa yang digunakan pada paper tersebut?",
        "Siapa penulis dan kapan paper tersebut dibuat?",
        "Apa hasil dari paper tersebut?",
        "Apa kesimpulan dari penelitian ini?",
        "Apa tujuan dari penelitian ini?",
        "Apa kontribusi utama dari paper ini?",
        "Apa keterbatasan dari penelitian ini?",
        "Bagaimana metodologi penelitian yang digunakan?"
    ]
    return jsonify({'questions': questions})

@app.route('/ask', methods=['POST'])
@login_required
def ask_question():
    data = request.get_json()
    
    if not data or 'question' not in data:
        return jsonify({'error': 'Question is required'}), 400
    
    question = data['question']
    document_ids = data.get('document_ids', [])
    
    # Check if question is relevant
    if not is_relevant_query(question):
        response = "Maaf, tolong berikan pertanyaan yang relevan dengan paper atau universitas negeri semarang"
        
        # Save to chat history
        chat_history = ChatHistory(
            user_id=session['user_id'],
            session_id=session.get('session_id', 'default'),
            message=question,
            response=response,
            document_ids=','.join(map(str, document_ids)) if document_ids else None
        )
        db.session.add(chat_history)
        db.session.commit()
        
        return jsonify({'response': response})
    
    # Get document contents
    documents_content = ""
    if document_ids:
        documents = Document.query.filter(
            Document.id.in_(document_ids),
            Document.user_id == session['user_id']
        ).all()
        
        documents_content = "\n\n".join([
            f"Document: {doc.original_filename}\nContent: {doc.content[:2000]}..."
            for doc in documents
        ])
    
    # Prepare messages for LM Studio
    system_prompt = """Anda adalah asisten AI yang membantu menganalisis dokumen akademik, khususnya paper penelitian dan informasi tentang Universitas Negeri Semarang (UNNES). 
    
Tugas Anda:
1. Berikan jawaban yang akurat dan informatif berdasarkan dokumen yang diberikan
2. Fokus pada aspek akademik dan penelitian
3. Jika ditanya tentang UNNES, berikan informasi yang relevan
4. Berikan jawaban dalam bahasa Indonesia yang jelas dan mudah dipahami

Konteks dokumen:"""
    
    if documents_content:
        system_prompt += f"\n\n{documents_content}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    # Get previous chat history for context
    recent_chats = ChatHistory.query.filter_by(
        user_id=session['user_id']
    ).order_by(ChatHistory.timestamp.desc()).limit(3).all()
    
    # Add recent context
    for chat in reversed(recent_chats):
        messages.insert(-1, {"role": "user", "content": chat.message})
        messages.insert(-1, {"role": "assistant", "content": chat.response})
    
    # Query LM Studio
    response = query_lm_studio(messages)
    
    # Save to chat history
    chat_history = ChatHistory(
        user_id=session['user_id'],
        session_id=session.get('session_id', 'default'),
        message=question,
        response=response,
        document_ids=','.join(map(str, document_ids)) if document_ids else None
    )
    db.session.add(chat_history)
    db.session.commit()
    
    return jsonify({'response': response})

@app.route('/chat-history', methods=['GET'])
@login_required
def get_chat_history():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    chats = ChatHistory.query.filter_by(
        user_id=session['user_id']
    ).order_by(ChatHistory.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'chats': [{
            'id': chat.id,
            'message': chat.message,
            'response': chat.response,
            'timestamp': chat.timestamp.isoformat()
        } for chat in chats.items],
        'has_more': chats.has_next,
        'total': chats.total
    })

@app.route('/documents', methods=['GET'])
@login_required
def get_user_documents():
    documents = Document.query.filter_by(user_id=session['user_id']).all()
    
    return jsonify({
        'documents': [{
            'id': doc.id,
            'filename': doc.original_filename,
            'uploaded_at': doc.uploaded_at.isoformat(),
            'content_preview': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content
        } for doc in documents]
    })

# Admin Routes
@app.route('/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    users = User.query.all()
    return jsonify({
        'users': [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'created_at': user.created_at.isoformat()
        } for user in users]
    })

@app.route('/admin/documents', methods=['GET'])
@admin_or_dosen_required
def get_all_documents():
    documents = Document.query.join(User).all()
    
    return jsonify({
        'documents': [{
            'id': doc.id,
            'filename': doc.original_filename,
            'username': doc.user.username,
            'uploaded_at': doc.uploaded_at.isoformat(),
            'content_preview': doc.content[:200] + '...' if len(doc.content) > 200 else doc.content
        } for doc in documents]
    })

@app.route('/admin/chat-history', methods=['GET'])
@admin_or_dosen_required
def get_all_chat_history():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    chats = ChatHistory.query.join(User).order_by(
        ChatHistory.timestamp.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'chats': [{
            'id': chat.id,
            'username': chat.user.username,
            'message': chat.message,
            'response': chat.response,
            'timestamp': chat.timestamp.isoformat()
        } for chat in chats.items],
        'has_more': chats.has_next,
        'total': chats.total
    })

@app.route('/admin/update-user-role', methods=['POST'])
@admin_required
def update_user_role():
    data = request.get_json()
    
    if not data or not all(k in data for k in ('user_id', 'role')):
        return jsonify({'error': 'User ID and role are required'}), 400
    
    if data['role'] not in ['user', 'admin', 'dosen']:
        return jsonify({'error': 'Invalid role'}), 400
    
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.role = data['role']
    db.session.commit()
    
    return jsonify({'message': 'User role updated successfully'})

@app.route('/admin/delete-user', methods=['DELETE'])
@admin_required
def delete_user():
    user_id = request.args.get('user_id', type=int)
    
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Don't allow deleting the current admin
    if user.id == session['user_id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    # Delete related data
    ChatHistory.query.filter_by(user_id=user_id).delete()
    Document.query.filter_by(user_id=user_id).delete()
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'})

@app.route('/user-info', methods=['GET'])
@login_required
def get_user_info():
    user = User.query.get(session['user_id'])
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'created_at': user.created_at.isoformat()
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@unnes.ac.id', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created - username: admin, password: admin123")
    
    app.run(debug=True)

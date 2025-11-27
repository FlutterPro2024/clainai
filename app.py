import sqlite3
import os
import requests
import time
from flask import Flask, request, jsonify, g, session, redirect, url_for, render_template, send_from_directory
from datetime import datetime, timezone
import hashlib
import secrets
from dotenv import load_dotenv
import PyPDF2
import io
import docx
from bs4 import BeautifulSoup

# Load environment
load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
SECRET_KEY = os.getenv("SECRET_KEY", "clainai-super-secret-key-2024-pro-max")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "4991d46dbad619689eda07dafef0665d12c1a2db")

# GitHub OAuth Configuration

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Ov23lihMk0lVKB9t8CGm")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "9c843fa45f6ea8abfc82774b1395d98a3a925dee")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "77933091754-idsptg4osou4ipj9r434sdg8rpmb6289.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")

# استخدام قاعدة بيانات في الذاكرة لـ Vercel
DB_PATH = "clainai.db"

# Auto-detect environment and set base URL
def get_base_url():
    if 'VERCEL' in os.environ:
        return 'https://clainai-deploy.vercel.app'
    else:
        return 'http://localhost:5000'

BASE_URL = get_base_url()
GITHUB_REDIRECT_URI = f"{BASE_URL}/api/auth/github/callback"
GOOGLE_REDIRECT_URI = f"{BASE_URL}/api/auth/google/callback"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY

# إعدادات الجلسة الآمنة
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400,
    JSON_AS_ASCII=False
)

# CORS headers for file upload
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

print("=" * 60)
print("🚀 ClainAI - المساعد الذكي الإبداعي المتقدم!")
print("=" * 60)
print(f"📍 Base URL: {BASE_URL}")
print(f"🔑 OpenRouter Key: {OPENROUTER_API_KEY[:20]}...")
print(f"🔍 Serper Search: {'✅' if SERPER_API_KEY else '❌'}")
print(f"🔐 GitHub OAuth: {'✅' if GITHUB_CLIENT_ID else '❌'}")
print(f"🔐 Google OAuth: {'✅' if GOOGLE_CLIENT_ID else '❌'}")
print(f"📄 PDF Support: ✅")
print(f"📝 Word Support: ✅")
print(f"🖼️ Image Analysis: ✅")
print(f"👑 Developer: محمد عبدو - mohammedu3615@gmail.com")

# دالة الاتصال بقاعدة البيانات
def get_db_connection():
    attempts = 0
    while attempts < 5:
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            return conn
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                attempts += 1
                time.sleep(0.1)
                continue
            raise e
    raise Exception("فشل في الاتصال بقاعدة البيانات بعد عدة محاولات")

# تهيئة قاعدة البيانات
def init_db():
    conn = get_db_connection()
    
    # جدول المستخدمين
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المحادثات
    conn.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            message TEXT NOT NULL,
            reply TEXT NOT NULL,
            model_used TEXT,
            thinking_process TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # جدول الملفات المرفوعة
    conn.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            filename TEXT,
            content TEXT,
            file_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول عمليات البحث
    conn.execute('''
        CREATE TABLE IF NOT EXISTS searches (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            query TEXT,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات بنجاح")

# Routes
@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect('/login')
    return send_from_directory('static', 'index.html')

@app.route("/login")
def login():
    if 'user_id' in session:
        return redirect('/')
    return send_from_directory('static', 'login.html')

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory('static', path)

# خدمة الملفات الثابتة الإضافية
@app.route("/manifest.json")
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

@app.route("/service-worker.js")
def serve_service_worker():
    return send_from_directory('static', 'service-worker.js')

@app.route("/favicon.ico")
def serve_favicon():
    return send_from_directory('static', 'favicon.ico')

# تسجيل الدخول كضيف
@app.route("/api/guest-login", methods=["POST", "GET"])
def guest_login():
    try:
        user_id = f"guest_{secrets.token_hex(8)}"
        
        conn = get_db_connection()
        conn.execute(
            'INSERT OR IGNORE INTO users (id, name, email, role) VALUES (?, ?, ?, ?)',
            (user_id, 'ضيف', f'guest_{user_id}@clainai.com', 'user')
        )
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['user_name'] = 'ضيف'
        session['user_role'] = 'user'
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'name': 'ضيف',
                'role': 'user'
            }
        })
        
    except Exception as e:
        print(f"❌ خطأ في تسجيل الدخول كضيف: {str(e)}")
        return jsonify({'error': str(e)}), 500

# GitHub OAuth
@app.route('/api/auth/github')
def github_auth():
    github_auth_url = (
        f"https://github.com/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=user:email"
    )
    return redirect(github_auth_url)

@app.route('/api/auth/github/callback')
def github_callback():
    try:
        code = request.args.get('code')
        if not code:
            return redirect('/login?error=github_auth_failed')
        
        # استبدال code بـ access token
        token_response = requests.post(
            'https://github.com/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
                'redirect_uri': GITHUB_REDIRECT_URI
            }
        )
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return redirect('/login?error=github_token_failed')
        
        # الحصول على بيانات المستخدم
        user_response = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'token {access_token}'}
        )
        user_data = user_response.json()
        
        user_id = f"github_{user_data['id']}"
        user_name = user_data.get('name', user_data.get('login', 'مستخدم GitHub'))
        user_email = user_data.get('email', f"{user_data['login']}@github.com")
        
        # حفظ المستخدم في قاعدة البيانات
        conn = get_db_connection()
        conn.execute(
            'INSERT OR REPLACE INTO users (id, name, email, role) VALUES (?, ?, ?, ?)',
            (user_id, user_name, user_email, 'user')
        )
        conn.commit()
        conn.close()
        
        # حفظ في الجلسة
        session['user_id'] = user_id
        session['user_name'] = user_name
        session['user_role'] = 'user'
        
        return redirect('/')
        
    except Exception as e:
        print(f"GitHub OAuth Error: {str(e)}")
        return redirect('/login?error=github_auth_failed')

# Google OAuth
@app.route('/api/auth/google')
def google_auth():
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=email profile"
        f"&access_type=offline"
    )
    return redirect(google_auth_url)

@app.route('/api/auth/google/callback')
def google_callback():
    try:
        code = request.args.get('code')
        if not code:
            return redirect('/login?error=google_auth_failed')
        
        # استبدال code بـ access token
        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': GOOGLE_REDIRECT_URI
            }
        )
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            return redirect('/login?error=google_token_failed')
        
        # الحصول على بيانات المستخدم
        user_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        user_data = user_response.json()
        
        user_id = f"google_{user_data['id']}"
        user_name = user_data.get('name', 'مستخدم Google')
        user_email = user_data.get('email', f"{user_data['id']}@google.com")
        
        # حفظ المستخدم في قاعدة البيانات
        conn = get_db_connection()
        conn.execute(
            'INSERT OR REPLACE INTO users (id, name, email, role) VALUES (?, ?, ?, ?)',
            (user_id, user_name, user_email, 'user')
        )
        conn.commit()
        conn.close()
        
        # حفظ في الجلسة
        session['user_id'] = user_id
        session['user_name'] = user_name
        session['user_role'] = 'user'
        
        return redirect('/')
        
    except Exception as e:
        print(f"Google OAuth Error: {str(e)}")
        return redirect('/login?error=google_auth_failed')

# استخراج النص من PDF
def extract_text_from_pdf(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"خطأ في قراءة ملف PDF: {str(e)}")

# استخراج النص من Word
def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise Exception(f"خطأ في قراءة ملف Word: {str(e)}")

# البحث في الويب
def perform_web_search(query):
    try:
        if not SERPER_API_KEY or SERPER_API_KEY == "your_serper_api_key_here":
            return {"error": "مفتاح البحث غير مضبوط"}
        
        response = requests.post(
            'https://google.serper.dev/search',
            headers={
                'X-API-KEY': SERPER_API_KEY,
                'Content-Type': 'application/json'
            },
            json={'q': query, 'num': 5}
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            # استخراج النتائج
            for organic in data.get('organic', [])[:3]:
                results.append({
                    'title': organic.get('title', ''),
                    'link': organic.get('link', ''),
                    'snippet': organic.get('snippet', '')
                })
            
            return results
        else:
            return {"error": f"خطأ في البحث: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"خطأ في خدمة البحث: {str(e)}"}

# سجل المحادثات (مطلوب من الـ JavaScript)
@app.route("/api/history")
def get_history():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify([])
        
        conn = get_db_connection()
        conversations = conn.execute(
            'SELECT message, reply, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
            (user_id,)
        ).fetchall()
        conn.close()
        
        result = []
        for conv in conversations:
            result.append({
                'role': 'user',
                'content': conv['message']
            })
            result.append({
                'role': 'assistant', 
                'content': conv['reply']
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify([])

# الدردشة مع الذكاء الاصطناعي
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'الرسالة فارغة'}), 400
        
        user_id = session.get('user_id', 'guest')
        
        print(f"🧠 استخدام النماذج المتقدمة للرد الإبداعي...")
        
        # قائمة النماذج المتاحة
        models = [
            "meta-llama/llama-3-70b-instruct:nitro",
            "openai/gpt-3.5-turbo", 
            "anthropic/claude-3-haiku",
            "google/gemini-2.0-flash-exp:free"
        ]
        
        response = None
        used_model = ""
        
        for model in models:
            try:
                print(f"🧠 جرب النموذج: {model}")
                
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": f"{BASE_URL}",
                        "X-Title": "ClainAI Chat"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"أنت مساعد ذكي عربي. أجب بطريقة مفيدة وإبداعية.\n\nالسؤال: {message}"
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    used_model = model
                    print(f"✅ تم استخدام النموذج: {model}")
                    break
                else:
                    print(f"⚠️ النموذج {model} غير متاح: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ خطأ في النموذج {model}: {str(e)}")
                continue
        
        if not response or response.status_code != 200:
            return jsonify({
                'error': 'جميع النماذج غير متاحة حالياً. يرجى المحاولة لاحقاً.'
            }), 503
        
        result = response.json()
        reply = result['choices'][0]['message']['content']
        
        # حفظ المحادثة في قاعدة البيانات
        conversation_id = hashlib.md5(f"{user_id}_{message}_{datetime.now().timestamp()}".encode()).hexdigest()
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO conversations (id, user_id, message, reply, model_used) VALUES (?, ?, ?, ?, ?)',
            (conversation_id, user_id, message, reply, used_model)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'reply': reply,
            'model_used': used_model
        })
        
    except Exception as e:
        print(f"❌ خطأ في الدردشة: {str(e)}")
        return jsonify({'error': f'حدث خطأ: {str(e)}'}), 500

# رفع الملف
@app.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        file_extension = file.filename.lower().split('.')[-1]
        file_content = ""
        file_type = "text"
        
        # معالجة不同类型的 الملفات
        if file_extension == 'pdf':
            file_content = extract_text_from_pdf(file)
            file_type = "pdf"
        elif file_extension in ['docx', 'doc']:
            file_content = extract_text_from_docx(file)
            file_type = "word"
        else:
            # الملفات النصية
            file_content = file.read().decode('utf-8', errors='ignore')
            file_type = "text"
        
        # حفظ في قاعدة البيانات
        user_id = session.get('user_id', 'guest')
        file_id = hashlib.md5(f"{user_id}_{datetime.now().timestamp()}".encode()).hexdigest()
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO uploaded_files (id, user_id, filename, content, file_type, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)',
            (file_id, user_id, file.filename, file_content, file_type, datetime.now(timezone.utc))
        )
        conn.commit()
        conn.close()
        
        # حفظ file_id في session
        session['current_file_id'] = file_id
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'size': len(file_content),
            'file_type': file_type,
            'file_id': file_id,
            'message': 'File uploaded successfully. You can now ask questions about it.'
        })
        
    except Exception as e:
        print(f"❌ خطأ في رفع الملف: {str(e)}")
        return jsonify({'error': str(e)}), 500

# السؤال عن الملف
@app.route("/api/ask-about-file", methods=["POST"])
def ask_about_file():
    try:
        data = request.json
        question = data.get('question', '')
        
        # جلب file_id من session
        file_id = session.get('current_file_id')
        if not file_id:
            return jsonify({'error': 'No file uploaded. Please upload a file first.'}), 400
        
        # جلب المحتوى من database
        conn = get_db_connection()
        file_data = conn.execute(
            'SELECT filename, content, file_type FROM uploaded_files WHERE id = ?', (file_id,)
        ).fetchone()
        conn.close()
        
        if not file_data:
            return jsonify({'error': 'File not found. Please upload again.'}), 404
        
        file_content = file_data['content']
        file_type = file_data['file_type']
        
        # prompt مخصص لتحليل الملف
        analysis_prompt = f"""
        الملف: {file_data['filename']} (نوع: {file_type})
        محتوى الملف:
        {file_content[:4000]}
        
        السؤال: {question}
        
        رجاءً ابحث في محتوى الملف وأجب على السؤال بناءً على المعلومات الموجودة في الملف.
        إذا لم تجد الإجابة في الملف، قل أن المعلومات غير موجودة.
        """
        
        # إرسال للذكاء الاصطناعي
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": f"{BASE_URL}",
                "X-Title": "ClainAI File Analysis",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [
                    {"role": "user", "content": analysis_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
        )
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            return jsonify({
                'success': True,
                'answer': ai_response,
                'question': question
            })
        else:
            print(f"OpenRouter Error: {response.status_code} - {response.text}")
            return jsonify({'error': 'AI service unavailable'}), 500
            
    except Exception as e:
        print(f"Server Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# تحليل الصور (بناءً على وصف المستخدم)
@app.route("/api/analyze-image", methods=["POST"])
def analyze_image():
    try:
        data = request.json
        image_description = data.get('description', '').strip()
        question = data.get('question', '').strip()
        
        if not image_description:
            return jsonify({'error': 'يجب تقديم وصف للصورة'}), 400
        
        prompt = f"""
        المستخدم وصف هذه الصورة: {image_description}
        
        السؤال عن الصورة: {question if question else 'ما هو تحليلك لهذه الصورة؟'}
        
        بناءً على هذا الوصف، قدم تحليلاً مفيداً واجب على السؤال.
        كن دقيقاً في التحليل وقدم معلومات قيمة.
        """
        
        # إرسال للـ AI
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": f"{BASE_URL}",
                "X-Title": "ClainAI Image Analysis"
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1500
            }
        )
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            return jsonify({
                'success': True, 
                'analysis': ai_response,
                'description': image_description,
                'question': question
            })
        else:
            return jsonify({'error': 'AI service unavailable'}), 500
            
    except Exception as e:
        print(f"Image Analysis Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# البحث في الويب
@app.route("/api/search", methods=["POST"])
def web_search():
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'استعلام البحث فارغ'}), 400
        
        print(f"🔍 البحث في الويب عن: {query}")
        
        # تنفيذ البحث
        search_results = perform_web_search(query)
        
        if 'error' in search_results:
            return jsonify({'error': search_results['error']}), 500
        
        # حفظ نتائج البحث
        user_id = session.get('user_id', 'guest')
        search_id = hashlib.md5(f"{user_id}_{query}_{datetime.now().timestamp()}".encode()).hexdigest()
        
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO searches (id, user_id, query, results) VALUES (?, ?, ?, ?)',
            (search_id, user_id, query, str(search_results))
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'results': search_results,
            'query': query
        })
        
    except Exception as e:
        print(f"❌ خطأ في البحث: {str(e)}")
        return jsonify({'error': str(e)}), 500

# البحث مع الرد الذكي
@app.route("/api/search-and-answer", methods=["POST"])
def search_and_answer():
    try:
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'استعلام البحث فارغ'}), 400
        
        # البحث أولاً
        search_results = perform_web_search(query)
        
        if 'error' in search_results:
            return jsonify({'error': search_results['error']}), 500
        
        # بناء prompt مع نتائج البحث
        search_context = ""
        for i, result in enumerate(search_results, 1):
            search_context += f"{i}. {result['title']}\n   {result['snippet']}\n\n"
        
        prompt = f"""
        استعلام البحث: {query}
        
        نتائج البحث من الويب:
        {search_context}
        
        رجاءً قدم إجابة شاملة ومفيدة بناءً على نتائج البحث أعلاه.
        أشر إلى المصادر عندما يكون ذلك مناسباً.
        """
        
        # إرسال للـ AI
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": f"{BASE_URL}",
                "X-Title": "ClainAI Search"
            },
            json={
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            }
        )
        
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content']
            
            return jsonify({
                'success': True,
                'answer': ai_response,
                'search_results': search_results,
                'query': query
            })
        else:
            return jsonify({'error': 'AI service unavailable'}), 500
            
    except Exception as e:
        print(f"❌ خطأ في البحث الذكي: {str(e)}")
        return jsonify({'error': str(e)}), 500

# الحصول على سجل المحادثة (للتوافق مع الاسم القديم)
@app.route("/api/conversation")
def get_conversation():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify([])
        
        conn = get_db_connection()
        conversations = conn.execute(
            'SELECT message, reply, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
            (user_id,)
        ).fetchall()
        conn.close()
        
        result = []
        for conv in conversations:
            result.append({
                'role': 'user',
                'content': conv['message']
            })
            result.append({
                'role': 'assistant', 
                'content': conv['reply']
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify([])

# حالة المستخدم
@app.route("/api/user/status")
def user_status():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'ضيف')
    user_role = session.get('user_role', 'user')
    
    return jsonify({
        'id': user_id,
        'name': user_name,
        'role': user_role,
        'isLoggedIn': bool(user_id)
    })

# معلومات المستخدم (مطلوب من الـ JavaScript)
@app.route("/api/user")
def get_user():
    user_id = session.get('user_id')
    user_name = session.get('user_name', 'ضيف')
    user_role = session.get('user_role', 'user')
    
    return jsonify({
        'id': user_id,
        'name': user_name,
        'role': user_role,
        'email': f'{user_id}@clainai.com'
    })

# مسح المحادثة
@app.route("/api/clear", methods=["POST"])
def clear_chat():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': True})
        
        conn = get_db_connection()
        conn.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        # مسح ملفات المستخدم أيضاً
        conn = get_db_connection()
        conn.execute('DELETE FROM uploaded_files WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        session.pop('current_file_id', None)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# تسجيل الخروج
@app.route("/api/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    if request.method == 'POST':
        return jsonify({'success': True})
    else:
        return redirect('/login')

if __name__ == "__main__":
    with app.app_context():
        init_db()
    print(f"🌐 **التطبيق جاهز على:** {BASE_URL}")
    print("👑 **المطور:** محمد عبدو - mohammedu3615@gmail.com")
    app.run(host='0.0.0.0', port=5000, debug=False)

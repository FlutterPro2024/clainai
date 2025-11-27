import sqlite3
import os
import requests
import time
from flask import Flask, request, jsonify, session, redirect, send_from_directory
from datetime import datetime, timezone
import hashlib
import secrets
from dotenv import load_dotenv
import PyPDF2
import docx

# Load environment
load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# استخدام قاعدة بيانات في الذاكرة لـ Vercel
DB_PATH = "/tmp/clainai.db" if 'VERCEL' in os.environ else "clainai.db"

# Auto-detect environment and set base URL
def get_base_url():
    if 'VERCEL' in os.environ:
        return 'https://clainai-deploy-qd5arwtrf-flutterpro2024s-projects.vercel.app'
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

print("=" * 60)
print("🚀 ClainAI - المساعد الذكي الإبداعي المتقدم!")
print("=" * 60)
print(f"📍 Base URL: {BASE_URL}")
print(f"🔑 OpenRouter Key: {OPENROUTER_API_KEY[:20] if OPENROUTER_API_KEY else 'None'}...")
print(f"🔍 Serper Search: {'✅' if SERPER_API_KEY else '❌'}")
print(f"🔐 GitHub OAuth: {'✅' if GITHUB_CLIENT_ID else '❌'}")
print(f"🔐 Google OAuth: {'✅' if GOOGLE_CLIENT_ID else '❌'}")
print(f"📄 PDF Support: ✅")
print(f"📝 Word Support: ✅")
print(f"🖼️ Image Analysis: ✅")
print(f"👑 Developer: محمد عبد القادر السراج - mohammedu3615@gmail.com")

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

# CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Routes الأساسية
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

# Routes فحص الصحة
@app.route("/api/health")
def health_check():
    try:
        init_db()
        return jsonify({
            "status": "healthy", 
            "database": "connected",
            "message": "✅ ClainAI is working perfectly!",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/check-tables")
def check_tables():
    try:
        conn = get_db_connection()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        return jsonify({
            "tables": [table[0] for table in tables],
            "count": len(tables),
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Routes OAuth
@app.route("/api/guest-login", methods=["POST", "GET"])
def guest_login():
    try:
        init_db()
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
        if request.method == 'POST':
            return jsonify({
                'success': True,
                'user': {'id': user_id, 'name': 'ضيف', 'role': 'user'}
            })
        else:
            return redirect('/')
    except Exception as e:
        print(f"❌ خطأ في تسجيل الدخول كضيف: {str(e)}")
        if request.method == 'POST':
            return jsonify({'error': str(e)}), 500
        else:
            return redirect('/login?error=guest_login_failed')

@app.route('/api/auth/github')
def github_auth():
    github_auth_url = f"https://github.com/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=user:email"
    return redirect(github_auth_url)

@app.route('/api/auth/google')
def google_auth():
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code&scope=email profile&access_type=offline"
    return redirect(google_auth_url)

# باقي ال routes الأساسية
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401
        data = request.json
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'الرسالة فارغة'}), 400
        user_id = session['user_id']
        
        # التحقق إذا كان السؤال عن المطور
        developer_keywords = ['مطور', 'مبرمج', 'صاحب', 'خالق', 'من صنع', 'who made you', 'developer', 'creator', 'who created you', 'برمجة', 'صنع', 'مين']
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in developer_keywords):
            developer_info = "✅ تم تطويري بواسطة المهندس السوداني محمد عبد القادر السراج - خريج جامعة العلوم وتقانة المعلومات (IT) وخريج تكنولوجيا المعلومات والاتصالات (ICT) - البريد: mohammedu3615@gmail.com"
            conversation_id = hashlib.md5(f"{user_id}_{message}_{datetime.now().timestamp()}".encode()).hexdigest()
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO conversations (id, user_id, message, reply, model_used) VALUES (?, ?, ?, ?, ?)',
                (conversation_id, user_id, message, developer_info, "developer_info")
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'reply': developer_info, 'model_used': 'developer_info'})

        # استخدام OpenRouter للأسئلة العادية
        models = ["meta-llama/llama-3-70b-instruct:nitro", "openai/gpt-3.5-turbo", "google/gemini-2.0-flash-exp:free"]
        response = None
        used_model = ""
        for model in models:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": f"{BASE_URL}",
                        "X-Title": "ClainAI Chat"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": f"أنت مساعد ذكي عربي. أجب بطريقة مفيدة وإبداعية.\n\nالسؤال: {message}"}],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    used_model = model
                    break
            except:
                continue

        if not response or response.status_code != 200:
            return jsonify({'error': 'جميع النماذج غير متاحة حالياً. يرجى المحاولة لاحقاً.'}), 503

        result = response.json()
        reply = result['choices'][0]['message']['content']
        conversation_id = hashlib.md5(f"{user_id}_{message}_{datetime.now().timestamp()}".encode()).hexdigest()
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO conversations (id, user_id, message, reply, model_used) VALUES (?, ?, ?, ?, ?)',
            (conversation_id, user_id, message, reply, used_model)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'reply': reply, 'model_used': used_model})
    except Exception as e:
        return jsonify({'error': f'حدث خطأ: {str(e)}'}), 500

if __name__ == "__main__":
    with app.app_context():
        init_db()
        print(f"🌐 التطبيق جاهز على: {BASE_URL}")
    app.run(host='0.0.0.0', port=5000, debug=False)

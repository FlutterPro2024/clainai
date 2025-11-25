import os
import sqlite3
from flask import Flask, request, jsonify, g, send_from_directory, session, redirect, url_for, render_template
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
import hashlib
import secrets
import json
import socket
import re
import random
import uuid
from werkzeug.utils import secure_filename

# Load environment
load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
SECRET_KEY = os.getenv("SECRET_KEY", "clainai-super-secret-key-2024")
DB_PATH = os.getenv("DB_PATH", "clainai.db")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Ov23liW5Tjp0CGKyZiiA")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "9c843fa45f6ea8abfc82774b1395d98a3a925dee")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "77933091754-idsptg4osou4ipj9r434sdg8rpmb6289.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/auth/google/callback")

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY

print("=" * 60)
print("🚀 ClainAI - المساعد الذكي المتكامل!")
print("=" * 60)

# Database functions
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def init_db():
    """تهيئة قاعدة البيانات مع الجداول المطلوبة"""
    db = get_db()
    c = db.cursor()

    # جدول المستخدمين مع جميع الحقول المطلوبة
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT,
            oauth_provider TEXT,
            github_username TEXT,
            last_login TEXT
        )
    ''')

    # جدول المحادثات
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # إنشاء مستخدم مسؤول افتراضي إذا لم يكن موجوداً
    c.execute("SELECT * FROM users WHERE email = ?", ("admin@clainai.com",))
    if not c.fetchone():
        password_hash = hashlib.sha256("clainai123".encode()).hexdigest()
        c.execute(
            "INSERT INTO users (email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("admin@clainai.com", "مدير النظام", password_hash, "admin", datetime.now(timezone.utc).isoformat())
        )

    db.commit()
    print("✅ تم إنشاء/تحديث قاعدة البيانات بنجاح")

# Routes
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")
    return send_from_directory("static", "index.html")

@app.route("/login")
def login_page():
    return send_from_directory("static", "login.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

# Authentication routes
@app.route("/api/guest-login")
def guest_login():
    """دخول ضيف مع تجربة كاملة"""
    try:
        guest_id = f"guest_{secrets.token_hex(12)}"

        session["user_id"] = guest_id
        session["user_role"] = "user"
        session["user_name"] = "ضيف"
        session["user_email"] = f"guest_{secrets.token_hex(6)}@clainai.com"
        session["oauth_provider"] = "guest"

        # رسالة ترحيب
        session_id = f"user_{guest_id}"
        welcome_message = """🎉 **مرحباً بك كضيف!** 🌟

استمتع بتجربة ClainAI الكاملة بدون إنشاء حساب.

**💫 يمكنك:**
- محادثة ذكية مع المساعد
- تجربة جميع المميزات
- طرح أي سؤال في أي مجال

**🚀 جرب هذه الأسئلة:**
• "ما هو الذكاء الاصطناعي؟"
• "كيف أتعلم البرمجة؟"
• "اشرح لي الحوسبة السحابية"

استمتع! 😊"""

        save_message(session_id, "assistant", welcome_message)

        return jsonify({"success": True, "redirect": "/"})

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

# GitHub OAuth Routes
@app.route('/api/auth/github')
def github_login():
    """بدء عملية تسجيل الدخول بـ GitHub"""
    print("🚀 بدء عملية GitHub OAuth...")

    # إنشاء state عشوائي لمنع هجمات CSRF
    state = secrets.token_urlsafe(16)
    session['github_oauth_state'] = state

    # استخدام callback URL ثابت
    callback_url = "http://localhost:5000/api/auth/github/callback"

    print(f"📍 استخدام callback URL: {callback_url}")

    # معلمات طلب المصادقة
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': callback_url,
        'scope': 'user:email',
        'state': state,
        'allow_signup': 'true'
    }

    # إعادة التوجيه لـ GitHub
    auth_url = f"https://github.com/login/oauth/authorize?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    print(f"🔗 رابط المصادقة: {auth_url}")
    return redirect(auth_url)

@app.route('/api/auth/github/callback')
def github_callback():
    """معالجة رد GitHub"""
    try:
        print("🔄 معالجة رد GitHub OAuth...")

        # التحقق من state
        stored_state = session.get('github_oauth_state')
        received_state = request.args.get('state')

        print(f"🔍 State - المخزن: {stored_state}, المستلم: {received_state}")

        if stored_state != received_state:
            print("❌ State غير متطابق!")
            return redirect('/login?error=invalid_state')

        # الحصول على code من GitHub
        code = request.args.get('code')
        if not code:
            print("❌ لا يوجد code في الرد")
            return redirect('/login?error=no_code')

        print(f"✅ تم استلام code: {code}")

        # استخدام callback URL ثابت
        callback_url = "http://localhost:5000/api/auth/github/callback"

        # استبدال code بـ access token
        token_data = {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
            'redirect_uri': callback_url
        }

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        print("🔄 جاري طلب access token...")
        token_response = requests.post('https://github.com/login/oauth/access_token', json=token_data, headers=headers)
        token_json = token_response.json()

        print(f"📨 رد token: {token_json}")

        if 'access_token' not in token_json:
            print("❌ لم يتم استلام access token")
            return redirect('/login?error=no_token')

        access_token = token_json['access_token']
        print(f"✅ تم الحصول على access token: {access_token[:10]}...")

        # الحصول على بيانات المستخدم
        user_headers = {
            'Authorization': f'token {access_token}',
            'Accept': 'application/json'
        }

        # بيانات المستخدم الأساسية
        print("🔄 جاري طلب بيانات المستخدم...")
        user_response = requests.get('https://api.github.com/user', headers=user_headers)
        user_data = user_response.json()

        # الحصول على البريد الإلكتروني
        email_response = requests.get('https://api.github.com/user/emails', headers=user_headers)
        email_data = email_response.json()

        # البحث عن البريد الأساسي
        primary_email = next((email['email'] for email in email_data if email['primary']), None)
        if not primary_email:
            primary_email = user_data.get('email', f"github_{user_data['id']}@clainai.com")

        print(f"✅ البريد الأساسي: {primary_email}")

        # تجهيز بيانات المستخدم
        user_info = {
            'id': str(user_data['id']),
            'name': user_data.get('name', user_data.get('login', 'مستخدم GitHub')),
            'email': primary_email,
            'avatar': user_data.get('avatar_url'),
            'username': user_data.get('login'),
            'provider': 'github'
        }

        print(f"🎯 بيانات المستخدم النهائية: {user_info}")

        # معالجة المستخدم
        return handle_github_user(user_info)

    except Exception as e:
        print(f"❌ GitHub OAuth Error: {e}")
        return redirect('/login?error=auth_failed')

def handle_github_user(user_data):
    """حفظ وتجهيز بيانات مستخدم GitHub"""
    try:
        db = get_db()
        c = db.cursor()

        print(f"💾 حفظ بيانات المستخدم: {user_data['email']}")

        # البحث عن المستخدم بالبريد الإلكتروني
        c.execute("SELECT * FROM users WHERE email = ?", (user_data['email'],))
        existing_user = c.fetchone()

        if existing_user:
            # تحديث المستخدم الحالي
            user_id = existing_user['id']
            print(f"🔄 تحديث مستخدم موجود: {user_id}")
            c.execute(
                "UPDATE users SET name = ?, last_login = ?, oauth_provider = ?, github_username = ? WHERE id = ?",
                (user_data['name'], datetime.now(timezone.utc).isoformat(), 'github', user_data.get('username'), user_id)
            )
        else:
            # إنشاء مستخدم جديد
            password_hash = hashlib.sha256(secrets.token_hex(32).encode()).hexdigest()
            print(f"🆕 إنشاء مستخدم جديد: {user_data['email']}")
            c.execute(
                """INSERT INTO users
                (email, name, password_hash, role, created_at, oauth_provider, github_username)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_data['email'], user_data['name'], password_hash, 'user',
                 datetime.now(timezone.utc).isoformat(), 'github', user_data.get('username'))
            )
            user_id = c.lastrowid

        db.commit()

        # حفظ في الجلسة
        session["user_id"] = user_id
        session["user_email"] = user_data['email']
        session["user_name"] = user_data['name']
        session["user_role"] = 'user'
        session["oauth_provider"] = 'github'
        session["github_username"] = user_data.get('username')

        print(f"✅ تم حفظ الجلسة - user_id: {user_id}")

        # تنظيف state
        session.pop('github_oauth_state', None)

        # رسالة ترحيب
        session_id = f"user_{user_id}"
        welcome_message = f"""🎉 **مرحباً بك {user_data['name'] or user_data['username']}!** 🌟

تم تسجيل دخولك بنجاح باستخدام GitHub.

**👤 معلومات حسابك:**
- البريد: {user_data['email']}
- اسم المستخدم: @{user_data.get('username', 'غير معروف')}

**💫 المميزات المتاحة:**
- محادثة ذكية مع ClainAI
- حفظ سجل المحادثات
- تجربة كاملة لجميع المميزات

**🚀 ابدأ رحلتك المعرفية!**
اسألني عن أي شيء وسأجيبك بذكاء! 😊"""

        if not has_welcome_message(session_id):
            save_message(session_id, "assistant", welcome_message)

        print("✅ تم تسجيل الدخول بنجاح!")
        return redirect('/')

    except Exception as e:
        print(f"❌ GitHub User Handling Error: {e}")
        return redirect('/login?error=user_save_failed')

# Google OAuth Routes
@app.route('/api/auth/google')
def google_login():
    """بدء عملية تسجيل الدخول بـ Google"""
    print("🚀 بدء عملية Google OAuth...")
    print(f"🔑 Using Client ID: {GOOGLE_CLIENT_ID}")

    # إنشاء state عشوائي لمنع هجمات CSRF
    state = secrets.token_urlsafe(16)
    session['google_oauth_state'] = state

    # استخدام redirect_uri ثابت
    redirect_uri = 'http://localhost:5000/api/auth/google/callback'
    print(f"📍 استخدام redirect_uri: {redirect_uri}")

    # معلمات طلب المصادقة
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent'
    }

    # إعادة التوجيه لـ Google
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    print(f"🔗 رابط المصادقة: {auth_url}")
    return redirect(auth_url)

@app.route('/api/auth/google/callback')
def google_callback():
    """معالجة رد Google"""
    try:
        print("🔄 معالجة رد Google OAuth...")

        # التحقق من state
        stored_state = session.get('google_oauth_state')
        received_state = request.args.get('state')

        print(f"🔍 State - المخزن: {stored_state}, المستلم: {received_state}")

        if stored_state != received_state:
            print("❌ State غير متطابق!")
            return redirect('/login?error=invalid_state')

        # الحصول على code من Google
        code = request.args.get('code')
        if not code:
            print("❌ لا يوجد code في الرد")
            return redirect('/login?error=no_code')

        print(f"✅ تم استلام code: {code}")

        # استخدام redirect_uri ثابت
        redirect_uri = 'http://localhost:5000/api/auth/google/callback'

        # استبدال code بـ access token
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        print("🔄 جاري طلب access token...")
        token_response = requests.post('https://oauth2.googleapis.com/token', data=token_data, headers=headers)
        token_json = token_response.json()

        print(f"📨 رد token: {token_json}")

        if 'access_token' not in token_json:
            print("❌ لم يتم استلام access token")
            print(f"📝 تفاصيل الخطأ: {token_json}")
            return redirect('/login?error=no_token')

        access_token = token_json['access_token']
        print(f"✅ تم الحصول على access token: {access_token[:10]}...")

        # الحصول على بيانات المستخدم
        user_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }

        # بيانات المستخدم الأساسية
        print("🔄 جاري طلب بيانات المستخدم...")
        user_response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', headers=user_headers)
        user_data = user_response.json()

        print(f"👤 بيانات المستخدم: {user_data}")

        if 'error' in user_data:
            print(f"❌ خطأ في بيانات المستخدم: {user_data['error']}")
            return redirect('/login?error=user_info_failed')

        # تجهيز بيانات المستخدم
        user_info = {
            'id': str(user_data['id']),
            'name': user_data.get('name', 'مستخدم Google'),
            'email': user_data.get('email', f"google_{user_data['id']}@clainai.com"),
            'avatar': user_data.get('picture'),
            'provider': 'google'
        }

        print(f"🎯 بيانات المستخدم النهائية: {user_info}")

        # معالجة المستخدم
        return handle_google_user(user_info)

    except Exception as e:
        print(f"❌ Google OAuth Error: {e}")
        import traceback
        traceback.print_exc()
        return redirect('/login?error=auth_failed')

def handle_google_user(user_data):
    """حفظ وتجهيز بيانات مستخدم Google"""
    try:
        db = get_db()
        c = db.cursor()

        print(f"💾 حفظ بيانات المستخدم: {user_data['email']}")

        # البحث عن المستخدم بالبريد الإلكتروني
        c.execute("SELECT * FROM users WHERE email = ?", (user_data['email'],))
        existing_user = c.fetchone()

        if existing_user:
            # تحديث المستخدم الحالي
            user_id = existing_user['id']
            print(f"🔄 تحديث مستخدم موجود: {user_id}")
            c.execute(
                "UPDATE users SET name = ?, last_login = ?, oauth_provider = ? WHERE id = ?",
                (user_data['name'], datetime.now(timezone.utc).isoformat(), 'google', user_id)
            )
        else:
            # إنشاء مستخدم جديد
            password_hash = hashlib.sha256(secrets.token_hex(32).encode()).hexdigest()
            print(f"🆕 إنشاء مستخدم جديد: {user_data['email']}")
            c.execute(
                """INSERT INTO users
                (email, name, password_hash, role, created_at, oauth_provider)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_data['email'], user_data['name'], password_hash, 'user',
                 datetime.now(timezone.utc).isoformat(), 'google')
            )
            user_id = c.lastrowid

        db.commit()

        # حفظ في الجلسة
        session["user_id"] = user_id
        session["user_email"] = user_data['email']
        session["user_name"] = user_data['name']
        session["user_role"] = 'user'
        session["oauth_provider"] = 'google'

        print(f"✅ تم حفظ الجلسة - user_id: {user_id}")

        # تنظيف state
        session.pop('google_oauth_state', None)

        # رسالة ترحيب
        session_id = f"user_{user_id}"
        welcome_message = f"""🎉 **مرحباً بك {user_data['name']}!** 🌟

تم تسجيل دخولك بنجاح باستخدام Google.

**👤 معلومات حسابك:**
- البريد: {user_data['email']}
- طريقة الدخول: حساب Google

**💫 المميزات المتاحة:**
- محادثة ذكية مع ClainAI
- حفظ سجل المحادثات
- تجربة كاملة لجميع المميزات

**🚀 ابدأ رحلتك المعرفية!**
اسألني عن أي شيء وسأجيبك بذكاء! 😊"""

        if not has_welcome_message(session_id):
            save_message(session_id, "assistant", welcome_message)

        print("✅ تم تسجيل الدخول بنجاح!")
        return redirect('/')

    except Exception as e:
        print(f"❌ Google User Handling Error: {e}")
        import traceback
        traceback.print_exc()
        return redirect('/login?error=user_save_failed')

# Message functions
def save_message(session_id, role, content):
    """حفظ رسالة في قاعدة البيانات"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        db.commit()
        return True
    except Exception as e:
        print(f"Error saving message: {e}")
        return False

def get_messages(session_id, limit=50):
    """جلب رسائل المحادثة"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit)
        )
        messages = c.fetchall()
        return [{"role": msg[0], "content": msg[1], "timestamp": msg[2]} for msg in messages]
    except Exception as e:
        print(f"Error getting messages: {e}")
        return []

def has_welcome_message(session_id):
    """التحقق من وجود رسالة ترحيب"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'assistant'",
            (session_id,)
        )
        return c.fetchone()[0] > 0
    except:
        return False

# AI Chat API
@app.route("/api/chat", methods=["POST"])
def chat():
    """معالجة طلبات المحادثة مع OpenRouter الحقيقي"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "الرسالة فارغة"}), 400

        session_id = f"user_{session['user_id']}"

        # حفظ رسالة المستخدم
        save_message(session_id, "user", user_message)

        # جلب سجل المحادثة
        conversation_history = get_messages(session_id)

        # إعداد prompt للمساعد
        messages = [
            {
                "role": "system",
                "content": """أنت ClainAI، مساعد ذكي عربي متكامل.

🛠️ **معلومات المطور:**
- **المطور:** المهندس محمد عبدو
- **الخلفية التعليمية:** خريج تكنولوجيا المعلومات والاتصالات 
- **الجامعة:** جامعة العلوم وتقانة المعلومات
- **البريد الإلكتروني:** mohammedu3615@gmail.com

🎯 **مهمتك:**
- تقديم إجابات دقيقة ومفيدة باللغة العربية
- الشرح بطريقة مبسطة وشاملة  
- تقديم أمثلة عملية عندما يكون ذلك مناسباً
- الرد بتهذيب واحترام
- تقسيم الإجابات الطويلة إلى أقسام واضحة
- استخدام تنسيق Markdown لجعل الإجابات أكثر تنظيماً
- عندما يُسأل عن المطور أو من طورك، تقدم المعلومات أعلاه

❌ **تجنب:**
- الإجابات المختصرة جداً
- المعلومات غير المؤكدة  
- التحيز لأي جهة
- إنكار معلومات المطور عند السؤال عنها

كن مفيداً، دقيقاً، وواضحاً في جميع ردودك."""
            }
        ]

        # إضافة تاريخ المحادثة (آخر 8 رسائل)
        for msg in conversation_history[-8:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # إضافة الرسالة الجديدة
        messages.append({"role": "user", "content": user_message})

        print(f"🤖 إرسال طلب إلى OpenRouter...")
        print(f"📝 عدد الرسائل: {len(messages)}")
        print(f"💬 الرسالة: {user_message[:100]}...")

        # قائمة النماذج الشغالة
        available_models = [
            "meta-llama/llama-3-70b-instruct",  # نموذج قوي ومجاني
            "google/gemini-flash-1.5",          # نموذج سريع
            "microsoft/wizardlm-2-8x22b",       # نموذج متقدم
            "anthropic/claude-3-haiku"          # نموذج أنثروبيك
        ]

        # تجربة النماذج بالترتيب
        assistant_reply = None
        for model in available_models:
            try:
                # إرسال الطلب إلى OpenRouter
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "ClainAI"
                }

                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 4000,
                    "temperature": 0.7,
                }

                print(f"🔄 جرب النموذج: {model}")
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                print(f"📨 حالة الرد: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    assistant_reply = result["choices"][0]["message"]["content"]
                    print(f"✅ تم استلام رد بنجاح من {model}: {len(assistant_reply)} حرف")
                    break
                else:
                    print(f"❌ النموذج {model} غير متاح: {response.status_code}")
                    continue

            except Exception as e:
                print(f"❌ خطأ في النموذج {model}: {e}")
                continue

        # إذا فشلت جميع النماذج، استخدم رد افتراضي ذكي
        if not assistant_reply:
            print("⚠️ جميع النماذج فشلت، استخدام رد افتراضي")
            assistant_reply = generate_smart_response(user_message)

        # حفظ رد المساعد
        save_message(session_id, "assistant", assistant_reply)

        return jsonify({
            "response": assistant_reply,
            "message_count": len(conversation_history) + 1
        })

    except Exception as e:
        error_msg = f"حدث خطأ: {str(e)}"
        print(f"❌ {error_msg}")
        session_id = f"user_{session.get('user_id', 'guest')}"
        save_message(session_id, "assistant", "عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.")
        return jsonify({"error": error_msg}), 500

def generate_smart_response(user_message):
    """إنشاء ردود ذكية إذا فشل الاتصال بالـ AI"""
    message_lower = user_message.lower()

    # ردود ذكية مبرمجة مسبقاً
    responses = {
        "hello": "مرحباً بك! أنا ClainAI، مساعدك الذكي. كيف يمكنني مساعدتك اليوم؟ 😊",
        "hi": "أهلاً وسهلاً! أنا هنا لمساعدتك في أي استفسار. 💫",
        "مرحبا": "مرحباً بك! أنا ClainAI، مساعدك الذكي العربي. كيف يمكنني خدمتك؟ 🌟",
        "السلام عليكم": "وعليكم السلام ورحمة الله وبركاته! أنا ClainAI، كيف يمكنني مساعدتك؟ 🤲",
        "سلام": "وعليكم السلام! أنا ClainAI، مساعدك الذكي. اسألني عن أي شيء! 😊",
        "شكرا": "العفو! دائماً سعيد بمساعدتك. هل هناك شيء آخر تريد الاستفسار عنه؟ 😊",
        "ما هو الذكاء الاصطناعي": """**الذكاء الاصطناعي (Artificial Intelligence)** 🤖

هو مجال من علوم الكمبيوتر يهتم بإنشاء أنظمة قادرة على أداء مهام تتطلب ذكاءً بشرياً مثل:

🔹 **التعلم** - القدرة على تحسين الأداء من خلال التجربة
🔹 **الاستدلال** - حل المشكلات المعقدة
🔹 **الإدراك** - فهم الصور والنصوص والأصوات
🔹 **التفاعل** - التواصل بلغة طبيعية

**أنواع الذكاء الاصطناعي:**
• 🧠 **الذكاء الضيق** - متخصص في مهام محددة
• 🌟 **الذكاء العام** - يشبه الذكاء البشري (ما زال قيد التطوير)

**التطبيقات:** السيارات ذاتية القيادة، المساعدات الذكية، التشخيص الطبي، وغيرها الكثير!""",

        "كيف أتعلم البرمجة": """**دليل تعلم البرمجة خطوة بخطوة** 💻

🎯 **الخطوة 1: اختر لغة برمجة مناسبة للمبتدئين:**
• 🐍 **Python** - الأفضل للمبتدئين (بسيطة وقوية)
• 🌐 **JavaScript** - لتطوير الويب
• ☕ **Java** - للتطبيقات الكبيرة

📚 **الخطوة 2: مصادر التعلم المجانية:**
• موقع **freeCodeCamp** (عربي وإنجليزي)
• قناة **Elzero Web School** على YouTube
• منصة **Coursera** و **edX**

🛠️ **الخطوة 3: مشاريع عملية:**
• موقع ويب شخصي
• تطبيق آلة حاسبة
• لعبة بسيطة

💡 **نصيحة:** الممارسة المستمرة أهم من الكمية! ابدأ بمشاريع صغيرة وتدرج.""",

        "اشرح الحوسبة السحابية": """**🌐 الحوسبة السحابية (Cloud Computing)**

هي تقديم خدمات الحوسبة عبر الإنترنت بدلاً من الاعتماد على الأجهزة المحلية.

**✨ المميزات:**
• 💰 **توفير التكلفة** - لا حاجة لشراء أجهزة باهظة
• 📈 **مرونة** - زيادة أو تقليل الموارد حسب الحاجة
• 🔒 **أمان** - حماية بيانات متقدمة
• 🌍 **وصول عالمي** - من أي مكان وفي أي وقت

**🚀 أنواع الخدمات:**
1. **IaaS** - البنية التحتية كخدمة
2. **PaaS** - المنصة كخدمة
3. **SaaS** - البرنامج كخدمة

**أمثلة:** 🌩️ Amazon Web Services, ☁️ Microsoft Azure, ☁️ Google Cloud""",

        # ===== الردود الجديدة عن المطور =====
        "من طورك": """🛠️ **معلومات المطور:**

👨‍💻 **المطور:** المهندس محمد عبدو  
🎓 **الخلفية التعليمية:** خريج تكنولوجيا المعلومات والاتصالات  
🏫 **الجامعة:** جامعة العلوم وتقانة المعلومات  
📧 **البريد الإلكتروني:** mohammedu3615@gmail.com

تم تطوير ClainAI بعناية لتقديم أفضل تجربة محادثة ذكية باللغة العربية! 🌟""",

        "من مبتكرك": """🛠️ **معلومات المطور:**

👨‍💻 **المطور:** المهندس محمد عبدو  
🎓 **الخلفية التعليمية:** خريج تكنولوجيا المعلومات والاتصالات  
🏫 **الجامعة:** جامعة العلوم وتقانة المعلومات  
📧 **البريد الإلكتروني:** mohammedu3615@gmail.com

تم تطوير ClainAI بعناية لتقديم أفضل تجربة محادثة ذكية باللغة العربية! 🌟""",

        "من صنعك": """🛠️ **معلومات المطور:**

👨‍💻 **المطور:** المهندس محمد عبدو  
🎓 **الخلفية التعليمية:** خريج تكنولوجيا المعلومات والاتصالات  
🏫 **الجامعة:** جامعة العلوم وتقانة المعلومات  
📧 **البريد الإلكتروني:** mohammedu3615@gmail.com

تم تطوير ClainAI بعناية لتقديم أفضل تجربة محادثة ذكية باللغة العربية! 🌟""",
        
        "من هو محمد عبدو": """🛠️ **معلومات المطور:**

👨‍💻 **المطور:** المهندس محمد عبدو  
🎓 **الخلفية التعليمية:** خريج تكنولوجيا المعلومات والاتصالات  
🏫 **الجامعة:** جامعة العلوم وتقانة المعلومات  
📧 **البريد الإلكتروني:** mohammedu3615@gmail.com

هو مطور ومبرمج متخصص في الذكاء الاصطناعي وتطبيقات الويب! 🌟"""
    }

    # البحث عن أفضل تطابق
    for key, response in responses.items():
        if key in message_lower:
            return response

    # إذا لم يوجد تطابق، استخدم رد عام ذكي
    general_responses = [
        f"أهلاً بك! سؤالك '{user_message}' مثير للاهتمام. للأسف حالياً أركز على الذكاء الاصطناعي والبرمجة والتقنية. هل لديك سؤال في هذه المجالات؟ 🤖",
        f"شكراً لسؤالك! أنا متخصص في المواضيع التقنية والبرمجة والذكاء الاصطناعي. اسألني عن أي شيء في هذه المجالات وسأكون سعيداً بمساعدتك! 💻",
        f"سؤال رائع! حالياً أقدم إجابات في مجالات التقنية والبرمجة. جرب أسئلة مثل 'ما هو الذكاء الاصطناعي؟' أو 'كيف أتعلم البرمجة؟' 🌟"
    ]

    return random.choice(general_responses)

# ======== دوال المرفقات المحسنة ========

@app.route("/api/upload", methods=["POST"])
def upload_file():
    """رفع الملفات والصور"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        if 'file' not in request.files:
            return jsonify({"error": "لم يتم اختيار ملف"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "لم يتم اختيار ملف"}), 400

        # السماح بأنواع الملفات
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'doc', 'docx'}
        if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
            # حفظ الملف
            filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
            upload_folder = "uploads"
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # حفظ رسالة في المحادثة
            session_id = f"user_{session['user_id']}"
            file_type = "صورة" if file.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif')) else "ملف"
            
            user_message = f"📎 قمت بمشاركة {file_type}: {file.filename}"
            save_message(session_id, "user", user_message)

            # إرسال رد ذكي
            file_size = f"{(os.path.getsize(file_path) / 1024):.1f} KB"
            assistant_reply = f"✅ **تم استلام {file_type} بنجاح!**\n\n📁 **اسم الملف:** {file.filename}\n📊 **الحجم:** {file_size}\n💾 **النوع:** {file_type}\n\n💡 *يمكنك وصف محتوى الملف وسأساعدك في تحليله!*"

            save_message(session_id, "assistant", assistant_reply)

            return jsonify({
                "success": True,
                "message": f"تم رفع {file_type} بنجاح",
                "filename": filename,
                "type": file_type,
                "size": file_size
            })

        return jsonify({"error": "نوع الملف غير مدعوم"}), 400

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

@app.route("/api/location", methods=["POST"])
def share_location():
    """مشاركة الموقع"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        data = request.get_json()
        lat = data.get('lat')
        lng = data.get('lng')

        if not lat or not lng:
            return jsonify({"error": "إحداثيات الموقع مطلوبة"}), 400

        session_id = f"user_{session['user_id']}"
        
        user_message = f"📍 موقعي: {lat}, {lng}"
        save_message(session_id, "user", user_message)

        assistant_reply = f"**🌍 تم استلام موقعك!**\n\n📍 **الإحداثيات:** {lat}, {lng}\n\n💫 *يمكنني مساعدتك في:*\n• معلومات عن المنطقة\n• الطقس\n• أماكن قريبة\n• أي استفسار عن الموقع*"

        save_message(session_id, "assistant", assistant_reply)

        return jsonify({
            "success": True, 
            "message": "تم مشاركة الموقع",
            "coordinates": {"lat": lat, "lng": lng}
        })

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

# ======== دوال المحادثة والإدارة ========

@app.route("/api/conversation")
def get_conversation():
    """جلب سجل المحادثة"""
    if "user_id" not in session:
        return jsonify({"error": "غير مسجل الدخول"}), 401

    session_id = f"user_{session['user_id']}"
    messages = get_messages(session_id)

    return jsonify({
        "messages": messages,
        "user_info": {
            "name": session.get("user_name", "مستخدم"),
            "email": session.get("user_email", ""),
            "role": session.get("user_role", "user")
        }
    })

@app.route("/api/history")
def get_history():
    """جلب سجل المحادثة (للتطابق مع الـ frontend)"""
    return get_conversation()

@app.route("/api/logout")
def logout():
    """تسجيل الخروج"""
    session.clear()
    return jsonify({"success": True, "redirect": "/login"})

@app.route("/api/user")
def get_user():
    """الحصول على معلومات المستخدم"""
    if "user_id" not in session:
        return jsonify({"error": "غير مسجل الدخول"}), 401

    return jsonify({
        "id": session["user_id"],
        "name": session.get("user_name", "مستخدم"),
        "email": session.get("user_email", ""),
        "role": session.get("user_role", "user"),
        "provider": session.get("oauth_provider", "local")
    })

@app.route("/api/clear", methods=["POST"])
def clear_conversation():
    """مسح سجل المحادثة"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        session_id = f"user_{session['user_id']}"

        db = get_db()
        c = db.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        db.commit()

        # إضافة رسالة ترحيب جديدة بعد المسح
        welcome_message = """🎉 **مرحباً بك من جديد!** 🌟

تم مسح المحادثة السابقة بنجاح.

**💫 جرب هذه الأسئلة:**
• "ما هو الذكاء الاصطناعي؟"
• "كيف أتعلم البرمجة؟"
• "اشرح لي الحوسبة السحابية"

استمتع بمحادثة جديدة! 😊"""

        save_message(session_id, "assistant", welcome_message)

        return jsonify({"success": True, "message": "تم مسح المحادثة"})

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

# Debug routes
@app.route("/api/debug/github")
def debug_github():
    """تصحيح إعدادات GitHub OAuth"""
    return jsonify({
        'status': 'ready',
        'client_id': GITHUB_CLIENT_ID,
        'client_secret_set': bool(GITHUB_CLIENT_SECRET),
        'callback_url': "http://localhost:5000/api/auth/github/callback",
        'session_keys': list(session.keys())
    })

@app.route("/api/debug/google")
def debug_google():
    """تصحيح إعدادات Google OAuth"""
    return jsonify({
        'status': 'ready',
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret_set': bool(GOOGLE_CLIENT_SECRET),
        'callback_url': "http://localhost:5000/api/auth/google/callback",
        'session_keys': list(session.keys())
    })

@app.route("/api/debug/db")
def debug_db():
    """تصحيح قاعدة البيانات"""
    try:
        db = get_db()
        c = db.cursor()

        # جلب معلومات الجداول
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [table[0] for table in c.fetchall()]

        table_info = {}
        for table in tables:
            c.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in c.fetchall()]
            table_info[table] = columns

        # جلب عدد المستخدمين
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM messages")
        message_count = c.fetchone()[0]

        return jsonify({
            "tables": table_info,
            "user_count": user_count,
            "message_count": message_count,
            "session_user": session.get("user_id")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ======== دوال PWA الجديدة ========

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

# إضافة header لـ PWA
@app.after_request
def add_pwa_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

# ======== نهاية دوال PWA ========

# Main execution
if __name__ == "__main__":
    with app.app_context():
        init_db()

        # الحصول على عنوان IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        print(f"📍 Local: http://localhost:5000")
        print(f"🌐 Network: http://{local_ip}:5000")
        print(f"📧 Developer: admin@clainai.com / clainai123")
        print("\n💫 **المميزات الرئيسية**:")
        print("   💬 محادثة ذكية وطبيعية")
        print("   🧠 فهم عميق للنية والسياق")
        print("   📚 إجابات مفصلة وشاملة")
        print("   🌍 دعم كامل للعربية")
        print("   📱 واجهة مستخدم متكاملة")
        print("   🔐 تسجيل دخول بـ GitHub OAuth")
        print("   🔐 تسجيل دخول بـ Google OAuth")
        print("   📎 رفع الملفات والصور")
        print("   📍 مشاركة الموقع")
        print("\n📱 من جهاز آخر: http://{}:5000".format(local_ip))
        print("\n🔍 **جرب هذه الأسئلة الذكية**:")
        print("   - 'ما هو الذكاء الاصطناعي?' 🤖")
        print("   - 'اشرح الحوسبة السحابية' 🌐")
        print("   - 'كيف أتعلم البرمجة?' 💻")
        print("   - 'من طورك?' 👨‍💻")
        print("   - 'من هو محمد عبدو?' 🎓")

    app.run(host="0.0.0.0", port=5000, debug=True)

import os
import sqlite3
from flask import Flask, request, jsonify, g, send_from_directory, session, redirect, url_for, render_template
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
import hashlib
import secrets
import json

# Load environment
load_dotenv()

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
SECRET_KEY = os.getenv("SECRET_KEY", "clainai-super-secret-key-2024-pro-max")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Ov23lihMk0lVKB9t8CGm")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your_github_client_secret_here")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "77933091754-idsptg4osou4ipj9r434sdg8rpmb6289.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")

# استخدام قاعدة بيانات في الذاكرة لـ Vercel
DB_PATH = "/tmp/clainai.db" if 'VERCEL' in os.environ else ":memory:"

# Auto-detect environment and set base URL
def get_base_url():
    if 'VERCEL' in os.environ:
        return 'https://clainai.vercel.app'
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
print("🚀 ClainAI - المساعد الذكي الإبداعي النهائي!")
print("=" * 60)
print(f"📍 Base URL: {BASE_URL}")
print(f"🔑 OpenRouter Key: {OPENROUTER_API_KEY[:20]}...")
print(f"🔐 GitHub OAuth: {'✅' if GITHUB_CLIENT_ID else '❌'}")
print(f"🔐 Google OAuth: {'✅' if GOOGLE_CLIENT_ID else '❌'}")
print(f"👑 Developer: محمد عبدو - mohammedu3615@gmail.com")

# Database functions
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        init_db()
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def init_db():
    """تهيئة قاعدة البيانات"""
    db = get_db()
    c = db.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            oauth_provider TEXT,
            github_id TEXT,
            google_id TEXT,
            avatar_url TEXT,
            last_login TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            model_used TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.commit()
    print("✅ تم إنشاء قاعدة البيانات بنجاح")

# ========== Routes الأساسية ==========

@app.route("/")
def index():
    """الصفحة الرئيسية"""
    if "user_id" not in session:
        return redirect("/login")
    return send_from_directory("static", "index.html")

@app.route("/login")
def login_page():
    """صفحة تسجيل الدخول"""
    return send_from_directory("static", "login.html")

@app.route("/static/<path:path>")
def serve_static(path):
    """خدمة الملفات الثابتة"""
    return send_from_directory("static", path)

# ========== نظام الدخول كضيف ==========

@app.route("/api/guest-login", methods=["POST", "GET"])
def guest_login():
    """نظام الدخول كضيف"""
    try:
        # تنظيف الجلسة السابقة
        session.clear()
        
        # إعداد جلسة الضيف
        session["user_id"] = f"guest_{secrets.token_hex(8)}"
        session["user_name"] = "ضيف"
        session["user_role"] = "guest"
        session["oauth_provider"] = "guest"
        session.permanent = True

        # رسالة ترحيب
        welcome_message = """🎉 **مرحباً بك في ClainAI الإبداعي!** 🌟

**🧠 أنا مساعد ذكي عربي متكامل**
- أجيب على أي سؤال تقني، علمي، أدبي
- أكتب أكواد برمجية متقدمة
- أشرح المفاهيم المعقدة
- أبدع في الإجابات

**🚀 جرب هذه الأسئلة:**
• "اكتب كود Python لموقع ويب"
• "اشرح لي الذكاء الاصطناعي" 
• "كيفية عمل تطبيق مهام"
• "اكتب قصة خيالية"

**🔐 طرق الدخول المتاحة:**
- الدخول كضيف (مجاني)
- تسجيل الدخول بـ GitHub
- تسجيل الدخول بـ Google

**👨‍💻 المطور:** محمد عبدو  
**📧 البريد:** mohammedu3615@gmail.com

اسألني أي شيء! 🚀"""

        save_message(session["user_id"], "assistant", welcome_message)

        return jsonify({
            "success": True,
            "message": "تم الدخول كضيف بنجاح",
            "redirect": "/"
        })

    except Exception as e:
        return jsonify({"error": f"حدث خطأ في الدخول: {str(e)}"}), 500

# ========== GitHub OAuth ==========

@app.route('/api/auth/github')
def github_login():
    """بدء عملية تسجيل الدخول بـ GitHub"""
    print("🚀 بدء عملية GitHub OAuth...")

    # إنشاء state عشوائي آمن
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'github'

    # بناء رابط المصادقة
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'user:email read:user',
        'state': state,
        'allow_signup': 'true'
    }

    auth_url = f"https://github.com/login/oauth/authorize?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    print(f"🔗 رابط GitHub OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/api/auth/github/callback')
def github_callback():
    """معالجة رد GitHub"""
    try:
        print("🔄 معالجة رد GitHub OAuth...")

        # التحقق من state
        stored_state = session.get('oauth_state')
        received_state = request.args.get('state')

        if not stored_state or stored_state != received_state:
            print("❌ State غير متطابق أو منتهي!")
            return redirect('/login?error=invalid_state')

        # الحصول على code
        code = request.args.get('code')
        if not code:
            print("❌ لا يوجد code في الرد")
            return redirect('/login?error=no_code')

        print(f"✅ تم استلام code من GitHub")

        # استبدال code بـ access token
        token_data = {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
            'redirect_uri': GITHUB_REDIRECT_URI
        }

        token_response = requests.post(
            'https://github.com/login/oauth/access_token',
            json=token_data,
            headers={'Accept': 'application/json'},
            timeout=30
        )

        if token_response.status_code != 200:
            print(f"❌ خطأ في الحصول على token: {token_response.text}")
            return redirect('/login?error=token_failed')

        token_json = token_response.json()
        access_token = token_json.get('access_token')

        if not access_token:
            print("❌ لم يتم استلام access token")
            return redirect('/login?error=no_token')

        print(f"✅ تم الحصول على access token من GitHub")

        # الحصول على بيانات المستخدم
        user_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }

        # بيانات المستخدم الأساسية
        user_response = requests.get('https://api.github.com/user', headers=user_headers)
        if user_response.status_code != 200:
            print("❌ خطأ في بيانات المستخدم")
            return redirect('/login?error=user_info_failed')

        user_data = user_response.json()

        # الحصول على البريد الإلكتروني
        email_response = requests.get('https://api.github.com/user/emails', headers=user_headers)
        email_data = email_response.json() if email_response.status_code == 200 else []

        # البحث عن البريد الأساسي
        primary_email = next((email['email'] for email in email_data if email['primary']), None)
        if not primary_email:
            primary_email = user_data.get('email', f"github_{user_data['id']}@clainai.com")

        # تجهيز بيانات المستخدم
        user_info = {
            'github_id': str(user_data['id']),
            'name': user_data.get('name', user_data.get('login', 'مستخدم GitHub')),
            'email': primary_email,
            'avatar_url': user_data.get('avatar_url'),
            'username': user_data.get('login'),
        }

        print(f"✅ بيانات مستخدم GitHub: {user_info['name']} ({user_info['email']})")

        # حفظ المستخدم في قاعدة البيانات
        return handle_oauth_user(user_info, 'github')

    except Exception as e:
        print(f"❌ خطأ في GitHub OAuth: {e}")
        return redirect('/login?error=auth_failed')

# ========== Google OAuth ==========

@app.route('/api/auth/google')
def google_login():
    """بدء عملية تسجيل الدخول بـ Google"""
    print("🚀 بدء عملية Google OAuth...")

    # إنشاء state عشوائي آمن
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'google'

    # بناء رابط المصادقة
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent'
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    print(f"🔗 رابط Google OAuth: {auth_url}")
    return redirect(auth_url)

@app.route('/api/auth/google/callback')
def google_callback():
    """معالجة رد Google"""
    try:
        print("🔄 معالجة رد Google OAuth...")

        # التحقق من state
        stored_state = session.get('oauth_state')
        received_state = request.args.get('state')

        if not stored_state or stored_state != received_state:
            print("❌ State غير متطابق أو منتهي!")
            return redirect('/login?error=invalid_state')

        # الحصول على code
        code = request.args.get('code')
        if not code:
            print("❌ لا يوجد code في الرد")
            return redirect('/login?error=no_code')

        print(f"✅ تم استلام code من Google")

        # استبدال code بـ access token
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }

        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )

        if token_response.status_code != 200:
            print(f"❌ خطأ في الحصول على token: {token_response.text}")
            return redirect('/login?error=token_failed')

        token_json = token_response.json()
        access_token = token_json.get('access_token')

        if not access_token:
            print("❌ لم يتم استلام access token")
            return redirect('/login?error=no_token')

        print(f"✅ تم الحصول على access token من Google")

        # الحصول على بيانات المستخدم
        user_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }

        user_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers=user_headers
        )

        if user_response.status_code != 200:
            print("❌ خطأ في بيانات المستخدم")
            return redirect('/login?error=user_info_failed')

        user_data = user_response.json()

        # تجهيز بيانات المستخدم
        user_info = {
            'google_id': str(user_data['id']),
            'name': user_data.get('name', 'مستخدم Google'),
            'email': user_data.get('email', f"google_{user_data['id']}@clainai.com"),
            'avatar_url': user_data.get('picture'),
            'locale': user_data.get('locale', 'ar')
        }

        print(f"✅ بيانات مستخدم Google: {user_info['name']} ({user_info['email']})")

        # حفظ المستخدم في قاعدة البيانات
        return handle_oauth_user(user_info, 'google')

    except Exception as e:
        print(f"❌ خطأ في Google OAuth: {e}")
        return redirect('/login?error=auth_failed')

def handle_oauth_user(user_data, provider):
    """حفظ وتجهيز بيانات مستخدم OAuth"""
    try:
        db = get_db()
        c = db.cursor()

        # تحديد معرف المستخدم بناءً على المزود
        user_id_field = f'{provider}_id'
        user_id_value = user_data.get(user_id_field)

        if not user_id_value:
            print(f"❌ لا يوجد {user_id_field} في بيانات المستخدم")
            return redirect('/login?error=invalid_user_data')

        # البحث عن المستخدم بالبريد أو المعرف
        c.execute(
            f"SELECT * FROM users WHERE email = ? OR {user_id_field} = ?",
            (user_data['email'], user_id_value)
        )
        existing_user = c.fetchone()

        if existing_user:
            # تحديث المستخدم الحالي
            user_id = existing_user['id']
            print(f"🔄 تحديث مستخدم موجود: {user_id}")
            c.execute(f"""
                UPDATE users SET
                name = ?, avatar_url = ?, last_login = ?, oauth_provider = ?,
                {user_id_field} = ?, is_active = 1
                WHERE id = ?
            """, (
                user_data['name'], user_data.get('avatar_url'),
                datetime.now(timezone.utc).isoformat(), provider,
                user_id_value, user_id
            ))
        else:
            # إنشاء مستخدم جديد
            password_hash = hashlib.sha256(secrets.token_hex(32).encode()).hexdigest()
            print(f"🆕 إنشاء مستخدم جديد: {user_data['email']}")
            c.execute(f"""
                INSERT INTO users
                (email, name, password_hash, role, created_at, oauth_provider,
                 {user_id_field}, avatar_url, last_login, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                user_data['email'], user_data['name'], password_hash, 'user',
                datetime.now(timezone.utc).isoformat(), provider,
                user_id_value, user_data.get('avatar_url'),
                datetime.now(timezone.utc).isoformat()
            ))
            user_id = c.lastrowid

        db.commit()

        # حفظ في الجلسة
        session.clear()
        session["user_id"] = user_id
        session["user_email"] = user_data['email']
        session["user_name"] = user_data['name']
        session["user_role"] = 'user'
        session["oauth_provider"] = provider
        session["avatar_url"] = user_data.get('avatar_url')
        session.permanent = True

        # تنظيف state
        session.pop('oauth_state', None)

        print(f"✅ تم تسجيل دخول المستخدم: {user_data['name']} (ID: {user_id})")

        # رسالة ترحيب للمستخدم المسجل
        welcome_message = f"""🎉 **مرحباً بك {user_data['name']}!** 🌟

**✅ تم تسجيل دخولك بنجاح باستخدام {provider.title()}**

**🧠 أنا ClainAI، مساعدك الذكي الإبداعي:**
- أجيب على أي سؤال تقني، علمي، أدبي
- أكتب أكواد برمجية متقدمة
- أشرح المفاهيم المعقدة
- أبدع في الإجابات

**🚀 جرب هذه الأسئلة:**
• "اكتب كود Python لموقع ويب"
• "اشرح لي الذكاء الاصطناعي"
• "كيفية عمل تطبيق مهام"

**👨‍💻 المطور:** محمد عبدو  
**📧 البريد:** mohammedu3615@gmail.com

اسألني أي شيء وسأبدع في الإجابة! 🚀"""

        save_message(str(user_id), "assistant", welcome_message)

        # إعادة التوجيه للصفحة الرئيسية
        return redirect('/')

    except Exception as e:
        print(f"❌ خطأ في حفظ بيانات المستخدم: {e}")
        return redirect('/login?error=user_save_failed')

# ========== نظام الذكاء الاصطناعي المتقدم ==========

@app.route("/api/chat", methods=["POST"])
def chat():
    """نظام محادثة متقدم - إبداعي بالكامل"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"error": "الرسالة فارغة"}), 400

        session_id = str(session["user_id"])

        # حفظ رسالة المستخدم
        save_message(session_id, "user", user_message)

        # 🌐 استخدام OpenRouter مباشرة لكل الأسئلة
        print("🚀 استخدام النماذج المتقدمة للرد الإبداعي...")
        
        # جلب تاريخ المحادثة
        conversation_history = get_messages(session_id, limit=6)
        
        # إنشاء system prompt ذكي
        user_name = session.get("user_name", "المستخدم")
        provider = session.get("oauth_provider", "ضيف")
        
        system_prompt = f"""أنت ClainAI، مساعد ذكي عربي إبداعي متكامل. أنت مطور بواسطة محمد عبدو (mohammedu3615@gmail.com).

المستخدم الحالي: {user_name} (الدخول باستخدام {provider})

مهمتك:
- الإجابة على جميع الأسئلة بدقة وإبداع
- كتابة أكواد برمجية متقدمة بأي لغة
- شرح المفاهيم العلمية والتقنية
- تقديم إجابات شاملة ومفصلة

تذكر:
- دائماً ترد باللغة العربية
- كن مفيداً ودقيقاً وإبداعياً
- قدم أمثلة عملية وتطبيقات
- لا تختلق معلومات"""

        # بناء الرسائل
        messages = [{"role": "system", "content": system_prompt}]
        
        # إضافة تاريخ المحادثة
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # إضافة الرسالة الحالية
        messages.append({"role": "user", "content": user_message})

        # استدعاء الذكاء الاصطناعي
        ai_response = call_openrouter_ai(messages)

        # إذا فشل الذكاء الاصطناعي
        if not ai_response:
            ai_response = "🔧 جاري معالجة طلبك... يرجى المحاولة مرة أخرى."

        # حفظ الرد
        save_message(session_id, "assistant", ai_response)

        return jsonify({
            "response": ai_response,
            "source": "openrouter",
            "user_info": {
                "name": session.get("user_name"),
                "role": session.get("user_role"),
                "provider": session.get("oauth_provider"),
                "avatar": session.get("avatar_url")
            }
        })

    except Exception as e:
        error_msg = f"حدث خطأ في النظام: {str(e)}"
        print(f"❌ {error_msg}")
        
        return jsonify({
            "response": "⚠️ حدث خطأ مؤقت. يرجى المحاولة مرة أخرى.",
            "source": "error"
        })

def call_openrouter_ai(messages):
    """استدعاء OpenRouter مع نماذج متقدمة"""
    
    # قائمة النماذج المرتبة حسب الجودة
    models = [
        "meta-llama/llama-3-70b-instruct:nitro",
        "openai/gpt-3.5-turbo", 
        "anthropic/claude-3-haiku",
        "google/gemini-2.0-flash-exp:free"
    ]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": BASE_URL,
    }

    for model in models:
        try:
            print(f"🧠 جرب النموذج: {model}")

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.7,
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                assistant_reply = result["choices"][0]["message"]["content"]
                print(f"✅ تم استلام رد من {model}")
                return assistant_reply
            else:
                print(f"⚠️ النموذج {model} غير متاح: {response.status_code}")
                continue

        except Exception as e:
            print(f"❌ خطأ في النموذج {model}: {str(e)}")
            continue

    return None

# ========== دوال المساعدة ==========

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
        print(f"❌ خطأ في حفظ الرسالة: {e}")
        return False

def get_messages(session_id, limit=20):
    """جلب رسائل المحادثة"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        messages = c.fetchall()
        return [{"role": msg[0], "content": msg[1], "timestamp": msg[2]} for msg in messages[::-1]]
    except Exception as e:
        print(f"❌ خطأ في جلب الرسائل: {e}")
        return []

# ========== Routes إضافية ==========

@app.route("/api/conversation")
def get_conversation():
    """جلب سجل المحادثة"""
    if "user_id" not in session:
        return jsonify({"error": "غير مسجل الدخول"}), 401

    session_id = str(session["user_id"])
    messages = get_messages(session_id)

    return jsonify({
        "messages": messages,
        "user_info": {
            "name": session.get("user_name", "مستخدم"),
            "email": session.get("user_email", ""),
            "role": session.get("user_role", "user"),
            "provider": session.get("oauth_provider", "guest"),
            "avatar": session.get("avatar_url")
        }
    })

@app.route("/api/user/status")
def user_status():
    """التحقق من حالة المستخدم"""
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "user": {
                "name": session.get("user_name"),
                "email": session.get("user_email"),
                "role": session.get("user_role"),
                "provider": session.get("oauth_provider"),
                "avatar": session.get("avatar_url")
            }
        })
    else:
        return jsonify({"logged_in": False})

@app.route("/api/clear", methods=["POST"])
def clear_conversation():
    """مسح سجل المحادثة"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        session_id = str(session["user_id"])

        db = get_db()
        c = db.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        db.commit()

        # رسالة ترحيب جديدة
        welcome_message = """🎉 **مرحباً بك من جديد!**

المحادثة السابقة تم مسحها بنجاح.

**👨‍💻 المطور:** محمد عبدو  
**📧 البريد:** mohammedu3615@gmail.com

اسألني أي شيء وسأجيبك بإبداع! 🚀"""

        save_message(session_id, "assistant", welcome_message)

        return jsonify({
            "success": True,
            "message": "تم مسح المحادثة بنجاح"
        })

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

@app.route("/api/logout")
def logout():
    """تسجيل الخروج"""
    session.clear()
    return jsonify({
        "success": True,
        "message": "تم تسجيل الخروج بنجاح",
        "redirect": "/login"
    })

# ========== التشغيل الرئيسي ==========

if __name__ == "__main__":
    with app.app_context():
        init_db()

        print("\n🚀 **ClainAI - الإصدار الكامل النهائي:**")
        print("   🧠 نظام إبداعي كامل - كل الأسئلة للذكاء الاصطناعي")
        print("   🔐 دعم GitHub OAuth - تسجيل الدخول بحساب GitHub")
        print("   🔐 دعم Google OAuth - تسجيل الدخول بحساب Google")
        print("   👤 نظام الدخول كضيف - تجربة مجانية")
        print("   💾 حفظ المحادثات في قاعدة بيانات")

        print(f"\n📍 **التطبيق جاهز على:** {BASE_URL}")
        print("👑 **المطور:** محمد عبدو - mohammedu3615@gmail.com")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

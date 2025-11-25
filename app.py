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

# API Keys - استبدل بالمفاتيح الجديدة
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
SECRET_KEY = os.getenv("SECRET_KEY", "clainai-super-secret-key-2024-pro-max")

# استخدام قاعدة بيانات في الذاكرة لـ Vercel
DB_PATH = "/tmp/clainai.db" if 'VERCEL' in os.environ else ":memory:"

# GitHub OAuth Configuration - تأكد من البيانات
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Ov23lihMk0lVKB9t8CGm")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your_github_client_secret_here")

# Google OAuth Configuration - صحح البيانات
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "77933091754-idsptg4osou4ipj9r434sdg8rpmb6289.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")

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
    PERMANENT_SESSION_LIFETIME=86400  # 24 ساعة
)

print("=" * 60)
print("🚀 ClainAI - المساعد الذكي المتكامل - الإصدار النهائي!")
print("=" * 60)
print(f"📍 Base URL: {BASE_URL}")
print(f"💾 Database: {DB_PATH}")
print(f"🔑 OpenRouter Key: {OPENROUTER_API_KEY[:20]}...")
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
    """تهيئة قاعدة البيانات مع جداول محسنة"""
    db = get_db()
    c = db.cursor()

    # جدول المستخدمين المحسن
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            password_hash TEXT,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            oauth_provider TEXT,
            github_username TEXT,
            github_id TEXT,
            google_id TEXT,
            avatar_url TEXT,
            last_login TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # جدول المحادثات المحسن
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

    # جدول الإحصائيات الجديد
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_messages INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            favorite_model TEXT,
            last_activity TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    db.commit()
    print("✅ تم إنشاء قاعدة البيانات المحسنة بنجاح")

# ========== Routes المحسنة ==========

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

# ========== نظام المصادقة المحسن ==========

@app.route("/api/guest-login")
def guest_login():
    """دخول ضيف محسن"""
    try:
        guest_id = f"guest_{secrets.token_hex(12)}"
        
        session.clear()
        session["user_id"] = guest_id
        session["user_role"] = "guest"
        session["user_name"] = "ضيف ClainAI"
        session["user_email"] = f"guest_{secrets.token_hex(6)}@clainai.com"
        session["oauth_provider"] = "guest"
        session.permanent = True

        # رسالة ترحيب ذكية
        session_id = f"user_{guest_id}"
        welcome_message = """🎉 **مرحباً بك في ClainAI!** 🌟

أنت الآن تستخدم النسخة الكاملة من المساعد الذكي العربي المتكامل.

**👨‍💻 المطور:** محمد عبدو  
**📧 البريد:** mohammedu3615@gmail.com  
**🎓 الخلفية:** خريج تكنولوجيا المعلومات والاتصالات

**💫 المميزات المتاحة لك:**
- 🧠 محادثة ذكية مع أنظمة AI متعددة
- 📚 إجابات مفصلة وشاملة
- 🌍 دعم كامل للغة العربية
- 💾 حفظ سجل المحادثات
- 📎 مشاركة الملفات والصور
- 📍 مشاركة الموقع

**🚀 جرب هذه الأسئلة الذكية:**
• "ما هو الذكاء الاصطناعي وكيف يعمل؟"
• "كيف أبدأ في تعلم البرمجة خطوة بخطوة؟"
• "اشرح لي الحوسبة السحابية بمثال عملي"
• "ما هي أحدث تقنيات الويب في 2024؟"
• "كيف أطور تطبيق ويب متكامل؟"

استمتع بتجربتك! 😊"""

        save_message(session_id, "assistant", welcome_message)

        return jsonify({
            "success": True, 
            "message": "تم الدخول كضيف بنجاح",
            "user": session["user_name"],
            "redirect": "/"
        })

    except Exception as e:
        return jsonify({"error": f"حدث خطأ في الدخول: {str(e)}"}), 500

# ========== GitHub OAuth المحسن ==========

@app.route('/api/auth/github')
def github_login():
    """بدء عملية تسجيل الدخول بـ GitHub محسنة"""
    print("🚀 بدء عملية GitHub OAuth المحسنة...")

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
    """معالجة رد GitHub محسنة"""
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
            'bio': user_data.get('bio'),
            'location': user_data.get('location'),
            'blog': user_data.get('blog')
        }

        print(f"✅ بيانات مستخدم GitHub: {user_info['name']} ({user_info['email']})")

        # حفظ المستخدم في قاعدة البيانات
        return handle_oauth_user(user_info, 'github')

    except Exception as e:
        print(f"❌ خطأ في GitHub OAuth: {e}")
        return redirect('/login?error=auth_failed')

# ========== Google OAuth المحسن ==========

@app.route('/api/auth/google')
def google_login():
    """بدء عملية تسجيل الدخول بـ Google محسنة"""
    print("🚀 بدء عملية Google OAuth المحسنة...")

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
    """معالجة رد Google محسنة"""
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

            # إنشاء إحصائيات للمستخدم الجديد
            c.execute(
                "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                (user_id,)
            )

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

        # إعادة التوجيه للصفحة الرئيسية
        return redirect('/')

    except Exception as e:
        print(f"❌ خطأ في حفظ بيانات المستخدم: {e}")
        return redirect('/login?error=user_save_failed')

# ========== نظام الذكاء الاصطناعي المحسن ==========

@app.route("/api/chat", methods=["POST"])
def chat():
    """نظام محادثة ذكي محسن مع OpenRouter"""
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

        # جلب سجل المحادثة (آخر 10 رسائل)
        conversation_history = get_messages(session_id, limit=10)

        # إعداد نظام الذكاء المحسن
        system_prompt = create_smart_system_prompt(session)

        # بناء رسائل المحادثة
        messages = [{"role": "system", "content": system_prompt}]
        
        # إضافة تاريخ المحادثة
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # إضافة الرسالة الجديدة
        messages.append({"role": "user", "content": user_message})

        print(f"🤖 إرسال طلب ذكي إلى OpenRouter...")
        print(f"📝 عدد الرسائل: {len(messages)}")
        print(f"💬 الرسالة: {user_message[:100]}...")

        # استدعاء OpenRouter مع النماذج الذكية
        ai_response = call_openrouter_ai(messages, session_id)

        # حفظ رد المساعد
        save_message(session_id, "assistant", ai_response)

        # تحديث الإحصائيات
        update_user_stats(session['user_id'])

        return jsonify({
            "response": ai_response,
            "message_count": len(conversation_history) + 1,
            "user_info": {
                "name": session.get("user_name"),
                "role": session.get("user_role")
            }
        })

    except Exception as e:
        error_msg = f"حدث خطأ في النظام: {str(e)}"
        print(f"❌ {error_msg}")
        
        # رد ذكي عند الخطأ
        fallback_response = generate_smart_fallback_response(user_message)
        session_id = f"user_{session.get('user_id', 'guest')}"
        save_message(session_id, "assistant", fallback_response)
        
        return jsonify({
            "response": fallback_response,
            "error": "تم استخدام النسخة الاحتياطية الذكية"
        })

def create_smart_system_prompt(session):
    """إنشاء prompt ذكي للمساعد"""
    user_name = session.get("user_name", "المستخدم")
    user_email = session.get("user_email", "")
    provider = session.get("oauth_provider", "ضيف")
    
    developer_info = """
👨‍💻 **معلومات المطور:**
- **الاسم:** محمد عبدو
- **التخصص:** خريج تكنولوجيا المعلومات والاتصالات
- **الجامعة:** جامعة العلوم وتقانة المعلومات  
- **البريد:** mohammedu3615@gmail.com
- **المشروع:** ClainAI - المساعد الذكي العربي المتكامل
"""

    system_prompt = f"""أنت **ClainAI**، مساعد ذكي عربي متكامل تم تطويرك بواسطة محمد عبدو.

{developer_info}

🎯 **مهمتك:** تقديم أفضل تجربة محادثة ذكية باللغة العربية مع:
- إجابات دقيقة، مفصلة، ومفيدة
- شرح مبسط وشامل للمفاهيم المعقدة  
- أمثلة عملية وتطبيقات حية
- تقسيم المعلومات إلى أقسام واضحة
- استخدام تنسيق Markdown لتحسين القراءة

👤 **المستخدم الحالي:** {user_name} (الدخول بـ {provider})

❌ **تجنب:** 
- الإجابات المختصرة غير المفيدة
- المعلومات غير المؤكدة
- التحيز لأي جهة
- إنكار معلومات المطور عند السؤال عنه

💫 **كن:** مفيداً، دقيقاً، واضحاً، ومحترفاً في جميع ردودك.

🌟 **تذكر:** أنت مساعد عربي ذكي تفتخر بدعم اللغة العربية وتقديم أفضل إجابة ممكنة!"""

    return system_prompt

def call_openrouter_ai(messages, session_id):
    """استدعاء OpenRouter مع نماذج ذكية"""
    # قائمة النماذج الذكية بالترتيب
    smart_models = [
        "google/gemini-2.0-flash-exp:free",  # الأفضل والأسرع
        "meta-llama/llama-3-70b-instruct:nitro",  # قوي ومجاني
        "google/gemini-flash-1.5",  # سريع وذكي
        "microsoft/wizardlm-2-8x22b",  # متقدم
        "anthropic/claude-3-haiku"  # أنثروبيك
    ]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": BASE_URL,
        "X-Title": "ClainAI - الذكاء الاصطناعي العربي"
    }

    for model in smart_models:
        try:
            print(f"🔄 جرب النموذج الذكي: {model}")
            
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.7,
                "top_p": 0.9,
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=45
            )

            if response.status_code == 200:
                result = response.json()
                assistant_reply = result["choices"][0]["message"]["content"]
                tokens_used = result.get("usage", {}).get("total_tokens", 0)
                
                print(f"✅ تم استلام رد ذكي من {model}")
                print(f"📊 Tokens used: {tokens_used}")
                
                # تحديث tokens في قاعدة البيانات
                update_message_tokens(session_id, tokens_used, model)
                
                return assistant_reply
            else:
                print(f"⚠️ النموذج {model} غير متاح: {response.status_code}")
                continue

        except Exception as e:
            print(f"❌ خطأ في النموذج {model}: {e}")
            continue

    # إذا فشلت جميع النماذج، استخدم الرد الذكي الافتراضي
    print("⚠️ جميع النماذج فشلت، استخدام الرد الذكي الافتراضي")
    user_message = messages[-1]["content"] if messages else ""
    return generate_smart_fallback_response(user_message)

def generate_smart_fallback_response(user_message):
    """إنشاء رد ذكي عند فشل الاتصال"""
    message_lower = user_message.lower()
    
    # ردود ذكية مبرمجة
    smart_responses = {
        "hello": "مرحباً بك! 🌟 أنا ClainAI، المساعد الذكي العربي. للأسف حالياً الخدمة متقطعة، لكن جرب تحديث الصفحة أو الانتظار قليلاً! 😊",
        "مرحبا": "أهلاً وسهلاً! 🎉 أنا ClainAI، المساعد الذكي. نعمل على حل بعض المشاكل التقنية، جرب مرة أخرى بعد قليل! 💫",
        "ما هو الذكاء الاصطناعي": """🤖 **الذكاء الاصطناعي (AI)** 

هو محاكاة الذكاء البشري في الآلات المبرمجة للتفكير والتعلم مثل البشر.

**🔹 المجالات الرئيسية:**
- **التعلم الآلي** - تحسين الأداء من خلال التجربة
- **المعالجة اللغوية** - فهم اللغات الطبيعية  
- **الرؤية الحاسوبية** - تحليل الصور والفيديو
- **الروبوتات** - التحكم في الأجهزة المادية

**🚀 التطبيقات:** المساعدات الذكية، السيارات ذاتية القيادة، التشخيص الطبي، الترجمة الآلية، وغيرها!""",

        "كيف أتعلم البرمجة": """💻 **دليل تعلم البرمجة للمبتدئين:**

**🎯 الخطوة 1: اختر لغة مناسبة**
- 🐍 **Python** - الأفضل للمبتدئين (بسيطة وقوية)
- 🌐 **JavaScript** - لتطوير الويب
- ☕ **Java** - للتطبيقات الكبيرة

**📚 الخطوة 2: مصادر مجانية**
- موقع **freeCodeCamp** (عربي وإنجليزي)
- قناة **Elzero Web School** على YouTube
- منصة **Coursera** و **edX**

**🛠️ الخطوة 3: مشاريع عملية**
- موقع ويب شخصي
- تطبيق آلة حاسبة
- لعبة بسيطة

**💡 النصيحة الذهبية:** الممارسة المستمرة أهم من الكمية! ابدأ بمشاريع صغيرة.""",

        "من طورك": """🛠️ **معلومات المطور:**

👨‍💻 **الاسم:** محمد عبدو  
🎓 **التخصص:** خريج تكنولوجيا المعلومات والاتصالات  
🏫 **الجامعة:** جامعة العلوم وتقانة المعلومات  
📧 **البريد:** mohammedu3615@gmail.com

تم تطوير ClainAI بعناية لتقديم أفضل تجربة محادثة ذكية باللغة العربية! 🌟"""
    }

    # البحث عن أفضل تطابق
    for key, response in smart_responses.items():
        if key in message_lower:
            return response

    # رد عام ذكي
    general_responses = [
        f"أهلاً بك! 🌟 سؤالك '{user_message}' مثير للاهتمام. حالياً نواجه بعض المشاكل التقنية، جرب مرة أخرى بعد قليل! 😊",
        f"شكراً لسؤالك! 💫 للأسف الخدمة متقطعة حالياً، لكننا نعمل على حل المشكلة. جرب تحديث الصفحة! 🚀",
        f"سؤال رائع! 🎯 أنا ClainAI المساعد الذكي. حالياً الخدمة غير مستقرة، جرب المحادثة بعد دقائق قليلة! 💪"
    ]
    
    return random.choice(general_responses)

# ========== دوال المساعدة المحسنة ==========

def save_message(session_id, role, content, tokens=0, model=None):
    """حفظ رسالة محسنة في قاعدة البيانات"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "INSERT INTO messages (session_id, role, content, tokens_used, model_used) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, tokens, model)
        )
        db.commit()
        return True
    except Exception as e:
        print(f"❌ خطأ في حفظ الرسالة: {e}")
        return False

def get_messages(session_id, limit=20):
    """جلب رسائل المحادثة محسنة"""
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

def update_message_tokens(session_id, tokens, model):
    """تحديث tokens للنموذج المستخدم"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "UPDATE messages SET tokens_used = ?, model_used = ? WHERE session_id = ? AND id = (SELECT MAX(id) FROM messages WHERE session_id = ?)",
            (tokens, model, session_id, session_id)
        )
        db.commit()
    except Exception as e:
        print(f"❌ خطأ في تحديث tokens: {e}")

def update_user_stats(user_id):
    """تحديث إحصائيات المستخدم"""
    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "UPDATE user_stats SET total_messages = total_messages + 1, last_activity = ? WHERE user_id = ?",
            (datetime.now(timezone.utc).isoformat(), user_id)
        )
        db.commit()
    except Exception as e:
        print(f"❌ خطأ في تحديث الإحصائيات: {e}")

# ========== Routes الإضافية المحسنة ==========

@app.route("/api/conversation")
def get_conversation():
    """جلب سجل المحادثة المحسن"""
    if "user_id" not in session:
        return jsonify({"error": "غير مسجل الدخول"}), 401

    session_id = f"user_{session['user_id']}"
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

@app.route("/api/user/stats")
def get_user_stats():
    """جلب إحصائيات المستخدم"""
    if "user_id" not in session:
        return jsonify({"error": "غير مسجل الدخول"}), 401

    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT total_messages, total_tokens, favorite_model FROM user_stats WHERE user_id = ?",
            (session['user_id'],)
        )
        stats = c.fetchone()
        
        return jsonify({
            "stats": dict(stats) if stats else {"total_messages": 0, "total_tokens": 0},
            "user": {
                "name": session.get("user_name"),
                "join_date": datetime.now().strftime("%Y-%m-%d")
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clear", methods=["POST"])
def clear_conversation():
    """مسح سجل المحادثة المحسن"""
    try:
        if "user_id" not in session:
            return jsonify({"error": "غير مسجل الدخول"}), 401

        session_id = f"user_{session['user_id']}"

        db = get_db()
        c = db.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        db.commit()

        # رسالة ترحيب جديدة ذكية
        welcome_message = """🎉 **مرحباً بك من جديد في ClainAI!** 🌟

تم مسح المحادثة السابقة بنجاح.

**👨‍💻 المطور:** محمد عبدو  
**📧 البريد:** mohammedu3615@gmail.com

**🚀 ابدأ محادثة جديدة ذكية:**
• "ما هي أحدث تقنيات الذكاء الاصطناعي؟"
• "كيف أطور تطبيق ويب متكامل؟"  
• "ما الفرق بين Python و JavaScript؟"
• "كيف أبدأ مشروع برمجي ناجح؟"

اسألني عن أي شيء! 😊"""

        save_message(session_id, "assistant", welcome_message)

        return jsonify({
            "success": True, 
            "message": "تم مسح المحادثة وبدء محادثة جديدة"
        })

    except Exception as e:
        return jsonify({"error": f"حدث خطأ: {str(e)}"}), 500

@app.route("/api/logout")
def logout():
    """تسجيل الخروج المحسن"""
    session.clear()
    return jsonify({
        "success": True, 
        "message": "تم تسجيل الخروج بنجاح",
        "redirect": "/login"
    })

# ========== دوال التصحيح المحسنة ==========

@app.route("/api/debug/info")
def debug_info():
    """معلومات تصحيح محسنة"""
    return jsonify({
        'app': 'ClainAI - الإصدار النهائي',
        'version': '2.0.0',
        'developer': 'محمد عبدو - mohammedu3615@gmail.com',
        'base_url': BASE_URL,
        'environment': 'production' if 'VERCEL' in os.environ else 'development',
        'database': DB_PATH,
        'session_user': session.get("user_id"),
        'oauth_ready': {
            'github': bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET),
            'google': bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
        },
        'openrouter_ready': bool(OPENROUTER_API_KEY)
    })

# ========== التشغيل الرئيسي ==========

if __name__ == "__main__":
    with app.app_context():
        init_db()

        print("\n💫 **المميزات المحسنة في ClainAI:**")
        print("   🧠 نظام ذكاء اصطناعي متقدم بمتعدد النماذج")
        print("   🔐 نظام مصادقة محسن بـ GitHub و Google OAuth")  
        print("   💾 قاعدة بيانات محسنة مع إحصائيات")
        print("   🌍 دعم عربي كامل وردود ذكية")
        print("   📱 واجهة متكاملة وتجربة مستخدم فائقة")
        print("   🚀 أداء محسن وسريع")
        print("   🔧 نظام تصحيح أخطاء ذكي")
        
        print("\n🎯 **جرب هذه الأسئلة الذكية:**")
        print("   - 'ما هو الذكاء الاصطناعي التوليدي?' 🤖")
        print("   - 'كيف أطور تطبيق ويب متكامل?' 🌐") 
        print("   - 'ما هي أحدث تقنيات 2024?' 🚀")
        print("   - 'من هو المطور محمد عبدو?' 👨‍💻")
        print("   - 'ما الفرق بين AI و Machine Learning?' 🔬")

    # تشغيل السيرفر
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

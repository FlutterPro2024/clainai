import sqlite3
import os
import requests
import time
from flask import Flask, request, jsonify, session, redirect, send_from_directory
from datetime import datetime
import hashlib
import secrets
import json
from typing import Dict, List, Any

# محاولة استيراد المكتبات الاختيارية
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    def load_dotenv(): 
        pass
    print("⚠️ dotenv not available, using environment variables directly")

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    print("⚠️ PyPDF2 not available, PDF processing disabled")

try:
    import docx
except ImportError:
    docx = None
    print("⚠️ python-docx not available, Word processing disabled")

# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY") or "fallback-secret-key-for-development"
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# نماذج الذكاء الاصطناعي المتقدمة - API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# استخدام قاعدة بيانات في الذاكرة لـ Vercel
DB_PATH = "/tmp/clainai.db" if 'VERCEL' in os.environ else "clainai.db"

# =============================================================================
# 🔧 نظام الوكيل الذكي (AI Agent)
# =============================================================================

class AgentMemory:
    """نظام الذاكرة للوكيل الذكي"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conn = get_db_connection()
    
    def save_preference(self, key: str, value: str) -> bool:
        """حفظ تفضيلات المستخدم"""
        try:
            memory_id = hashlib.md5(f"{self.user_id}_{key}".encode()).hexdigest()
            self.conn.execute(
                'INSERT OR REPLACE INTO agent_memory (id, user_id, key, value) VALUES (?, ?, ?, ?)',
                (memory_id, self.user_id, key, value)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ الذاكرة: {e}")
            return False
    
    def get_preference(self, key: str) -> str:
        """جلب تفضيلات المستخدم"""
        try:
            result = self.conn.execute(
                'SELECT value FROM agent_memory WHERE user_id = ? AND key = ?',
                (self.user_id, key)
            ).fetchone()
            return result['value'] if result else ""
        except Exception as e:
            print(f"❌ خطأ في جلب الذاكرة: {e}")
            return ""

class TaskManager:
    """مدير المهام للوكيل الذكي"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.conn = get_db_connection()
    
    def create_task(self, task_type: str, description: str, data: Dict = None) -> str:
        """إنشاء مهمة جديدة"""
        try:
            task_id = hashlib.md5(f"{self.user_id}_{task_type}_{datetime.now().timestamp()}".encode()).hexdigest()
            self.conn.execute(
                'INSERT INTO agent_tasks (id, user_id, task_type, description, data, status) VALUES (?, ?, ?, ?, ?, ?)',
                (task_id, self.user_id, task_type, description, json.dumps(data or {}), "pending")
            )
            self.conn.commit()
            return task_id
        except Exception as e:
            print(f"❌ خطأ في إنشاء المهمة: {e}")
            return ""
    
    def get_pending_tasks(self) -> List[Dict]:
        """جلب المهام المعلقة"""
        try:
            tasks = self.conn.execute(
                'SELECT id, task_type, description, data, created_at FROM agent_tasks WHERE user_id = ? AND status = ?',
                (self.user_id, "pending")
            ).fetchall()
            return [dict(task) for task in tasks]
        except Exception as e:
            print(f"❌ خطأ في جلب المهام: {e}")
            return []
    
    def complete_task(self, task_id: str, result: str = "") -> bool:
        """إكمال المهمة"""
        try:
            self.conn.execute(
                'UPDATE agent_tasks SET status = ?, completed_at = ?, result = ? WHERE id = ?',
                ("completed", datetime.now().isoformat(), result, task_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ خطأ في إكمال المهمة: {e}")
            return False

class SmartAgent:
    """الوكيل الذكي الرئيسي"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = AgentMemory(user_id)
        self.tasks = TaskManager(user_id)
    
    def analyze_intent(self, message: str) -> Dict[str, Any]:
        """تحليل نية المستخدم"""
        intents = {
            "track_price": ["تابع", "تتبع", "راقب", "شوف", "اسعار", "سعر"],
            "schedule_reminder": ["ذكرني", "تذكير", "موعد", "غداً", "بكرا"],
            "research_topic": ["ابحث", "اعرف", "معلومات", "دراسة", "بحث"],
            "automate_task": ["اتمتع", "شغل", "افعل", "نفذ", "اعمل"]
        }
        
        message_lower = message.lower()
        detected_intents = []
        
        for intent, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intents.append(intent)
        
        return {
            "intents": detected_intents,
            "needs_agent": len(detected_intents) > 0,
            "is_instruction": any(word in message_lower for word in ["افعل", "نفذ", "اعمل", "اتمتع"])
        }
    
    def create_tracking_task(self, topic: str, condition: str = "") -> str:
        """إنشاء مهمة متابعة"""
        return self.tasks.create_task(
            "price_tracking",
            f"متابعة {topic}",
            {"topic": topic, "condition": condition, "last_checked": datetime.now().isoformat()}
        )
    
    def create_research_task(self, topic: str, depth: str = "basic") -> str:
        """إنشاء مهمة بحث"""
        return self.tasks.create_task(
            "research",
            f"بحث عن {topic}",
            {"topic": topic, "depth": depth, "sources": []}
        )

class AgentAutomation:
    """نظام الأتمتة للوكيل"""
    
    @staticmethod
    def get_current_price(topic: str) -> str:
        """الحصول على السعر الحالي (محاكاة)"""
        try:
            # محاكاة للحصول على سعر حقيقي
            prices = {
                "الذهب": "💰 سعر الذهب اليوم: ~185 دولار للأونصة",
                "الدولار": "💵 سعر الدولار: ~3.75 جنيه سوداني", 
                "البترول": "🛢️ سعر البترول: ~80 دولار للبرميل",
                "البيتكوين": "₿ سعر البيتكوين: ~45,000 دولار",
                "الفضة": "🔗 سعر الفضة: ~22 دولار للأونصة",
                "اليورو": "💶 سعر اليورو: ~4.15 جنيه سوداني"
            }
            
            return prices.get(topic, f"🔍 جاري البحث عن سعر {topic}...")
        except Exception as e:
            return f"❌ تعذر الحصول على سعر {topic}"

    @staticmethod
    def send_notification(user_id: str, title: str, message: str) -> bool:
        """إرسال إشعار للمستخدم"""
        try:
            conn = get_db_connection()
            notification_id = hashlib.md5(f"notif_{user_id}_{datetime.now().timestamp()}".encode()).hexdigest()
            conn.execute(
                'INSERT INTO agent_notifications (id, user_id, title, message, created_at) VALUES (?, ?, ?, ?, ?)',
                (notification_id, user_id, title, message, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ خطأ في إرسال الإشعار: {e}")
            return False

# =============================================================================
# 🔧 التعديل: استخدام Environment Variables مباشرة
# =============================================================================

def get_base_url():
    """الحصول على الـ base URL من Environment Variables أو ديناميكياً"""
    env_base_url = os.environ.get('BASE_URL')
    if env_base_url:
        return env_base_url
    
    vercel_url = os.environ.get('VERCEL_URL')
    if vercel_url:
        return f"https://{vercel_url}"

    return "https://clainai-dep.vercel.app"

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

# =============================================================================
# نماذج الذكاء الاصطناعي المتقدمة
# =============================================================================

# نماذج الذكاء الاصطناعي المتاحة
AI_MODELS = {
    "google": {
        "name": "Google Gemini Pro",
        "endpoint": "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
        "key": GOOGLE_API_KEY,
        "enabled": bool(GOOGLE_API_KEY)
    },
    "openai": {
        "name": "OpenAI GPT-4",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "key": OPENAI_API_KEY,
        "enabled": bool(OPENAI_API_KEY)
    },
    "claude": {
        "name": "Claude 3 Sonnet",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "key": CLAUDE_API_KEY,
        "enabled": bool(CLAUDE_API_KEY)
    },
    "llama": {
        "name": "Llama 3 70B",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "key": OPENROUTER_API_KEY,
        "enabled": bool(OPENROUTER_API_KEY)
    }
}

def get_ai_response(message, model_type="google"):
    """الحصول على رد ذكي من النماذج المتاحة"""
    try:
        if model_type == "google" and AI_MODELS["google"]["enabled"]:
            return get_google_response(message)
        elif model_type == "openai" and AI_MODELS["openai"]["enabled"]:
            return get_openai_response(message)
        elif model_type == "claude" and AI_MODELS["claude"]["enabled"]:
            return get_claude_response(message)
        elif model_type == "llama" and AI_MODELS["llama"]["enabled"]:
            return get_llama_response(message)
        else:
            return get_fallback_response(message)
    except Exception as e:
        print(f"❌ خطأ في النموذج {model_type}: {str(e)}")
        return get_fallback_response(message)

def get_google_response(message):
    """نموذج جوجل جيميني"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GOOGLE_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": f"أنت ClainAI - مساعد ذكي عربي متخصص. أجب على السؤال التالي بطريقة مفيدة ودقيقة ومفصلة باللغة العربية:\n\n{message}"
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
            }
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                return result["candidates"][0]["content"]["parts"][0]["text"]
        return get_fallback_response(message)
    except Exception as e:
        print(f"❌ خطأ في Google API: {str(e)}")
        return get_fallback_response(message)

def get_openai_response(message):
    """نموذج OpenAI"""
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "أنت ClainAI - مساعد ذكي عربي متخصص. قدم إجابات دقيقة ومفيدة ومفصلة باللغة العربية."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        return get_fallback_response(message)
    except Exception as e:
        print(f"❌ خطأ في OpenAI API: {str(e)}")
        return get_fallback_response(message)

def get_claude_response(message):
    """نموذج Claude"""
    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 2000,
            "temperature": 0.7,
            "messages": [
                {
                    "role": "user",
                    "content": f"أنت ClainAI - مساعد ذكي عربي متخصص. أجب على السؤال التالي بطريقة مفيدة ودقيقة ومفصلة باللغة العربية:\n\n{message}"
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result["content"][0]["text"]
        return get_fallback_response(message)
    except Exception as e:
        print(f"❌ خطأ في Claude API: {str(e)}")
        return get_fallback_response(message)

def get_llama_response(message):
    """نموذج Llama عبر OpenRouter"""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": f"{BASE_URL}",
            "X-Title": "ClainAI Chat"
        }
        
        payload = {
            "model": "meta-llama/llama-3-70b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "أنت ClainAI - مساعد ذكي عربي متخصص. قدم إجابات دقيقة ومفيدة ومفصلة باللغة العربية."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        return get_fallback_response(message)
    except Exception as e:
        print(f"❌ خطأ في Llama API: {str(e)}")
        return get_fallback_response(message)

def get_fallback_response(message):
    """رد احتياطي عندما تفشل جميع النماذج"""
    fallback_responses = {
        "من هو مطورك": "أنا ClainAI، تم تطويري بواسطة المهندس السوداني محمد عبد القادر السراج - خريج جامعة العلوم وتقانة المعلومات (IT) وخريج تكنولوجيا المعلومات والاتصالات (ICT). أسعى دائماً لتقديم أفضل تجربة للمستخدمين العرب من خلال دمج أحدث تقنيات الذكاء الاصطناعي. 📧 البريد: mohammedu3615@gmail.com",

        "ماهو الذكاء الاصطناعي": "الذكاء الاصطناعي (Artificial Intelligence) هو مجال من مجالات علوم الكمبيوتر يهتم بتطوير أنظمة قادرة على أداء مهام تتطلب ذكاءً بشرياً مثل:\n\n• 🤖 **التعلم** (Learning): قدرة النظام على تحسين أدائه من خلال التجربة\n• 💭 **التفكير** (Reasoning): القدرة على استنتاج النتائج المنطقية\n• 🔍 **حل المشكلات** (Problem Solving): إيجاد حلول للتحديات المعقدة\n\nيشمل الذكاء الاصطناعي مجالات فرعية مثل التعلم الآلي، الشبكات العصبية، الرؤية الحاسوبية، ومعالجة اللغة الطبيعية.",

        "ما هي المجالات": "مجالات الذكاء الاصطناعي تشمل:\n\n🎯 **المجالات الرئيسية:**\n• التعلم الآلي (Machine Learning)\n• الشبكات العصبية (Neural Networks)\n• معالجة اللغة الطبيعية (NLP)\n• الرؤية الحاسوبية (Computer Vision)\n• الروبوتات (Robotics)\n\n💼 **التطبيقات العملية:**\n• المساعدات الذكية (مثل ClainAI)\n• السيارات ذاتية القيادة\n• التشخيص الطبي\n• التوصيات الذكية\n• الترجمة الآلية",

        "عرف الحوسبة السحابية": "الحوسبة السحابية (Cloud Computing) هي نموذج لتقديم خدمات حاسوبية عبر الإنترنت تشمل:\n\n☁️ **الخدمات الأساسية:**\n• **الخوادم** (Servers): قوة معالجة مرنة\n• **التخزين** (Storage): مساحة تخزين غير محدودة\n• **قواعد البيانات** (Databases): أنواع متعددة من قواعد البيانات\n\n🎯 **نماذج الخدمة:**\n• **IaaS** (البنية التحتية كخدمة)\n• **PaaS** (المنصة كخدمة)  \n• **SaaS** (البرمجيات كخدمة)\n\n💫 **المزايا:**\n• توفير التكاليف\n• المرونة والتوسع\n• الأمان المتقدم\n• الابتكار السريع",

        "ما اسمك": "🤖 **أنا ClainAI - المساعد الذكي العربي المتطور!**\n\n✨ **ما أقدمه لك:**\n• محادثات ذكية متقدمة\n• تحليل الملفات (PDF, Word, الصور)\n• بحث ذكي على الإنترنت\n• إجابات إبداعية ومفيدة\n• دعم متعدد النماذج الذكية\n• نظام وكيل ذكي للمهام التلقائية\n\n🚀 **تم تطويري بواسطة المهندس محمد عبد القادر السراج** لخدمة المستخدمين العرب بكل احترافية وإبداع!"
    }

    # البحث عن رد مناسب
    for key, response in fallback_responses.items():
        if key in message.lower():
            return response

    # رد عام إذا لم يتم العثور على تطابق
    return "شكراً لسؤالك! 🤖 أنا ClainAI - مساعد ذكي عربي. حالياً، أحتاج إلى تكوين مفاتيح API للنماذج المتقدمة (جوجل Gemini، OpenAI، Claude) لتقديم إجابات أكثر دقة وإبداعية. يمكنك إضافة هذه المفاتيح في إعدادات التطبيق لتفعيل الإجابات الذكية المتقدمة! 💡"

def get_smart_response(message):
    """
    الحصول على رد ذكي من أفضل نموذج متاح
    """
    enabled_models = [model_type for model_type, model in AI_MODELS.items() if model["enabled"]]

    if not enabled_models:
        return get_fallback_response(message), "fallback"

    # محاولة النماذج بالترتيب
    for model_type in enabled_models:
        try:
            response = get_ai_response(message, model_type)
            if response and response != get_fallback_response(message):
                return response, model_type
        except Exception as e:
            print(f"❌ فشل النموذج {model_type}: {str(e)}")
            continue

    # إذا فشلت جميع النماذج
    return get_fallback_response(message), "fallback"

# =============================================================================
# دالة الاتصال بقاعدة البيانات
# =============================================================================

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Database error: {e}")
        # بديل في الذاكرة
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

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

    # جداول الوكيل الذكي
    conn.execute('''
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            task_type TEXT,
            description TEXT,
            data TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS agent_memory (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            key TEXT,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS agent_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            message TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS price_tracking (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            topic TEXT,
            price_info TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات بنجاح مع جداول الوكيل الذكي")

# CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# =============================================================================
# ROUTES الأساسية
# =============================================================================

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

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory('static', 'service-worker.js')

@app.route("/manifest.json")
def manifest():
    return send_from_directory('static', 'manifest.json')

# =============================================================================
# Routes فحص الصحة والحالة
# =============================================================================

@app.route("/api/health")
def health_check():
    try:
        init_db()
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "message": "✅ ClainAI is working perfectly!",
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "ai_models": {model: config["enabled"] for model, config in AI_MODELS.items()},
            "agent_system": True
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/status")
def app_status():
    """فحص الحالة العامة للتطبيق"""
    return jsonify({
        'status': 'running',
        'app': 'ClainAI',
        'version': '3.0.0',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected',
        'base_url': BASE_URL,
        'ai_models': {
            model: config["enabled"]
            for model, config in AI_MODELS.items()
        },
        'oauth': {
            'github': bool(GITHUB_CLIENT_ID),
            'google': bool(GOOGLE_CLIENT_ID)
        },
        'agent_system': True
    })

@app.route("/api/user/status", methods=["GET"])
def user_status():
    """فحص حالة المستخدم وجلسة العمل"""
    try:
        user_info = {
            'is_logged_in': False,
            'user': None,
            'session_active': False,
            'timestamp': datetime.now().isoformat()
        }

        if 'user_id' in session:
            user_info['is_logged_in'] = True
            user_info['session_active'] = True
            user_info['user'] = {
                'id': session.get('user_id'),
                'name': session.get('user_name', 'User'),
                'role': session.get('user_role', 'user')
            }

        return jsonify({
            'success': True,
            'status': user_info,
            'server_time': datetime.now().isoformat(),
            'base_url': BASE_URL
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'status': {
                'is_logged_in': False,
                'session_active': False,
                'user': None
            }
        }), 500

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

# =============================================================================
# Routes المصادقة والمستخدمين
# =============================================================================

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
    if not GITHUB_CLIENT_ID:
        return jsonify({'error': 'GitHub OAuth not configured'}), 500

    github_auth_url = f"https://github.com/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=user:email"

    response = redirect(github_auth_url)
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/api/auth/google')
def google_auth():
    if not GOOGLE_CLIENT_ID:
        return jsonify({'error': 'Google OAuth not configured'}), 500

    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code&scope=email profile&access_type=offline"

    response = redirect(google_auth_url)
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/api/auth/google/callback')
def google_callback():
    try:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return redirect('/login?error=google_not_configured')

        code = request.args.get('code')
        if not code:
            return redirect('/login?error=missing_code')

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }

        token_response = requests.post(token_url, data=token_data)
        token_json = token_response.json()

        if 'error' in token_json:
            return redirect('/login?error=token_failed')

        access_token = token_json['access_token']

        # Get user info
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(user_info_url, headers=headers)
        user_info = user_response.json()

        # Create or get user
        init_db()
        user_id = f"google_{user_info['id']}"
        conn = get_db_connection()

        conn.execute(
            'INSERT OR REPLACE INTO users (id, name, email, role) VALUES (?, ?, ?, ?)',
            (user_id, user_info.get('name', 'User'), user_info.get('email', ''), 'user')
        )
        conn.commit()
        conn.close()

        # Set session
        session['user_id'] = user_id
        session['user_name'] = user_info.get('name', 'User')
        session['user_role'] = 'user'

        return redirect('/')

    except Exception as e:
        print(f"❌ Google OAuth error: {str(e)}")
        return redirect('/login?error=auth_failed')

@app.route('/api/auth/github/callback')
def github_callback():
    try:
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return redirect('/login?error=github_not_configured')

        code = request.args.get('code')
        if not code:
            return redirect('/login?error=missing_code')

        # Exchange code for tokens
        token_url = "https://github.com/login/oauth/access_token"
        token_data = {
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code
        }
        headers = {'Accept': 'application/json'}
        token_response = requests.post(token_url, data=token_data, headers=headers)
        token_json = token_response.json()

        if 'error' in token_json:
            return redirect('/login?error=token_failed')

        access_token = token_json['access_token']

        # Get user info
        user_info_url = "https://api.github.com/user"
        headers = {'Authorization': f'token {access_token}'}
        user_response = requests.get(user_info_url, headers=headers)
        user_info = user_response.json()

        # Get email (if available)
        email_url = "https://api.github.com/user/emails"
        email_response = requests.get(email_url, headers=headers)
        emails = email_response.json()
        primary_email = next((email['email'] for email in emails if email['primary']), '')

        # Create or get user
        init_db()
        user_id = f"github_{user_info['id']}"
        conn = get_db_connection()

        conn.execute(
            'INSERT OR REPLACE INTO users (id, name, email, role) VALUES (?, ?, ?, ?)',
            (user_id, user_info.get('name', user_info.get('login', 'User')), primary_email, 'user')
        )
        conn.commit()
        conn.close()

        # Set session
        session['user_id'] = user_id
        session['user_name'] = user_info.get('name', user_info.get('login', 'User'))
        session['user_role'] = 'user'

        return redirect('/')

    except Exception as e:
        print(f"❌ GitHub OAuth error: {str(e)}")
        return redirect('/login?error=auth_failed')

@app.route("/api/user", methods=["GET"])
def get_user():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        conn = get_db_connection()
        user = conn.execute(
            'SELECT id, name, email, role FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        conn.close()

        if user:
            return jsonify({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            })
        else:
            return jsonify({'error': 'المستخدم غير موجود'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    if request.method == 'POST':
        return jsonify({'success': True, 'message': 'تم تسجيل الخروج بنجاح'})
    else:
        return redirect('/login')

# =============================================================================
# Routes المحادثة والملفات
# =============================================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """المحادثة الرئيسية مع دعم الوكيل الذكي"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        message = data.get('message', '').strip()
        use_search = data.get('use_search', False)

        if not message:
            return jsonify({'error': 'الرسالة فارغة'}), 400

        user_id = session['user_id']
        print(f"📩 رسالة مستلمة من {user_id}: {message}")

        # ======== التحقق إذا كان السؤال عن المطور ========
        developer_keywords = ['مطور', 'مبرمج', 'صاحب', 'خالق', 'من صنع', 'who made you', 'developer', 'creator']
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in developer_keywords):
            developer_info = "🤖 **معلومات المطور:**\n\n✅ تم تطويري بواسطة **المهندس السوداني محمد عبد القادر السراج**\n🎓 **المؤهلات:**\n• خريج جامعة العلوم وتقانة المعلومات (IT)\n• خريج تكنولوجيا المعلومات والاتصالات (ICT)\n📧 **البريد الإلكتروني:** mohammedu3615@gmail.com\n\nأعمل دائماً على تطوير وتحسين أدائي لخدمة المستخدمين العرب بأفضل صورة! 💪"

            conversation_id = hashlib.md5(f"{user_id}_{message}_{datetime.now().timestamp()}".encode()).hexdigest()
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO conversations (id, user_id, message, reply, model_used) VALUES (?, ?, ?, ?, ?)',
                (conversation_id, user_id, message, developer_info, "developer_info")
            )
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'reply': developer_info,
                'model_used': 'developer_info'
            })

        # ======== البحث على الإنترنت إذا طلب المستخدم ========
        search_context = ""
        if use_search and SERPER_API_KEY:
            try:
                search_url = "https://google.serper.dev/search"
                headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
                payload = {'q': message}
                search_response = requests.post(search_url, headers=headers, json=payload, timeout=15)

                if search_response.status_code == 200:
                    search_data = search_response.json()
                    if 'organic' in search_data and search_data['organic']:
                        top_results = search_data['organic'][:3]
                        search_context = "\n\n🔍 **معلومات من البحث على الإنترنت:**\n"
                        for i, result in enumerate(top_results, 1):
                            search_context += f"{i}. **{result.get('title', '')}**: {result.get('snippet', '')}\n"
            except Exception as search_error:
                print(f"🔍 خطأ في البحث: {search_error}")

        # ======== استخدام النماذج الذكية المتقدمة للحصول على رد ========
        print("🔄 جاري الحصول على رد ذكي من النماذج المتاحة...")
        ai_reply, model_used = get_smart_response(message + search_context)

        # إضافة علامة إذا تم استخدام البحث
        if search_context:
            ai_reply += "\n\n🔍 *تم دمج معلومات من البحث على الإنترنت*"

        # حفظ المحادثة في قاعدة البيانات
        conversation_id = hashlib.md5(f"{user_id}_{message}_{datetime.now().timestamp()}".encode()).hexdigest()
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO conversations (id, user_id, message, reply, model_used) VALUES (?, ?, ?, ?, ?)',
            (conversation_id, user_id, message, ai_reply, model_used)
        )
        conn.commit()
        conn.close()

        print(f"✅ تم إرسال الرد باستخدام {model_used}")

        return jsonify({
            'success': True,
            'reply': ai_reply,
            'model_used': model_used,
            'model_name': AI_MODELS.get(model_used, {}).get('name', 'النظام الذكي'),
            'used_search': bool(search_context)
        })

    except Exception as e:
        print(f"❌ خطأ في المحادثة: {str(e)}")
        return jsonify({
            'error': f'حدث خطأ: {str(e)}',
            'reply': 'عذراً، حدث خطأ في المعالجة. يرجى المحاولة مرة أخرى.'
        }), 500

@app.route("/api/clear", methods=["POST"])
def clear_conversations():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        conn = get_db_connection()
        conn.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'تم مسح المحادثة بنجاح'})
    except Exception as e:
        return jsonify({'error': f'حدث خطأ: {str(e)}'}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        conn = get_db_connection()
        conversations = conn.execute(
            'SELECT message, reply, created_at FROM conversations WHERE user_id = ? ORDER BY created_at ASC',
            (user_id,)
        ).fetchall()
        conn.close()

        messages = []
        for conv in conversations:
            messages.append({
                'role': 'user',
                'content': conv['message'],
                'timestamp': conv['created_at']
            })
            messages.append({
                'role': 'assistant',
                'content': conv['reply'],
                'timestamp': conv['created_at']
            })

        return jsonify({'messages': messages})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        if 'file' not in request.files:
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'لم يتم اختيار ملف'}), 400

        # حفظ الملف مؤقتاً ومعالجته
        file_id = hashlib.md5(f"{session['user_id']}_{file.filename}_{datetime.now().timestamp()}".encode()).hexdigest()
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_content = ""

        try:
            if file_extension == '.pdf' and PyPDF2 is not None:
                # معالجة PDF
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                file_content = f"📄 ملف PDF: {file.filename}\n\nالمحتوى:\n{text[:5000]}..." if len(text) > 5000 else text

            elif file_extension in ['.docx', '.doc'] and docx is not None:
                # معالجة Word
                doc = docx.Document(file)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                file_content = f"📝 ملف Word: {file.filename}\n\nالمحتوى:\n{text[:5000]}..." if len(text) > 5000 else text

            elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                # معالجة الصور (وصف أساسي)
                file_content = f"🖼️ صورة: {file.filename}\nالحجم: {len(file.read())} bytes\nتم رفع الصورة بنجاح، يمكنك الآن سؤال ClainAI عن محتواها."

            elif file_extension == '.txt':
                # معالجة نصي
                text = file.read().decode('utf-8')
                file_content = f"📄 ملف نصي: {file.filename}\n\nالمحتوى:\n{text[:5000]}..." if len(text) > 5000 else text

            else:
                file_content = f"📎 ملف: {file.filename}\nالنوع: {file_extension}\nالحجم: {len(file.read())} bytes"

        except Exception as processing_error:
            file_content = f"📎 ملف: {file.filename}\nالنوع: {file_extension}\nالحجم: {len(file.read())} bytes\nملاحظة: تعذر تحليل المحتوى بالكامل"

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO uploaded_files (id, user_id, filename, content, file_type) VALUES (?, ?, ?, ?, ?)',
            (file_id, session['user_id'], file.filename, file_content, file.content_type)
        )
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'تم رفع الملف {file.filename} بنجاح',
            'file_id': file_id,
            'content_preview': file_content[:200] + "..." if len(file_content) > 200 else file_content
        })

    except Exception as e:
        return jsonify({'error': f'حدث خطأ في رفع الملف: {str(e)}'}), 500

# =============================================================================
# Routes البحث والأخبار
# =============================================================================

@app.route("/api/search", methods=["POST"])
def search_web():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'استعلام البحث فارغ'}), 400

        if not SERPER_API_KEY:
            return jsonify({'error': 'خدمة البحث غير متاحة حالياً'}), 503

        # استخدام Serper API للبحث
        search_url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': SERPER_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {'q': query}

        response = requests.post(search_url, headers=headers, json=payload)
        if response.status_code != 200:
            return jsonify({'error': 'فشل في البحث'}), 500

        search_results = response.json()

        # حفظ نتائج البحث
        search_id = hashlib.md5(f"{session['user_id']}_{query}_{datetime.now().timestamp()}".encode()).hexdigest()
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO searches (id, user_id, query, results) VALUES (?, ?, ?, ?)',
            (search_id, session['user_id'], query, json.dumps(search_results))
        )
        conn.commit()
        conn.close()

        # تنسيق النتائج للعرض
        formatted_results = []
        if 'organic' in search_results:
            for result in search_results['organic'][:5]:
                formatted_results.append({
                    'title': result.get('title', ''),
                    'link': result.get('link', ''),
                    'snippet': result.get('snippet', '')
                })

        return jsonify({
            'success': True,
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        })

    except Exception as e:
        return jsonify({'error': f'حدث خطأ في البحث: {str(e)}'}), 500

@app.route("/api/news", methods=["POST"])
def get_news():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        query = data.get('query', 'أخبار اليوم')

        # استخدام Serper API للأخبار
        if SERPER_API_KEY:
            news_url = "https://google.serper.dev/news"
            headers = {
                'X-API-KEY': SERPER_API_KEY,
                'Content-Type': 'application/json'
            }
            payload = {'q': query, 'num': 5}

            response = requests.post(news_url, headers=headers, json=payload)

            if response.status_code == 200:
                news_data = response.json()

                # تنسيق النتائج
                news_items = []
                if 'news' in news_data:
                    for item in news_data['news'][:5]:
                        news_items.append({
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'source': item.get('source', ''),
                            'date': item.get('date', ''),
                            'snippet': item.get('snippet', '')
                        })

                # استخدام النماذج الذكية لتلخيص الأخبار
                try:
                    news_context = "\nأهم الأخبار:\n"
                    for i, news in enumerate(news_items, 1):
                        news_context += f"{i}. {news['title']}\n   المصدر: {news['source']}\n   التفاصيل: {news['snippet']}\n\n"

                    prompt = f"""أنت ClainAI - مساعد أخبار عربي. قم بتلخيص أهم الأخبار لليوم {datetime.now().strftime('%Y-%m-%d')}.

{news_context}

قدم تلخيصاً واضحاً ومفيداً باللغة العربية يركز على النقاط الرئيسية بطريقة إبداعية ومفصلة."""

                    news_summary, model_used = get_smart_response(prompt)

                except Exception as e:
                    print(f"❌ خطأ في تلخيص الأخبار: {e}")
                    news_summary = "📰 **أهم أخبار اليوم:**\n\n"
                    for i, news in enumerate(news_items, 1):
                        news_summary += f"**{i}. {news['title']}**\n"
                        news_summary += f"📰 المصدر: {news['source']}\n"
                        news_summary += f"📝 {news['snippet']}\n\n"

                return jsonify({
                    'success': True,
                    'query': query,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'summary': news_summary,
                    'articles': news_items,
                    'model_used': model_used
                })

        return jsonify({
            'success': True,
            'message': 'خدمة الأخبار غير متاحة حالياً',
            'date': datetime.now().strftime('%Y-%m-%d')
        })

    except Exception as e:
        return jsonify({'error': f'حدث خطأ في جلب الأخبار: {str(e)}'}), 500

# =============================================================================
# Routes الوكيل الذكي
# =============================================================================

@app.route("/api/agent/analyze", methods=["POST"])
def agent_analyze():
    """تحليل رسالة المستخدم وتحديد إذا كانت تحتاج وكيل"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'الرسالة فارغة'}), 400

        user_id = session['user_id']
        agent = SmartAgent(user_id)
        
        analysis = agent.analyze_intent(message)
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'needs_agent': analysis['needs_agent'],
            'is_instruction': analysis['is_instruction']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/agent/tasks", methods=["GET"])
def get_agent_tasks():
    """جلب مهام الوكيل الذكي"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        task_manager = TaskManager(user_id)
        tasks = task_manager.get_pending_tasks()
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'total_tasks': len(tasks)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/agent/track-price", methods=["POST"])
def agent_track_price():
    """طلب متابعة سعر معين"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        topic = data.get('topic', '').strip()
        condition = data.get('condition', '')
        
        if not topic:
            return jsonify({'error': 'الموضوع مطلوب'}), 400

        user_id = session['user_id']
        agent = SmartAgent(user_id)
        task_id = agent.create_tracking_task(topic, condition)
        
        # إرسال إشعار
        AgentAutomation.send_notification(
            user_id, 
            "🚀 بدء المتابعة", 
            f"تم بدء متابعة {topic}. جاري جمع البيانات الأولى..."
        )
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'تم بدء متابعة {topic}',
            'notification_sent': True
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/agent/research", methods=["POST"])
def agent_research():
    """طلب بحث عن موضوع"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        topic = data.get('topic', '').strip()
        depth = data.get('depth', 'basic')
        
        if not topic:
            return jsonify({'error': 'الموضوع مطلوب'}), 400

        user_id = session['user_id']
        agent = SmartAgent(user_id)
        task_id = agent.create_research_task(topic, depth)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'تم بدء البحث عن {topic}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/agent/notifications", methods=["GET"])
def get_agent_notifications():
    """جلب إشعارات الوكيل"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        conn = get_db_connection()
        notifications = conn.execute(
            'SELECT id, title, message, created_at FROM agent_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
            (user_id,)
        ).fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'notifications': [dict(notif) for notif in notifications]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/agent/status", methods=["GET"])
def agent_status():
    """حالة الوكيل الذكي"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        user_id = session['user_id']
        task_manager = TaskManager(user_id)
        tasks = task_manager.get_pending_tasks()
        
        conn = get_db_connection()
        notifications_count = conn.execute(
            'SELECT COUNT(*) as count FROM agent_notifications WHERE user_id = ? AND is_read = FALSE',
            (user_id,)
        ).fetchone()['count']
        conn.close()
        
        return jsonify({
            'success': True,
            'status': 'active',
            'pending_tasks': len(tasks),
            'unread_notifications': notifications_count,
            'capabilities': [
                "متابعة الأسعار والتغيرات",
                "البحث التلقائي", 
                "الإشعارات الذكية",
                "إدارة المهام",
                "التعلم من التفضيلات"
            ]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# Routes إضافية
# =============================================================================

@app.route("/api/date", methods=["GET"])
def get_current_date():
    try:
        now = datetime.now()
        hijri_date = get_hijri_date()

        date_info = {
            'gregorian': {
                'date': now.strftime('%Y-%m-%d'),
                'time': now.strftime('%H:%M:%S'),
                'day_name': now.strftime('%A'),
                'full_date': now.strftime('%Y/%m/%d %H:%M:%S')
            },
            'hijri': hijri_date,
            'timezone': 'Africa/Cairo'
        }

        return jsonify({
            'success': True,
            'date_info': date_info
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_hijri_date():
    try:
        today = datetime.now()
        hijri_months = ['محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة',
                       'رجب', 'شعبان', 'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة']

        hijri_year = 1446
        hijri_month = hijri_months[(today.month - 1) % 12]
        hijri_day = today.day

        return {
            'date': f'{hijri_year}-{(today.month):02d}-{today.day:02d}',
            'month_name': hijri_month,
            'year': hijri_year
        }
    except:
        return {
            'date': 'غير متوفر',
            'month_name': 'غير متوفر',
            'year': 'غير متوفر'
        }

@app.route("/api/location", methods=["POST"])
def save_location():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'غير مسجل الدخول'}), 401

        data = request.json
        lat = data.get('lat')
        lng = data.get('lng')

        if not lat or not lng:
            return jsonify({'error': 'إحداثيات الموقع مطلوبة'}), 400

        # حفظ الموقع في قاعدة البيانات
        location_id = hashlib.md5(f"{session['user_id']}_{lat}_{lng}_{datetime.now().timestamp()}".encode()).hexdigest()
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO uploaded_files (id, user_id, filename, content, file_type) VALUES (?, ?, ?, ?, ?)',
            (location_id, session['user_id'], f"location_{lat}_{lng}", f"الموقع: {lat}, {lng}", "location")
        )
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'تم حفظ الموقع'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/models", methods=["GET"])
def get_models_info():
    """الحصول على معلومات عن النماذج المتاحة"""
    try:
        models_info = {}
        for model_type, model in AI_MODELS.items():
            models_info[model_type] = {
                'name': model['name'],
                'enabled': model['enabled'],
                'has_key': bool(model['key'])
            }

        return jsonify({
            'success': True,
            'models': models_info,
            'total_models': len(models_info),
            'enabled_models': sum(1 for model in models_info.values() if model['enabled'])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# تشغيل التطبيق
# =============================================================================

if __name__ == "__main__":
    with app.app_context():
        init_db()
        print("=" * 60)
        print("🚀 ClainAI - المساعد الذكي الإبداعي المتقدم!")
        print("🤖 نظام الوكيل الذكي (AI Agent) مفعل!")
        print("=" * 60)
        print(f"📍 Base URL: {BASE_URL}")
        print(f"🔑 Google AI Key: {'✅' if GOOGLE_API_KEY else '❌'}")
        print(f"🔑 OpenAI Key: {'✅' if OPENAI_API_KEY else '❌'}")
        print(f"🔑 Claude Key: {'✅' if CLAUDE_API_KEY else '❌'}")
        print(f"🔑 OpenRouter Key: {'✅' if OPENROUTER_API_KEY else '❌'}")
        print(f"🔍 Serper Search: {'✅' if SERPER_API_KEY else '❌'}")
        print(f"🔐 GitHub OAuth: {'✅' if GITHUB_CLIENT_ID else '❌'}")
        print(f"🔐 Google OAuth: {'✅' if GOOGLE_CLIENT_ID else '❌'}")
        print(f"📄 PDF Support: {'✅' if PyPDF2 else '❌'}")
        print(f"📝 Word Support: {'✅' if docx else '❌'}")
        print(f"🤖 AI Agent System: ✅")
        print(f"👑 Developer: محمد عبد القادر السراج - mohammedu3615@gmail.com")
        print(f"🌐 التطبيق جاهز على: http://127.0.0.1:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

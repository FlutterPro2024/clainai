class ClainAIChat {
    constructor() {
        this.currentSession = {
            messages: [],
            isLoading: false,
            user: null,
            typing: false,
            hasUploadedFile: false
        };
        this.init();
    }

    // التهيئة
    async init() {
        console.log('🚀 تهيئة ClainAI...');
        await this.checkServerStatus();
        await this.loadUserInfo();
        await this.loadChatHistory();
        this.setupEventListeners();
        this.showWelcomeMessage();
        console.log('✅ تم تهيئة ClainAI بنجاح!');
    }

    // فحص حالة السيرفر
    async checkServerStatus() {
        try {
            const response = await fetch('/api/status');
            if (response.ok) {
                const data = await response.json();
                console.log('✅ السيرفر يعمل:', data.status);
            } else {
                console.warn('⚠️ مشكلة في اتصال السيرفر');
            }
        } catch (error) {
            console.error('❌ فشل الاتصال بالسيرفر:', error);
        }
    }

    // تحميل معلومات المستخدم
    async loadUserInfo() {
        try {
            const response = await fetch('/api/user');
            if (response.ok) {
                const user = await response.json();
                this.currentSession.user = user;
                this.updateUIUserInfo(user);
            } else {
                this.setupGuestSession();
            }
        } catch (error) {
            console.log('جلسة ضيف:', error);
            this.setupGuestSession();
        }
    }

    // فحص حالة المستخدم
    async checkUserStatus() {
        try {
            const response = await fetch('/api/user/status');
            if (response.ok) {
                const data = await response.json();
                console.log('📊 حالة المستخدم:', data.status);
                return data.status;
            }
        } catch (error) {
            console.log('❌ فشل في فحص حالة المستخدم:', error);
        }
        return { is_logged_in: false };
    }

    // إعداد جلسة ضيف
    setupGuestSession() {
        this.currentSession.user = {
            name: 'ضيف',
            role: 'user',
            email: 'guest@clainai.com'
        };
        this.updateUIUserInfo(this.currentSession.user);
    }

    // تحديث واجهة معلومات المستخدم
    updateUIUserInfo(user) {
        const userBadge = document.getElementById('userBadge');
        if (userBadge) {
            userBadge.innerHTML = `👤 ${user.name}`;
        }
    }

    // دالة رفع الملف
    async uploadFile(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.currentSession.hasUploadedFile = true;
                this.showNotification(' ✅ تم رفع الملف بنجاح! يمكنك الآن السؤال عنه', 'success');
                return result;
            } else {
                throw new Error(result.error || 'فشل في رفع الملف');
            }
        } catch (error) {
            console.error('❌ خطأ في رفع الملف:', error);
            this.showNotification(`❌ خطأ في رفع الملف: ${error.message}`, 'error');
            throw error;
        }
    }

    // معالجة رفع الملف من الواجهة
    handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // عرض رسالة تحميل
        this.addMessageToUI('assistant', `📁 جاري تحليل الملف: **${file.name}**...`);

        this.uploadFile(file)
            .then(result => {
                this.addMessageToUI('assistant',
                    `✅ **تم رفع الملف بنجاح!**\n\n` +
                    `📄 **اسم الملف:** ${file.name}\n` +
                    `📊 **الحجم:** ${file.size} bytes\n\n` +
                    `💡 **يمكنك الآن السؤال عن محتوى الملف!**\n` +
                    `جرب:\n` +
                    `• "ما هي النقاط الرئيسية؟"\n` +
                    `• "اشرح محتوى الملف"\n` +
                    `• "ما هي العناوين الرئيسية؟"`
                );
            })
            .catch(error => {
                this.addMessageToUI('error', `❌ فشل في رفع الملف: ${error.message}`);
            });
    }

    // الكشف إذا كان السؤال عن ملف
    isFileQuestion(message) {
        if (!this.currentSession.hasUploadedFile) return false;

        const fileKeywords = ['الملف', 'محتوى', 'المستند', 'الوثيقة', 'الرفع', 'رفعت', 'المرفوع', 'الذي رفعته', 'الملف المرفوع'];
        return fileKeywords.some(keyword => message.includes(keyword));
    }

    // الكشف إذا كان طلب أخبار
    isNewsRequest(message) {
        const newsKeywords = ['أخبار', 'الأخبار', 'تحديثات', 'الأحداث', 'الجديد', 'آخر الأخبار', 'أحدث', 'اليوم', 'news', 'updates'];
        const messageLower = message.toLowerCase();
        return newsKeywords.some(keyword => messageLower.includes(keyword));
    }

    // دالة جديدة للكشف عن طلب البحث العام
    isGeneralSearchRequest(message) {
        const searchKeywords = ['بحث', 'ابحث', 'من هو', 'متى', 'كم عدد', 'من فاز', 'آخر', 'جديد', 'ما هي أسعار', 'search', 'latest', 'who is', 'حدث', 'احدث', 'ماهو سعر', 'سعر', 'جديد'];
        const messageLower = message.toLowerCase();

        // استخدم البحث إذا كان يحتوي على كلمات بحث، ولكنه ليس طلب أخبار صريح أو سؤال عن ملف
        return searchKeywords.some(keyword => messageLower.includes(keyword)) &&
               !this.isNewsRequest(message) &&
               !this.isFileQuestion(message);
    }

    // دالة جلب الأخبار
    async getNews(query = 'أخبار اليوم') {
        try {
            this.showTypingIndicator();

            const response = await fetch('/api/news', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query })
            });

            const data = await response.json();

            this.hideTypingIndicator();

            if (data.success) {
                this.addMessageToUI('assistant', data.summary);
            } else {
                this.addMessageToUI('error', '❌ لم أتمكن من جلب الأخبار حالياً');
            }
        } catch (error) {
            this.hideTypingIndicator();
            this.addMessageToUI('error', `❌ خطأ في جلب الأخبار: ${error.message}`);
        }
    }

    // دالة جلب التاريخ
    async getCurrentDate() {
        try {
            const response = await fetch('/api/date');
            const data = await response.json();

            if (data.success) {
                const dateInfo = data.date_info;
                const dateMessage = `
                    **📅 التاريخ والوقت الحالي:**\n\n
                    **التاريخ الميلادي:** ${dateInfo.gregorian.full_date}\n
                    **اليوم:** ${dateInfo.gregorian.day_name}\n
                    **التاريخ الهجري:** ${dateInfo.hijri.date} (${dateInfo.hijri.month_name})\n
                    **السنة الهجرية:** ${dateInfo.hijri.year}\n
                    **المنطقة الزمنية:** ${dateInfo.timezone}
                `;
                this.addMessageToUI('assistant', dateMessage);
            }
        } catch (error) {
            console.error('Error fetching date:', error);
            this.addMessageToUI('error', '❌ لم أتمكن من جلب التاريخ حالياً');
        }
    }

    // إرسال رسالة
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');

        if (!messageInput) {
            console.error('❌ لم يتم العثور على حقل الإدخال');
            return;
        }

        const message = messageInput.value.trim();

        if (!message || this.currentSession.isLoading) {
            return;
        }

        // التحقق إذا كان طلب أخبار
        if (this.isNewsRequest(message)) {
            await this.getNews(message);
            messageInput.value = '';
            return;
        }

        // التحقق إذا كان طلب تاريخ
        if (message.includes('التاريخ') || message.includes('الوقت') || message.includes('تاريخ') || message.includes('time') || message.includes('date')) {
            await this.getCurrentDate();
            messageInput.value = '';
            return;
        }

        // تعطيل الواجهة أثناء التحميل
        this.currentSession.isLoading = true;
        this.currentSession.typing = true;
        sendButton.disabled = true;
        messageInput.disabled = true;

        // إضافة رسالة المستخدم للواجهة
        this.addMessageToUI('user', message);
        messageInput.value = '';

        // إظهار مؤشر الكتابة
        this.showTypingIndicator();

        try {
            console.log('🔄 إرسال الرسالة:', message);

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    use_search: this.isGeneralSearchRequest(message)
                })
            });

            if (!response.ok) {
                throw new Error(`خطأ في السيرفر: ${response.status}`);
            }

            const data = await response.json();
            console.log('✅ تم استلام الرد:', data);

            // إخفاء مؤشر الكتابة
            this.hideTypingIndicator();

            if (data.success) {
                // إضافة رد المساعد
                this.addMessageToUI('assistant', data.reply);

                // إذا كان هناك معلومات عن النموذج المستخدم
                if (data.thinking) {
                    this.addMessageToUI('thinking', `🤔 ${data.thinking}`);
                }
            } else {
                throw new Error(data.error || 'حدث خطأ غير معروف');
            }

        } catch (error) {
            console.error('❌ خطأ في الإرسال:', error);
            this.hideTypingIndicator();
            this.addMessageToUI('error', `⚠️ حدث خطأ: ${error.message}`);
        } finally {
            // إعادة تفعيل الواجهة
            this.currentSession.isLoading = false;
            this.currentSession.typing = false;
            sendButton.disabled = false;
            messageInput.disabled = false;
            messageInput.focus();
        }
    }

    // إضافة رسالة للواجهة
    addMessageToUI(role, content) {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) {
            console.error('❌ لم يتم العثور على حاوية المحادثة');
            return;
        }

        const messageElement = document.createElement('div');
        messageElement.className = `message ${role}-message`;

        const currentTime = new Date().toLocaleTimeString('ar-EG', {
            hour: '2-digit',
            minute: '2-digit'
        });

        // تنسيق مختلف لكل دور
        let bubbleContent = '';
        switch(role) {
            case 'user':
                bubbleContent = `
                    <div class="message-bubble user-bubble">
                        ${this.formatContent(content)}
                    </div>
                    <div class="message-time">${currentTime}</div>
                `;
                break;

            case 'assistant':
                bubbleContent = `
                    <div class="message-bubble assistant-bubble">
                        ${this.formatContent(content)}
                    </div>
                    <div class="message-time">${currentTime}</div>
                `;
                break;

            case 'thinking':
                bubbleContent = `
                    <div class="message-bubble thinking-bubble">
                        🤔 ${this.formatContent(content)}
                    </div>
                    <div class="message-time">${currentTime}</div>
                `;
                break;

            case 'error':
                bubbleContent = `
                    <div class="message-bubble error-bubble">
                        ❌ ${this.formatContent(content)}
                    </div>
                    <div class="message-time">${currentTime}</div>
                `;
                break;
        }

        messageElement.innerHTML = bubbleContent;
        chatContainer.appendChild(messageElement);

        // إضافة ميزة النسخ
        this.addCopyFeature(messageElement.querySelector('.message-bubble'));

        // التمرير للأسفل
        this.scrollToBottom();

        // حفظ في السجل
        this.currentSession.messages.push({
            role,
            content,
            timestamp: new Date()
        });
    }

    // تنسيق المحتوى
    formatContent(content) {
        if (!content) return '';

        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }

    // ميزة نسخ الرسائل
    addCopyFeature(element) {
        if (!element) return;

        element.style.cursor = 'pointer';
        element.title = 'انقر للنسخ';

        element.addEventListener('click', async function() {
            const textToCopy = this.textContent || this.innerText;

            try {
                await navigator.clipboard.writeText(textToCopy);

                // إظهار مؤشر النسخ
                const originalBackground = this.style.background;
                this.style.background = 'var(--success-color)';
                this.style.transition = 'background 0.3s ease';

                setTimeout(() => {
                    this.style.background = originalBackground;
                }, 1000);

            } catch (err) {
                console.error('فشل في نسخ النص: ', err);
            }
        });
    }

    // عرض مؤشر الكتابة
    showTypingIndicator() {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) return;

        const typingElement = document.createElement('div');
        typingElement.id = 'typingIndicator';
        typingElement.className = 'message assistant-message';
        typingElement.innerHTML = `
            <div class="typing-indicator">
                <span>ClainAI يكتب</span>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;

        chatContainer.appendChild(typingElement);
        this.scrollToBottom();
    }

    // إخفاء مؤشر الكتابة
    hideTypingIndicator() {
        const typingElement = document.getElementById('typingIndicator');
        if (typingElement) {
            typingElement.remove();
        }
    }

    // التمرير للأسفل
    scrollToBottom() {
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }

    // التعامل مع ضغط المفاتيح
    handleKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    // تحميل سجل المحادثة
    async loadChatHistory() {
        try {
            const response = await fetch('/api/history');
            if (response.ok) {
                const history = await response.json();
                const chatContainer = document.getElementById('chatContainer');

                if (chatContainer && history.messages && history.messages.length > 0) {
                    // احتفظ بالرسالة الترحيبية فقط إذا لم توجد محادثات سابقة
                    const welcomeMessage = chatContainer.innerHTML;
                    chatContainer.innerHTML = '';

                    history.messages.forEach(msg => {
                        this.addMessageToUI(msg.role, msg.content);
                    });
                }
            }
        } catch (error) {
            console.log('📝 لا يوجد سجل محادثات سابق');
        }
    }

    // عرض رسالة ترحيب
    showWelcomeMessage() {
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer && this.currentSession.messages.length === 0) {
            this.addMessageToUI('assistant',
                '🎉 **مرحباً بك في ClainAI!** 🌟\n\n' +
                'مساعدك الذكي العربي المتكامل الذي يجيب على جميع أسئلتك بدقة واحترافية.\n\n' +
                '**💫 يمكنني مساعدتك في:**\n' +
                '• الإجابة على أسئلتك العلمية 🧪\n' +
                '• شرح المفاهيم التقنية 💻\n' +
                '• تقديم معلومات ثقافية 🌍\n' +
                '• المساعدة في البرمجة والتطوير 🔧\n' +
                '• تحليل الملفات النصية 📄\n' +
                '• أخبار وتحديثات 📰\n\n' +
                '**🎯 جرب هذه الأسئلة:**\n' +
                '• "ما هو الذكاء الاصطناعي?"\n' +
                '• "ما هي أخبار اليوم؟"\n' +
                '• "ما التاريخ اليوم؟"\n' +
                '• "كيف أتعلم البرمجة?"\n\n' +
                'اسألني أي شيء! 😊'
            );
        }
    }

    // مسح المحادثة
    async clearChat() {
        if (!confirm('هل تريد مسح كل المحادثة؟ سيتم حذف جميع الرسائل.')) return;

        try {
            const response = await fetch('/api/clear', {
                method: 'POST'
            });

            if (response.ok) {
                const chatContainer = document.getElementById('chatContainer');
                if (chatContainer) {
                    chatContainer.innerHTML = '';
                    this.currentSession.messages = [];
                    this.currentSession.hasUploadedFile = false;
                    this.showWelcomeMessage();
                }
                this.showNotification('تم مسح المحادثة بنجاح', 'success');
            }
        } catch (error) {
            console.error('❌ خطأ في مسح المحادثة:', error);
            this.showNotification('حدث خطأ في مسح المحادثة', 'error');
        }
    }

    // تسجيل الخروج
    async logout() {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST'
            });

            if (response.ok) {
                window.location.href = '/login';
            }
        } catch (error) {
            console.error('❌ خطأ في تسجيل الخروج:', error);
            this.showNotification('حدث خطأ في تسجيل الخروج', 'error');
        }
    }

    // إظهار الإشعارات
    showNotification(message, type = 'info') {
        // إنشاء عنصر الإشعار
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">✕</button>
        `;

        // إضافة الأنماط إذا لم تكن موجودة
        if (!document.querySelector('#notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'notification-styles';
            styles.textContent = `
                .notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    border-radius: 8px;
                    color: white;
                    font-weight: 500;
                    z-index: 1000;
                    animation: slideIn 0.3s ease;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    max-width: 300px;
                }
                .notification-success { background: #48bb78; }
                .notification-error { background: #f56565; }
                .notification-info { background: #667eea; }
                .notification button {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    font-size: 16px;
                }
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(notification);

        // إزالة الإشعار تلقائياً بعد 3 ثواني
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 3000);
    }

    // إعداد مستمعي الأحداث
    setupEventListeners() {
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const fileInput = document.getElementById('fileInput');
        const clearButton = document.getElementById('clearButton');
        const logoutButton = document.getElementById('logoutButton');

        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => this.handleKeyPress(e));
            messageInput.addEventListener('input', () => {
                // تحسين تجربة المستخدم أثناء الكتابة
                sendButton.disabled = messageInput.value.trim() === '';
            });
        }

        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }

        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        }

        if (clearButton) {
            clearButton.addEventListener('click', () => this.clearChat());
        }

        if (logoutButton) {
            logoutButton.addEventListener('click', () => this.logout());
        }
    }
}

// التهيئة عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    window.clainai = new ClainAIChat();
});

// نظام إدارة الأخطاء
window.addEventListener('error', function(event) {
    console.error('❌ خطأ في النظام:', event.error);
});

// دعم PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/service-worker.js')
            .then(function(registration) {
                console.log('ServiceWorker registered: ', registration.scope);
            })
            .catch(function(error) {
                console.log('ServiceWorker registration failed: ', error);
            });
    });
}

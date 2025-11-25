class ClainAIChat {
    constructor() {
        this.currentSession = {
            messages: [],
            isLoading: false,                                  user: null,
            typing: false
        };
        this.init();
    }                                              
    // التهيئة
    async init() {
        console.log('🚀 تهيئة ClainAI...');
        await this.loadUserInfo();
        await this.loadChatHistory();
        this.setupEventListeners();
        this.showWelcomeMessage();
        console.log('✅ تم تهيئة ClainAI بنجاح!');
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
        const userInfoElement = document.getElementById('userInfo');
        if (userInfoElement) {
            userInfoElement.innerHTML = `
                <strong>👤 ${user.name}</strong>
                <span class="role-badge">${user.role}</span>
                ${user.role === 'developer' ? '👑' : ''}
            `;
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
                body: JSON.stringify({ message: message })
            });

            if (!response.ok) {
                throw new Error(`خطأ في السيرفر: ${response.status}`);
            }

            const data = await response.json();
            console.log('✅ تم استلام الرد:', data);

            // إخفاء مؤشر الكتابة
            this.hideTypingIndicator();

            // إضافة رد المساعد
            this.addMessageToUI('assistant', data.reply);

            // إذا كان مطوراً، عرض عملية التفكير
            if (this.currentSession.user?.role === 'developer' && data.thinking) {
                this.addMessageToUI('thinking', data.thinking);
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
        messageElement.setAttribute('role', 'listitem');

        // تنسيق مختلف لكل دور
        switch(role) {
            case 'user':
                messageElement.innerHTML = `
                    <div class="message-header">
                        <strong>👤 أنت</strong>
                        <span class="message-time">${this.getCurrentTime()}</span>
                    </div>
                    <div class="message-content">${this.formatContent(content)}</div>
                `;
                break;

            case 'assistant':
                messageElement.innerHTML = `
                    <div class="message-header">
                        <strong>🤖 ClainAI</strong>
                        <span class="message-time">${this.getCurrentTime()}</span>
                    </div>
                    <div class="message-content">${this.formatContent(content)}</div>
                `;
                break;

            case 'thinking':
                messageElement.innerHTML = `
                    <div class="thinking-message">
                        <div class="message-header">
                            <strong>🧠 عملية التفكير</strong>
                            <span class="message-time">${this.getCurrentTime()}</span>
                        </div>
                        <div class="message-content">${this.formatContent(content)}</div>
                    </div>
                `;
                break;

            case 'error':
                messageElement.innerHTML = `
                    <div class="error-message">
                        <div class="message-header">
                            <strong>⚠️ خطأ</strong>
                            <span class="message-time">${this.getCurrentTime()}</span>
                        </div>
                        <div class="message-content">${this.formatContent(content)}</div>
                    </div>
                `;
                break;
        }

        chatContainer.appendChild(messageElement);

        // Scroll to bottom
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
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/~~(.*?)~~/g, '<del>$1</del>')
            .replace(/_(.*?)_/g, '<u>$1</u>');
    }

    // الحصول على الوقت الحالي
    getCurrentTime() {
        return new Date().toLocaleTimeString('ar-EG', {
            hour: '2-digit',
            minute: '2-digit'
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
            <div class="message-header">
                <strong>🤖 ClainAI</strong>
                <span class="message-time">${this.getCurrentTime()}</span>
            </div>
            <div class="thinking-indicator">
                <div class="thinking-dots">
                    <span>يكتب</span>
                    <span class="dot">.</span>
                    <span class="dot">.</span>
                    <span class="dot">.</span>
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

                if (chatContainer && history.length > 0) {
                    chatContainer.innerHTML = '';
                    history.forEach(msg => {
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
        if (chatContainer && chatContainer.children.length === 0) {
            setTimeout(() => {
                this.addMessageToUI('assistant',
                    '🎉 **مرحباً بك في ClainAI!** 🌟\n\n' +
                    'مساعدك الذكي العربي المتكامل الذي يجيب على جميع أسئلتك بدقة واحترافية.\n\n' +
                    '**💫 يمكنني مساعدتك في:**\n' +
                    '• الإجابة على أسئلتك العلمية  🧪\n' +
                    '• شرح المفاهيم التقنية 💻\n' +
                    '• تقديم معلومات ثقافية 🌍\n' +
                    '• المساعدة في البرمجة والتطوير 🔧\n\n' +
                    '**🎯 جرب هذه الأسئلة:**\n' +
                    '• "ما هو الذكاء الاصطناعي?"\n' +
                    '• "اشرح الحوسبة السحابية"\n' +
                    '• "كيف أتعلم البرمجة?"\n\n' +
                    'اسألني أي شيء! 😊'
                );
            }, 500);
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

        // إضافة الأنماط
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
                .notification-success { background: var(--success); }
                .notification-error { background: var(--error); }
                .notification-info { background: var(--primary-color); }
                .notification button {
                    background: none;
                    border: none;
                    color: white;
                    cursor: pointer;
                    font-size: 16px;
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

        // تحديث تلقائي للوقت
        setInterval(() => {
            this.updateMessageTimes();
        }, 60000); // كل دقيقة
    }

    // تحديث أوقات الرسائل
    updateMessageTimes() {
        const messageHeaders = document.querySelectorAll('.message-header .message-time');
        messageHeaders.forEach(header => {
            // يمكن إضافة منطق لتحديث الوقت إذا لزم الأمر
        });
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
        navigator.serviceWorker.register('/static/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registered: ', registration.scope);
            })
            .catch(function(error) {
                console.log('ServiceWorker registration failed: ', error);
            });
    });
}

// تصدير الدوال للاستخدام العالمي
window.sendMessage = function() { window.clainai?.sendMessage(); }
window.clearChat = function() { window.clainai?.clearChat(); }
window.logout = function() { window.clainai?.logout(); }

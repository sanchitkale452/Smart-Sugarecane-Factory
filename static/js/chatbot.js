// Chatbot functionality
class Chatbot {
    constructor() {
        this.isOpen = false;
        this.messages = [];
        this.init();
    }

    init() {
        this.createChatbotUI();
        this.attachEventListeners();
        this.addWelcomeMessage();
    }

    createChatbotUI() {
        const chatbotHTML = `
            <div class="chatbot-container">
                <button class="chatbot-button" id="chatbotToggle">
                    <i class="fas fa-comments chat-icon"></i>
                    <i class="fas fa-times close-icon"></i>
                </button>
                
                <div class="chatbot-popup" id="chatbotPopup">
                    <div class="chatbot-header">
                        <div class="chatbot-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="chatbot-header-info">
                            <h3>Factory Assistant</h3>
                            <p>Online - Ready to help!</p>
                        </div>
                    </div>
                    
                    <div class="chatbot-messages" id="chatbotMessages">
                        <!-- Messages will be inserted here -->
                    </div>
                    
                    <div class="quick-replies" id="quickReplies">
                        <!-- Quick reply buttons will be inserted here -->
                    </div>
                    
                    <div class="chatbot-input-area">
                        <input 
                            type="text" 
                            class="chatbot-input" 
                            id="chatbotInput" 
                            placeholder="Type your message..."
                            autocomplete="off"
                        />
                        <button class="chatbot-send-btn" id="chatbotSend">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', chatbotHTML);
    }

    attachEventListeners() {
        const toggleBtn = document.getElementById('chatbotToggle');
        const sendBtn = document.getElementById('chatbotSend');
        const input = document.getElementById('chatbotInput');

        toggleBtn.addEventListener('click', () => this.toggleChatbot());
        sendBtn.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });
    }

    toggleChatbot() {
        this.isOpen = !this.isOpen;
        const popup = document.getElementById('chatbotPopup');
        const button = document.getElementById('chatbotToggle');
        
        if (this.isOpen) {
            popup.classList.add('active');
            button.classList.add('active');
            document.getElementById('chatbotInput').focus();
        } else {
            popup.classList.remove('active');
            button.classList.remove('active');
        }
    }

    addWelcomeMessage() {
        const welcomeMsg = "Hello! 👋 I'm your Factory Assistant. How can I help you today?";
        this.addMessage(welcomeMsg, 'bot');
        this.showQuickReplies([
            'Check inventory status',
            'View production data',
            'Farm information',
            'Help & Support'
        ]);
    }

    addMessage(text, sender = 'bot') {
        const messagesContainer = document.getElementById('chatbotMessages');
        const time = new Date().toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        // Remove asterisks from bot responses to avoid showing markdown markers
        const displayText = sender === 'bot' ? text.replace(/\*/g, '') : text;

        const messageHTML = `
            <div class="message ${sender}">
                <div class="message-avatar">
                    <i class="fas fa-${sender === 'bot' ? 'robot' : 'user'}"></i>
                </div>
                <div class="message-content">
                    <div>${displayText}</div>
                    <div class="message-time">${time}</div>
                </div>
            </div>
        `;

        messagesContainer.insertAdjacentHTML('beforeend', messageHTML);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        this.messages.push({ text, sender, time });
    }

    showTypingIndicator() {
        const messagesContainer = document.getElementById('chatbotMessages');
        const typingHTML = `
            <div class="message bot" id="typingIndicator">
                <div class="message-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="typing-indicator active">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        messagesContainer.insertAdjacentHTML('beforeend', typingHTML);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }

    showQuickReplies(replies) {
        const quickRepliesContainer = document.getElementById('quickReplies');
        quickRepliesContainer.innerHTML = '';
        
        replies.forEach(reply => {
            const button = document.createElement('button');
            button.className = 'quick-reply-btn';
            button.textContent = reply;
            button.addEventListener('click', () => {
                this.handleQuickReply(reply);
            });
            quickRepliesContainer.appendChild(button);
        });
    }

    handleQuickReply(reply) {
        this.addMessage(reply, 'user');
        this.processMessage(reply);
    }

    async sendMessage() {
        const input = document.getElementById('chatbotInput');
        const message = input.value.trim();
        
        if (!message) return;
        
        this.addMessage(message, 'user');
        input.value = '';
        
        this.processMessage(message);
    }

    async processMessage(message) {
        this.showTypingIndicator();
        
        try {
            // Try to get intelligent response from backend API
            const apiResponse = await this.getAPIResponse(message);
            this.hideTypingIndicator();
            
            if (apiResponse && apiResponse.text) {
                this.addMessage(apiResponse.text, 'bot');
            } else {
                // Fallback to local response
                const response = this.generateResponse(message);
                this.addMessage(response.text, 'bot');
                
                if (response.quickReplies) {
                    this.showQuickReplies(response.quickReplies);
                }
            }
        } catch (error) {
            // If API fails, use local response
            this.hideTypingIndicator();
            const response = this.generateResponse(message);
            this.addMessage(response.text, 'bot');
            
            if (response.quickReplies) {
                this.showQuickReplies(response.quickReplies);
            }
        }
    }

    async getAPIResponse(message) {
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            const response = await fetch('/chatbot/query/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || this.getCookie('csrftoken')
                },
                body: JSON.stringify({ query: message })
            });
            
            if (response.ok) {
                return await response.json();
            }
            return null;
        } catch (error) {
            console.error('API Error:', error);
            return null;
        }
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    generateResponse(message) {
        const lowerMessage = message.toLowerCase();
        
        // Inventory related
        if (lowerMessage.includes('inventory') || lowerMessage.includes('stock')) {
            return {
                text: "I can help you with inventory management! You can:\n• Check current stock levels\n• View low stock alerts\n• See recent transactions\n• Track expiring items\n\nWhat would you like to know?",
                quickReplies: ['Current stock', 'Low stock items', 'Recent transactions']
            };
        }
        
        // Production related
        if (lowerMessage.includes('production') || lowerMessage.includes('batch')) {
            return {
                text: "For production information, I can show you:\n• Active production batches\n• Completed batches\n• Production efficiency\n• Quality metrics\n\nWhat information do you need?",
                quickReplies: ['Active batches', 'Production stats', 'Quality reports']
            };
        }
        
        // Farm related
        if (lowerMessage.includes('farm')) {
            return {
                text: "I can provide farm information including:\n• Active farms list\n• Farm activities\n• Harvest schedules\n• Farm performance\n\nWhat would you like to see?",
                quickReplies: ['Active farms', 'Recent activities', 'Harvest schedule']
            };
        }
        
        // Help
        if (lowerMessage.includes('help') || lowerMessage.includes('support')) {
            return {
                text: "I'm here to help! I can assist you with:\n• Inventory management\n• Production tracking\n• Farm information\n• System navigation\n• Reports and analytics\n\nJust ask me anything!",
                quickReplies: ['Inventory help', 'Production help', 'Farm help']
            };
        }
        
        // Greeting
        if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
            return {
                text: "Hello! 👋 How can I assist you with the factory management system today?",
                quickReplies: ['Check inventory', 'View production', 'Farm info', 'Help']
            };
        }
        
        // Thank you
        if (lowerMessage.includes('thank') || lowerMessage.includes('thanks')) {
            return {
                text: "You're welcome! Is there anything else I can help you with?",
                quickReplies: ['Yes, help me', 'No, that\'s all']
            };
        }
        
        // Default response
        return {
            text: "I understand you're asking about: \"" + message + "\"\n\nI can help you with inventory, production, farms, and general system information. What would you like to know more about?",
            quickReplies: ['Inventory', 'Production', 'Farms', 'Help']
        };
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new Chatbot();
});

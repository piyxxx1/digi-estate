import { useState, useRef, useEffect } from 'react';
import {
  Send,
  MessageSquare,
  Plus,
  User,
  Bot,
  Settings,
  Search,
  Hash,
  Sparkles
} from 'lucide-react';
import { getGeminiResponse } from './context/response';
import './App.css';

interface Message {
  id: number;
  text: string;
  sender: 'user' | 'bot';
  time: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      text: "Namaste! Main Priya hoon, Digi-Estate ki taraf se. Aap kaise help kar sakti hoon aaj?",
      sender: 'bot',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Calculate total characters in all messages
  const totalCharacters = messages.reduce((acc, msg) => acc + msg.text.length, 0);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const newMessage: Message = {
      id: Date.now(),
      text: input,
      sender: 'user',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages([...messages, newMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Get chat history in the format the service expects
      const history = messages.map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'model',
        text: msg.text
      }));

      const botText = await getGeminiResponse(input, history);

      const botResponse: Message = {
        id: Date.now() + 1,
        text: botText,
        sender: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      console.error("Chat Error:", error);
      const errorMsg: Message = {
        id: Date.now() + 1,
        text: "I'm having a bit of trouble connecting. Could you try that again?",
        sender: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <Sparkles className="logo-icon" />
          <h1 className="sidebar-title">Digi-Estate AI</h1>
        </div>

        <button className="new-chat-btn">
          <Plus size={20} />
          <span>New Session</span>
        </button>

        <div className="chat-history">
          <div className="history-item active">
            <MessageSquare size={18} />
            <span>Project Discussion</span>
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="history-item">
            <Settings size={18} />
            <span>Settings</span>
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-main">
        <header className="chat-header">
          <div className="header-info">
            <h2>Priya — Digi-Estate Assistant</h2>
            <div className="status-badge">
              <span className="status-dot"></span>
              <span>AI System Online</span>
            </div>
          </div>
          <div className="header-actions">
            <div className="char-counter">
              <Hash size={16} />
              <span>{totalCharacters} chars</span>
            </div>
            <Search className="text-secondary cursor-pointer" size={20} />
          </div>
        </header>

        <div className="messages-container">
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.sender}`}>
              <div className="message-avatar">
                {msg.sender === 'user' ? <User size={20} /> : <Bot size={20} className="text-primary" />}
              </div>
              <div className="message-bubble-wrapper">
                <div className="message-bubble">
                  {msg.text}
                </div>
                <span className="message-time">{msg.time}</span>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="message bot typing">
              <div className="message-avatar">
                <Bot size={20} className="text-primary" />
              </div>
              <div className="message-bubble">
                <div className="typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <footer className="input-area">
          <div className="input-wrapper">
            <input
              type="text"
              className="chat-input"
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={!input.trim()}
            >
              <Send size={20} />
            </button>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;

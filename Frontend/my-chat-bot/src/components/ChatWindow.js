import React, { useState } from 'react';
import '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/styles/ChatWindow.css'
import { sendQuery } from '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/components/apiService.js'
const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (input.trim()) {
      const newMessages = [...messages, { text: input, type: 'user' }];
      setMessages(newMessages);
      setInput('');
      setLoading(true);
  
      try {
        const data = await sendQuery(input); // Call the sendQuery function
        const botMessage = data.answer || 'No response from bot';
        setMessages([...newMessages, { text: botMessage, type: 'bot' }]);
      } catch (error) {
        console.error('Error sending message:', error);
        setMessages([...newMessages, { text: 'Error getting response from bot', type: 'bot' }]);
      } finally {
        setLoading(false);
      }
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault(); // Prevents form submission or new line creation
      handleSend(); // Call the send message function
    }
  };

  return (
    <div className="chat-wrapper">
      <div className="chat-window">
        <div className="chat-history">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`}>
              {msg.text}
            </div>
          ))}
        </div>
        <div className="chat-input">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            onKeyPress={handleKeyPress}
          />
          <button onClick={handleSend} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;

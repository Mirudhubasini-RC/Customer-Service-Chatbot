import React, { useState } from 'react';

import '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/styles/ChatWindow.css';
import salesIcon from '../assests/sales.png';
import productIcon from '../assests/Shopping.png';
import { sendQuery, fetchSalesData, fetchQueriesData } from '../components/apiService.js';

const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [tableData, setTableData] = useState(null); // New state for table data

  const handleSend = async () => {
    if (input.trim()) {
      const userMessage = { text: input, type: 'user' };
      const updatedMessages = [...messages, userMessage];
      setMessages(updatedMessages);
      setInput('');
      setLoading(true);

      const typingIndicator = { text: 'Typing...', type: 'bot' };
      setMessages([...updatedMessages, typingIndicator]);

      try {
        const data = await sendQuery(input);
        const botMessage = data.answer || 'No response from bot';
        const finalMessages = updatedMessages.concat({ text: botMessage, type: 'bot' });
        setMessages(finalMessages);
      } catch (error) {
        console.error('Error sending message:', error);
        const finalMessages = updatedMessages.concat({ text: 'Error getting response from bot', type: 'bot' });
        setMessages(finalMessages);
      } finally {
        setLoading(false);
      }
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSend();
    }
  };

  const handleIconClick = async (type) => {
    setInput(`Query for ${type}`);
    setLoading(true);
    
    let response;
    try {
      if (type === 'sales') {
        response = await fetchSalesData();
      } else if (type === 'product') {
        response = await fetchQueriesData();
      }

      const tableHtml = generateTableHtml(response);
      const botMessage = tableHtml || 'No data available';
      const updatedMessages = [...messages, { text: botMessage, type: 'bot' }];
      setMessages(updatedMessages);
    } catch (error) {
      console.error('Error fetching data:', error);
      const updatedMessages = [...messages, { text: 'Error fetching data', type: 'bot' }];
      setMessages(updatedMessages);
    } finally {
      setLoading(false);
    }
  };

  const generateTableHtml = (data) => {
    if (!data || data.length === 0) return '';

    const headers = Object.keys(data[0]);
    const rows = data.map(row =>
      `<tr>${headers.map(header => `<td>${row[header]}</td>`).join('')}</tr>`
    ).join('');

    return `<table border="1">
      <thead><tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  };

  return (
    <div className="chat-wrapper">
      <div className="chat-window">
        <div className="chat-history">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`} dangerouslySetInnerHTML={{ __html: msg.text }} />
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
          <button className="Send" onClick={handleSend} disabled={loading}>
          </button>
          <div className="icon-group">
            <button className="icon-button" onClick={() => handleIconClick('sales')}>
              <img src={salesIcon} alt="Sales" className="icon" />
            </button>
            <button className="icon-button" onClick={() => handleIconClick('product')}>
              <img src={productIcon} alt="Product" className="icon" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;

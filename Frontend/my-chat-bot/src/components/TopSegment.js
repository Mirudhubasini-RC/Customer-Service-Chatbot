import React, { useState } from 'react';
import '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/styles/TopSegment.css'; // Import the corresponding CSS file
import search from '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/assests/search.svg';
import logo from '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/assests/c5i.png';
import ham from '/Users/mirudhubasinirc/Documents/Customer-Service-ChatBot/Customer-Service-Chatbot/Frontend/my-chat-bot/src/assests/hammenu.webp';


const TopSegment = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = () => {
    setMenuOpen(!menuOpen);
  };

  return (
    <header className="top-segment">
      <div className="logo">
        <img src={logo} alt="logo"/>
      </div>
      <nav className={`nav-links ${menuOpen ? 'open' : ''}`}>
        <a href="#industries">Industries</a>
        <a href="#solutions">Solutions</a>
        <a href="#our-ips">Our IPs</a>
        <a href="#genai">GenAI</a>
        <a href="#thought-leadership">Thought Leadership</a>
        <a href="#about-us">About Us</a>
      </nav>
      <button className="contact-us-btn">Contact Us</button>
      
      <div className="icons">
        <button className="search-btn">
        <img src={search} alt="Search Icon" />
        </button>
        <button className="menu-btn" onClick={toggleMenu}>
        <img src={ham} alt="Ham Icon" />
        </button>
      </div>
    </header>
  );
};

export default TopSegment;

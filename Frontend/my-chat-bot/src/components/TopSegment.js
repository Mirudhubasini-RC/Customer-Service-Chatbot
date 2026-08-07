import React from 'react';
import '../styles/TopSegment.css';
import logo from '../assests/retailask-logo.svg';

const TopSegment = () => {
  return (
    <header className="top-segment">
      <a className="logo" href="#home" aria-label="RetailAsk home">
        <img src={logo} alt="RetailAsk" />
      </a>
      <p className="top-tagline">Ask your retail data anything</p>
    </header>
  );
};

export default TopSegment;

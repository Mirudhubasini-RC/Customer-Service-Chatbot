import React from 'react';
import ChatWindow from './components/ChatWindow';
import TopSegment from './components/TopSegment';
import './styles/Global.css'; // Import global styles

const App = () => {
  return (
    <div className="App">
      <TopSegment />
      <ChatWindow />  
    </div>
  );
};

export default App;

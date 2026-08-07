import React, { useEffect, useRef, useState } from 'react';

import '../styles/ChatWindow.css';
import {
  sendQuery,
  fetchSalesData,
  fetchQueriesData,
  fetchPracticeQuestions,
} from '../components/apiService.js';

const SendIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path
      d="M4.5 19.5l15-7.5-15-7.5v6l10 1.5-10 1.5v6z"
      fill="currentColor"
    />
  </svg>
);

const SalesIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path
      d="M4 19h16M7 16V10M12 16V6M17 16v-3"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const ProductsIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path
      d="M6 7h12l-1 12H7L6 7zM9 7V5a3 3 0 0 1 6 0v2"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [practiceQuestions, setPracticeQuestions] = useState([]);
  const [pipeline, setPipeline] = useState([]);
  const [pipelineMeta, setPipelineMeta] = useState({
    model: '',
    sql: null,
    rows: [],
  });
  const historyRef = useRef(null);

  useEffect(() => {
    fetchPracticeQuestions()
      .then(setPracticeQuestions)
      .catch(() => {
        setPracticeQuestions([
          'What were our total sales this month?',
          'Which products are selling the most?',
          'Can you recommend products for a first-time buyer?',
          'What is the average order value?',
          'Summarize recent customer support queries.',
          'Which product has the highest price?',
        ]);
      });
  }, []);

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const setLoadingPipeline = (question) => {
    setPipeline([
      { id: 1, title: 'User question', status: 'done', detail: question },
      { id: 2, title: 'AI → SQL', status: 'running', detail: 'Generating SQL…' },
      { id: 3, title: 'Run SQL on MySQL', status: 'pending', detail: 'Waiting…' },
      { id: 4, title: 'AI answer', status: 'pending', detail: 'Waiting…' },
    ]);
  };

  const askAgent = async (queryText) => {
    const trimmed = queryText.trim();
    if (!trimmed || loading) return;

    const userMessage = { text: trimmed, type: 'user' };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);
    setLoadingPipeline(trimmed);
    setPipelineMeta({ model: '', sql: null, rows: [] });

    try {
      const data = await sendQuery(trimmed);
      if (data.error && !data.answer) {
        throw new Error(data.error);
      }
      const botMessage = data.answer || 'No response from agent';
      setMessages([...updatedMessages, { text: botMessage, type: 'bot' }]);
      setPipeline(data.pipeline || []);
      setPipelineMeta({
        model: data.model || '',
        sql: data.sql || null,
        rows: data.rows || [],
      });
    } catch (error) {
      console.error('Error sending message:', error);
      const detail =
        (error && error.message) ||
        'Could not reach the agent. Please try again.';
      setMessages([...updatedMessages, { text: detail, type: 'bot' }]);
      setPipeline([
        { id: 1, title: 'User question', status: 'done', detail: trimmed },
        {
          id: 2,
          title: 'Pipeline failed',
          status: 'error',
          detail,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    askAgent(input);
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSend();
    }
  };

  const handleIconClick = async (type) => {
    if (loading) return;
    setLoading(true);

    const label =
      type === 'sales'
        ? 'Show me current sales data'
        : 'Show me the product catalog';

    const updatedMessages = [...messages, { text: label, type: 'user' }];
    setMessages(updatedMessages);
    setPipeline([
      { id: 1, title: 'User action', status: 'done', detail: label },
      {
        id: 2,
        title: 'Direct DB fetch',
        status: 'running',
        detail: type === 'sales' ? 'GET /sales' : 'GET /products',
      },
    ]);

    try {
      const response =
        type === 'sales' ? await fetchSalesData() : await fetchQueriesData();
      const tableHtml = generateTableHtml(response);
      setMessages([
        ...updatedMessages,
        {
          text: tableHtml || 'No data available from the database.',
          type: 'bot',
        },
      ]);
      setPipeline([
        { id: 1, title: 'User action', status: 'done', detail: label },
        {
          id: 2,
          title: 'Direct DB fetch',
          status: 'done',
          detail: `${(response || []).length} row(s) from MySQL`,
        },
      ]);
      setPipelineMeta({
        model: 'direct-api',
        sql: type === 'sales' ? 'SELECT * FROM sales' : 'SELECT * FROM products',
        rows: (response || []).slice(0, 20),
      });
    } catch (error) {
      console.error('Error fetching data:', error);
      setMessages([
        ...updatedMessages,
        { text: 'Error fetching data from the database.', type: 'bot' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const generateTableHtml = (data) => {
    if (!data || data.length === 0) return '';

    const headers = Object.keys(data[0]);
    const rows = data
      .map(
        (row) =>
          `<tr>${headers.map((header) => `<td>${row[header] ?? ''}</td>`).join('')}</tr>`,
      )
      .join('');

    return `<div class="table-scroll"><table>
      <thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  };

  return (
    <div className="chat-wrapper">
      <div className="workspace">
        <div className="chat-window">
          <div className="chat-toolbar">
            <div>
              <p className="chat-title">RetailAsk</p>
              <p className="chat-subtitle">Retail analytics assistant</p>
            </div>
            <span className={`status-dot ${loading ? 'busy' : 'online'}`}>
              {loading ? 'Thinking' : 'Online'}
            </span>
          </div>

          <div className="chat-history" ref={historyRef}>
            {messages.length === 0 && (
              <div className="empty-state">
                <p className="empty-title">Ask the agent about your retail store</p>
                <p className="empty-hint">
                  Type any of these sample questions to test the agent:
                </p>
                <ul className="practice-list">
                  {practiceQuestions.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ul>
              </div>
            )}

            {messages.map((msg, index) => (
              <div
                key={`${msg.type}-${index}`}
                className={`message ${msg.type}`}
                dangerouslySetInnerHTML={{ __html: msg.text }}
              />
            ))}

            {loading && (
              <div className="message bot typing">
                <span />
                <span />
                <span />
              </div>
            )}
          </div>

          <div className="chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about sales, products, stock..."
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
            <button
              className="Send"
              onClick={handleSend}
              disabled={loading || !input.trim()}
              aria-label="Send message"
              type="button"
            >
              <SendIcon />
            </button>
            <div className="icon-group">
              <button
                className="icon-button"
                onClick={() => handleIconClick('sales')}
                disabled={loading}
                title="Sales data"
                type="button"
                aria-label="Show sales data"
              >
                <SalesIcon />
              </button>
              <button
                className="icon-button"
                onClick={() => handleIconClick('product')}
                disabled={loading}
                title="Products"
                type="button"
                aria-label="Show products"
              >
                <ProductsIcon />
              </button>
            </div>
          </div>
        </div>

        <aside className="pipeline-panel">
          <div className="pipeline-header">
            <p className="pipeline-title">AI Pipeline</p>
            <p className="pipeline-subtitle">
              Proof the answer came from the model + database
            </p>
          </div>

          <div className="pipeline-scroll">
          {pipelineMeta.model && (
            <div className="pipeline-model">
              Model: <code>{pipelineMeta.model}</code>
            </div>
          )}

          {pipeline.length === 0 ? (
            <div className="pipeline-empty">
              Ask a retail question to see:
              <ul>
                <li>AI turning your question into SQL</li>
                <li>SQL running on MySQL</li>
                <li>AI writing the final answer</li>
              </ul>
            </div>
          ) : (
            <ol className="pipeline-steps">
              {pipeline.map((step) => (
                <li
                  key={step.id}
                  className={`pipeline-step status-${step.status || 'done'}`}
                >
                  <div className="step-top">
                    <span className="step-badge">{step.id}</span>
                    <span className="step-title">{step.title}</span>
                    <span className={`step-status ${step.status || 'done'}`}>
                      {step.status || 'done'}
                    </span>
                  </div>
                  {step.model && (
                    <p className="step-model">via {step.model}</p>
                  )}
                  <pre className="step-detail">{step.detail}</pre>
                </li>
              ))}
            </ol>
          )}

          {pipelineMeta.sql && (
            <div className="pipeline-block">
              <p className="block-label">Generated SQL</p>
              <pre>{pipelineMeta.sql}</pre>
            </div>
          )}

          {pipelineMeta.rows && pipelineMeta.rows.length > 0 && (
            <div className="pipeline-block">
              <p className="block-label">
                DB preview ({pipelineMeta.rows.length} row
                {pipelineMeta.rows.length === 1 ? '' : 's'})
              </p>
              <pre>{JSON.stringify(pipelineMeta.rows.slice(0, 5), null, 2)}</pre>
            </div>
          )}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ChatWindow;

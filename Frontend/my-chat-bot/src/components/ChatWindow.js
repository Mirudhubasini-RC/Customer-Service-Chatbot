import React, { useEffect, useRef, useState } from 'react';

import '../styles/ChatWindow.css';
import {
  sendQuery,
  fetchSalesData,
  fetchQueriesData,
  fetchPracticeQuestions,
  submitFeedback,
} from '../components/apiService.js';
import FeedbackPanel from './FeedbackPanel.js';

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

const ThumbIcon = ({ down }) => (
  <svg
    viewBox="0 0 24 24"
    width="15"
    height="15"
    aria-hidden="true"
    style={down ? { transform: 'rotate(180deg)' } : undefined}
  >
    <path
      d="M7 11v9H4v-9h3zm2 9h8.2a2 2 0 0 0 2-1.6l1.3-6.4A2 2 0 0 0 18.5 9.6H14V5.5A2.5 2.5 0 0 0 11.5 3L9 11v9z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);

const MessageFeedback = ({ meta, feedback, onChange }) => {
  const [comment, setComment] = useState('');
  const [expected, setExpected] = useState('');
  const status = feedback.status;

  const send = async (rating, extra = {}) => {
    onChange({ status: 'saving', rating });
    try {
      await submitFeedback({
        question: meta.question,
        answer: meta.answer,
        route: meta.route,
        sql: meta.sql,
        rating,
        ...extra,
      });
      onChange({ status: 'saved', rating });
    } catch (error) {
      onChange({
        status: 'error',
        rating,
        error: (error && error.message) || 'Could not save feedback',
      });
    }
  };

  if (status === 'saved') {
    return (
      <div className="msg-feedback saved">
        {feedback.rating === 'down'
          ? 'Thanks. Your feedback was saved for review.'
          : 'Thanks for the feedback!'}
      </div>
    );
  }

  if (status === 'form' || (status === 'saving' && feedback.rating === 'down')) {
    return (
      <div className="msg-feedback form">
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="What was wrong with this answer?"
          rows={2}
          disabled={status === 'saving'}
        />
        <textarea
          value={expected}
          onChange={(e) => setExpected(e.target.value)}
          placeholder="What should the answer be? (optional)"
          rows={2}
          disabled={status === 'saving'}
        />
        <div className="msg-feedback-actions">
          <button
            type="button"
            className="fb-submit"
            onClick={() => send('down', { comment, expected_answer: expected })}
            disabled={status === 'saving'}
          >
            {status === 'saving' ? 'Saving…' : 'Submit feedback'}
          </button>
          <button
            type="button"
            className="fb-cancel"
            onClick={() => onChange({ status: 'idle' })}
            disabled={status === 'saving'}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="msg-feedback">
      <span>Was this helpful?</span>
      <button
        type="button"
        className="thumb"
        onClick={() => send('up')}
        disabled={status === 'saving'}
        aria-label="Like answer"
        title="Like"
      >
        <ThumbIcon />
      </button>
      <button
        type="button"
        className="thumb"
        onClick={() => onChange({ status: 'form', rating: 'down' })}
        disabled={status === 'saving'}
        aria-label="Dislike answer"
        title="Dislike"
      >
        <ThumbIcon down />
      </button>
      {status === 'error' && <span className="msg-feedback-error">{feedback.error}</span>}
    </div>
  );
};

const DEFAULT_PRACTICE_QUESTIONS = [
  'How much revenue did we make?',
  'Which products have the highest sales?',
  'Which products have quality issues?',
  'Which products have negative feedback and returns?',
  'Which products have high sales and quality issues?',
  'Which high-selling products also have negative feedback?',
  'For products with quality issues, what issue types are linked and which brands do they belong to?',
  'What is customer retention?',
];

const ROUTE_LABELS = {
  sql: 'SQL Agent',
  graph: 'Graph Agent',
  sql_and_graph: 'SQL + Graph',
  general: 'General',
};

const emptyPipelineMeta = () => ({
  model: '',
  route: '',
  sql: null,
  rows: [],
  graph: null,
});

/** Escape plain answers; light markdown (**bold**, newlines). Leave HTML tables intact. */
const formatBotHtml = (text) => {
  if (!text) return '';
  if (text.includes('<table') || text.includes('table-scroll')) {
    return text;
  }
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>');
};

const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [practiceQuestions, setPracticeQuestions] = useState(
    DEFAULT_PRACTICE_QUESTIONS,
  );
  const [pipeline, setPipeline] = useState([]);
  const [pipelineMeta, setPipelineMeta] = useState(emptyPipelineMeta());
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const historyRef = useRef(null);

  const updateMessageFeedback = (index, feedback) => {
    setMessages((prev) =>
      prev.map((msg, i) => (i === index ? { ...msg, feedback } : msg)),
    );
  };

  useEffect(() => {
    fetchPracticeQuestions()
      .then((questions) => {
        if (Array.isArray(questions) && questions.length > 0) {
          setPracticeQuestions(questions);
        }
      })
      .catch(() => {
        setPracticeQuestions(DEFAULT_PRACTICE_QUESTIONS);
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
      {
        id: 2,
        title: 'Supervisor route',
        status: 'running',
        detail: 'Choosing SQL / Graph / both / general…',
      },
      {
        id: 3,
        title: 'Specialized agents',
        status: 'pending',
        detail: 'Waiting for route…',
      },
      {
        id: 4,
        title: 'Final answer',
        status: 'pending',
        detail: 'Waiting…',
      },
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
    setPipelineMeta(emptyPipelineMeta());

    try {
      const data = await sendQuery(trimmed);
      if (data.error && !data.answer) {
        throw new Error(data.error);
      }
      const botMessage = formatBotHtml(data.answer || 'No response from agent');
      setMessages([
        ...updatedMessages,
        {
          text: botMessage,
          type: 'bot',
          meta: {
            question: trimmed,
            answer: data.answer || '',
            route: data.route || '',
            sql: data.sql || null,
          },
          feedback: { status: 'idle' },
        },
      ]);
      setPipeline(data.pipeline || []);
      setPipelineMeta({
        model: data.model || '',
        route: data.route || '',
        sql: data.sql || null,
        rows: data.rows || [],
        graph: data.graph || null,
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

  const handlePracticeClick = (question) => {
    askAgent(question);
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
          title: 'Direct DB fetch (bypass agents)',
          status: 'done',
          detail: `${(response || []).length} row(s) from MySQL`,
        },
      ]);
      setPipelineMeta({
        model: 'direct-api',
        route: 'direct',
        sql: type === 'sales' ? 'SELECT * FROM sales' : 'SELECT * FROM products',
        rows: (response || []).slice(0, 20),
        graph: null,
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

  const routeLabel = ROUTE_LABELS[pipelineMeta.route] || pipelineMeta.route;
  const graphIntent =
    pipelineMeta.graph &&
    pipelineMeta.graph.intent &&
    pipelineMeta.graph.intent.intent_type;

  return (
    <div className="chat-wrapper">
      <div className="workspace">
        <div className="chat-window">
          <div className="chat-toolbar">
            <div>
              <p className="chat-title">RetailAsk</p>
              <p className="chat-subtitle">
                Supervisor · SQL Agent · Graph-RAG Agent
              </p>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="feedback-open"
                onClick={() => setFeedbackOpen(true)}
              >
                Feedback &amp; Eval
              </button>
              <span className={`status-dot ${loading ? 'busy' : 'online'}`}>
                {loading ? 'Routing…' : 'Online'}
              </span>
            </div>
          </div>

          <div className="chat-history" ref={historyRef}>
            {messages.length === 0 && (
              <div className="empty-state">
                <p className="empty-title">
                  Ask RetailAsk — it routes to the right agent
                </p>
                <p className="empty-hint">
                  SQL for metrics · Graph for product–feedback–issue links · both
                  when needed. Try a sample:
                </p>
                <ul className="practice-list">
                  {practiceQuestions.map((question) => (
                    <li key={question}>
                      <button
                        type="button"
                        className="practice-chip"
                        onClick={() => handlePracticeClick(question)}
                        disabled={loading}
                      >
                        {question}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {messages.map((msg, index) =>
              msg.meta ? (
                <div key={`${msg.type}-${index}`} className="bot-turn">
                  <div
                    className={`message ${msg.type}`}
                    dangerouslySetInnerHTML={{ __html: msg.text }}
                  />
                  <MessageFeedback
                    meta={msg.meta}
                    feedback={msg.feedback || { status: 'idle' }}
                    onChange={(feedback) => updateMessageFeedback(index, feedback)}
                  />
                </div>
              ) : (
                <div
                  key={`${msg.type}-${index}`}
                  className={`message ${msg.type}`}
                  dangerouslySetInnerHTML={{ __html: msg.text }}
                />
              ),
            )}

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
              placeholder="Ask about sales, quality issues, returns, brands…"
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
                title="Sales table"
                type="button"
                aria-label="Sales table"
              >
                <SalesIcon />
              </button>
              <button
                className="icon-button"
                onClick={() => handleIconClick('product')}
                disabled={loading}
                title="Product table"
                type="button"
                aria-label="Product table"
              >
                <ProductsIcon />
              </button>
            </div>
          </div>
        </div>

        <aside className="pipeline-panel">
          <div className="pipeline-header">
            <p className="pipeline-title">Agent Pipeline</p>
            <p className="pipeline-subtitle">
              Supervisor decides the route; specialized agents query MySQL and/or
              Neo4j
            </p>
          </div>

          <div className="pipeline-scroll">
            {(pipelineMeta.model || pipelineMeta.route) && (
              <div className="pipeline-meta-row">
                {pipelineMeta.route && (
                  <span className={`route-pill route-${pipelineMeta.route}`}>
                    {routeLabel || pipelineMeta.route}
                  </span>
                )}
                {pipelineMeta.model && (
                  <div className="pipeline-model">
                    Model: <code>{pipelineMeta.model}</code>
                  </div>
                )}
              </div>
            )}

            {pipeline.length === 0 ? (
              <div className="pipeline-empty">
                Ask a question to see:
                <ul>
                  <li>Supervisor choosing sql / graph / both / general</li>
                  <li>Schema RAG + SQL Agent on MySQL</li>
                  <li>Graph retrieval + Graph-RAG on Neo4j</li>
                  <li>Synthesis when both sources are needed</li>
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
                  MySQL preview ({pipelineMeta.rows.length} row
                  {pipelineMeta.rows.length === 1 ? '' : 's'})
                </p>
                <pre>
                  {JSON.stringify(pipelineMeta.rows.slice(0, 5), null, 2)}
                </pre>
              </div>
            )}

            {pipelineMeta.graph && (
              <div className="pipeline-block">
                <p className="block-label">
                  Graph context
                  {graphIntent ? ` · ${graphIntent}` : ''}
                  {typeof pipelineMeta.graph.fact_count === 'number'
                    ? ` · ${pipelineMeta.graph.fact_count} fact(s)`
                    : ''}
                </p>
                <pre>
                  {JSON.stringify(
                    {
                      intent: pipelineMeta.graph.intent || null,
                      facts_preview: (
                        pipelineMeta.graph.facts_preview || []
                      ).slice(0, 6),
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
            )}
          </div>
        </aside>
      </div>
      <FeedbackPanel
        open={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        onAsk={(question) => {
          setFeedbackOpen(false);
          askAgent(question);
        }}
      />
    </div>
  );
};

export default ChatWindow;

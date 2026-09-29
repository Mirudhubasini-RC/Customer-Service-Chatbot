import React, { useCallback, useEffect, useState } from 'react';

import '../styles/FeedbackPanel.css';
import {
  fetchFeedback,
  reviewFeedback,
  fetchEvalDataset,
  fetchEvalResults,
  runRoutingEval,
} from './apiService.js';

const ROUTE_OPTIONS = ['sql', 'graph', 'sql_and_graph', 'general'];

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'down', label: 'Disliked' },
  { id: 'up', label: 'Liked' },
  { id: 'eval', label: 'In eval set' },
];

const formatDate = (value) => {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
};

const percent = (value) =>
  typeof value === 'number' ? `${Math.round(value * 100)}%` : '—';

const FeedbackCard = ({ item, onAsk, onSaved }) => {
  const [showAnswer, setShowAnswer] = useState(false);
  const [expectedRoute, setExpectedRoute] = useState(item.expected_route || '');
  const [keywords, setKeywords] = useState((item.expected_keywords || []).join(', '));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async (inEvalSet) => {
    setSaving(true);
    setError('');
    try {
      const updated = await reviewFeedback(item.feedback_id, {
        expected_route: expectedRoute,
        expected_keywords: keywords,
        in_eval_set: inEvalSet,
      });
      onSaved(updated);
    } catch (e) {
      setError(e.message || 'Could not save review');
    } finally {
      setSaving(false);
    }
  };

  return (
    <li className={`fb-card rating-${item.rating}`}>
      <div className="fb-card-top">
        <span className={`fb-rating ${item.rating}`}>
          {item.rating === 'down' ? 'Disliked' : 'Liked'}
        </span>
        {item.route && <span className="fb-route">{item.route}</span>}
        {item.in_eval_set && <span className="fb-eval-badge">In eval set</span>}
        <span className="fb-date">{formatDate(item.created_at)}</span>
      </div>

      <p className="fb-question">{item.question}</p>

      {item.comment && (
        <p className="fb-comment">
          <strong>What was wrong:</strong> {item.comment}
        </p>
      )}
      {item.expected_answer && (
        <p className="fb-comment">
          <strong>Expected answer:</strong> {item.expected_answer}
        </p>
      )}

      <div className="fb-actions">
        <button type="button" className="fb-btn" onClick={() => setShowAnswer((v) => !v)}>
          {showAnswer ? 'Hide answer' : 'View answer'}
        </button>
        <button type="button" className="fb-btn" onClick={() => onAsk(item.question)}>
          Ask again
        </button>
      </div>

      {showAnswer && (
        <div className="fb-answer">
          <p>{item.answer || '(no answer stored)'}</p>
          {item.generated_sql && <pre>{item.generated_sql}</pre>}
        </div>
      )}

      {item.rating === 'down' && (
        <div className="fb-review">
          <p className="fb-review-title">Review → add to eval set</p>
          <div className="fb-review-row">
            <label>
              Correct route
              <select
                value={expectedRoute}
                onChange={(e) => setExpectedRoute(e.target.value)}
                disabled={saving}
              >
                <option value="">(any)</option>
                {ROUTE_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <label className="fb-grow">
              Answer must mention (comma separated)
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="e.g. Laptop, Mouse"
                disabled={saving}
              />
            </label>
          </div>
          <div className="fb-actions">
            {item.in_eval_set ? (
              <>
                <button type="button" className="fb-btn primary" onClick={() => save(true)} disabled={saving}>
                  Update eval case
                </button>
                <button type="button" className="fb-btn" onClick={() => save(false)} disabled={saving}>
                  Remove from eval set
                </button>
              </>
            ) : (
              <button type="button" className="fb-btn primary" onClick={() => save(true)} disabled={saving}>
                Add to eval set
              </button>
            )}
          </div>
          {error && <p className="fb-error">{error}</p>}
        </div>
      )}
    </li>
  );
};

const FeedbackTab = ({ onAsk }) => {
  const [filter, setFilter] = useState('all');
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({ up: 0, down: 0, in_eval_set: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchFeedback(filter);
      setItems(data.items || []);
      setCounts(data.counts || {});
    } catch (e) {
      setError(e.message || 'Could not load feedback');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaved = (updated) => {
    setItems((prev) =>
      prev.map((it) => (it.feedback_id === updated.feedback_id ? updated : it)),
    );
    load();
  };

  const countFor = (id) => {
    if (id === 'all') return (counts.up || 0) + (counts.down || 0);
    if (id === 'eval') return counts.in_eval_set || 0;
    return counts[id] || 0;
  };

  return (
    <div className="fb-tab">
      <div className="fb-toolbar">
        <div className="fb-filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`fb-filter ${filter === f.id ? 'active' : ''}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label} <span>{countFor(f.id)}</span>
            </button>
          ))}
        </div>
        <button type="button" className="fb-btn" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && <p className="fb-error">{error}</p>}
      {!error && !loading && items.length === 0 && (
        <p className="fb-empty">
          No feedback yet. Use the thumbs up / down buttons under any answer in the chat.
        </p>
      )}

      <ul className="fb-list">
        {items.map((item) => (
          <FeedbackCard key={item.feedback_id} item={item} onAsk={onAsk} onSaved={handleSaved} />
        ))}
      </ul>
    </div>
  );
};

const EvalTab = ({ onAsk }) => {
  const [cases, setCases] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [dataset, results] = await Promise.all([fetchEvalDataset(), fetchEvalResults()]);
      setCases(dataset.cases || []);
      setReport(results.available ? results : null);
    } catch (e) {
      setError(e.message || 'Could not load eval data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runEval = async () => {
    setRunning(true);
    setError('');
    try {
      const results = await runRoutingEval();
      setReport(results);
    } catch (e) {
      setError(e.message || 'Eval run failed');
    } finally {
      setRunning(false);
    }
  };

  const resultById = {};
  ((report && report.cases) || []).forEach((c) => {
    resultById[c.id] = c;
  });
  const summary = report && report.summary;

  return (
    <div className="fb-tab">
      <div className="eval-summary">
        <div className="eval-stat">
          <span>Cases</span>
          <strong>{cases.length}</strong>
        </div>
        <div className="eval-stat">
          <span>Pass rate</span>
          <strong>{summary ? percent(summary.pass_rate) : '—'}</strong>
        </div>
        <div className="eval-stat">
          <span>Route accuracy</span>
          <strong>{summary ? percent(summary.route_accuracy) : '—'}</strong>
        </div>
        <div className="eval-stat">
          <span>Answer accuracy</span>
          <strong>{summary ? percent(summary.answer_accuracy) : '—'}</strong>
        </div>
      </div>

      <div className="fb-toolbar">
        <p className="eval-meta">
          {report
            ? `Last run: ${formatDate(report.run_at)} · ${report.mode === 'full' ? 'full pipeline' : 'routing only'} · ${report.model}`
            : 'No eval run yet.'}
        </p>
        <div className="fb-actions">
          <button type="button" className="fb-btn" onClick={load} disabled={loading || running}>
            Refresh
          </button>
          <button type="button" className="fb-btn primary" onClick={runEval} disabled={running}>
            {running ? 'Running… (~30s)' : 'Run routing eval'}
          </button>
        </div>
      </div>
      <p className="eval-hint">
        Full answer-level eval (route + answer + safety):{' '}
        <code>cd Backend && python -m evaluation.run_eval --include-feedback</code>
      </p>

      {error && <p className="fb-error">{error}</p>}

      <div className="eval-table-wrap">
        <table className="eval-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Question</th>
              <th>Expected route</th>
              <th>Last result</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => {
              const r = resultById[c.id];
              const open = openId === c.id;
              return (
                <React.Fragment key={c.id}>
                  <tr className={c.source === 'feedback' ? 'from-feedback' : ''}>
                    <td className="eval-id">{c.id}</td>
                    <td>{c.question}</td>
                    <td>{(c.expected_routes || []).join(' / ') || 'any'}</td>
                    <td>
                      {r ? (
                        <span className={`eval-result ${r.passed ? 'pass' : 'fail'}`}>
                          {r.passed ? 'PASS' : 'FAIL'} · {r.actual_route}
                        </span>
                      ) : (
                        <span className="eval-result none">not run</span>
                      )}
                    </td>
                    <td className="eval-row-actions">
                      <button type="button" className="fb-btn small" onClick={() => setOpenId(open ? null : c.id)}>
                        {open ? 'Hide' : 'Details'}
                      </button>
                      <button type="button" className="fb-btn small" onClick={() => onAsk(c.question)}>
                        Ask
                      </button>
                    </td>
                  </tr>
                  {open && (
                    <tr className="eval-details">
                      <td colSpan={5}>
                        <p><strong>Correct answer:</strong> {c.notes || '—'}</p>
                        {(c.answer_must_include || []).length > 0 && (
                          <p><strong>Answer must mention:</strong> {c.answer_must_include.join(', ')}</p>
                        )}
                        {c.expect_refusal && <p><strong>Safety:</strong> no SQL may be executed.</p>}
                        {r && r.route_reason && <p><strong>Supervisor reason:</strong> {r.route_reason}</p>}
                        {r && r.answer && <p><strong>Last answer:</strong> {r.answer}</p>}
                        {r && r.missing_keywords && r.missing_keywords.length > 0 && (
                          <p><strong>Missing:</strong> {r.missing_keywords.join(', ')}</p>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const FeedbackPanel = ({ open, onClose, onAsk }) => {
  const [tab, setTab] = useState('feedback');

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fb-overlay" onClick={onClose} role="presentation">
      <div
        className="fb-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Feedback and evaluation"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="fb-header">
          <div>
            <p className="fb-title">Feedback &amp; Eval</p>
            <p className="fb-subtitle">
              Users rate answers → disliked questions are reviewed → added to the eval set → re-tested
            </p>
          </div>
          <button type="button" className="fb-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="fb-tabs">
          <button
            type="button"
            className={tab === 'feedback' ? 'active' : ''}
            onClick={() => setTab('feedback')}
          >
            User feedback
          </button>
          <button
            type="button"
            className={tab === 'eval' ? 'active' : ''}
            onClick={() => setTab('eval')}
          >
            Eval dataset
          </button>
        </div>
        <div className="fb-body">
          {tab === 'feedback' ? <FeedbackTab onAsk={onAsk} /> : <EvalTab onAsk={onAsk} />}
        </div>
      </div>
    </div>
  );
};

export default FeedbackPanel;

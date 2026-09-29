"""
User feedback on RetailAsk answers (thumbs up / down), stored in MySQL.

Disliked answers can be reviewed and promoted into the evaluation set
(`in_eval_set = 1`), which closes the continual-feedback loop:
user dislikes -> reviewer labels expected route/keywords -> eval runner re-tests it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable

logger = logging.getLogger('retail-agent')

ConnectionFactory = Callable[[], Any]

VALID_RATINGS = frozenset({'up', 'down'})
VALID_ROUTES = frozenset({'sql', 'graph', 'general', 'sql_and_graph'})
MAX_TEXT = 10000

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `answer_feedback` (
  `feedback_id` int NOT NULL AUTO_INCREMENT,
  `question` text NOT NULL,
  `answer` text,
  `rating` enum('up','down') NOT NULL,
  `comment` text,
  `expected_answer` text,
  `route` varchar(32) DEFAULT NULL,
  `generated_sql` text,
  `expected_route` varchar(32) DEFAULT NULL,
  `expected_keywords` varchar(500) DEFAULT NULL,
  `in_eval_set` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`feedback_id`),
  KEY `answer_feedback_rating` (`rating`),
  KEY `answer_feedback_in_eval_set` (`in_eval_set`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""".strip()

SELECT_COLUMNS = (
    'feedback_id, question, answer, rating, comment, expected_answer, route, '
    'generated_sql, expected_route, expected_keywords, in_eval_set, created_at, reviewed_at'
)

_table_ready = False


def _default_connection_factory() -> Any:
    from app import get_db_connection

    return get_db_connection()


def _clip(value: Any, limit: int = MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
        else:
            out[key] = value
    out['in_eval_set'] = bool(out.get('in_eval_set'))
    keywords = out.get('expected_keywords') or ''
    out['expected_keywords'] = [k.strip() for k in keywords.split(',') if k.strip()]
    return out


def ensure_table(connection_factory: ConnectionFactory | None = None) -> None:
    global _table_ready
    if _table_ready:
        return
    conn = (connection_factory or _default_connection_factory)()
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        _table_ready = True
    finally:
        cursor.close()
        conn.close()


def add_feedback(
    payload: dict[str, Any],
    *,
    connection_factory: ConnectionFactory | None = None,
) -> int:
    rating = str(payload.get('rating') or '').strip().lower()
    if rating not in VALID_RATINGS:
        raise ValueError("rating must be 'up' or 'down'")
    question = _clip(payload.get('question'))
    if not question:
        raise ValueError('question is required')

    route = _clip(payload.get('route'), 32)
    params = (
        question,
        _clip(payload.get('answer')),
        rating,
        _clip(payload.get('comment')),
        _clip(payload.get('expected_answer')),
        route,
        _clip(payload.get('sql')),
    )

    ensure_table(connection_factory)
    conn = (connection_factory or _default_connection_factory)()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO answer_feedback '
            '(question, answer, rating, comment, expected_answer, route, generated_sql) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
            params,
        )
        conn.commit()
        feedback_id = cursor.lastrowid
    finally:
        cursor.close()
        conn.close()
    logger.info('Feedback saved | id=%s | rating=%s | route=%s', feedback_id, rating, route)
    return feedback_id


def list_feedback(
    rating: str | None = None,
    *,
    limit: int = 200,
    connection_factory: ConnectionFactory | None = None,
) -> dict[str, Any]:
    rating = (rating or '').strip().lower()
    where = ''
    params: tuple[Any, ...] = ()
    if rating in VALID_RATINGS:
        where = 'WHERE rating = %s'
        params = (rating,)
    elif rating == 'eval':
        where = 'WHERE in_eval_set = 1'

    ensure_table(connection_factory)
    conn = (connection_factory or _default_connection_factory)()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            f'SELECT {SELECT_COLUMNS} FROM answer_feedback {where} '
            'ORDER BY created_at DESC, feedback_id DESC LIMIT %s',
            params + (int(limit),),
        )
        items = [_serialize_row(r) for r in cursor.fetchall() or []]
        cursor.execute(
            'SELECT rating, COUNT(*) AS n FROM answer_feedback GROUP BY rating'
        )
        counts = {'up': 0, 'down': 0}
        for row in cursor.fetchall() or []:
            counts[row['rating']] = int(row['n'])
        cursor.execute('SELECT COUNT(*) AS n FROM answer_feedback WHERE in_eval_set = 1')
        in_eval = cursor.fetchone() or {}
        counts['in_eval_set'] = int(in_eval.get('n') or 0)
    finally:
        cursor.close()
        conn.close()
    return {'items': items, 'counts': counts}


def review_feedback(
    feedback_id: int,
    payload: dict[str, Any],
    *,
    connection_factory: ConnectionFactory | None = None,
) -> dict[str, Any] | None:
    """Label a feedback item (expected route / keywords) and add or remove it from the eval set."""
    sets: list[str] = []
    params: list[Any] = []

    if 'expected_route' in payload:
        route = (payload.get('expected_route') or '').strip().lower() or None
        if route is not None and route not in VALID_ROUTES:
            raise ValueError(f'expected_route must be one of {sorted(VALID_ROUTES)}')
        sets.append('expected_route = %s')
        params.append(route)

    if 'expected_keywords' in payload:
        raw = payload.get('expected_keywords')
        if isinstance(raw, list):
            raw = ','.join(str(k) for k in raw)
        keywords = ','.join(k.strip() for k in str(raw or '').split(',') if k.strip())
        sets.append('expected_keywords = %s')
        params.append(keywords[:500] or None)

    if 'in_eval_set' in payload:
        sets.append('in_eval_set = %s')
        params.append(1 if payload.get('in_eval_set') else 0)

    if not sets:
        raise ValueError('nothing to update')

    sets.append('reviewed_at = CURRENT_TIMESTAMP')

    ensure_table(connection_factory)
    conn = (connection_factory or _default_connection_factory)()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            f"UPDATE answer_feedback SET {', '.join(sets)} WHERE feedback_id = %s",
            tuple(params) + (int(feedback_id),),
        )
        conn.commit()
        cursor.execute(
            f'SELECT {SELECT_COLUMNS} FROM answer_feedback WHERE feedback_id = %s',
            (int(feedback_id),),
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    return _serialize_row(row) if row else None


def feedback_to_eval_case(item: dict[str, Any]) -> dict[str, Any]:
    expected_route = item.get('expected_route')
    return {
        'id': f"fb-{item['feedback_id']}",
        'question': item['question'],
        'category': 'user_feedback',
        'source': 'feedback',
        'expected_routes': [expected_route] if expected_route else [],
        'expect_success': True,
        'answer_must_include': list(item.get('expected_keywords') or []),
        'notes': item.get('expected_answer') or item.get('comment') or 'Promoted from user feedback',
    }


def feedback_eval_cases(
    *,
    connection_factory: ConnectionFactory | None = None,
) -> list[dict[str, Any]]:
    items = list_feedback('eval', limit=1000, connection_factory=connection_factory)['items']
    return [feedback_to_eval_case(item) for item in items]

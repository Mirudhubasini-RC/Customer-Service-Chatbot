"""Unit tests for the feedback store and /feedback + /eval endpoints. MySQL is mocked."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import feedback_store
from app import app


def _fake_connection(fetchall=None, fetchone=None, lastrowid=7):
    cursor = MagicMock()
    cursor.lastrowid = lastrowid
    cursor.fetchall.side_effect = list(fetchall or [])
    cursor.fetchone.side_effect = list(fetchone or [])
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        feedback_store._table_ready = True

    def test_add_feedback_inserts_row(self):
        conn, cursor = _fake_connection(lastrowid=42)
        feedback_id = feedback_store.add_feedback(
            {
                'question': ' Which products have quality issues? ',
                'answer': 'Laptop',
                'rating': 'DOWN',
                'comment': 'Missing Mouse',
                'route': 'graph',
            },
            connection_factory=lambda: conn,
        )
        self.assertEqual(feedback_id, 42)
        sql, params = cursor.execute.call_args[0]
        self.assertIn('INSERT INTO answer_feedback', sql)
        self.assertEqual(params[0], 'Which products have quality issues?')
        self.assertEqual(params[2], 'down')
        self.assertEqual(params[3], 'Missing Mouse')
        conn.commit.assert_called_once()

    def test_add_feedback_validates_input(self):
        with self.assertRaises(ValueError):
            feedback_store.add_feedback({'question': 'q', 'rating': 'meh'}, connection_factory=MagicMock())
        with self.assertRaises(ValueError):
            feedback_store.add_feedback({'question': '  ', 'rating': 'up'}, connection_factory=MagicMock())

    def test_list_feedback_filters_and_counts(self):
        row = {
            'feedback_id': 1,
            'question': 'q',
            'rating': 'down',
            'in_eval_set': 1,
            'expected_keywords': 'Laptop, Mouse',
        }
        conn, cursor = _fake_connection(
            fetchall=[[row], [{'rating': 'down', 'n': 3}, {'rating': 'up', 'n': 5}]],
            fetchone=[{'n': 1}],
        )
        data = feedback_store.list_feedback('down', connection_factory=lambda: conn)
        first_sql, first_params = cursor.execute.call_args_list[0][0]
        self.assertIn('WHERE rating = %s', first_sql)
        self.assertEqual(first_params, ('down', 200))
        self.assertEqual(data['counts'], {'up': 5, 'down': 3, 'in_eval_set': 1})
        self.assertEqual(data['items'][0]['expected_keywords'], ['Laptop', 'Mouse'])
        self.assertIs(data['items'][0]['in_eval_set'], True)

    def test_review_rejects_bad_route(self):
        with self.assertRaises(ValueError):
            feedback_store.review_feedback(1, {'expected_route': 'magic'}, connection_factory=MagicMock())

    def test_review_updates_and_returns_row(self):
        conn, cursor = _fake_connection(
            fetchone=[{'feedback_id': 3, 'question': 'q', 'in_eval_set': 1, 'expected_keywords': 'Mouse'}]
        )
        item = feedback_store.review_feedback(
            3,
            {'expected_route': 'graph', 'expected_keywords': 'Mouse', 'in_eval_set': True},
            connection_factory=lambda: conn,
        )
        update_sql, params = cursor.execute.call_args_list[0][0]
        self.assertIn('expected_route = %s', update_sql)
        self.assertIn('in_eval_set = %s', update_sql)
        self.assertEqual(params, ('graph', 'Mouse', 1, 3))
        self.assertEqual(item['expected_keywords'], ['Mouse'])

    def test_feedback_to_eval_case(self):
        case = feedback_store.feedback_to_eval_case(
            {
                'feedback_id': 9,
                'question': 'Which brands have defects?',
                'expected_route': 'graph',
                'expected_keywords': ['TechNova'],
                'comment': 'wrong brand',
            }
        )
        self.assertEqual(case['id'], 'fb-9')
        self.assertEqual(case['expected_routes'], ['graph'])
        self.assertEqual(case['answer_must_include'], ['TechNova'])
        self.assertEqual(case['source'], 'feedback')


class FeedbackEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('feedback_store.add_feedback', return_value=11)
    def test_post_feedback(self, add):
        resp = self.client.post('/feedback', json={'question': 'q', 'rating': 'down'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json(), {'id': 11})

    @patch('feedback_store.add_feedback', side_effect=ValueError('bad rating'))
    def test_post_feedback_bad_input(self, add):
        resp = self.client.post('/feedback', json={'question': 'q', 'rating': 'x'})
        self.assertEqual(resp.status_code, 400)

    @patch('feedback_store.list_feedback', return_value={'items': [], 'counts': {'up': 0, 'down': 0}})
    def test_get_feedback(self, list_fn):
        resp = self.client.get('/feedback?rating=down')
        self.assertEqual(resp.status_code, 200)
        list_fn.assert_called_once_with('down')

    @patch('feedback_store.review_feedback', return_value=None)
    def test_patch_missing_feedback(self, review):
        resp = self.client.patch('/feedback/99', json={'in_eval_set': True})
        self.assertEqual(resp.status_code, 404)

    @patch('feedback_store.feedback_eval_cases', side_effect=RuntimeError('db down'))
    def test_eval_dataset_survives_db_outage(self, cases_fn):
        resp = self.client.get('/eval/dataset')
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(data['cases']), 20)
        self.assertEqual(data['feedback_error'], 'db down')


if __name__ == '__main__':
    unittest.main()

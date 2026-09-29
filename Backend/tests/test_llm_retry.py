"""call_llm retries on HTTP 429 (LLM provider rate limit). Network is mocked."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import app


def _response(status, content='ok', headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = {'choices': [{'message': {'content': content}}]}
    if status >= 400:
        resp.raise_for_status.side_effect = app.requests.exceptions.HTTPError(str(status))
    return resp


ENDPOINT = {'provider': 'groq', 'url': 'http://llm', 'model': 'm', 'headers': {}}


@patch('app._llm_endpoint', return_value=ENDPOINT)
@patch('app.time.sleep')
class CallLlmRetryTests(unittest.TestCase):
    def test_retries_then_succeeds(self, sleep, _endpoint):
        with patch('app.requests.post', side_effect=[_response(429, headers={'retry-after': '2'}), _response(200, 'hi')]) as post:
            self.assertEqual(app.call_llm([{'role': 'user', 'content': 'x'}]), 'hi')
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(2.0)

    def test_gives_up_after_max_retries(self, sleep, _endpoint):
        responses = [_response(429) for _ in range(app.LLM_RATE_LIMIT_RETRIES + 1)]
        with patch('app.requests.post', side_effect=responses) as post:
            with self.assertRaises(app.requests.exceptions.HTTPError):
                app.call_llm([{'role': 'user', 'content': 'x'}])
        self.assertEqual(post.call_count, app.LLM_RATE_LIMIT_RETRIES + 1)

    def test_no_retry_on_other_errors(self, sleep, _endpoint):
        with patch('app.requests.post', return_value=_response(401)) as post:
            with self.assertRaises(app.requests.exceptions.HTTPError):
                app.call_llm([{'role': 'user', 'content': 'x'}])
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()

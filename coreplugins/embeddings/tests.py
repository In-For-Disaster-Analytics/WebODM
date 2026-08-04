"""
Tests for coreplugins/embeddings/label_studio_client.py's access-token
exchange/cache/retry logic.

Decision 32 correction (see that module's own top-of-file comment): a real
live run hit a 401 "Authentication credentials were not provided" because
the code was sending the raw Personal Access Token directly as a Bearer
header. A Label Studio PAT is a JWT REFRESH token, not a usable access
token on its own -- it must be exchanged via POST /api/token/refresh first
(https://labelstud.io/guide/access_tokens). These tests cover that
exchange, the module-level cache, and _request()'s retry-once-on-401.

Plain unittest.TestCase, not django.test.TestCase -- nothing here touches
the DB or Django's request/response cycle, only this module's own
in-memory token cache and `requests` calls (mocked; no real HTTP). Run via
`./webodm.sh test backend coreplugins.embeddings.tests` (see repo
CLAUDE.md's "Run specific test" convention).
"""

import unittest
from unittest import mock

from coreplugins.embeddings import label_studio_client as lsc


class LabelStudioAccessTokenTests(unittest.TestCase):

    def setUp(self):
        lsc._invalidate_access_token()
        self._settings = mock.Mock(
            WO_LABEL_STUDIO_URL='https://labelstudio.example.test',
            WO_LABEL_STUDIO_API_TOKEN='a-real-pat',
        )
        patcher = mock.patch.object(lsc, 'settings', self._settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lsc._invalidate_access_token)

    def test_exchanges_pat_for_access_token(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post:
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'short-lived-1'})
            token = lsc._get_access_token()
        self.assertEqual(token, 'short-lived-1')
        mocked_post.assert_called_once_with(
            'https://labelstudio.example.test/api/token/refresh',
            json={'refresh': 'a-real-pat'},
            timeout=lsc.DEFAULT_REQUEST_TIMEOUT,
        )

    def test_caches_access_token_across_calls(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post:
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'cached-1'})
            first = lsc._get_access_token()
            second = lsc._get_access_token()
        self.assertEqual(first, second)
        mocked_post.assert_called_once()

    def test_refreshes_again_after_invalidation(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post:
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'first'})
            lsc._get_access_token()
            lsc._invalidate_access_token()
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'second'})
            second = lsc._get_access_token()
        self.assertEqual(second, 'second')
        self.assertEqual(mocked_post.call_count, 2)

    def test_refresh_failure_raises_label_studio_api_error(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post:
            mocked_post.return_value = mock.Mock(ok=False, status_code=401, text='denied')
            with self.assertRaises(lsc.LabelStudioAPIError):
                lsc._get_access_token()

    def test_refresh_failure_message_does_not_echo_response_body(self):
        # Security fix: this endpoint's request body IS the PAT itself, so
        # the raised exception's message (which api_views.py returns to the
        # browser verbatim via Response({'error': str(e)})) must never
        # contain Label Studio's raw response text, unlike every other
        # LabelStudioAPIError in this module. The body is still attached to
        # .response_body for server-side logging/debugging.
        with mock.patch.object(lsc.requests, 'post') as mocked_post:
            mocked_post.return_value = mock.Mock(
                ok=False, status_code=401,
                text='{"detail": "token_not_valid", "refresh": "a-real-pat"}',
            )
            with self.assertRaises(lsc.LabelStudioAPIError) as ctx:
                lsc._get_access_token()
        self.assertNotIn('a-real-pat', str(ctx.exception))
        self.assertIn('a-real-pat', ctx.exception.response_body)

    def test_missing_pat_raises_config_error(self):
        self._settings.WO_LABEL_STUDIO_API_TOKEN = ''
        with self.assertRaises(lsc.LabelStudioConfigError):
            lsc._get_access_token()


class LabelStudioRequestRetryTests(unittest.TestCase):
    """
    _request() must send `Authorization: Bearer <access token>` -- never
    the raw PAT, which is exactly the bug this fixes -- and retry exactly
    once on a 401 by forcing a fresh access-token refresh, since Label
    Studio's own docs don't state an exact access-token TTL.
    """

    def setUp(self):
        lsc._invalidate_access_token()
        patcher = mock.patch.object(lsc, 'settings', mock.Mock(
            WO_LABEL_STUDIO_URL='https://labelstudio.example.test',
            WO_LABEL_STUDIO_API_TOKEN='a-real-pat',
        ))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lsc._invalidate_access_token)

    def test_sends_bearer_access_token_not_pat(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post, \
                mock.patch.object(lsc.requests, 'request') as mocked_request:
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'the-access-token'})
            mocked_request.return_value = mock.Mock(ok=True, status_code=200, content=b'{}', json=lambda: {})
            lsc._request('GET', '/api/projects/')
        headers = mocked_request.call_args.kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer the-access-token')

    def test_retries_once_on_401_then_succeeds(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post, \
                mock.patch.object(lsc.requests, 'request') as mocked_request:
            mocked_post.side_effect = [
                mock.Mock(ok=True, json=lambda: {'access': 'stale'}),
                mock.Mock(ok=True, json=lambda: {'access': 'fresh'}),
            ]
            mocked_request.side_effect = [
                mock.Mock(ok=False, status_code=401, content=b'', text='expired'),
                mock.Mock(ok=True, status_code=200, content=b'{}', json=lambda: {}),
            ]
            result = lsc._request('GET', '/api/projects/')
        self.assertEqual(result, {})
        self.assertEqual(mocked_request.call_count, 2)
        second_call_headers = mocked_request.call_args_list[1].kwargs['headers']
        self.assertEqual(second_call_headers['Authorization'], 'Bearer fresh')

    def test_401_twice_raises_label_studio_api_error(self):
        with mock.patch.object(lsc.requests, 'post') as mocked_post, \
                mock.patch.object(lsc.requests, 'request') as mocked_request:
            mocked_post.return_value = mock.Mock(ok=True, json=lambda: {'access': 'token'})
            mocked_request.return_value = mock.Mock(ok=False, status_code=401, content=b'', text='still denied')
            with self.assertRaises(lsc.LabelStudioAPIError):
                lsc._request('GET', '/api/projects/')
        self.assertEqual(mocked_request.call_count, 2)


if __name__ == '__main__':
    unittest.main()

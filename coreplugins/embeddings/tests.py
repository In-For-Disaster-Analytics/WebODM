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
from datetime import datetime, timedelta, timezone
from unittest import mock

from coreplugins.embeddings import label_studio_client as lsc
from coreplugins.embeddings import embeddings_client
from coreplugins.embeddings.api_views import _embed_status_value, _label_studio_title


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


class LabelStudioTitleTests(unittest.TestCase):
    """
    bug-005: Label Studio's title field rejects anything over 50 chars, and
    task names are user-entered with no length cap of their own -- a 400
    from create_project() surfaced to the browser as a confusing 502.
    """

    def test_title_within_limit_is_unchanged(self):
        title = _label_studio_title('short task', '— 2024-01-01T00:00:00Z')
        self.assertEqual(title, 'short task — 2024-01-01T00:00:00Z')
        self.assertLessEqual(len(title), 50)

    def test_long_task_name_is_truncated_to_fit(self):
        long_name = 'a' * 200
        title = _label_studio_title(long_name, '— 2024-01-01T00:00:00Z')
        self.assertLessEqual(len(title), 50)
        self.assertTrue(title.endswith('— 2024-01-01T00:00:00Z'))

    def test_missing_task_name_falls_back_to_unnamed(self):
        title = _label_studio_title(None, '— suffix')
        self.assertEqual(title, 'unnamed — suffix')

    def test_result_never_exceeds_max_len_regardless_of_suffix(self):
        title = _label_studio_title('x' * 10, 'y' * 80)
        self.assertLessEqual(len(title), 50)


class EmbedStatusValueTests(unittest.TestCase):
    """
    bug-005: a `visits` row existing isn't proof the ls6 Tapis Job behind it
    is still alive -- these cover the 'running' vs 'timed_out' cutoff.
    """

    def test_recent_activity_is_running(self):
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        last_activity = now - timedelta(minutes=10)
        self.assertEqual(_embed_status_value(last_activity, 75, now=now), 'running')

    def test_activity_older_than_timeout_is_timed_out(self):
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        last_activity = now - timedelta(minutes=76)
        self.assertEqual(_embed_status_value(last_activity, 75, now=now), 'timed_out')

    def test_activity_exactly_at_timeout_boundary_is_running(self):
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        last_activity = now - timedelta(minutes=75)
        self.assertEqual(_embed_status_value(last_activity, 75, now=now), 'running')

    def test_no_activity_at_all_is_timed_out(self):
        now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(_embed_status_value(None, 75, now=now), 'timed_out')


class EmbedJobStatusTests(unittest.TestCase):
    """
    bug-005 follow-up: status is now primarily determined by polling the
    REAL Tapis Job (t.jobs.getJobStatus), not just an idle-time guess. These
    cover the terminal-status set and get_embed_job_uuid/get_embed_job_status.
    """

    def test_terminal_statuses_are_no_longer_running(self):
        self.assertEqual(
            embeddings_client.EMBED_JOB_TERMINAL_STATUSES,
            frozenset({'FINISHED', 'CANCELLED', 'FAILED'}),
        )

    def test_in_progress_statuses_are_not_terminal(self):
        in_progress = {
            'PENDING', 'PROCESSING_INPUTS', 'STAGING_INPUTS', 'STAGING_JOB',
            'SUBMITTING_JOB', 'QUEUED', 'RUNNING', 'ARCHIVING', 'BLOCKED', 'PAUSED',
        }
        self.assertFalse(in_progress & embeddings_client.EMBED_JOB_TERMINAL_STATUSES)

    def test_get_embed_job_uuid_returns_none_when_never_recorded(self):
        with mock.patch('app.plugins.data_store.GlobalDataStore') as MockStore:
            MockStore.return_value.get_string.return_value = ''
            result = embeddings_client.get_embed_job_uuid('some-visit-id')
        self.assertIsNone(result)

    def test_get_embed_job_uuid_returns_stored_value(self):
        with mock.patch('app.plugins.data_store.GlobalDataStore') as MockStore:
            MockStore.return_value.get_string.return_value = 'job-uuid-123'
            result = embeddings_client.get_embed_job_uuid('some-visit-id')
        self.assertEqual(result, 'job-uuid-123')

    def test_get_embed_job_status_raises_when_no_active_tapis_client(self):
        with mock.patch('app.models.oauth2.TapisOAuth2Client') as MockClient:
            MockClient.objects.filter.return_value.first.return_value = None
            with self.assertRaises(embeddings_client.TapisJobStatusError):
                embeddings_client.get_embed_job_status('job-uuid-123', mock.Mock())

    def test_get_embed_job_status_returns_real_tapis_status(self):
        fake_user = mock.Mock(username='alice')
        fake_token_obj = mock.Mock()
        fake_token_obj.get_or_refresh_access_token.return_value = 'a-jwt'

        with mock.patch('app.models.oauth2.TapisOAuth2Client') as MockClient, \
                mock.patch('app.models.oauth2.TapisOAuth2Token') as MockToken, \
                mock.patch('tapipy.tapis.Tapis') as MockTapis:
            MockClient.objects.filter.return_value.first.return_value = mock.Mock()
            MockToken.objects.get.return_value = fake_token_obj
            MockTapis.return_value.jobs.getJobStatus.return_value = mock.Mock(status='RUNNING')

            result = embeddings_client.get_embed_job_status('job-uuid-123', fake_user)
        self.assertEqual(result, 'RUNNING')

    def test_get_embed_job_status_wraps_tapis_failure(self):
        fake_user = mock.Mock(username='alice')
        fake_token_obj = mock.Mock()
        fake_token_obj.get_or_refresh_access_token.return_value = 'a-jwt'

        with mock.patch('app.models.oauth2.TapisOAuth2Client') as MockClient, \
                mock.patch('app.models.oauth2.TapisOAuth2Token') as MockToken, \
                mock.patch('tapipy.tapis.Tapis') as MockTapis:
            MockClient.objects.filter.return_value.first.return_value = mock.Mock()
            MockToken.objects.get.return_value = fake_token_obj
            MockTapis.return_value.jobs.getJobStatus.side_effect = RuntimeError('network error')

            with self.assertRaises(embeddings_client.TapisJobStatusError):
                embeddings_client.get_embed_job_status('job-uuid-123', fake_user)


if __name__ == '__main__':
    unittest.main()

import base64
import json
import time
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
from app.services import tapis_credentials as svc
from .classes import BootTestCase

LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'tapis-credentials-tests',
    }
}
TAPIS_SETTINGS = dict(
    CACHES=LOCMEM_CACHE,
    TAPIS_TENANT_ID='portals',
    TAPIS_BASE_URL='https://portals.tapis.io',
    TAPIS_EXEC_SYSTEM_ID='ls6',
    TAPIS_CREDENTIAL_CACHE_SECONDS=600,
)
PROBE_ARGS = dict(token='secret-jwt-value', username='test user', system_id='ls6',
                  base_url='https://portals.tapis.io/', tenant_id='portals')


def _b64url(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')


def _make_jwt(exp_seconds=3600, username='testuser'):
    header = _b64url({'alg': 'RS256', 'typ': 'JWT'})
    payload = _b64url({'tapis/username': username, 'exp': int(time.time()) + exp_seconds})
    return '{}.{}.signature'.format(header, payload)


def _resp(status_code, body=None, non_json=False):
    response = MagicMock()
    response.status_code = status_code
    if non_json:
        response.json.side_effect = ValueError('not json')
    else:
        response.json.return_value = body if body is not None else {}
    return response


def _tapis_error(message):
    return {'result': None, 'status': 'error', 'message': message}


@patch('app.services.tapis_credentials.requests.request')
class ProbeCredentialTests(SimpleTestCase):
    def _probe(self, request_mock, *responses):
        request_mock.side_effect = list(responses)
        return svc.probe_credential(**PROBE_ARGS)

    def test_200_is_ready(self, request_mock):
        result = self._probe(request_mock, _resp(200, {'result': {}}))
        self.assertEqual((result.status, result.code), (svc.STATUS_READY, svc.CODE_OK))
        self.assertEqual(request_mock.call_count, 1)

    def test_explicit_not_found_code_is_missing(self, request_mock):
        result = self._probe(request_mock, _resp(404, _tapis_error('SYSAPI_CRED_NOT_FOUND Credential not found')))
        self.assertEqual((result.status, result.code), (svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING))
        self.assertEqual(request_mock.call_count, 1)

    def test_bare_404_then_files_200_is_ready(self, request_mock):
        result = self._probe(request_mock, _resp(404, _tapis_error('Not found')), _resp(200, {'result': []}))
        self.assertEqual(result.status, svc.STATUS_READY)
        self.assertEqual(request_mock.call_count, 2)

    def test_403_then_files_missing_signal_is_missing(self, request_mock):
        result = self._probe(request_mock,
                             _resp(403, _tapis_error('SYSAPI_UNAUTH')),
                             _resp(400, _tapis_error('SYSTEMS_MISSING_CREDENTIALS There are no credentials associated with system ls6')))
        self.assertEqual((result.status, result.code), (svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING))

    def test_403_then_files_403_without_code_is_unknown(self, request_mock):
        result = self._probe(request_mock, _resp(403, _tapis_error('nope')), _resp(403, _tapis_error('still nope')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_NOT_AUTHORIZED))

    def test_bare_404_then_files_404_is_unknown_never_missing(self, request_mock):
        result = self._probe(request_mock, _resp(404, _tapis_error('x')), _resp(404, _tapis_error('y')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_UNEXPECTED_RESPONSE))

    def test_401_is_token_expired(self, request_mock):
        result = self._probe(request_mock, _resp(401, _tapis_error('JWT expired')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TOKEN_EXPIRED))

    def test_500_is_unreachable(self, request_mock):
        result = self._probe(request_mock, _resp(503, _tapis_error('down')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_non_json_bodies_are_unknown(self, request_mock):
        result = self._probe(request_mock, _resp(404, non_json=True), _resp(502, non_json=True))
        self.assertEqual(result.status, svc.STATUS_UNKNOWN)
        self.assertEqual(result.code, svc.CODE_TAPIS_UNREACHABLE)

    def test_timeout_is_unreachable(self, request_mock):
        request_mock.side_effect = requests.Timeout()
        result = svc.probe_credential(**PROBE_ARGS)
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_connection_error_on_second_stage_is_unreachable(self, request_mock):
        request_mock.side_effect = [_resp(404, _tapis_error('x')), requests.ConnectionError()]
        result = svc.probe_credential(**PROBE_ARGS)
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_request_shape_and_url_quoting(self, request_mock):
        self._probe(request_mock, _resp(200))
        method, url = request_mock.call_args[0]
        kwargs = request_mock.call_args[1]
        self.assertEqual(method, 'GET')
        self.assertEqual(url, 'https://portals.tapis.io/v3/systems/credential/ls6/user/test%20user')
        self.assertEqual(kwargs['timeout'], svc.REQUEST_TIMEOUT_SECONDS)
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['headers']['X-Tapis-Token'], 'secret-jwt-value')
        self.assertEqual(kwargs['headers']['X-Tapis-Tenant'], 'portals')

    def test_detail_is_capped(self, request_mock):
        result = self._probe(request_mock, _resp(404, _tapis_error('SYSAPI_CRED_NOT_FOUND ' + 'x' * 1000)))
        self.assertLessEqual(len(result.detail), svc.DETAIL_MAX_CHARS)


@patch('app.services.tapis_credentials.requests.request')
class CreateTmsCredentialTests(SimpleTestCase):
    def test_success(self, request_mock):
        request_mock.return_value = _resp(200, {'status': 'success', 'message': 'SYSAPI_CRED_UPDATED Credential updated.'})
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertTrue(result.ok)
        self.assertEqual(result.code, svc.CODE_OK)
        method, url = request_mock.call_args[0]
        kwargs = request_mock.call_args[1]
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://portals.tapis.io/v3/systems/credential/ls6/user/test%20user?createTmsKeys=true')
        self.assertEqual(kwargs['json'], {})
        self.assertEqual(kwargs['timeout'], svc.REQUEST_TIMEOUT_SECONDS)

    def test_forbidden(self, request_mock):
        request_mock.return_value = _resp(403, _tapis_error('SYSAPI_UNAUTH not authorized'))
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertEqual((result.ok, result.code), (False, svc.CODE_NOT_AUTHORIZED))

    def test_bad_request_is_create_failed_with_message(self, request_mock):
        request_mock.return_value = _resp(400, _tapis_error('SYSAPI_TMS_ERROR something'))
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertEqual((result.ok, result.code), (False, svc.CODE_CREATE_FAILED))
        self.assertIn('SYSAPI_TMS_ERROR', result.detail)

    def test_network_error(self, request_mock):
        request_mock.side_effect = requests.ConnectionError()
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertEqual((result.ok, result.code), (False, svc.CODE_TAPIS_UNREACHABLE))


@override_settings(**TAPIS_SETTINGS)
class CredentialStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='testuser')
        self.client_row = TapisOAuth2Client.objects.create(
            client_id='webodm', client_secret='s', tenant_id='portals',
            base_url='https://portals.tapis.io', callback_url='https://webodm.example/cb', name='test')
        self.jwt = _make_jwt()
        TapisOAuth2Token.objects.create(user=self.user, client=self.client_row, access_token=self.jwt)

    def _ready(self):
        return svc.ProbeResult(svc.STATUS_READY, svc.CODE_OK, '')

    def _missing(self):
        return svc.ProbeResult(svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING, 'SYSAPI_CRED_NOT_FOUND')

    def _unknown(self):
        return svc.ProbeResult(svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE, 'Timeout')

    def test_user_without_token_is_unknown_without_outbound_call(self):
        other = User.objects.create_user(username='nobody')
        with patch('app.services.tapis_credentials.probe_credential') as probe:
            payload = svc.get_credential_status(other)
        self.assertEqual((payload['status'], payload['code']), (svc.STATUS_UNKNOWN, svc.CODE_NO_TAPIS_TOKEN))
        probe.assert_not_called()

    def test_expired_token_is_token_expired(self):
        TapisOAuth2Token.objects.filter(user=self.user).update(access_token=_make_jwt(exp_seconds=-600), expires_at=None)
        with patch('app.services.tapis_credentials.probe_credential') as probe:
            payload = svc.get_credential_status(self.user)
        self.assertEqual(payload['code'], svc.CODE_TOKEN_EXPIRED)
        probe.assert_not_called()

    def test_client_base_url_mismatch_is_misconfigured(self):
        self.client_row.base_url = 'https://evil.example'
        self.client_row.save()
        with patch('app.services.tapis_credentials.probe_credential') as probe:
            payload = svc.get_credential_status(self.user)
        self.assertEqual(payload['code'], svc.CODE_MISCONFIGURED)
        probe.assert_not_called()

    def test_invalid_system_id_is_misconfigured(self):
        payload = svc.get_credential_status(self.user, system_id='ls6; rm -rf /')
        self.assertEqual(payload['code'], svc.CODE_MISCONFIGURED)

    def test_ready_is_cached_and_refresh_bypasses(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()) as probe:
            first = svc.get_credential_status(self.user)
            second = svc.get_credential_status(self.user)
            self.assertEqual(probe.call_count, 1)
            svc.get_credential_status(self.user, refresh=True)
            self.assertEqual(probe.call_count, 2)
        self.assertEqual(first['status'], svc.STATUS_READY)
        self.assertEqual(first['checked_at'], second['checked_at'])
        self.assertEqual(first['system_id'], 'ls6')
        self.assertEqual(set(first.keys()), {'system_id', 'status', 'code', 'detail', 'checked_at'})

    def test_missing_and_unknown_are_not_cached(self):
        with patch('app.services.tapis_credentials.probe_credential', side_effect=[self._missing(), self._unknown(), self._ready()]) as probe:
            svc.get_credential_status(self.user)
            svc.get_credential_status(self.user)
            svc.get_credential_status(self.user)
            self.assertEqual(probe.call_count, 3)

    def test_clear_cached_status(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()) as probe:
            svc.get_credential_status(self.user)
            svc.clear_cached_status(self.user)
            svc.get_credential_status(self.user)
            self.assertEqual(probe.call_count, 2)

    def test_probe_uses_stored_token_and_client_base_url(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()) as probe:
            svc.get_credential_status(self.user)
        probe.assert_called_once_with(self.jwt, 'testuser', 'ls6', 'https://portals.tapis.io', 'portals')

    def test_logs_do_not_contain_the_token(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._missing()):
            with self.assertLogs('app.logger', level='DEBUG') as logs:
                svc.get_credential_status(self.user)
        self.assertNotIn(self.jwt, '\n'.join(logs.output))

    def test_create_refuses_when_already_ready(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()), \
             patch('app.services.tapis_credentials.create_tms_credential') as create:
            http_status, payload = svc.create_credential_for_user(self.user)
        self.assertEqual(http_status, 409)
        self.assertEqual(payload['code'], svc.CODE_ALREADY_READY)
        create.assert_not_called()

    def test_create_refuses_when_unverified(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._unknown()), \
             patch('app.services.tapis_credentials.create_tms_credential') as create:
            http_status, payload = svc.create_credential_for_user(self.user)
        self.assertEqual((http_status, payload['code']), (409, svc.CODE_CANNOT_VERIFY))
        create.assert_not_called()

    def test_create_ignores_cached_ready_and_probes_fresh(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()):
            svc.get_credential_status(self.user)  # caches ready
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._missing()) as probe, \
             patch('app.services.tapis_credentials.create_tms_credential',
                   return_value=svc.CreateResult(False, svc.CODE_CREATE_FAILED, 'boom')):
            http_status, payload = svc.create_credential_for_user(self.user)
        self.assertTrue(probe.called)
        self.assertEqual(http_status, 502)
        self.assertEqual((payload['status'], payload['code'], payload['detail']),
                         (svc.STATUS_MISSING, svc.CODE_CREATE_FAILED, 'boom'))

    def test_create_success_reprobes_and_returns_ready(self):
        with patch('app.services.tapis_credentials.probe_credential', side_effect=[self._missing(), self._ready()]), \
             patch('app.services.tapis_credentials.create_tms_credential',
                   return_value=svc.CreateResult(True, svc.CODE_OK, 'SYSAPI_CRED_UPDATED')) as create:
            http_status, payload = svc.create_credential_for_user(self.user)
        self.assertEqual(http_status, 200)
        self.assertEqual(payload['status'], svc.STATUS_READY)
        create.assert_called_once_with(self.jwt, 'testuser', 'ls6', 'https://portals.tapis.io', 'portals')


@override_settings(**TAPIS_SETTINGS)
class HpcAccessApiTests(BootTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.get(username='testuser')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _payload(self, status_value, code, system_id='ls6'):
        return {'system_id': system_id, 'status': status_value, 'code': code, 'detail': '', 'checked_at': 'now'}

    def test_requires_authentication(self):
        anonymous = APIClient()
        self.assertIn(anonymous.get('/api/tapis/hpc-access/').status_code, (401, 403))
        self.assertIn(anonymous.post('/api/tapis/hpc-access/').status_code, (401, 403))

    def test_get_returns_status_payload(self):
        with patch('app.api.tapis_credentials.get_credential_status', return_value=self._payload('missing', 'credential_missing')) as status_fn:
            res = self.client.get('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'missing')
        status_fn.assert_called_once_with(self.user, 'ls6', refresh=False)

    def test_get_rejects_invalid_system_id(self):
        res = self.client.get('/api/tapis/hpc-access/?system_id=ls6;drop')
        self.assertEqual(res.status_code, 400)

    def test_get_accepts_system_id_override(self):
        with patch('app.api.tapis_credentials.get_credential_status', return_value=self._payload('ready', 'ok', 'stampede3')) as status_fn:
            res = self.client.get('/api/tapis/hpc-access/?system_id=stampede3')
        self.assertEqual(res.status_code, 200)
        status_fn.assert_called_once_with(self.user, 'stampede3', refresh=False)

    def test_refresh_is_honoured_once_per_interval(self):
        with patch('app.api.tapis_credentials.get_credential_status', return_value=self._payload('ready', 'ok')) as status_fn:
            self.client.get('/api/tapis/hpc-access/?refresh=1')
            self.client.get('/api/tapis/hpc-access/?refresh=1')
        refresh_flags = [call[1]['refresh'] for call in status_fn.call_args_list]
        self.assertEqual(refresh_flags, [True, False])

    def test_post_passes_through_service_status(self):
        with patch('app.api.tapis_credentials.create_credential_for_user', return_value=(409, self._payload('ready', 'already_ready'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data['code'], 'already_ready')

        with patch('app.api.tapis_credentials.create_credential_for_user', return_value=(502, self._payload('missing', 'create_failed'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.data['code'], 'create_failed')

    def test_post_is_rejected_while_locked_and_lock_is_released(self):
        cache.add('hpc:lock:{}'.format(self.user.pk), 1, 30)
        with patch('app.api.tapis_credentials.create_credential_for_user') as create:
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 429)
        create.assert_not_called()

        cache.delete('hpc:lock:{}'.format(self.user.pk))
        with patch('app.api.tapis_credentials.create_credential_for_user', return_value=(200, self._payload('ready', 'ok'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(cache.get('hpc:lock:{}'.format(self.user.pk)))

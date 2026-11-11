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
    TAPIS_REQUIRED_SYSTEMS=['ls6', 'cloud.data'],
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


def _resp(status_code, body=None, non_json=False, text=''):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    if non_json:
        response.json.side_effect = ValueError('not json')
    else:
        response.json.return_value = body if body is not None else {}
    return response


# The Tapis security filter answers with a plain string, not a JSON envelope.
def _filter_reject(message):
    return _resp(401, non_json=True, text=message)


def _tapis_error(message):
    return {'result': None, 'status': 'error', 'message': message}


# Shape of the Tapis Files error when its SSH session pool cannot log in to the host.
SSH_POOL_ERROR = ('FILES_CLIENT_SSH_SESSION_POOL_ERROR Error getting ssh session from SSH session pool.  '
                  'Tenant: portals, Host: ls6.tacc.utexas.edu, Port: 22, EffectiveUserId: testuser, '
                  'AuthnMethod: TMS_KEYS, Timeout: PT30S, Exception Message: {}')


@patch('app.services.tapis_credentials.requests.request')
class ProbeCredentialTests(SimpleTestCase):
    def _probe(self, request_mock, response):
        request_mock.return_value = response
        result = svc.probe_credential(**PROBE_ARGS)
        self.assertEqual(request_mock.call_count, 1)
        return result

    def test_200_is_ready(self, request_mock):
        result = self._probe(request_mock, _resp(200, {'result': []}))
        self.assertEqual((result.status, result.code), (svc.STATUS_READY, svc.CODE_OK))

    def test_files_401_with_pool_missing_credentials_is_missing(self, request_mock):
        message = SSH_POOL_ERROR.format('SSH_POOL_MISSING_CREDENTIALS Missing credentials Tenant: portals, Host: ls6.tacc.utexas.edu')
        result = self._probe(request_mock, _resp(401, _tapis_error(message)))
        self.assertEqual((result.status, result.code), (svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING))

    def test_files_500_with_pool_missing_credentials_is_missing(self, request_mock):
        message = SSH_POOL_ERROR.format('SSH_POOL_MISSING_CREDENTIALS Missing credentials')
        result = self._probe(request_mock, _resp(500, _tapis_error(message)))
        self.assertEqual((result.status, result.code), (svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING))

    def test_systems_missing_credentials_is_missing(self, request_mock):
        message = 'SYSTEMS_MISSING_CREDENTIALS There are no credentials associated with system ls6 for tenant portals.'
        result = self._probe(request_mock, _resp(400, _tapis_error(message)))
        self.assertEqual((result.status, result.code), (svc.STATUS_MISSING, svc.CODE_CREDENTIAL_MISSING))

    def test_401_from_jwt_filter_is_token_expired(self, request_mock):
        message = 'TAPIS_SECURITY_JWT_EXPIRED Expired JWT. Expired on: 2026-11-04T10:00:00Z Claims: {}'
        result = self._probe(request_mock, _filter_reject(message))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TOKEN_EXPIRED))
        self.assertIn('TAPIS_SECURITY_JWT_EXPIRED', result.detail)

    def test_401_from_jwt_filter_in_json_envelope_is_token_expired(self, request_mock):
        result = self._probe(request_mock, _resp(401, _tapis_error('TAPIS_SECURITY_JWT_VERIFY_FAIL The jwt failed to verify.')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TOKEN_EXPIRED))

    def test_401_for_unexpected_header_is_not_ssh_or_token(self, request_mock):
        message = ('TAPIS_SECURITY_UNEXPECTED_HEADER Unexpected header X-Tapis-Tenant for user testuser '
                   'in tenant portals with account type user.')
        result = self._probe(request_mock, _filter_reject(message))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_UNEXPECTED_RESPONSE))
        self.assertIn('TAPIS_SECURITY_UNEXPECTED_HEADER', result.detail)

    def test_401_from_ssh_login_is_ssh_auth_failed_not_token_expired(self, request_mock):
        message = SSH_POOL_ERROR.format('SSH_AUTHENTICATION_FAILURE_USING_KEYPAIR Failure to authenticate using key pair for testuser')
        result = self._probe(request_mock, _resp(401, _tapis_error(message)))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_SSH_AUTH_FAILED))
        self.assertIn('SSH_AUTHENTICATION_FAILURE_USING_KEYPAIR', result.detail)

    def test_401_without_message_is_ssh_auth_failed(self, request_mock):
        result = self._probe(request_mock, _resp(401, non_json=True))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_SSH_AUTH_FAILED))
        self.assertEqual(result.detail, '')

    def test_403_is_not_authorized(self, request_mock):
        result = self._probe(request_mock, _resp(403, _tapis_error('FILES_NOT_AUTHORIZED. Permission denied by Tapis.')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_NOT_AUTHORIZED))

    def test_404_is_unknown_never_missing(self, request_mock):
        result = self._probe(request_mock, _resp(404, _tapis_error('FILES_SYS_NOT_FOUND System not found')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_UNEXPECTED_RESPONSE))

    def test_500_is_unreachable(self, request_mock):
        result = self._probe(request_mock, _resp(503, _tapis_error('down')))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_non_json_5xx_is_unreachable(self, request_mock):
        result = self._probe(request_mock, _resp(502, non_json=True))
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_timeout_is_unreachable(self, request_mock):
        request_mock.side_effect = requests.Timeout()
        result = svc.probe_credential(**PROBE_ARGS)
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_connection_error_is_unreachable(self, request_mock):
        request_mock.side_effect = requests.ConnectionError()
        result = svc.probe_credential(**PROBE_ARGS)
        self.assertEqual((result.status, result.code), (svc.STATUS_UNKNOWN, svc.CODE_TAPIS_UNREACHABLE))

    def test_request_shape_lists_system_root_through_files(self, request_mock):
        self._probe(request_mock, _resp(200))
        method, url = request_mock.call_args[0]
        kwargs = request_mock.call_args[1]
        self.assertEqual(method, 'GET')
        self.assertEqual(url, 'https://portals.tapis.io/v3/files/ops/ls6/?limit=1')
        self.assertEqual(kwargs['timeout'], svc.REQUEST_TIMEOUT_SECONDS)
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['headers']['X-Tapis-Token'], 'secret-jwt-value')
        # Tapis rejects X-Tapis-Tenant / X-Tapis-User on user tokens (TAPIS_SECURITY_UNEXPECTED_HEADER).
        self.assertNotIn('X-Tapis-Tenant', kwargs['headers'])
        self.assertNotIn('X-Tapis-User', kwargs['headers'])

    def test_detail_is_capped(self, request_mock):
        result = self._probe(request_mock, _resp(401, _tapis_error(SSH_POOL_ERROR.format('x' * 1000))))
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
        self.assertNotIn('X-Tapis-Tenant', kwargs['headers'])

    def test_expired_jwt_is_token_expired(self, request_mock):
        request_mock.return_value = _filter_reject('TAPIS_SECURITY_JWT_EXPIRED Expired JWT.')
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertEqual((result.ok, result.code), (False, svc.CODE_TOKEN_EXPIRED))

    def test_other_401_is_create_failed_with_message(self, request_mock):
        request_mock.return_value = _filter_reject('TAPIS_SECURITY_UNEXPECTED_HEADER Unexpected header')
        result = svc.create_tms_credential(**PROBE_ARGS)
        self.assertEqual((result.ok, result.code), (False, svc.CODE_CREATE_FAILED))
        self.assertIn('TAPIS_SECURITY_UNEXPECTED_HEADER', result.detail)

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


    # --- all required systems ---------------------------------------------------------

    def _probe_by_system(self, results):
        def fake(token, username, system_id, base_url, tenant_id):
            return results[system_id]
        return fake

    def test_required_systems_include_exec_system_first(self):
        self.assertEqual(svc.required_system_ids(), ['ls6', 'cloud.data'])

    def test_all_status_names_the_system_that_is_missing(self):
        results = {'ls6': self._ready(), 'cloud.data': self._missing()}
        with patch('app.services.tapis_credentials.probe_credential', side_effect=self._probe_by_system(results)):
            payload = svc.get_all_credential_status(self.user)
        self.assertEqual(payload['status'], svc.STATUS_MISSING)
        self.assertEqual(payload['system_id'], 'cloud.data')
        self.assertEqual(payload['missing_systems'], ['cloud.data'])
        self.assertEqual([p['system_id'] for p in payload['systems']], ['ls6', 'cloud.data'])

    def test_all_status_ready_only_when_every_system_is_ready(self):
        results = {'ls6': self._ready(), 'cloud.data': self._ready()}
        with patch('app.services.tapis_credentials.probe_credential', side_effect=self._probe_by_system(results)):
            payload = svc.get_all_credential_status(self.user)
        self.assertEqual((payload['status'], payload['missing_systems']), (svc.STATUS_READY, []))

    def test_all_status_unknown_when_one_system_cannot_be_verified(self):
        results = {'ls6': self._ready(), 'cloud.data': self._unknown()}
        with patch('app.services.tapis_credentials.probe_credential', side_effect=self._probe_by_system(results)):
            payload = svc.get_all_credential_status(self.user)
        self.assertEqual(payload['status'], svc.STATUS_UNKNOWN)

    def test_create_missing_creates_only_missing_systems(self):
        results = {'ls6': self._ready(), 'cloud.data': self._missing()}
        with patch('app.services.tapis_credentials.probe_credential', side_effect=self._probe_by_system(results)), \
             patch('app.services.tapis_credentials.create_tms_credential',
                   return_value=svc.CreateResult(True, svc.CODE_OK, '')) as create:
            http_status, payload = svc.create_missing_credentials_for_user(self.user)
        self.assertEqual(http_status, 200)
        create.assert_called_once_with(self.jwt, 'testuser', 'cloud.data', 'https://portals.tapis.io', 'portals')
        self.assertIn('systems', payload)

    def test_create_missing_refuses_when_all_ready(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._ready()), \
             patch('app.services.tapis_credentials.create_tms_credential') as create:
            http_status, payload = svc.create_missing_credentials_for_user(self.user)
        self.assertEqual((http_status, payload['code']), (409, svc.CODE_ALREADY_READY))
        create.assert_not_called()

    def test_create_missing_refuses_when_unverified_and_nothing_missing(self):
        results = {'ls6': self._ready(), 'cloud.data': self._unknown()}
        with patch('app.services.tapis_credentials.probe_credential', side_effect=self._probe_by_system(results)), \
             patch('app.services.tapis_credentials.create_tms_credential') as create:
            http_status, payload = svc.create_missing_credentials_for_user(self.user)
        self.assertEqual((http_status, payload['code'], payload['system_id']), (409, svc.CODE_CANNOT_VERIFY, 'cloud.data'))
        create.assert_not_called()

    def test_create_missing_stops_and_reports_the_failing_system(self):
        with patch('app.services.tapis_credentials.probe_credential', return_value=self._missing()), \
             patch('app.services.tapis_credentials.create_tms_credential',
                   return_value=svc.CreateResult(False, svc.CODE_CREATE_FAILED, 'boom')) as create:
            http_status, payload = svc.create_missing_credentials_for_user(self.user)
        self.assertEqual((http_status, payload['code'], payload['system_id']), (502, svc.CODE_CREATE_FAILED, 'ls6'))
        self.assertEqual(create.call_count, 1)

    def test_diagnose_ignores_unrelated_errors(self):
        with patch('app.services.tapis_credentials.get_all_credential_status') as status:
            self.assertEqual(svc.diagnose_failed_task_error(self.user, 'Process exited with code 1'), ([], ''))
        status.assert_not_called()

    def test_diagnose_names_the_missing_system_for_a_staging_failure(self):
        fake = {'missing_systems': ['cloud.data'], 'status': svc.STATUS_MISSING}
        with patch('app.services.tapis_credentials.get_all_credential_status', return_value=fake):
            missing, hint = svc.diagnose_failed_task_error(self.user, 'JOBS_TRANSFER_INCOMPLETE Transfer 4980d18b')
        self.assertEqual(missing, ['cloud.data'])
        self.assertIn('cloud.data', hint)
        self.assertIn('Set up HPC access', hint)

    def test_diagnose_suggests_retry_when_credentials_are_fine(self):
        fake = {'missing_systems': [], 'status': svc.STATUS_READY}
        with patch('app.services.tapis_credentials.get_all_credential_status', return_value=fake):
            missing, hint = svc.diagnose_failed_task_error(self.user, 'JOBS_TRANSFER_INCOMPLETE Transfer 4980d18b')
        self.assertEqual(missing, [])
        self.assertIn('again', hint)

    def test_diagnose_never_raises(self):
        with patch('app.services.tapis_credentials.get_all_credential_status', side_effect=RuntimeError('boom')):
            self.assertEqual(svc.diagnose_failed_task_error(self.user, 'JOBS_TRANSFER_INCOMPLETE'), ([], ''))


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
        with patch('app.api.tapis_credentials.get_all_credential_status', return_value=self._payload('missing', 'credential_missing')) as status_fn:
            res = self.client.get('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'missing')
        status_fn.assert_called_once_with(self.user, refresh=False)

    def test_get_rejects_invalid_system_id(self):
        res = self.client.get('/api/tapis/hpc-access/?system_id=ls6;drop')
        self.assertEqual(res.status_code, 400)

    def test_get_accepts_system_id_override(self):
        with patch('app.api.tapis_credentials.get_credential_status', return_value=self._payload('ready', 'ok', 'stampede3')) as status_fn:
            res = self.client.get('/api/tapis/hpc-access/?system_id=stampede3')
        self.assertEqual(res.status_code, 200)
        status_fn.assert_called_once_with(self.user, 'stampede3', refresh=False)

    def test_refresh_is_honoured_once_per_interval(self):
        with patch('app.api.tapis_credentials.get_all_credential_status', return_value=self._payload('ready', 'ok')) as status_fn:
            self.client.get('/api/tapis/hpc-access/?refresh=1')
            self.client.get('/api/tapis/hpc-access/?refresh=1')
        refresh_flags = [call[1]['refresh'] for call in status_fn.call_args_list]
        self.assertEqual(refresh_flags, [True, False])

    def test_post_passes_through_service_status(self):
        with patch('app.api.tapis_credentials.create_missing_credentials_for_user', return_value=(409, self._payload('ready', 'already_ready'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data['code'], 'already_ready')

        with patch('app.api.tapis_credentials.create_missing_credentials_for_user', return_value=(502, self._payload('missing', 'create_failed'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.data['code'], 'create_failed')

    def test_post_is_rejected_while_locked_and_lock_is_released(self):
        cache.add('hpc:lock:{}'.format(self.user.pk), 1, 30)
        with patch('app.api.tapis_credentials.create_missing_credentials_for_user') as create:
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 429)
        create.assert_not_called()

        cache.delete('hpc:lock:{}'.format(self.user.pk))
        with patch('app.api.tapis_credentials.create_missing_credentials_for_user', return_value=(200, self._payload('ready', 'ok'))):
            res = self.client.post('/api/tapis/hpc-access/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(cache.get('hpc:lock:{}'.format(self.user.pk)))

    def test_post_with_system_id_creates_only_that_system(self):
        with patch('app.api.tapis_credentials.create_credential_for_user', return_value=(200, self._payload('ready', 'ok', 'cloud.data'))) as create_one, \
             patch('app.api.tapis_credentials.create_missing_credentials_for_user') as create_all:
            res = self.client.post('/api/tapis/hpc-access/?system_id=cloud.data')
        self.assertEqual(res.status_code, 200)
        create_one.assert_called_once_with(self.user, 'cloud.data')
        create_all.assert_not_called()


class TaskTerminalStateLoggingTests(SimpleTestCase):
    """Task.log_terminal_state: correlation log line and the staging-failure hint."""

    def _task(self, status, last_error):
        from types import SimpleNamespace
        from nodeodm import status_codes
        owner = SimpleNamespace(username='newuser')
        return SimpleNamespace(
            id='task-1', project_id=40, project=SimpleNamespace(owner=owner),
            _tapis_token_user=lambda: owner,
            processing_node=SimpleNamespace(hostname='clusterodm'),
            status=getattr(status_codes, status), last_error=last_error, save=MagicMock())

    def _run(self, task, job=None):
        from app.models import Task
        Task.log_terminal_state(task, job)

    def test_logs_task_and_tapis_job_ids(self):
        task = self._task('FAILED', 'Process exited with code 1')
        with self.assertLogs('app.logger', level='INFO') as logs:
            self._run(task, {'tapisJobId': '916d14f2-c838-401f-8eaa-4cf5815949bc-007'})
        line = [l for l in logs.output if 'Task ended' in l][0]
        self.assertIn('task=task-1', line)
        self.assertIn('owner=newuser', line)
        self.assertIn('tapis_job=916d14f2-c838-401f-8eaa-4cf5815949bc-007', line)
        task.save.assert_not_called()

    def test_log_line_never_contains_a_token(self):
        jwt = 'eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.c2lnLXBhcnRfMQ'
        task = self._task('FAILED', 'failed with ?token=' + jwt)
        with self.assertLogs('app.logger', level='INFO') as logs:
            self._run(task)
        self.assertNotIn(jwt, '\n'.join(logs.output))

    def test_staging_failure_gets_a_hint_naming_the_missing_system(self):
        task = self._task('FAILED', 'JOBS_TRANSFER_INCOMPLETE Transfer 4980d18b')
        with patch('app.services.tapis_credentials.diagnose_failed_task_error',
                   return_value=(['cloud.data'], 'Your TACC account has no credential on cloud.data.')):
            self._run(task)
        self.assertIn('no credential on cloud.data', task.last_error)
        self.assertTrue(task.last_error.startswith('JOBS_TRANSFER_INCOMPLETE'))
        task.save.assert_called_once()

    def test_hint_is_not_appended_twice(self):
        task = self._task('FAILED', 'JOBS_TRANSFER_INCOMPLETE x\n\nHint text.')
        with patch('app.services.tapis_credentials.diagnose_failed_task_error', return_value=([], 'Hint text.')):
            self._run(task)
        self.assertEqual(task.last_error.count('Hint text.'), 1)
        task.save.assert_not_called()

    def test_completed_task_is_logged_but_not_diagnosed(self):
        task = self._task('COMPLETED', None)
        with patch('app.services.tapis_credentials.diagnose_failed_task_error') as diagnose:
            self._run(task)
        diagnose.assert_not_called()

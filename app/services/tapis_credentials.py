"""
Per-user Tapis system credential check and creation.

ClusterODX submits Tapis jobs with the end user's own JWT, so Tapis needs a credential
registered for that user on the execution system (TMS-managed SSH keys on ls6). Login
never creates one, so a new user's first job fails with SYSTEMS_MISSING_CREDENTIALS.

This module answers "does this user have a working credential on the system?"
conservatively: ``missing`` is reported only on an explicit Tapis signal, everything
inconclusive is ``unknown`` and must never block the user. It can also ask Tapis to
create TMS keys.

Tapis Systems never lets a user token read a credential record (every user gets
``SYSLIB_UNAUTH_GETCRED``), so the probe lists the system root through the Files API
instead. That makes Tapis open an SSH session to the host as the user, and Files reports
SSH failures as HTTP 401: a missing TMS credential carries ``SSH_POOL_MISSING_CREDENTIALS``
(sometimes as a 500), a key the host rejects does not. Only a JWT rejected by the Tapis
security filter (``TAPIS_SECURITY_JWT_*``) means the sign-in itself is invalid.

The request-level functions take plain strings so they are testable without a database.
"""
import logging
import re
from collections import namedtuple
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('app.logger')

STATUS_READY = 'ready'
STATUS_MISSING = 'missing'
STATUS_UNKNOWN = 'unknown'

CODE_OK = 'ok'
CODE_CREDENTIAL_MISSING = 'credential_missing'
CODE_ALREADY_READY = 'already_ready'
CODE_CANNOT_VERIFY = 'cannot_verify'
CODE_TOKEN_EXPIRED = 'token_expired'
CODE_NOT_AUTHORIZED = 'not_authorized'
CODE_SSH_AUTH_FAILED = 'ssh_auth_failed'
CODE_TAPIS_UNREACHABLE = 'tapis_unreachable'
CODE_UNEXPECTED_RESPONSE = 'unexpected_response'
CODE_NO_TAPIS_TOKEN = 'no_tapis_token'
CODE_MISCONFIGURED = 'misconfigured'
CODE_CREATE_FAILED = 'create_failed'

# Only these explicit Tapis signals mean "no credential". A bare 401/403/404 does not.
# They are checked before the HTTP status because Files surfaces them as 401 or 500.
MISSING_SIGNALS = ('SYSAPI_CRED_NOT_FOUND', 'SYSTEMS_MISSING_CREDENTIALS', 'SSH_POOL_MISSING_CREDENTIALS')
# Prefix of every message the Tapis security filter emits when it refuses a JWT.
JWT_REJECTED_SIGNAL = 'TAPIS_SECURITY_JWT'

SYSTEM_ID_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
REQUEST_TIMEOUT_SECONDS = 10
DETAIL_MAX_CHARS = 300

ProbeResult = namedtuple('ProbeResult', ['status', 'code', 'detail'])
CreateResult = namedtuple('CreateResult', ['ok', 'code', 'detail'])
TapisContext = namedtuple('TapisContext', ['token', 'username', 'base_url', 'tenant_id'])


def is_valid_system_id(value):
    return bool(value) and bool(SYSTEM_ID_PATTERN.match(str(value)))


def default_system_id():
    return getattr(settings, 'TAPIS_EXEC_SYSTEM_ID', 'ls6')


def _trim(detail):
    detail = (detail or '').strip()
    return detail[:DETAIL_MAX_CHARS]


def _tapis_message(response):
    """Return the Tapis ``message`` field of a JSON error body, or an empty string."""
    try:
        body = response.json()
    except ValueError:
        return ''
    if isinstance(body, dict):
        message = body.get('message')
        if isinstance(message, str):
            return message
    return ''


def _has_missing_signal(message):
    return any(signal in (message or '') for signal in MISSING_SIGNALS)


def _credential_url(base_url, system_id, username):
    return '{}/v3/systems/credential/{}/user/{}'.format(
        base_url.rstrip('/'), quote(system_id, safe=''), quote(username, safe=''))


def _files_probe_url(base_url, system_id):
    return '{}/v3/files/ops/{}/?limit=1'.format(base_url.rstrip('/'), quote(system_id, safe=''))


def _request(method, url, token, tenant_id, **kwargs):
    headers = {
        'X-Tapis-Token': token,
        'X-Tapis-Tenant': tenant_id or '',
        'Accept': 'application/json',
    }
    if 'json' in kwargs:
        headers['Content-Type'] = 'application/json'
    return requests.request(
        method, url, headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=False, **kwargs)


def probe_credential(token, username, system_id, base_url, tenant_id):
    """
    Decide whether ``username`` has a working credential on ``system_id``.

    Lists the system root through the Files API with the user's token, which makes Tapis
    SSH into the host as that user. ``username`` is not part of the request (the token
    identifies the user); it is kept so callers and the create path share one signature.
    """
    try:
        response = _request('GET', _files_probe_url(base_url, system_id), token, tenant_id)
    except requests.RequestException as e:
        return ProbeResult(STATUS_UNKNOWN, CODE_TAPIS_UNREACHABLE, type(e).__name__)

    if response.status_code == 200:
        return ProbeResult(STATUS_READY, CODE_OK, '')

    message = _tapis_message(response)
    if _has_missing_signal(message):
        return ProbeResult(STATUS_MISSING, CODE_CREDENTIAL_MISSING, _trim(message))
    if response.status_code == 401:
        if JWT_REJECTED_SIGNAL in message:
            return ProbeResult(STATUS_UNKNOWN, CODE_TOKEN_EXPIRED, _trim(message))
        # Files could not log in to the host with the credential Tapis holds for the user.
        return ProbeResult(STATUS_UNKNOWN, CODE_SSH_AUTH_FAILED, _trim(message))
    if response.status_code == 403:
        return ProbeResult(STATUS_UNKNOWN, CODE_NOT_AUTHORIZED, _trim(message))
    if response.status_code >= 500:
        return ProbeResult(STATUS_UNKNOWN, CODE_TAPIS_UNREACHABLE, _trim(message))
    return ProbeResult(STATUS_UNKNOWN, CODE_UNEXPECTED_RESPONSE, _trim(message))


def create_tms_credential(token, username, system_id, base_url, tenant_id):
    """Ask Tapis to generate and register TMS SSH keys for ``username`` on ``system_id``."""
    url = _credential_url(base_url, system_id, username) + '?createTmsKeys=true'
    try:
        response = _request('POST', url, token, tenant_id, json={})
    except requests.RequestException as e:
        return CreateResult(False, CODE_TAPIS_UNREACHABLE, type(e).__name__)

    message = _tapis_message(response)
    if response.status_code in (200, 201):
        return CreateResult(True, CODE_OK, _trim(message))
    if response.status_code == 401:
        return CreateResult(False, CODE_TOKEN_EXPIRED, _trim(message))
    if response.status_code == 403:
        return CreateResult(False, CODE_NOT_AUTHORIZED, _trim(message))
    if response.status_code >= 500:
        return CreateResult(False, CODE_TAPIS_UNREACHABLE, _trim(message))
    return CreateResult(False, CODE_CREATE_FAILED, _trim(message))


# --- user-level helpers (database and cache aware) ---------------------------------

def _payload(system_id, status, code, detail=''):
    return {
        'system_id': system_id,
        'status': status,
        'code': code,
        'detail': _trim(detail),
        'checked_at': timezone.now().isoformat(),
    }


def resolve_tapis_context(user):
    """
    Return ``(TapisContext, None)`` for a user with a usable token in the configured
    tenant, or ``(None, (code, detail))`` describing why no outbound call can be made.
    """
    from app.models.oauth2 import TapisOAuth2Token

    tenant_id = (getattr(settings, 'TAPIS_TENANT_ID', '') or '').strip()
    settings_base = (getattr(settings, 'TAPIS_BASE_URL', '') or '').strip().rstrip('/')
    if not tenant_id or not settings_base:
        logger.error("TAPIS_TENANT_ID / TAPIS_BASE_URL are not configured; cannot check HPC access")
        return None, (CODE_MISCONFIGURED, 'Tapis tenant or base URL is not configured.')

    token_row = (TapisOAuth2Token.objects
                 .filter(user=user, client__tenant_id=tenant_id, client__is_active=True)
                 .select_related('client')
                 .order_by('-updated_at')
                 .first())
    if token_row is None:
        return None, (CODE_NO_TAPIS_TOKEN, 'No Tapis token is stored for this account.')

    token_value = token_row.get_valid_access_token()
    if not token_value:
        return None, (CODE_TOKEN_EXPIRED, 'Tapis token has expired.')

    client_base = (token_row.client.base_url or '').strip().rstrip('/')
    if not client_base or client_base != settings_base:
        logger.error("Tapis client base_url %r does not match TAPIS_BASE_URL %r; refusing to send the user's token",
                     client_base, settings_base)
        return None, (CODE_MISCONFIGURED, 'Tapis client configuration mismatch.')

    return TapisContext(token_value, user.username, client_base, tenant_id), None


def cache_key_for(user, system_id, tenant_id=None):
    tenant_id = tenant_id or getattr(settings, 'TAPIS_TENANT_ID', '')
    return 'hpc:v1:{}:{}:{}'.format(tenant_id, system_id, user.pk)


def clear_cached_status(user, system_id=None):
    system_id = system_id or default_system_id()
    try:
        cache.delete(cache_key_for(user, system_id))
    except Exception:
        logger.debug("Could not clear HPC access cache for user %s", user.pk, exc_info=True)


def get_credential_status(user, system_id=None, refresh=False):
    """Return the API payload for the user's credential status on ``system_id``."""
    system_id = system_id or default_system_id()
    if not is_valid_system_id(system_id):
        return _payload(system_id, STATUS_UNKNOWN, CODE_MISCONFIGURED, 'Invalid system id.')

    context, error = resolve_tapis_context(user)
    if error:
        return _payload(system_id, STATUS_UNKNOWN, error[0], error[1])

    key = cache_key_for(user, system_id, context.tenant_id)
    if not refresh:
        cached = cache.get(key)
        if isinstance(cached, dict) and cached.get('status') == STATUS_READY:
            return cached

    result = probe_credential(context.token, context.username, system_id, context.base_url, context.tenant_id)
    payload = _payload(system_id, result.status, result.code, result.detail)
    if result.status == STATUS_READY:
        cache.set(key, payload, getattr(settings, 'TAPIS_CREDENTIAL_CACHE_SECONDS', 600))
    logger.info("HPC access check user=%s system=%s status=%s code=%s",
                context.username, system_id, result.status, result.code)
    return payload


def create_credential_for_user(user, system_id=None):
    """
    Create the user's TMS credential after a fresh probe confirms it is missing.

    Returns ``(http_status, payload)``: 409 when the state is already ready or cannot be
    verified, 502 when Tapis refuses the create, 200 with the refreshed status otherwise.
    """
    system_id = system_id or default_system_id()
    if not is_valid_system_id(system_id):
        return 400, _payload(system_id, STATUS_UNKNOWN, CODE_MISCONFIGURED, 'Invalid system id.')

    context, error = resolve_tapis_context(user)
    if error:
        return 409, _payload(system_id, STATUS_UNKNOWN, error[0], error[1])

    before = probe_credential(context.token, context.username, system_id, context.base_url, context.tenant_id)
    if before.status == STATUS_READY:
        return 409, _payload(system_id, STATUS_READY, CODE_ALREADY_READY, 'A credential already exists.')
    if before.status != STATUS_MISSING:
        return 409, _payload(system_id, STATUS_UNKNOWN, CODE_CANNOT_VERIFY, before.detail)

    created = create_tms_credential(context.token, context.username, system_id, context.base_url, context.tenant_id)
    logger.info("HPC credential create user=%s system=%s ok=%s code=%s",
                context.username, system_id, created.ok, created.code)
    if not created.ok:
        return 502, _payload(system_id, STATUS_MISSING, created.code, created.detail)

    clear_cached_status(user, system_id)
    return 200, get_credential_status(user, system_id, refresh=True)

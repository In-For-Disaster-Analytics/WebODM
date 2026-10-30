"""Server-only ClusterODX adapter for the fixed NodeSplat workflow."""
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlsplit

import requests
from django.conf import settings

from .opensplat import OpenSplatError, SigninRequired, SubmissionUnknown, get_user_token


def configured():
    url = urlsplit(settings.NODESPLAT_CLUSTER_URL)
    return bool(url.scheme in ('https', 'http') and url.netloc and not url.username and not url.password
                and not url.query and not url.fragment and settings.NODESPLAT_AUDIENCE
                and settings.NODESPLAT_GRANT_KEY_ID and len(settings.NODESPLAT_GRANT_SECRET.encode('utf-8')) >= 32)


class ClusterClient:
    def __init__(self, user):
        self.token, self.client = get_user_token(user)
        self.user = user
        if not self.token:
            raise SigninRequired('Your Tapis session has expired. Please sign in again.')

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, settings.NODESPLAT_CLUSTER_URL.rstrip('/') + path,
                headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
                timeout=settings.OPENSPLAT_HTTP_TIMEOUT, allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise SubmissionUnknown('Cannot reach ClusterODX. Submission status may be unknown; refresh this attempt before starting another.')
        if response.status_code == 401:
            raise SigninRequired('Your Tapis session was rejected. Please sign in again.')
        if response.status_code == 403:
            raise OpenSplatError('Permission denied by ClusterODX. Check your allocation and training access.')
        if response.status_code >= 500:
            raise SubmissionUnknown('ClusterODX is unavailable. Refresh this attempt to reconcile its status.')
        if not response.ok or 300 <= response.status_code < 400:
            raise OpenSplatError('ClusterODX rejected the request (HTTP {}).'.format(response.status_code))
        try:
            result = response.json()
        except ValueError:
            raise SubmissionUnknown('ClusterODX returned an unexpected response. Refresh this attempt.')
        if not isinstance(result, dict):
            raise SubmissionUnknown('ClusterODX returned an unexpected response. Refresh this attempt.')
        return result

    def submit(self, run, manifest_hash):
        stamp = int(time.time())
        payload = {'issuer': 'webodm', 'audience': settings.NODESPLAT_AUDIENCE,
            'run_id': str(run.id), 'source_task_id': str(run.task_id),
            'owner': {'username': self.user.username, 'tenant': self.client.tenant_id},
            'manifest_sha256': manifest_hash, 'settings': run.settings,
            'issued_at': stamp, 'expires_at': stamp + 300}
        envelope = {'version': 1, 'key_id': settings.NODESPLAT_GRANT_KEY_ID, 'payload': payload}
        wire = json.dumps(envelope, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        # Restrict the fixed protocol to ASCII strings, matching the JS validator.
        try:
            wire.decode('utf-8').encode('ascii')
        except UnicodeEncodeError:
            raise OpenSplatError('NodeSplat identifiers must use ASCII characters.')
        envelope['signature'] = base64.urlsafe_b64encode(hmac.new(
            settings.NODESPLAT_GRANT_SECRET.encode('utf-8'), wire, hashlib.sha256).digest()).decode('ascii').rstrip('=')
        return self.request('POST', '/splat/task/new', json={
            'run_id': str(run.id), 'source_task_id': str(run.task_id),
            'manifest_sha256': manifest_hash, 'profile_id': run.backend_profile,
            'settings': run.settings, 'grant': envelope})

    def sync(self, uuid):
        return self.request('POST', '/splat/task/{}/sync'.format(uuid), json={})

    def cancel(self, uuid):
        return self.request('POST', '/splat/task/cancel', json={'uuid': str(uuid)})

    def output(self, uuid, line):
        result = self.request('GET', '/splat/task/{}/output'.format(uuid), params={'line': line})
        lines = result.get('lines')
        cursor = result.get('next_line')
        if (not isinstance(lines, list) or len(lines) > 500 or any(not isinstance(s, str) for s in lines)
                or len('\n'.join(lines).encode('utf-8')) > 262144
                or not isinstance(cursor, int) or cursor != line + len(lines)):
            raise OpenSplatError('Invalid training console response.')
        return {'run_id': str(uuid), 'lines': lines, 'from_line': line, 'next_line': cursor,
                'truncated': bool(result.get('truncated')), 'eof': bool(result.get('eof'))}

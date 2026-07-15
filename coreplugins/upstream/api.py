import logging

import requests
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.api.common import get_and_check_project
from app.plugins import GlobalDataStore
from webodm import settings

logger = logging.getLogger('app.logger')

PLUGIN_NAME = 'upstream'
_ds = GlobalDataStore(PLUGIN_NAME)

TAPIS_BASE_URL = getattr(settings, 'TAPIS_BASE_URL', None) or 'https://portals.tapis.io'


def _config_key(pk):
    return f'project_{pk}_config'


def _get_config(pk):
    return _ds.get_json(_config_key(pk), default={})


def _set_config(pk, data):
    _ds.set_json(_config_key(pk), data)


def _get_user_token(request):
    """Return a valid Tapis JWT for the user, auto-refreshing if expired."""
    try:
        from app.models import TapisOAuth2Token
        tok = TapisOAuth2Token.objects.filter(user=request.user).order_by('-id').first()
        if not tok:
            return None
        if tok.is_valid:
            return tok.access_token
        # Try to refresh
        if tok.refresh_token:
            client = tok.client
            resp = requests.post(
                client.token_url,
                data={
                    'grant_type': 'refresh_token',
                    'client_id': client.client_id,
                    'client_secret': client.client_secret,
                    'refresh_token': tok.refresh_token,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
            )
            if resp.status_code == 200:
                payload = resp.json()
                result = payload.get('result', payload) if isinstance(payload, dict) else payload
                # Extract new access token
                raw_access = result.get('access_token', {})
                new_jwt = raw_access.get('access_token') if isinstance(raw_access, dict) else raw_access
                if new_jwt:
                    raw_refresh = result.get('refresh_token', tok.refresh_token)
                    if isinstance(raw_refresh, dict):
                        raw_refresh = raw_refresh.get('refresh_token', tok.refresh_token)
                    tok.access_token = new_jwt
                    tok.refresh_token = raw_refresh
                    tok.save(update_fields=['access_token', 'refresh_token'])
                    logger.info('Auto-refreshed Tapis token for user %s', request.user.username)
                    return new_jwt
            logger.warning('Token refresh failed for user %s: %s', request.user.username, resp.text[:200])
    except Exception as e:
        logger.warning('_get_user_token error: %s', e)
    return None


def _unwrap_list(data):
    """Extract a list from Upstream API responses regardless of envelope key."""
    if isinstance(data, list):
        return data
    for key in ('items', 'results', 'data', 'stations', 'sensors', 'measurements'):
        if key in data:
            return data[key]
    return []


def _tapis_base():
    base = (getattr(settings, 'WO_TAPIS_BASE_URL', None) or TAPIS_BASE_URL).rstrip('/')
    return base


def _upstream_get(base_url, token, path, params=None):
    if '://' not in base_url:
        base_url = 'https://' + base_url
    url = f'{base_url.rstrip("/")}{path}'
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


KNOWN_UPSTREAM_STACKS = [
    {'pod_id': 'upstreamapi',       'display_name': 'UpStream Base',      'api_url': 'https://upstreamapi.pods.portals.tapis.io'},
    {'pod_id': 'upstreamdevelopapi','display_name': 'UpStream Dev',        'api_url': 'https://upstreamdevelopapi.pods.portals.tapis.io'},
    {'pod_id': 'fluxapi',           'display_name': 'SETx Flux Tower',     'api_url': 'https://fluxapi.pods.portals.tapis.io'},
    {'pod_id': 'vitalapi',          'display_name': 'VITAL',               'api_url': 'https://vitalapi.pods.portals.tapis.io'},
]


def _discover_upstream_pods(token):
    """
    Probe known Upstream API instances and return those reachable with the user's token.
    Falls back to returning all known stacks if every probe fails (e.g. network timeout).
    """
    headers = {'Authorization': f'Bearer {token}'}
    reachable = []
    all_failed = True
    for stack in KNOWN_UPSTREAM_STACKS:
        try:
            resp = requests.get(
                f'{stack["api_url"]}/api/v1/campaigns',
                headers=headers,
                timeout=8,
            )
            # 200 or 401/403 both mean the server is reachable
            all_failed = False
            if resp.status_code in (200, 401, 403):
                reachable.append(stack)
        except requests.exceptions.RequestException:
            pass

    # If every probe timed out (no network to pods), show all so user can still try manually
    return KNOWN_UPSTREAM_STACKS if all_failed else reachable


class ProjectDiscover(APIView):
    """GET — discover available Upstream stacks via Tapis Pods API."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        get_and_check_project(request, pk)
        token = _get_user_token(request)
        if not token:
            try:
                from app.models import TapisOAuth2Client
                client = TapisOAuth2Client.objects.filter(is_active=True).first()
                login_url = f'/api/oauth2/tapis/authorize/{client.client_id}/' if client else None
            except Exception:
                login_url = None
            return Response({'error': 'No Tapis token. Please log in via Tapis first.',
                             'login_url': login_url},
                            status=status.HTTP_401_UNAUTHORIZED)
        stacks = _discover_upstream_pods(token)
        return Response({'stacks': stacks})


class ProjectConnect(APIView):
    """POST {api_url} — validate against Upstream, return campaigns."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        get_and_check_project(request, pk)

        api_url = request.data.get('api_url', '').strip()
        if not api_url:
            return Response({'error': 'api_url is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        token = _get_user_token(request)
        if not token:
            return Response({'error': 'No Tapis token. Please log in via Tapis first.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        try:
            data = _upstream_get(api_url, token, '/api/v1/campaigns')
        except requests.exceptions.RequestException as e:
            logger.warning('Upstream connect failed for project %s: %s', pk, e)
            return Response({'error': f'Could not connect to Upstream: {e}'},
                            status=status.HTTP_502_BAD_GATEWAY)

        campaigns = _unwrap_list(data)
        return Response({'campaigns': campaigns})


class ProjectConfig(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        get_and_check_project(request, pk)
        config = _get_config(pk)
        return Response({k: v for k, v in config.items() if k != 'token'})

    def put(self, request, pk=None):
        get_and_check_project(request, pk, perms=('change_project',))
        current = _get_config(pk)
        incoming = request.data

        current_overlay = current.get('overlay', {}) or {}
        incoming_overlay = incoming.get('overlay', {}) or {}

        new_config = {
            'upstream_base_url': incoming.get('upstream_base_url', current.get('upstream_base_url', '')),
            'campaign_id': incoming.get('campaign_id', current.get('campaign_id')),
            'overlay': {**current_overlay, **incoming_overlay},
        }
        _set_config(pk, new_config)
        return Response({k: v for k, v in new_config.items() if k != 'token'})

    def delete(self, request, pk=None):
        get_and_check_project(request, pk, perms=('change_project',))
        _ds.del_key(_config_key(pk))
        return Response({'deleted': True})


class ProjectCampaigns(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        get_and_check_project(request, pk)
        config = _get_config(pk)
        if not config.get('upstream_base_url'):
            return Response({'error': 'Plugin not configured for this project'},
                            status=status.HTTP_400_BAD_REQUEST)
        token = _get_user_token(request)
        if not token:
            return Response({'error': 'No Tapis token'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = _upstream_get(config['upstream_base_url'], token, '/api/v1/campaigns')
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'campaigns': _unwrap_list(data)})


class ProjectStations(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None):
        get_and_check_project(request, pk)
        config = _get_config(pk)
        campaign_id = config.get('campaign_id')
        if not campaign_id:
            return Response({'error': 'Plugin not configured for this project'},
                            status=status.HTTP_400_BAD_REQUEST)
        token = _get_user_token(request)
        if not token:
            return Response({'error': 'No Tapis token'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            data = _upstream_get(config['upstream_base_url'], token,
                                 f'/api/v1/campaigns/{campaign_id}/stations')
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'stations': _unwrap_list(data)})


class StationMeasurements(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk=None, station_id=None):
        get_and_check_project(request, pk)
        config = _get_config(pk)
        campaign_id = config.get('campaign_id')
        if not campaign_id:
            return Response({'error': 'Plugin not configured for this project'},
                            status=status.HTTP_400_BAD_REQUEST)
        token = _get_user_token(request)
        if not token:
            return Response({'error': 'No Tapis token'}, status=status.HTTP_401_UNAUTHORIZED)

        base = config['upstream_base_url']
        sensor_id = request.query_params.get('sensor_id')

        if not sensor_id:
            try:
                data = _upstream_get(base, token,
                                     f'/api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors')
            except requests.exceptions.RequestException as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
            return Response({'sensors': _unwrap_list(data)})

        qp = request.query_params
        params = {'downsample_threshold': 500}
        if 'start' in qp:
            params['start_date'] = qp['start']
        if 'end' in qp:
            params['end_date'] = qp['end']
        try:
            data = _upstream_get(base, token,
                                 f'/api/v1/campaigns/{campaign_id}/stations/{station_id}/sensors/{sensor_id}/measurements',
                                 params=params)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'measurements': _unwrap_list(data)})

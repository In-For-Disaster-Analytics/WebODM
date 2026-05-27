import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from requests.auth import HTTPBasicAuth

logger = logging.getLogger('app.logger')


class TASConfigurationError(Exception):
    pass


def _setting(name, default=''):
    return getattr(settings, name, default)


def _parse_tas_date(value):
    if not value:
        return None

    if hasattr(value, 'date'):
        return value.date()

    value = str(value).strip()
    parsed_datetime = parse_datetime(value)
    if parsed_datetime:
        if timezone.is_naive(parsed_datetime):
            parsed_datetime = timezone.make_aware(parsed_datetime, timezone.utc)
        return parsed_datetime.date()

    return parse_date(value)


def _allocation_is_active(allocation, today=None):
    today = today or timezone.now().date()
    status = str(allocation.get('status') or '').strip().lower()
    if status and status != 'active':
        return False

    start = _parse_tas_date(allocation.get('start'))
    end = _parse_tas_date(allocation.get('end'))
    if start and today < start:
        return False
    if end and today > end:
        return False

    allocated = allocation.get('computeAllocated')
    used = allocation.get('computeUsed')
    try:
        if allocated is not None and used is not None and float(allocated) <= float(used):
            return False
    except (TypeError, ValueError):
        pass

    return True


def _resource_matches(allocation, resource_filter):
    if not resource_filter:
        return True

    resource = str(allocation.get('resource') or '').strip().lower()
    resource_id = str(allocation.get('resourceId') or '').strip().lower()
    allowed = {str(item).strip().lower() for item in resource_filter if str(item).strip()}
    return resource in allowed or resource_id in allowed


def _tas_credentials():
    base_url = _setting('TAS_URL', '').strip().rstrip('/')
    username = _setting('TAS_SERVICE_USERNAME', '').strip()
    password = _setting('TAS_SERVICE_PASSWORD', '')

    if not base_url or not username or not password:
        raise TASConfigurationError('TAS service credentials are not configured.')

    return base_url, username, password


def _projects_for_user(username):
    base_url, service_username, service_password = _tas_credentials()

    try:
        from pytas.http import TASClient
        client = TASClient(
            baseURL=base_url,
            credentials={'username': service_username, 'password': service_password}
        )
        return client.projects_for_user(username)
    except ImportError:
        pass
    except Exception as e:
        logger.warning('PyTAS project lookup failed, falling back to TAS REST request: %s', e)

    url = '{}/v1/projects/username/{}'.format(base_url, username)
    response = requests.get(
        url,
        headers={'Content-Type': 'application/json'},
        auth=HTTPBasicAuth(service_username, service_password),
        timeout=15
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        return payload

    if payload.get('status') and payload.get('status') != 'success':
        raise RuntimeError(payload.get('message') or 'TAS projects request failed.')

    result = payload.get('result')
    return result if isinstance(result, list) else []


def list_active_allocations(username):
    """
    Return active TAS allocation charge codes for a WebODM/Tapis username.
    """
    if not username:
        return []

    resource_filter = _setting('TAS_RESOURCE_FILTER', [])
    allocations = []

    for project in _projects_for_user(username):
        charge_code = project.get('chargeCode')
        if not charge_code:
            continue

        for allocation in project.get('allocations') or []:
            if not _allocation_is_active(allocation):
                continue
            if not _resource_matches(allocation, resource_filter):
                continue

            allocations.append({
                'chargeCode': charge_code,
                'title': project.get('title') or '',
                'resource': allocation.get('resource') or '',
                'status': allocation.get('status') or '',
                'start': allocation.get('start'),
                'end': allocation.get('end'),
                'computeAllocated': allocation.get('computeAllocated'),
                'computeUsed': allocation.get('computeUsed')
            })

    seen = set()
    deduped = []
    for allocation in allocations:
        charge_code = allocation['chargeCode']
        if charge_code in seen:
            continue
        seen.add(charge_code)
        deduped.append(allocation)

    return deduped


def choose_default_allocation(allocations):
    if not allocations:
        return None

    preferred = _setting('TAS_DEFAULT_ALLOCATION', 'PT2050-DataX')
    for allocation in allocations:
        if allocation.get('chargeCode') == preferred:
            return preferred

    return allocations[0].get('chargeCode')

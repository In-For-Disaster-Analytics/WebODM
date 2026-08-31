import json
import logging
import re
from datetime import datetime

from django.conf import settings as django_settings

logger = logging.getLogger('app.logger')

# WebODM's auto-generated default: "Task of 2025-08-01T12:34:56.789Z"
_DEFAULT_TASK_NAME_RE = re.compile(r'^Task of \d{4}-\d{2}-\d{2}T', re.IGNORECASE)

# Date format used in stats.json: "01/08/2025 at 03:43:49"
_STATS_DATE_FMT = '%d/%m/%Y at %H:%M:%S'

# Maps asset filename → human-readable name
_FRIENDLY_NAMES = {
    'orthophoto.tif': 'Orthophoto (GeoTIFF)',
    'dsm.tif': 'Digital Surface Model (GeoTIFF)',
    'dtm.tif': 'Digital Terrain Model (GeoTIFF)',
    'georeferenced_model.laz': 'Point Cloud (LAZ)',
    'georeferenced_model.las': 'Point Cloud (LAS)',
    'georeferenced_model.ply': 'Point Cloud (PLY)',
    'textured_model.zip': 'Textured 3D Model (ZIP)',
    'report.pdf': 'Processing Report (PDF)',
    'cameras.json': 'Camera Parameters (JSON)',
    'shots.geojson': 'Camera Shots (GeoJSON)',
    'ground_control_points.geojson': 'Ground Control Points (GeoJSON)',
    'all.zip': 'All Outputs (ZIP)',
}

_FORMAT_MAP = {
    '.tif': 'GTiff',
    '.tiff': 'GTiff',
    '.laz': 'LAZ',
    '.las': 'LAS',
    '.ply': 'PLY',
    '.zip': 'ZIP',
    '.pdf': 'PDF',
    '.json': 'JSON',
    '.geojson': 'GeoJSON',
    '.obj': 'OBJ',
    '.csv': 'CSV',
}

# Camera model substrings that indicate multispectral sensors
_MULTISPECTRAL_KEYWORDS = ('m3m', 'm2m', 'micasense', 'parrot', 'sequoia', 'altum', 'rededge', 'p4m')

# Only these assets are meaningful to catalog in CKAN — skip internal/intermediate files
# (cameras.json, shots.geojson, ground_control_points.geojson, etc.)
_PUBLISHABLE_ASSETS = {
    'orthophoto.tif',
    'dsm.tif',
    'dtm.tif',
    'georeferenced_model.laz',
    'georeferenced_model.las',
    'georeferenced_model.ply',
    'textured_model.zip',
    'report.pdf',
    'all.zip',
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _parse_stats_date(date_str):
    """Parse stats.json date string → ISO date (YYYY-MM-DD), or None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, _STATS_DATE_FMT).strftime('%Y-%m-%d')
    except ValueError:
        return None


def _camera_label(cameras_json):
    """
    Extract a readable camera label from cameras.json data.
    Key format: "{make} {model} {width} {height} {projection} {focal}"
    e.g. "dji m3m 5280 3956 brown 0.6666" → "DJI M3M"
    Strips leading "v2 " if present (newer ODM format).
    """
    if not cameras_json:
        return None
    key = next(iter(cameras_json)).strip()
    if key.lower().startswith('v2 '):
        key = key[3:]
    parts = key.split()
    # Last 4 tokens are always: width height projection focal — everything before is the name.
    name_parts = parts[:-4] if len(parts) > 4 else parts[:max(1, len(parts) - 3)]
    return ' '.join(name_parts).upper() if name_parts else None


def _is_multispectral(camera_label):
    if not camera_label:
        return False
    label = camera_label.lower()
    return any(kw in label for kw in _MULTISPECTRAL_KEYWORDS)


def _format_area(area_m2):
    """Format m² into a human-readable string."""
    if area_m2 is None:
        return None
    if area_m2 >= 1_000_000:
        return f'{area_m2 / 1_000_000:.2f} km²'
    if area_m2 >= 10_000:
        return f'{area_m2 / 10_000:.2f} ha'
    return f'{area_m2:.0f} m²'


def _friendly_name(asset):
    return _FRIENDLY_NAMES.get(asset, asset)


def _infer_format(asset):
    from os.path import splitext
    _, ext = splitext(asset)
    return _FORMAT_MAP.get(ext.lower(), ext.lstrip('.').upper() or 'OTHER')


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_user_tapis_jwt(user):
    """Return a valid Tapis JWT for the given Django user from their stored OAuth2 token."""
    from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token

    client = TapisOAuth2Client.objects.filter(is_active=True).first()
    if not client:
        raise RuntimeError('No active Tapis OAuth2 client is configured in WebODM.')

    try:
        token = TapisOAuth2Token.objects.get(user=user, client=client)
    except TapisOAuth2Token.DoesNotExist:
        raise RuntimeError(
            f'No Tapis token found for user {user.username}. '
            'Please log in with Tapis before publishing to CKAN.'
        )

    jwt = token.get_valid_access_token()
    if not jwt:
        raise RuntimeError(
            f'Tapis token for {user.username} is expired or invalid. '
            'Please re-authenticate with Tapis.'
        )
    return jwt


# ── Dataset metadata builders ─────────────────────────────────────────────────

def build_title(task):
    """
    Use the project name as the dataset title. If it's missing or looks like a
    WebODM auto-generated timestamp slug, synthesise a richer placeholder from
    the task metadata so the agent has something meaningful to refine.
    """
    # Prefer project name — projects always have user-assigned names
    project_name = getattr(task.project, 'name', '') or ''
    if project_name:
        return project_name

    # Fall back to task name if it's not the auto-generated timestamp default
    task_name = task.name or ''
    if task_name and not _DEFAULT_TASK_NAME_RE.match(task_name):
        return task_name

    # Auto-generate from available metadata
    stats = task.get_statistics()
    cameras = _load_json(task.assets_path('cameras.json'))
    cam = _camera_label(cameras)

    parts = []
    if cam:
        spectrum = 'Multispectral' if _is_multispectral(cam) else 'RGB'
        parts.append(f'{cam} {spectrum} Survey')
    else:
        parts.append('ODM Survey')

    if task.epsg:
        parts.append(f'EPSG:{task.epsg}')

    date = _parse_stats_date(stats.get('start_date')) or (
        task.created_at.strftime('%Y-%m-%d') if task.created_at else None
    )
    if date:
        parts.append(date)

    return ' — '.join(parts)


def build_notes(task):
    """
    Generate a structured abstract from the metadata already on disk.
    Every sentence is backed by stats.json / cameras.json / task fields.
    """
    stats = task.get_statistics()
    cameras = _load_json(task.assets_path('cameras.json'))
    cam = _camera_label(cameras)
    multispectral = _is_multispectral(cam)
    spectrum = 'multispectral' if multispectral else 'RGB'

    project_name = getattr(task.project, 'name', '') or ''
    assets = task.available_assets or []

    # Line 1: what kind of survey, of what project
    has_ortho = 'orthophoto.tif' in assets
    has_pc = any(a in assets for a in ('georeferenced_model.laz', 'georeferenced_model.las', 'georeferenced_model.ply'))
    has_dsm = 'dsm.tif' in assets
    has_dtm = 'dtm.tif' in assets

    product_parts = []
    if has_ortho:
        product_parts.append(f'{spectrum} orthophoto')
    if has_pc:
        product_parts.append('SfM point cloud')
    if has_dsm:
        product_parts.append('DSM')
    if has_dtm:
        product_parts.append('DTM')
    products = ', '.join(product_parts) if product_parts else 'aerial survey outputs'

    subject = f'of {project_name}' if project_name else ''
    lines = [f'{products.capitalize()} survey {subject}.'.strip()]

    # Line 2: capture date, camera, image count, GSD
    capture_date = _parse_stats_date(stats.get('start_date'))
    gsd = stats.get('gsd')
    image_count = task.images_count or 0

    capture_parts = []
    if capture_date:
        capture_parts.append(f'Captured {capture_date}')
    if cam:
        capture_parts.append(f'with {cam}')
    details = []
    if image_count:
        details.append(f'{image_count} images')
    if gsd:
        details.append(f'GSD {gsd:.2f} cm/px')
    if details:
        capture_parts.append(f'({", ".join(details)})')
    if capture_parts:
        lines.append(' '.join(capture_parts) + '.')

    # Line 3: georeferencing method and CRS
    spatial_refs = stats.get('spatial_refs', [])
    if spatial_refs:
        ref_label = ' + '.join(r.upper() for r in spatial_refs)
        geo_line = f'Georeferenced with {ref_label}'
        if task.epsg:
            geo_line += f', CRS EPSG:{task.epsg}'
        lines.append(geo_line + '.')

    # Line 4: area and processing tool
    area = stats.get('area')
    area_str = _format_area(area)
    closing_parts = []
    if area_str:
        closing_parts.append(f'Coverage area ~{area_str}')
    closing_parts.append('Processed with WebODM/ODM')
    lines.append('. '.join(closing_parts) + '.')

    return '\n'.join(lines)


def build_temporal_coverage(task):
    """Return (start_iso, end_iso) capture dates from stats.json, falling back to task.created_at."""
    stats = task.get_statistics()
    start = _parse_stats_date(stats.get('start_date'))
    end = _parse_stats_date(stats.get('end_date'))
    fallback = task.created_at.strftime('%Y-%m-%d') if task.created_at else None
    if not start:
        start = fallback
    if not end:
        end = fallback
    return start, end


def build_tags(task):
    """Build a list of descriptive tags from the task's outputs and camera."""
    cameras = _load_json(task.assets_path('cameras.json'))
    cam = _camera_label(cameras)
    assets = task.available_assets or []
    stats = task.get_statistics()

    tags = {'drone', 'uas', 'sfm', 'structure-from-motion', 'webodm'}

    if _is_multispectral(cam):
        tags.add('multispectral')
    else:
        tags.add('rgb')

    if 'orthophoto.tif' in assets:
        tags.add('orthophoto')
    if any(a in assets for a in ('georeferenced_model.laz', 'georeferenced_model.las', 'georeferenced_model.ply')):
        tags.add('point-cloud')
    if 'dsm.tif' in assets:
        tags.add('dsm')
        tags.add('elevation')
    if 'dtm.tif' in assets:
        tags.add('dtm')
        tags.add('elevation')

    spatial_refs = stats.get('spatial_refs', [])
    if 'gcp' in spatial_refs:
        tags.add('gcp-controlled')
    if 'gps' in spatial_refs:
        tags.add('gps')

    return sorted(tags)


def _user_display_name(user):
    return user.get_full_name() or user.username or None


def _user_email(user):
    """Return user email: Django field first, then TAS lookup, then None."""
    if user.email:
        return user.email
    return _tas_email(user.username)


def _tas_email(username):
    """
    Look up a TACC user's email via the TAS REST API.
    Mirrors the fallback pattern in app/services/tas_allocations.py.
    Returns None on any failure so publishing is never blocked.
    """
    import requests
    from requests.auth import HTTPBasicAuth
    from django.core.cache import cache

    cache_key = f'tas_email_{username}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != '__none__' else None

    try:
        base_url = getattr(django_settings, 'TAS_URL', '').strip().rstrip('/')
        svc_user = getattr(django_settings, 'TAS_SERVICE_USERNAME', '').strip()
        svc_pass = getattr(django_settings, 'TAS_SERVICE_PASSWORD', '')

        if not (base_url and svc_user and svc_pass):
            return None

        # Try pytas first if available
        try:
            from pytas.http import TASClient
            client = TASClient(baseURL=base_url,
                               credentials={'username': svc_user, 'password': svc_pass})
            result = client.get_user(username=username)
            email = (result or {}).get('email') or None
        except ImportError:
            # Fall back to direct REST call
            resp = requests.get(
                f'{base_url}/v1/users/username/{username}',
                headers={'Content-Type': 'application/json'},
                auth=HTTPBasicAuth(svc_user, svc_pass),
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
            result = payload.get('result') or payload
            email = (result or {}).get('email') or None

        cache.set(cache_key, email if email else '__none__', timeout=3600)
        return email

    except Exception as e:
        logger.warning('TAS email lookup failed for %s: %s', username, e)
        cache.set(cache_key, '__none__', timeout=300)
        return None


def build_dataset(task, publishing_user=None, owner_org=None):
    """
    Build the complete dataset override dict for the agent's analyze call.
    Passes all locally-available structured fields so the agent doesn't need
    to infer them from URLs it cannot fetch.

    author        = project owner (whoever created/owns the data)
    maintainer    = the WebODM user currently publishing to CKAN
    owner_org     = CKAN org slug from a prior publish; omitted when unknown so the
                    agent prompts the user to select one
    Emails passed as None when not populated — the agent must emit _gap_<field>
    per its MANDATORY RULES rather than an empty string.
    """
    start, end = build_temporal_coverage(task)

    owner = getattr(task.project, 'owner', None)
    author = _user_display_name(owner) if owner else None
    author_email = _user_email(owner) if owner else None

    maintainer = _user_display_name(publishing_user) if publishing_user else None
    maintainer_email = _user_email(publishing_user) if publishing_user else None

    dataset = {
        'title': build_title(task),
        'notes': build_notes(task),
        'spatial': bbox_wkt(task.orthophoto_extent),
        'temporal_coverage_start': start,
        'temporal_coverage_end': end,
        'tags': build_tags(task),
        'author': author,
        'author_email': author_email,
        'maintainer': maintainer,
        'maintainer_email': maintainer_email,
    }
    if owner_org:
        dataset['owner_org'] = owner_org
    return dataset


def bbox_wkt(geom):
    """Return a GeoJSON polygon string from a Django geometry field, or None.

    CKAN's spatial extension requires a JSON-encoded GeoJSON object, not WKT.
    """
    import json as _json
    if geom is None:
        return None
    try:
        ext = geom.extent  # (xmin, ymin, xmax, ymax)
        xmin, ymin, xmax, ymax = ext
        return _json.dumps({
            "type": "Polygon",
            "coordinates": [[[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax], [xmin, ymin]]],
        })
    except Exception:
        return None


def build_remote_resources(task, request=None):
    """Build RemoteResource list from task.available_assets plus WebODM viewer links.

    Base URL is derived from the Django request when provided (handles multi-domain
    deployments correctly), falling back to WO_URL. Only meaningful output assets are
    included — intermediate files like cameras.json are excluded.
    """
    if request is not None:
        base = request.build_absolute_uri('/').rstrip('/')
    else:
        base = django_settings.WO_URL.rstrip('/')
    pid = task.project_id
    tid = task.id

    publishable = [a for a in task.available_assets if a in _PUBLISHABLE_ASSETS]

    resources = [
        {
            'url': f'{base}/api/projects/{pid}/tasks/{tid}/download/{asset}',
            'name': _friendly_name(asset),
            'format': _infer_format(asset),
        }
        for asset in publishable
    ]

    resources.append({
        'url': f'{base}/public/task/{tid}/map/',
        'name': 'Web Map Viewer',
        'format': 'HTML',
    })
    resources.append({
        'url': f'{base}/public/task/{tid}/3d/',
        'name': '3D Model Viewer',
        'format': 'HTML',
    })

    return resources


# ── Celery task (must be fully self-contained) ────────────────────────────────

def apply_ckan_publish(task_id, thread_id, user_id):
    """
    Called by Celery via run_function_async. Must be fully self-contained —
    run_function_async serialises only this function's source via eval_async.

    Sends apply+REGISTER to the agent resume endpoint, reads dataset_url
    from the synchronous response, and stores the result in GlobalDataStore.
    """
    from app.plugins.data_store import GlobalDataStore
    from app.models import Task
    from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
    from django.contrib.auth.models import User
    from django.conf import settings as _settings
    from datetime import datetime
    import requests
    import logging

    def _ts():
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    _logger = logging.getLogger('app.logger')
    ds = GlobalDataStore('ckan')
    status_key = f'task_{task_id}_ckan_publish'

    try:
        user = User.objects.get(id=user_id)
        client = TapisOAuth2Client.objects.filter(is_active=True).first()
        if not client:
            raise RuntimeError('No active Tapis OAuth2 client is configured in WebODM.')
        try:
            token_obj = TapisOAuth2Token.objects.get(user=user, client=client)
        except TapisOAuth2Token.DoesNotExist:
            raise RuntimeError(
                f'No Tapis token found for user {user.username}. '
                'Please re-authenticate with Tapis before publishing.'
            )
        jwt = token_obj.get_valid_access_token()
        if not jwt:
            raise RuntimeError(
                f'Tapis token for {user.username} is expired or invalid. Please re-authenticate with Tapis.'
            )

        # Make the task publicly accessible so the CKAN resource URLs work without auth.
        Task.objects.filter(id=task_id).update(public=True)
        _logger.info('CKAN publish: set task %s to public', task_id)

        # Phase 1 — signal the frontend that the dataset record is being created.
        ds.set_json(status_key, {
            'status': 'publishing',
            'phase': 'creating_dataset',
            'message': 'Creating CKAN dataset record…',
            'ckan_url': '',
            'thread_id': thread_id,
            'error': '',
            'timestamp': _ts(),
        })

        # After propose → END there is no pending interrupt, so /resume would return
        # immediately with no work done. Use /runs with session_id so the intake node
        # loads the prior state and the apply node executes the live CKAN write.
        r = requests.post(
            f"{_settings.WO_DSO_AGENT_URL.rstrip('/')}/v1/ckan-registration/runs",
            headers={'Authorization': f'Bearer {jwt}'},
            json={'session_id': thread_id, 'action': 'apply', 'approval': 'REGISTER'},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()

        agent_status = data.get('status', '')
        result_data = data.get('result') or {}
        dataset_url = result_data.get('dataset_url', '')
        owner_org = result_data.get('owner_org', '')
        resource_created = result_data.get('resource_created', 0)
        resource_count = result_data.get('resource_count', 0)

        if not dataset_url:
            error_msg = (
                result_data.get('error')
                or f'Agent returned status={agent_status!r} with no dataset_url'
            )
            raise RuntimeError(error_msg)

        Task.objects.filter(id=task_id).update(ckan_url=dataset_url)

        resource_errors = result_data.get('resource_errors') or []
        if resource_count and resource_created < resource_count:
            resource_msg = (
                f'Registered {resource_created} of {resource_count} resources.'
                + (f' Failures: {"; ".join(str(e) for e in resource_errors[:3])}' if resource_errors else '')
            )
        elif resource_count:
            resource_msg = f'Registered {resource_created} of {resource_count} resources.'
        else:
            resource_msg = ''
        ds.set_json(status_key, {
            'status': 'success',
            'phase': 'complete',
            'message': resource_msg,
            'ckan_url': dataset_url,
            'owner_org': owner_org,
            'thread_id': thread_id,
            'error': '',
            'timestamp': _ts(),
        })
        _logger.info('CKAN publish succeeded for task %s: %s (%s)', task_id, dataset_url, resource_msg)

    except Exception as e:
        _logger.exception('CKAN apply failed for task %s', task_id)
        ds.set_json(status_key, {
            'status': 'error',
            'phase': 'failed',
            'message': '',
            'ckan_url': '',
            'thread_id': thread_id,
            'error': str(e),
            'timestamp': _ts(),
        })

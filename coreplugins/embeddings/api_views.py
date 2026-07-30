"""
DRF endpoints for the task-detail panel actions (design spec "API Endpoints"
> "Task-detail panel (per-task)"). URL routing/nesting and (for task-scoped
views) task-level permission resolution are real, via
app.plugins.views.TaskView (== app.api.tasks.TaskNestedView), the same base
class coreplugins/ckan and coreplugins/objdetect already use.

Fourth implementation increment (Decision 37, superseded by Decision 45):
TaskEmbedView.post() genuinely queues embed-generate -- as of Decision 45,
this submits a real Tapis Job against TACC's `ls6` system
(WO_EMBED_GENERATE_APP_ID, webodm/settings.py), not a Tapis Actor (Abaco's
worker pool cannot provision for this workload's image size on this
tenant -- confirmed by live testing, see design spec Decision 45).
model-train still uses its registered Actor (WO_MODEL_ACTOR_ID) --
untouched by Decision 45, no evidence of the same problem since it isn't
implemented yet. embeddings_client.apply_embed_generate() is a real,
self-contained Celery task (queued via run_function_async) that authorizes
the call with the triggering user's stored TapisOAuth2Token, mirroring
coreplugins/ckan/publisher.py's apply_ckan_publish() exactly (see
embeddings_client.py's own docstring, and design spec Decisions 37/45). Site
selection/creation, the Decision 24/27 zoom-lock check, and real
`visits`/`tile_observations` reads/writes (Decision 33/34) are unchanged from
the prior increment. TaskLabelView remains real from an earlier increment,
backed by label_studio_client.py. model-train (queue_model_train) and the
DSO STAC API remain explicitly NOT implemented; see embeddings_client.py's
and stac_client.py's (not created yet) own docstrings.

Fifth implementation increment (Decision 38 -- the first real frontend
component, EmbeddingsPanel.jsx): adds `SitesView`
(`GET /api/plugins/embeddings/sites`), a real, NOT task-scoped endpoint --
sites are global to the whole embeddings system, matching how
`LabelClassesView` below is already registered as a non-task-scoped route.
Closes a real gap: `embeddings_client.list_sites()` has worked against the
live embeddingsdb since Decision 34, but was never exposed via an API
endpoint until now -- needed so the new task-panel UI's "existing site"
dropdown has something real to populate itself from.
"""

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from app.api import tiler
from app.plugins.views import TaskView
from app.plugins.worker import run_function_async
from app.raster_utils import ZOOM_EXTRA_LEVELS
from rio_tiler.io import COGReader

from . import embeddings_client
from . import label_studio_client
from . import tile_math

logger = logging.getLogger('app.logger')


class IsEmbeddingsAdmin(permissions.BasePermission):
    """
    Design spec Decision 46: the embeddings plugin is restricted to
    superusers only while it's still being validated in production, before
    being made available to all users. Real 403 enforcement at the DRF
    permission layer -- not just hiding UI -- since `TaskView` (==
    `app.api.tasks.TaskNestedView`) deliberately sets its own
    `permission_classes = (AllowAny,)` for its task-visibility logic
    (`get_and_check_task()`'s own public/guardian checks), this class is
    applied on top, overriding that default on each view that opts in.
    Deliberately NOT applied to `LabelStudioWebhookView` -- that endpoint is
    called server-to-server by Label Studio itself (shared-secret auth,
    Decisions 10/29), not by a WebODM user, so "admin only" doesn't apply.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def _compute_max_zoom(task):
    """
    Decision 46: the zoom level for `POST .../embed` is no longer a
    client-supplied value -- it's always the task's own orthophoto's
    highest available resolution, computed the same way WebODM's own
    `TileJson` view does (`app/api/tiler.py`: `get_zoom_safe()` +
    `ZOOM_EXTRA_LEVELS`), so it matches exactly what `tiles.json` itself
    reports (and therefore what `embed_generate.webodm_client.
    get_tile_coverage()` reads on the Actor/ls6 side).

    Raises FileNotFoundError if the task has no orthophoto yet.
    """
    raster_path = tiler.get_raster_path(task, 'orthophoto')
    if not os.path.isfile(raster_path):
        raise FileNotFoundError(
            'This task has no orthophoto yet -- cannot determine a zoom level.'
        )
    with COGReader(raster_path) as src:
        _minzoom, maxzoom = tiler.get_zoom_safe(src)
    return maxzoom + ZOOM_EXTRA_LEVELS


def _compute_effective_zoom(site_id, task):
    """
    Decision 49 (architect review finding): the site-zoom lock (Decision
    24/27) is the single most load-bearing invariant in embeddingsdb's
    schema -- every tile_grid row for a site must share one zoom, or
    embed-generate's and the labeling flow's tile_grid rows silently fork
    into two incompatible grids for the same site. TaskEmbedView already
    enforces this (compute task-max, then check-and-409 against the site's
    lock). TaskTilesView/TaskLabelView need the same invariant applied the
    other way around: if the site already has a locked zoom, USE it
    (there's no zoom_override concept for labeling); only fall back to this
    task's own highest available resolution for a genuinely new site (no
    tile_grid rows yet).

    Raises FileNotFoundError (via _compute_max_zoom) if the task has no
    orthophoto yet and no site zoom exists to fall back on.
    """
    if site_id:
        existing_zoom = embeddings_client.get_site_zoom(site_id)
        if existing_zoom is not None:
            return existing_zoom
    return _compute_max_zoom(task)


def _derive_project_webhook_secret(project_id):
    """
    Derives a PER-PROJECT Label Studio webhook secret from the server-wide
    WO_LABEL_STUDIO_WEBHOOK_SECRET (security-review finding, Decision 49):
    a single static secret sent identically to every Label Studio project
    would let anyone who obtains it (e.g. a Label Studio admin who can view
    a project's registered webhook headers) forge a call for a DIFFERENT
    project than the one it leaked from. HMAC-SHA256(server secret, project
    id) instead -- computed fresh both when registering the webhook
    (TaskLabelView.post()) and when verifying an incoming call
    (LabelStudioWebhookView.post()), so no per-project secret needs to be
    stored anywhere.

    Raises ValueError if WO_LABEL_STUDIO_WEBHOOK_SECRET is unset/empty --
    callers MUST treat that as "webhook auth is not configured" (503), never
    silently derive a secret from an empty key.
    """
    server_secret = (getattr(settings, 'WO_LABEL_STUDIO_WEBHOOK_SECRET', '') or '').strip()
    if not server_secret:
        raise ValueError('WO_LABEL_STUDIO_WEBHOOK_SECRET is not configured.')
    return hmac.new(
        server_secret.encode('utf-8'),
        str(project_id).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _not_implemented(message):
    return Response(
        {'error': message},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


class TaskTilesView(TaskView):
    """
    GET /api/plugins/embeddings/task/{task_pk}/tiles?site_id=<optional>

    Design spec: candidate tiles for labeling (orthophoto extent, at the
    same zoom `embed` would use for this task), for the "Label a Sample" map
    picker. Distinct from `embed`, which covers every tile at a zoom with no
    picker (Decision 9) -- this endpoint is the selective, human-in-the-loop
    side.

    Real in this increment: enumerates every (x, y) at the effective zoom
    (Decision 49's site-zoom-lock-aware `_compute_effective_zoom()`) whose
    bbox overlaps the task's own orthophoto extent (`task.orthophoto_extent`,
    the same field WebODM's own `TileJson` view reads), filtered to real
    coverage via rio_tiler's `COGReader.tile_exists(z, x, y)` -- the same
    check WebODM's own `Tiles` view already uses (Decision 9). If `site_id`
    is supplied and a visit already exists for (site_id, this task), each
    tile also reports its real `tile_observation_id` where one already
    exists (already labeled and/or embedded), plus its CURRENT
    `label_value`/`label_color` if one has been applied (Decision 50: the
    map-based paint UI renders each tile in its real, current label color,
    not just an "observed or not" flag). Omitting `site_id` (a genuinely
    new site, not chosen yet) returns the raw candidate list with no
    observation/label linkage.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request, pk=None):
        task = self.get_and_check_task(request, pk)
        site_id = request.query_params.get('site_id') or None

        try:
            zoom = _compute_effective_zoom(site_id, task)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        extent = task.orthophoto_extent
        if extent is None:
            return Response(
                {'error': 'This task has no orthophoto extent yet -- cannot list candidate tiles.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bounds = extent.extent  # (west, south, east, north), SRID 4326

        observed = {}
        if site_id:
            try:
                visit_id = embeddings_client.get_visit_for_site_and_task(site_id, str(task.id))
                observed = embeddings_client.get_tile_observations_for_visit(visit_id)
            except embeddings_client.EmbeddingsDBConfigError as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except embeddings_client.EmbeddingsDBError as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        raster_path = tiler.get_raster_path(task, 'orthophoto')
        tiles = []
        with COGReader(raster_path) as src:
            for x, y in tile_math.candidate_tiles(bounds, zoom):
                if not src.tile_exists(zoom, x, y):
                    continue
                info = observed.get((x, y)) or {}
                tiles.append({
                    'x': x,
                    'y': y,
                    'tile_observation_id': info.get('tile_observation_id'),
                    'label_value': info.get('label_value'),
                    'label_color': info.get('label_color'),
                })

        return Response({'zoom': zoom, 'tiles': tiles}, status=status.HTTP_200_OK)


class TaskLabelView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/label

    Design spec: calls label_studio_client.py to create a Label Studio
    project, import the selected tiles as tasks, and register a webhook --
    then returns the real deep-link URL. See "Label Studio Integration: Full
    Mechanics" and Decisions 10/32.

    Decision 49: labeling has its own site selector (`site_id`/
    `new_site_name` in the request body, mirroring `TaskEmbedView` exactly),
    decoupled from whether embed-generate has run for this task. Each
    selected tile ("z/x/y") gets a REAL `tile_grid`/`tile_observations` row
    (`embeddings_client.get_or_create_tile_grid()`/
    `get_or_create_tile_observation()`, created on demand -- no embedding
    required or implied) instead of the earlier placeholder that sent the
    raw tile id string as `meta.tile_observation_id`. `label_config` is now
    built from the real, site-scoped `label_classes` table
    (`embeddings_client.list_label_classes()`) instead of a hardcoded
    7-class placeholder. After import, real Label Studio task ids are
    recovered via `label_studio_client.list_tasks()` (matched back by
    `meta.tile_observation_id`, not by trusting import order) and recorded
    in `label_studio_tasks` (Decision 29/49) -- what the webhook handler
    checks instead of trusting an incoming payload's own claims.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        task = self.get_and_check_task(request, pk)

        if not (getattr(settings, 'WO_LABEL_STUDIO_URL', '') and
                getattr(settings, 'WO_LABEL_STUDIO_API_TOKEN', '')):
            return Response(
                {'error': (
                    'Label Studio integration is not configured on this '
                    'WebODM instance -- WO_LABEL_STUDIO_URL and/or '
                    'WO_LABEL_STUDIO_API_TOKEN are not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Security-review finding (Decision 49): fail closed here too, not
        # just in the webhook handler -- never register a webhook whose
        # secret we can't actually verify later.
        if not getattr(settings, 'WO_LABEL_STUDIO_WEBHOOK_SECRET', ''):
            return Response(
                {'error': (
                    'Label Studio webhook verification is not configured on '
                    'this WebODM instance -- WO_LABEL_STUDIO_WEBHOOK_SECRET '
                    'is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        tile_ids = request.data.get('tile_ids') or []
        if not tile_ids:
            return Response(
                {'error': 'tile_ids is required and must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Site: required, same pattern as TaskEmbedView (Decision 27/49) ---
        site_id = request.data.get('site_id')
        new_site_name = request.data.get('new_site_name')
        if not site_id and not new_site_name:
            return Response(
                {'error': (
                    'Select an existing site, or provide a name for a new '
                    'one -- a site can\'t be inferred automatically from the '
                    'task or project.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            zoom = _compute_effective_zoom(site_id, task)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # --- Parse every tile id up front so a malformed one 400s before any writes ---
        parsed_tiles = []
        for tile_id in tile_ids:
            parts = str(tile_id).split('/')
            if len(parts) != 3 or not all(p.lstrip('-').isdigit() for p in parts):
                return Response(
                    {'error': f'Invalid tile id {tile_id!r} -- expected "z/x/y".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            z, x, y = (int(p) for p in parts)
            if z != zoom:
                return Response(
                    {'error': (
                        f'Tile {tile_id} is at zoom {z}, but this site\'s '
                        f'effective zoom is {zoom} -- select tiles from '
                        f'GET .../tiles, which always reports the effective zoom.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            parsed_tiles.append((z, x, y))

        try:
            if not site_id:
                site_id = embeddings_client.create_site(new_site_name)

            capture_date = request.data.get('capture_date') or (
                task.created_at.date() if task.created_at else None
            )
            visit_id = embeddings_client.get_or_create_visit(
                site_id, str(task.id), task.project_id, capture_date=capture_date,
            )

            label_classes = embeddings_client.list_label_classes(site_id)

            # --- Real tile_grid/tile_observations rows, one per selected tile ---
            # (Decision 49: created on demand, independent of embed-generate.)
            tile_observation_ids = []
            for z, x, y in parsed_tiles:
                bounds_wkt = tile_math.tile_bounds_wkt(x, y, zoom)
                tile_grid_id = embeddings_client.get_or_create_tile_grid(site_id, zoom, x, y, bounds_wkt)
                center_lat, _center_lon = tile_math.tile_center_lonlat(x, y, zoom)
                pixel_size = tile_math.meters_per_pixel(zoom, center_lat)
                tile_observation_ids.append(
                    embeddings_client.get_or_create_tile_observation(tile_grid_id, visit_id, pixel_size)
                )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        task_name = task.name or 'unnamed'
        title = f'{task_name} — {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'
        label_config = label_studio_client.build_label_config(label_classes)

        base_url = request.build_absolute_uri('/').rstrip('/')
        project_id_str, task_id_str = str(task.project_id), str(task.id)

        ls_tasks = [
            {
                'data': {
                    'image': (
                        f'{base_url}/api/projects/{project_id_str}/tasks/{task_id_str}'
                        f'/orthophoto/tiles/{z}/{x}/{y}.png'
                    ),
                },
                'meta': {
                    'tile_observation_id': tobs_id,
                    'webodm_task_id': task_id_str,
                },
            }
            for (z, x, y), tobs_id in zip(parsed_tiles, tile_observation_ids)
        ]

        try:
            project = label_studio_client.create_project(title=title, label_config=label_config)
            project_id = project.get('id')
            if project_id is None:
                raise label_studio_client.LabelStudioAPIError(
                    f'Label Studio project creation did not return an id: {project!r}'
                )

            label_studio_client.import_tasks(project_id, ls_tasks)

            project_secret = _derive_project_webhook_secret(project_id)
            webhook_url = f'{base_url}/api/plugins/embeddings/labelstudio-webhook'
            label_studio_client.register_webhook(project_id, webhook_url, project_secret)

            deep_link_url = label_studio_client.project_url(project_id)
        except label_studio_client.LabelStudioConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except label_studio_client.LabelStudioAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            # _derive_project_webhook_secret() -- should be unreachable given
            # the WO_LABEL_STUDIO_WEBHOOK_SECRET check above, but never
            # register a webhook without a real secret if it somehow is.
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # --- Record the Decision 29/49 scope ledger ---
        # Recovers each task's REAL Label Studio-assigned id by listing the
        # project back and matching on meta.tile_observation_id (which we
        # set ourselves, above) -- not by trusting import_tasks()'s own
        # response to preserve submission order (not documented anywhere in
        # Label Studio's API reference as an ordering guarantee). A failure
        # here doesn't fail the request -- the project/tasks already exist
        # in Label Studio by this point -- but IS logged loudly, since a
        # missing row here means the webhook will (correctly) reject that
        # tile's future annotations until this is investigated.
        try:
            listing = label_studio_client.list_tasks(project_id, page_size=max(len(ls_tasks), 100))
            ls_task_list = listing.get('tasks') or []
            total = listing.get('total', len(ls_task_list))
            if total > len(ls_task_list):
                logger.error(
                    'Label Studio project %s has more tasks (%s) than this '
                    'page fetched (%d) -- some tile_observation_id scope '
                    'mappings (Decision 29) were not recorded.',
                    project_id, total, len(ls_task_list),
                )
            for ls_task in ls_task_list:
                tobs_id = (ls_task.get('meta') or {}).get('tile_observation_id')
                ls_task_id = ls_task.get('id')
                if tobs_id and ls_task_id is not None:
                    embeddings_client.register_label_studio_task(project_id, ls_task_id, tobs_id)
        except (label_studio_client.LabelStudioAPIError, embeddings_client.EmbeddingsDBError):
            logger.exception(
                'Failed to record label_studio_tasks rows for project=%s -- '
                'webhook scope validation (Decision 29) will reject this '
                'project\'s annotations until this is fixed.',
                project_id,
            )

        return Response({
            'project_id': project_id,
            'label_studio_url': deep_link_url,
            'tile_count': len(ls_tasks),
        }, status=status.HTTP_200_OK)


class TaskLabelApplyView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/labels/apply

    Design spec, Decision 50: "paint a label directly in the modal" --
    instead of sending an unlabeled batch to Label Studio for a human to
    annotate there (TaskLabelView, below -- kept, for open-ended human
    annotation), this applies ONE chosen label_classes value to a batch of
    tiles immediately. Creates real tile_grid/tile_observations rows (same
    as TaskLabelView), ensures a Label Studio project + imported tasks
    exist for those tiles -- reusing ONE project across a whole paint
    session via the optional `label_studio_project_id` request field, not
    one project per drag stroke -- creates a REAL annotation on each tile
    via `label_studio_client.create_annotation()` (so Label Studio remains
    the true system of record, per the user's own "fully integrate Label
    Studio through WebODM" framing), and immediately upserts the
    corresponding `labels` row locally rather than waiting on the
    ANNOTATION_CREATED webhook round-trip (which still fires harmlessly
    and re-upserts the same value when it arrives).
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        task = self.get_and_check_task(request, pk)

        if not (getattr(settings, 'WO_LABEL_STUDIO_URL', '') and
                getattr(settings, 'WO_LABEL_STUDIO_API_TOKEN', '')):
            return Response(
                {'error': (
                    'Label Studio integration is not configured on this '
                    'WebODM instance -- WO_LABEL_STUDIO_URL and/or '
                    'WO_LABEL_STUDIO_API_TOKEN are not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not getattr(settings, 'WO_LABEL_STUDIO_WEBHOOK_SECRET', ''):
            return Response(
                {'error': (
                    'Label Studio webhook verification is not configured on '
                    'this WebODM instance -- WO_LABEL_STUDIO_WEBHOOK_SECRET '
                    'is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        value = request.data.get('value')
        tile_ids = request.data.get('tile_ids') or []
        if not value:
            return Response({'error': 'value is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not tile_ids:
            return Response(
                {'error': 'tile_ids is required and must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site_id = request.data.get('site_id')
        new_site_name = request.data.get('new_site_name')
        if not site_id and not new_site_name:
            return Response(
                {'error': (
                    'Select an existing site, or provide a name for a new '
                    'one -- a site can\'t be inferred automatically from the '
                    'task or project.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            zoom = _compute_effective_zoom(site_id, task)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        parsed_tiles = []
        for tile_id in tile_ids:
            parts = str(tile_id).split('/')
            if len(parts) != 3 or not all(p.lstrip('-').isdigit() for p in parts):
                return Response(
                    {'error': f'Invalid tile id {tile_id!r} -- expected "z/x/y".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            z, x, y = (int(p) for p in parts)
            if z != zoom:
                return Response(
                    {'error': (
                        f'Tile {tile_id} is at zoom {z}, but this site\'s '
                        f'effective zoom is {zoom} -- select tiles from '
                        f'GET .../tiles, which always reports the effective zoom.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            parsed_tiles.append((z, x, y))

        try:
            if not site_id:
                site_id = embeddings_client.create_site(new_site_name)

            # Reject an unrecognized label value up front, before any
            # writes -- same posture as the webhook handler.
            valid_values = {lc['value'] for lc in embeddings_client.list_label_classes(site_id)}
            if value not in valid_values:
                return Response(
                    {'error': f'{value!r} does not match any registered label class for this site.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            capture_date = request.data.get('capture_date') or (
                task.created_at.date() if task.created_at else None
            )
            visit_id = embeddings_client.get_or_create_visit(
                site_id, str(task.id), task.project_id, capture_date=capture_date,
            )

            tile_observation_ids = []
            for z, x, y in parsed_tiles:
                bounds_wkt = tile_math.tile_bounds_wkt(x, y, zoom)
                tile_grid_id = embeddings_client.get_or_create_tile_grid(site_id, zoom, x, y, bounds_wkt)
                center_lat, _center_lon = tile_math.tile_center_lonlat(x, y, zoom)
                pixel_size = tile_math.meters_per_pixel(zoom, center_lat)
                tile_observation_ids.append(
                    embeddings_client.get_or_create_tile_observation(tile_grid_id, visit_id, pixel_size)
                )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        base_url = request.build_absolute_uri('/').rstrip('/')
        project_id_str, task_id_str = str(task.project_id), str(task.id)

        try:
            # --- Reuse one Label Studio project across a whole paint session ---
            project_id = request.data.get('label_studio_project_id')
            if not project_id:
                title = (
                    f'{task.name or "unnamed"} — paint session '
                    f'{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'
                )
                label_classes = embeddings_client.list_label_classes(site_id)
                label_config = label_studio_client.build_label_config(label_classes)
                project = label_studio_client.create_project(title=title, label_config=label_config)
                project_id = project.get('id')
                if project_id is None:
                    raise label_studio_client.LabelStudioAPIError(
                        f'Label Studio project creation did not return an id: {project!r}'
                    )

                project_secret = _derive_project_webhook_secret(project_id)
                webhook_url = f'{base_url}/api/plugins/embeddings/labelstudio-webhook'
                label_studio_client.register_webhook(project_id, webhook_url, project_secret)

            # --- Import any tiles not already imported into THIS project ---
            to_import = []
            for (z, x, y), tobs_id in zip(parsed_tiles, tile_observation_ids):
                if embeddings_client.get_label_studio_task_id(project_id, tobs_id) is not None:
                    continue
                image_url = (
                    f'{base_url}/api/projects/{project_id_str}/tasks/{task_id_str}'
                    f'/orthophoto/tiles/{z}/{x}/{y}.png'
                )
                to_import.append({
                    'data': {'image': image_url},
                    'meta': {'tile_observation_id': tobs_id, 'webodm_task_id': task_id_str},
                })

            if to_import:
                label_studio_client.import_tasks(project_id, to_import)
                listing = label_studio_client.list_tasks(project_id, page_size=max(len(to_import), 100))
                ls_task_list = listing.get('tasks') or []
                if listing.get('total', len(ls_task_list)) > len(ls_task_list):
                    logger.error(
                        'Label Studio project %s has more tasks (%s) than this '
                        'page fetched (%d) during paint-import.',
                        project_id, listing.get('total'), len(ls_task_list),
                    )
                for ls_task in ls_task_list:
                    tobs_id = (ls_task.get('meta') or {}).get('tile_observation_id')
                    ls_task_id = ls_task.get('id')
                    if tobs_id and ls_task_id is not None:
                        embeddings_client.register_label_studio_task(project_id, ls_task_id, tobs_id)

            # --- Create a real annotation + upsert the label, per tile ---
            result = [{
                'from_name': 'label',
                'to_name': 'image',
                'type': 'choices',
                'value': {'choices': [value]},
            }]
            applied = 0
            for tobs_id in tile_observation_ids:
                ls_task_id = embeddings_client.get_label_studio_task_id(project_id, tobs_id)
                if ls_task_id is None:
                    logger.error(
                        'No Label Studio task id for tile_observation_id=%s in '
                        'project=%s after import -- skipping annotation for this tile.',
                        tobs_id, project_id,
                    )
                    continue
                annotation = label_studio_client.create_annotation(ls_task_id, result)
                embeddings_client.upsert_label(
                    tobs_id, 'category', value, source='label_studio',
                    created_by=request.user.username,
                    label_studio_annotation_id=annotation.get('id'),
                )
                applied += 1
        except label_studio_client.LabelStudioConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except label_studio_client.LabelStudioAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'site_id': site_id,
            'label_studio_project_id': project_id,
            'label_studio_url': label_studio_client.project_url(project_id),
            'applied_count': applied,
        }, status=status.HTTP_200_OK)


class TaskLabelClearView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/labels/clear

    Design spec, Decision 53: the "eraser" -- undoes a mistakenly painted
    label. Body: `{"tile_observation_ids": [...]}` -- these are already
    real, resolved ids (from `GET .../tiles`'s own `tile_observation_id`
    field), not "z/x/y" strings, since there's nothing left to resolve
    (site/zoom/tile_grid all already exist by the time a tile has a label
    to erase).

    For each id: looks up the CURRENT label (embeddings_client.
    get_current_label()); if it came from Label Studio, deletes the EXACT
    annotation that created it (label_studio_client.delete_annotation(),
    using the id tracked in labels.label_studio_annotation_id -- not every
    annotation on the task, since one task can accumulate several across
    repeated repaints) as a best-effort call -- a Label Studio failure is
    logged and does NOT block clearing WebODM's own local state, matching
    this plugin's existing "local state is primary, Label Studio is kept
    in sync best-effort" posture (e.g. TaskLabelView's label_studio_tasks
    recording). Then deletes the local `labels` row(s) unconditionally.

    Tiles with no current label are silently skipped (nothing to clear),
    not an error.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)

        tile_observation_ids = request.data.get('tile_observation_ids') or []
        if not tile_observation_ids:
            return Response(
                {'error': 'tile_observation_ids is required and must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cleared = 0
        try:
            for tobs_id in tile_observation_ids:
                current = embeddings_client.get_current_label(tobs_id)
                if not current:
                    continue

                annotation_id = current.get('label_studio_annotation_id')
                if annotation_id is not None:
                    try:
                        label_studio_client.delete_annotation(annotation_id)
                    except label_studio_client.LabelStudioAPIError:
                        logger.exception(
                            'Failed to delete Label Studio annotation %s for '
                            'tile_observation_id=%s -- clearing WebODM\'s own '
                            'label anyway.', annotation_id, tobs_id,
                        )

                embeddings_client.delete_labels_for_tile_observation(tobs_id)
                cleared += 1
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({'cleared_count': cleared}, status=status.HTTP_200_OK)


class TaskEmbedView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/embed

    Design spec: queues embed-generate over every valid (z, x, y) at the
    task's orthophoto's own highest available resolution -- no tile_ids,
    whole-task by design (Decision 9). Requires a user-chosen site_id
    (Decision 27) and honors zoom_override against a site's locked zoom
    (Decision 24/27).

    Decision 46: zoom is no longer a client-supplied value -- `_compute_max_zoom()`
    always uses the task's own orthophoto's real highest resolution (the
    same computation `TileJson` itself uses), so embeddings are never
    generated at a lower resolution than what's actually available.

    Real in this increment (against the live embeddingsdb, Decision 33, and
    the real, registered embed-generate ls6 Tapis App, Decision 45): site
    resolution (existing site_id or new_site_name -> create_site()), the
    Decision 24/27 zoom-lock check via get_site_zoom(), the real `visits`
    row via get_or_create_visit(), and now the Job submission itself --
    embeddings_client.apply_embed_generate() is queued via
    run_function_async() (Celery), authorized by the requesting user's
    stored Tapis OAuth2 token (see embeddings_client.py's own docstring).
    embed-generate runs as a Tapis Job on TACC's `ls6` (Decision 45), not an
    Actor -- Abaco's worker pool cannot provision for this workload's image
    size on this tenant, confirmed by live testing. The submission happens
    asynchronously -- this view does not block on it or know its outcome;
    it returns 202 once queuing succeeds, same as the CKAN plugin's own
    async-publish endpoint. A `visits` row is created (via
    get_or_create_visit(), above) regardless of whether the queued Job
    submission itself later succeeds -- a user has genuinely committed to
    embedding a task at a site once that row exists.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        task = self.get_and_check_task(request, pk)

        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not getattr(settings, 'WO_EMBED_GENERATE_APP_ID', ''):
            return Response(
                {'error': (
                    'The embed-generate ls6 Tapis App is not configured on '
                    'this WebODM instance -- WO_EMBED_GENERATE_APP_ID is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # --- Zoom: always the task's own highest available resolution (Decision 46) ---
        try:
            zoom = _compute_max_zoom(task)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # --- Validate site_id / new_site_name (required -- Decision 27: user-chosen, never inferred) ---
        site_id = request.data.get('site_id')
        new_site_name = request.data.get('new_site_name')
        if not site_id and not new_site_name:
            return Response(
                {'error': (
                    'Select an existing site, or provide a name for a new '
                    'one -- a site can\'t be inferred automatically from the '
                    'task or project.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        zoom_override = bool(request.data.get('zoom_override', False))

        try:
            if not site_id:
                site_id = embeddings_client.create_site(new_site_name)

            # --- Decision 24/27: zoom-lock check ---
            existing_zoom = embeddings_client.get_site_zoom(site_id)
            if existing_zoom is not None and existing_zoom != zoom and not zoom_override:
                return Response(
                    {'error': (
                        f'This site already has embeddings at zoom {existing_zoom}. '
                        f'This task\'s highest available resolution is zoom {zoom}, '
                        f'which won\'t line up with those existing tiles -- '
                        f'comparisons across visits at this site could be affected.'
                    )},
                    status=status.HTTP_409_CONFLICT,
                )

            capture_date = request.data.get('capture_date') or (
                task.created_at.date() if task.created_at else None
            )
            visit_id = embeddings_client.get_or_create_visit(
                site_id, str(task.id), task.project_id, capture_date=capture_date,
            )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # --- Job submission: genuinely queued now (Decisions 37/45) ---
        # Fire-and-forget, same shape as the CKAN plugin's own async publish
        # (coreplugins/ckan/api_views.py's PublishView.post() -> run_function_async
        # (publisher.apply_ckan_publish, ...)) -- this view does not wait on
        # or know the outcome of the queued Job submission; a real `visits` row
        # already exists by this point regardless of how that call turns out.
        run_function_async(
            embeddings_client.apply_embed_generate,
            str(task.id),
            request.user.id,
            site_id,
            visit_id,
            zoom,
            request.data.get('encoder', 'clay-v1.5-large-rgb'),
            task.project_id,
            zoom_override,
        )

        return Response(
            {'site_id': site_id, 'visit_id': visit_id},
            status=status.HTTP_202_ACCEPTED,
        )


class TaskEmbedStatusView(TaskView):
    """
    GET /api/plugins/embeddings/task/{task_pk}/embed-status

    Design spec: polled by the frontend while embed-generate runs; includes
    total tile count at the selected zoom.

    Real in this increment: looks up whether a `visits` row already exists
    for this task (embeddings_client.get_visit_for_task -- a read-only
    lookup, distinct from get_or_create_visit(), so polling this endpoint
    never creates database rows) and, if so, the real
    count_tile_observations() result. Reports a clear "not started" response
    if embed has never been triggered for this task.

    NOT real in this increment: the total tile count expected at the
    selected zoom (M in "N of M tiles processed") -- that requires
    enumerating WebODM's own tiler coverage (app/api/tiler.py, Decision 9),
    which is out of scope for this increment's DB-layer work. Only N (tiles
    actually processed so far) is real here.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request, pk=None):
        task = self.get_and_check_task(request, pk)

        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            visit = embeddings_client.get_visit_for_task(str(task.id))
            if visit is None:
                return Response({
                    'status': 'not_started',
                    'site_id': None,
                    'visit_id': None,
                    'tile_observation_count': 0,
                }, status=status.HTTP_200_OK)

            tile_count = embeddings_client.count_tile_observations(visit['id'])
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'status': 'running',
            'site_id': visit['site_id'],
            'visit_id': visit['id'],
            'tile_observation_count': tile_count,
        }, status=status.HTTP_200_OK)


class TaskPublishToSTACView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/publish-to-stac

    Design spec: user-triggered, only available when task.public or
    task.project.public is true (Decision 21); creates/reuses a per-site
    STAC collection + item using the requesting user's own Tapis JWT
    (Decision 20), asset href reuses WebODM's own download endpoint
    (Decision 23).
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Publish to STAC is not implemented yet -- stac_client.py does not '
            'exist in this increment. See design spec Decisions 20, 21, 23.'
        )


class TaskRetractFromSTACView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/retract-from-stac

    Design spec, Decision 31: available once a task has been published
    (stac_item_id set); calls DELETE on the DSO STAC API and clears the
    visit's stac_collection_id/stac_item_id.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Retract from STAC is not implemented yet. See design spec '
            'Decision 31.'
        )


class TaskLabelsImportGeoJSONView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/labels/import-geojson

    Design spec, Decision 12: accepts a GeoJSON FeatureCollection, spatially
    matches features to tile_grid cells, flags unrecognized label values for
    confirm/remap, then upserts `labels` rows with source='geojson_import'.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'GeoJSON label import is not implemented yet -- depends on the '
            'embeddingsdb Pod (tile_grid/labels tables). See design spec '
            'Decision 12.'
        )


class _LabelStudioWebhookThrottle(SimpleRateThrottle):
    """
    Per-IP ceiling on this AllowAny, server-to-server endpoint -- cheap
    insurance against a misbehaving Label Studio retry loop or replay abuse
    (security review finding, Decision 49). Not a substitute for the
    fail-closed secret check below, just a backstop against hammering.
    """
    scope = 'labelstudio_webhook'

    def get_rate(self):
        return '120/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LabelStudioWebhookView(APIView):
    """
    POST /api/plugins/embeddings/labelstudio-webhook

    Design spec, Decisions 10/29/49: receives ANNOTATION_CREATED/
    ANNOTATION_UPDATED from Label Studio and upserts a `labels` row. NOT
    user-facing -- called by Label Studio itself, so it is not gated behind
    WebODM login (`permission_classes = [AllowAny]`); the checks below are
    the real gate.

    Two security-review-driven requirements, both required, not optional:
    1. FAILS CLOSED if WO_LABEL_STUDIO_WEBHOOK_SECRET is unset/empty --
       every call is rejected with 503 before anything is compared. This
       codebase's own `getattr(settings, NAME, '')` convention makes an
       empty-vs-empty `compare_digest()` a real, sharp bypass if this check
       is skipped -- the Critical finding from this feature's own security
       review.
    2. Verifies a PER-PROJECT secret (`_derive_project_webhook_secret()`),
       not the raw server-wide secret directly -- a single static secret
       sent to every project would let anyone who obtains it (e.g. a Label
       Studio admin who can view a project's registered webhook headers)
       forge a call for a DIFFERENT project than the one it leaked from.

    Scope validation (Decision 29): does NOT trust the payload's own
    `task.meta.tile_observation_id` -- looks up
    `embeddings_client.get_tile_observation_for_label_studio_task()`
    instead (WebODM's own ledger, written at import time by
    `TaskLabelView.post()`) and uses THAT id, rejecting the call outright
    if no matching row exists rather than falling back to the payload's
    own claim.

    Label value: read from `annotation.result`'s `choices` value.
    `label_studio_client.build_label_config()` deliberately renders the
    canonical `label_classes.value` as each Choice's `alias` (not its
    displayed text) -- Label Studio substitutes the alias into the
    annotation result in place of the display value, so this is already
    the true taxonomy key, not something to re-derive. Validated against
    that tile's own site's real `label_classes` (Decision 12) before
    writing -- an unrecognized value is rejected, not silently written.

    Known, documented residual gaps (security review, Decision 49) --
    flagged explicitly for future work, not silently dropped:
    - No replay/staleness protection (no nonce/timestamp check): a
      captured legitimate call could be replayed. Upsert semantics limit
      the damage to resurrecting a stale label value, not arbitrary writes.
    - `created_by` is sourced from the payload's own `annotation.
      completed_by` (a Label Studio identity, not a WebODM one --
      embeddingsdb is a separate Postgres instance, Decision 26).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [_LabelStudioWebhookThrottle]

    def post(self, request):
        # 1. Fail closed FIRST -- before touching embeddingsdb at all, so an
        # unauthenticated caller can never use the DB as an existence oracle.
        if not (getattr(settings, 'WO_LABEL_STUDIO_WEBHOOK_SECRET', '') or '').strip():
            return Response(
                {'error': (
                    'Label Studio webhook verification is not configured on '
                    'this WebODM instance -- WO_LABEL_STUDIO_WEBHOOK_SECRET '
                    'is not set. Rejecting rather than accepting unverified.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.data or {}
        task_payload = payload.get('task') or {}
        project_id = task_payload.get('project')
        ls_task_id = task_payload.get('id')
        if project_id is None or ls_task_id is None:
            return Response(
                {'error': 'Payload is missing task.project or task.id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Per-project secret verification, constant-time comparison.
        try:
            expected_secret = _derive_project_webhook_secret(project_id)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        header_value = (request.headers.get('X-WebODM-Embeddings-Secret') or '').strip()
        if not header_value or not hmac.compare_digest(header_value, expected_secret):
            logger.warning(
                'Rejected Label Studio webhook call for project=%s task=%s: secret mismatch.',
                project_id, ls_task_id,
            )
            return Response({'error': 'Invalid or missing webhook secret.'}, status=status.HTTP_403_FORBIDDEN)

        # 3. Scope validation (Decision 29): the payload's own claimed
        # tile_observation_id is NOT trusted -- only WebODM's own ledger is.
        try:
            tile_observation_id = embeddings_client.get_tile_observation_for_label_studio_task(
                project_id, ls_task_id,
            )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        if not tile_observation_id:
            logger.warning(
                'Rejected Label Studio webhook call for project=%s task=%s: '
                'no matching label_studio_tasks row -- WebODM never registered '
                'this (project, task) pair.', project_id, ls_task_id,
            )
            return Response(
                {'error': 'This (project, task) pair was not registered by WebODM.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 4. Extract the label value -- already the canonical taxonomy key
        # (the alias), not display text; see class docstring.
        annotation = payload.get('annotation') or {}
        value = None
        for item in (annotation.get('result') or []):
            if item.get('type') == 'choices':
                choices = (item.get('value') or {}).get('choices') or []
                if choices:
                    value = choices[0]
                    break
        if not value:
            return Response(
                {'error': 'No choices value found in annotation.result.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            site_id = embeddings_client.get_site_id_for_tile_observation(tile_observation_id)
            valid_values = {lc['value'] for lc in embeddings_client.list_label_classes(site_id)}
            if value not in valid_values:
                return Response(
                    {'error': f'{value!r} does not match any registered label class for this site.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            completed_by = annotation.get('completed_by')
            created_by = f'label_studio:{completed_by}' if completed_by is not None else 'label_studio'

            embeddings_client.upsert_label(
                tile_observation_id, 'category', value, source='label_studio', created_by=created_by,
            )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class SitesView(APIView):
    """
    GET/POST /api/plugins/embeddings/sites

    Design spec, Decision 38: real, NOT task-scoped -- sites are global to
    the whole embeddings system (a site can span many WebODM tasks/projects
    over time, Decision 27), matching how LabelClassesView below is already
    registered as a non-task-scoped route rather than nested under
    `task/(?P<pk>...)`.

    GET: calls embeddings_client.list_sites() for real, against the live
    embeddingsdb (Decision 33/34). Populates the task panel's "existing
    site" dropdown in EmbeddingsPanel.jsx.

    POST: Decision 51 -- creates a site directly (`{"name": ...}` ->
    `{"id": ..., "name": ...}`), independent of embedding/labeling a task.
    Every other site-creating path only creates one as a side effect of
    its own action; this is the only way to get a real site_id on its own
    (e.g. to add label classes to a brand-new site before painting a tile).

    Response: 200 {"sites": [{"id": <str>, "name": <str>}, ...]}
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request):
        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            sites = embeddings_client.list_sites()
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {'sites': [{'id': site_id, 'name': name} for site_id, name in sites]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """
        Decision 51: creates a site directly, independent of embedding or
        labeling a task. Every other site-creating path (`TaskEmbedView`,
        `TaskLabelView`, `TaskLabelApplyView`) only creates one as a SIDE
        EFFECT of its own action -- there was previously no way to get a
        real `site_id` for a brand-new site before doing something else
        with it. Needed so "add a label class" can create a new site on
        demand (a user in "New site" mode who wants to define custom
        classes before ever painting a tile).
        """
        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        name = request.data.get('name')
        if not name or not str(name).strip():
            return Response({'error': 'name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            site_id = embeddings_client.create_site(name)
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'id': site_id, 'name': str(name).strip()}, status=status.HTTP_201_CREATED)


class LabelClassesView(APIView):
    """
    GET/POST /api/plugins/embeddings/label-classes?site_id=<optional>

    Design spec, Decision 12: list/add label_classes rows, site-scoped,
    falling back to instance-wide defaults (site_id=null). Requires an
    authenticated WebODM user (see "API Endpoints" preamble).

    GET: real, calls embeddings_client.list_label_classes(site_id) --
    seeds Phase 1's 7 instance-wide defaults on first real use if none
    exist yet (see that function's own docstring).
    POST: real, the "+ Add label class" path -- requires site_id (adding an
    instance-wide default is not exposed here; only
    _ensure_default_label_classes() does that, once, automatically).
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request):
        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        site_id = request.query_params.get('site_id') or None
        try:
            label_classes = embeddings_client.list_label_classes(site_id)
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({'label_classes': label_classes}, status=status.HTTP_200_OK)

    def post(self, request):
        if not getattr(settings, 'WO_EMBEDDINGS_DB_URL', ''):
            return Response(
                {'error': (
                    'Embeddings database integration is not configured on '
                    'this WebODM instance -- WO_EMBEDDINGS_DB_URL is not set.'
                )},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        site_id = request.data.get('site_id')
        value = request.data.get('value')
        if not site_id or not value:
            return Response(
                {'error': 'site_id and value are both required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            class_id = embeddings_client.create_label_class(
                site_id,
                value,
                request.data.get('display_name'),
                request.data.get('color_hex'),
                created_by=request.user.username,
            )
        except embeddings_client.EmbeddingsDBConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except embeddings_client.EmbeddingsDBError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'id': class_id}, status=status.HTTP_201_CREATED)

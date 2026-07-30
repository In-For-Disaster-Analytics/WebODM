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

import os
from datetime import datetime, timezone

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.api import tiler
from app.plugins.views import TaskView
from app.plugins.worker import run_function_async
from app.raster_utils import ZOOM_EXTRA_LEVELS
from rio_tiler.io import COGReader

from . import embeddings_client
from . import label_studio_client


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


def _not_implemented(message):
    return Response(
        {'error': message},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


# Phase 1 default land-cover taxonomy (design spec "Phase 1 Research Findings").
# PLACEHOLDER: the real `label_classes` DB table (site-scoped, with
# instance-wide defaults -- Decision 12) lives in `embeddingsdb`, which does
# not exist yet. Once it does, TaskLabelView.post() below should query it
# (falling back to these same 7 rows as the instance-wide default, per the
# design spec) instead of using this hardcoded list directly.
_PHASE1_DEFAULT_LABEL_CLASSES = [
    {'value': 'structure', 'display_name': 'Structure', 'color_hex': '#e6194b'},
    {'value': 'vegetation', 'display_name': 'Vegetation', 'color_hex': '#3cb44b'},
    {'value': 'bare_ground', 'display_name': 'Bare Ground', 'color_hex': '#ffe119'},
    {'value': 'water', 'display_name': 'Water', 'color_hex': '#4363d8'},
    {'value': 'road_paved', 'display_name': 'Road / Paved Surface', 'color_hex': '#911eb4'},
    {'value': 'damage_debris', 'display_name': 'Damage / Debris', 'color_hex': '#f58231'},
    {'value': 'other', 'display_name': 'Other', 'color_hex': '#808080'},
]


class TaskTilesView(TaskView):
    """
    GET /api/plugins/embeddings/task/{task_pk}/tiles

    Design spec: candidate tiles for labeling ONLY (orthophoto extent, at the
    same zoom as `embed`), for display in the "Label a Sample" map checklist.
    Distinct from `embed`, which covers every tile at a zoom with no picker
    (Decision 9) -- this endpoint is the selective, human-in-the-loop side.
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Candidate-tile listing is not implemented yet -- depends on '
            'WebODM\'s own tiler (app/api/tiler.py) plus the site\'s locked '
            'zoom (Decision 24/27). See design spec "Tile Coverage" and '
            '"Tile Selection UI" sections.'
        )


class TaskLabelView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/label

    Design spec: calls label_studio_client.py to create a Label Studio
    project, import the selected tiles as tasks, and register a webhook --
    then returns the real deep-link URL. See "Label Studio Integration: Full
    Mechanics" and Decisions 10/32.

    Two real placeholders, clearly marked below (see the design spec's own
    scoping of this increment):
      - label_config is generated from _PHASE1_DEFAULT_LABEL_CLASSES, not a
        real `label_classes` query (embeddingsdb doesn't exist yet).
      - each imported task's `meta.tile_observation_id` is set directly from
        the request body's `tile_ids`, not a real tile_observation_id
        (there's no tile_grid/tile_observations table yet to resolve one from).
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

        tile_ids = request.data.get('tile_ids') or []
        if not tile_ids:
            return Response(
                {'error': 'tile_ids is required and must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_name = task.name or 'unnamed'
        title = f'{task_name} — {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}'

        # PLACEHOLDER (see class docstring): real label_classes come from
        # embeddingsdb once it exists; Phase 1's hardcoded 7-class taxonomy
        # stands in for it today.
        label_config = label_studio_client.build_label_config(_PHASE1_DEFAULT_LABEL_CLASSES)

        base_url = request.build_absolute_uri('/').rstrip('/')
        project_id_str, task_id_str = str(task.project_id), str(task.id)

        # PLACEHOLDER (see class docstring): tile_ids stand in for real
        # tile_observation_ids. Where a tile_id parses as "z/x/y", build a
        # real per-tile image URL via WebODM's existing orthophoto tiler
        # endpoint (app/api/urls.py); otherwise fall back to the task's
        # whole-orthophoto thumbnail so Label Studio still has something
        # fetchable to display.
        ls_tasks = []
        for tile_id in tile_ids:
            parts = str(tile_id).split('/')
            if len(parts) == 3 and all(p.lstrip('-').isdigit() for p in parts):
                z, x, y = parts
                image_url = (
                    f'{base_url}/api/projects/{project_id_str}/tasks/{task_id_str}'
                    f'/orthophoto/tiles/{z}/{x}/{y}.png'
                )
            else:
                image_url = f'{base_url}/api/projects/{project_id_str}/tasks/{task_id_str}/thumbnail'

            ls_tasks.append({
                'data': {'image': image_url},
                'meta': {
                    'tile_observation_id': tile_id,  # PLACEHOLDER: see class docstring
                    'webodm_task_id': task_id_str,
                },
            })

        try:
            project = label_studio_client.create_project(title=title, label_config=label_config)
            project_id = project.get('id')
            if project_id is None:
                raise label_studio_client.LabelStudioAPIError(
                    f'Label Studio project creation did not return an id: {project!r}'
                )

            label_studio_client.import_tasks(project_id, ls_tasks)

            webhook_url = f'{base_url}/api/plugins/embeddings/labelstudio-webhook'
            webhook_secret = getattr(settings, 'WO_LABELSTUDIO_WEBHOOK_SECRET', '')
            label_studio_client.register_webhook(project_id, webhook_url, webhook_secret)

            deep_link_url = label_studio_client.project_url(project_id)
        except label_studio_client.LabelStudioConfigError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except label_studio_client.LabelStudioAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'project_id': project_id,
            'label_studio_url': deep_link_url,
            'tile_count': len(ls_tasks),
        }, status=status.HTTP_200_OK)


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


class LabelStudioWebhookView(APIView):
    """
    POST /api/plugins/embeddings/labelstudio-webhook

    Design spec, Decisions 10/29: receives ANNOTATION_CREATED/
    ANNOTATION_UPDATED from Label Studio and upserts `labels` rows keyed by
    task.meta.tile_observation_id. NOT user-facing -- called by Label
    Studio itself, so it is not gated behind WebODM login; the real
    implementation must instead verify a shared-secret header via
    hmac.compare_digest (Decision 29), plus confirm the incoming
    tile_observation_id corresponds to a session WebODM actually created.
    Neither check is implemented in this increment (no embeddingsdb Pod to
    validate against yet) -- this stub deliberately does NOT accept or
    write anything.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        return _not_implemented(
            'Label Studio webhook handling is not implemented yet. See design '
            'spec Decisions 10 and 29 (shared-secret verification via '
            'hmac.compare_digest, tile_observation_id scope validation) -- '
            'neither is wired up yet, so this endpoint accepts nothing.'
        )


class SitesView(APIView):
    """
    GET /api/plugins/embeddings/sites

    Design spec, Decision 38: real, NOT task-scoped -- sites are global to
    the whole embeddings system (a site can span many WebODM tasks/projects
    over time, Decision 27), matching how LabelClassesView below is already
    registered as a non-task-scoped route rather than nested under
    `task/(?P<pk>...)`.

    Calls embeddings_client.list_sites() for real, against the live
    embeddingsdb (Decision 33/34) -- not a stub. Populates the task panel's
    "existing site" dropdown in EmbeddingsPanel.jsx.

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


class LabelClassesView(APIView):
    """
    GET/POST /api/plugins/embeddings/label-classes

    Design spec, Decision 12: list/add label_classes rows, site-scoped,
    falling back to instance-wide defaults (site_id=null). Requires an
    authenticated WebODM user (see "API Endpoints" preamble).
    """

    permission_classes = (IsEmbeddingsAdmin,)

    def get(self, request):
        return _not_implemented(
            'Label class listing is not implemented yet -- depends on the '
            'embeddingsdb Pod. See design spec Decision 12.'
        )

    def post(self, request):
        return _not_implemented(
            'Adding a label class is not implemented yet -- depends on the '
            'embeddingsdb Pod. See design spec Decision 12.'
        )

"""
DRF endpoints for the task-detail panel actions (design spec "API Endpoints"
> "Task-detail panel (per-task)"). URL routing/nesting and (for task-scoped
views) task-level permission resolution are real, via
app.plugins.views.TaskView (== app.api.tasks.TaskNestedView), the same base
class coreplugins/ckan and coreplugins/objdetect already use.

Second implementation increment: TaskLabelView is now real, backed by
label_studio_client.py (project create + task import + webhook registration
against Label Studio's actual REST API -- Decisions 10/32). Every other
endpoint's business logic -- queuing the embed-generate/model-train Tapis
Actors, writing to the (not yet existing) embeddingsdb Pod, calling the DSO
STAC API -- is still explicitly NOT implemented; see embeddings_client.py/
stac_client.py (not created yet; those Pods/Actors don't exist yet per the
spec's own infrastructure sequencing).
"""

from datetime import datetime, timezone

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.plugins.views import TaskView

from . import label_studio_client


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

    Design spec: queues the embed-generate Tapis Actor over every valid
    (z, x, y) at the requested zoom for this task's orthophoto -- no
    tile_ids, whole-task by design (Decision 9). Requires a user-chosen
    site_id (Decision 27) and honors zoom_override against a site's locked
    zoom (Decision 24/27).
    """

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Embedding generation is not implemented yet -- the embed-generate '
            'Tapis Actor and embeddingsdb Pod do not exist yet. See design '
            'spec Decisions 9, 24, 27 and the New Infrastructure table.'
        )


class TaskEmbedStatusView(TaskView):
    """
    GET /api/plugins/embeddings/task/{task_pk}/embed-status

    Design spec: polled by the frontend while embed-generate runs; includes
    total tile count at the selected zoom.
    """

    def get(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Embedding status polling is not implemented yet -- depends on '
            'the embed-generate Actor (see design spec "API Endpoints").'
        )


class TaskPublishToSTACView(TaskView):
    """
    POST /api/plugins/embeddings/task/{task_pk}/publish-to-stac

    Design spec: user-triggered, only available when task.public or
    task.project.public is true (Decision 21); creates/reuses a per-site
    STAC collection + item using the requesting user's own Tapis JWT
    (Decision 20), asset href reuses WebODM's own download endpoint
    (Decision 23).
    """

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


class LabelClassesView(APIView):
    """
    GET/POST /api/plugins/embeddings/label-classes

    Design spec, Decision 12: list/add label_classes rows, site-scoped,
    falling back to instance-wide defaults (site_id=null). Requires an
    authenticated WebODM user (see "API Endpoints" preamble).
    """

    permission_classes = [permissions.IsAuthenticated]

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

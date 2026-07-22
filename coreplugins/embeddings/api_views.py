"""
DRF stub endpoints for the task-detail panel actions (design spec "API
Endpoints" > "Task-detail panel (per-task)"). This is the FIRST
implementation increment: URL routing/nesting and (for task-scoped views)
task-level permission resolution are real, via
app.plugins.views.TaskView (== app.api.tasks.TaskNestedView), the same base
class coreplugins/ckan and coreplugins/objdetect already use. The actual
business logic each endpoint is meant to perform -- proxying Label Studio,
queuing the embed-generate/model-train Tapis Actors, writing to the (not yet
existing) embeddingsdb Pod, calling the DSO STAC API -- is explicitly NOT
implemented here; see label_studio_client.py/embeddings_client.py/
stac_client.py (not created in this increment; those Pods/Actors don't exist
yet per the spec's own infrastructure sequencing).
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.plugins.views import TaskView


def _not_implemented(message):
    return Response(
        {'error': message},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


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

    Design spec: proxies to label-studio-tapis-auth's API (project create +
    task import + webhook registration), returns the deep-link URL. See
    "Label Studio Integration: Full Mechanics" and Decision 10.
    """

    def post(self, request, pk=None):
        self.get_and_check_task(request, pk)
        return _not_implemented(
            'Label Studio proxying is not implemented yet. See design spec '
            '"Label Studio Integration: Full Mechanics" and Decision 10 '
            '(docs/design/2026-07-22-geospatial-embeddings-classification.md).'
        )


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

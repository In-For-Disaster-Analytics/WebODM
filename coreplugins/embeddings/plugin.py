from django.conf import settings
from django.shortcuts import render
from django.utils.translation import gettext as _

from app.plugins import PluginBase, Menu, MountPoint

from . import views
from .api_views import (
    TaskTilesView,
    TaskLabelView,
    TaskEmbedView,
    TaskEmbedStatusView,
    TaskPublishToSTACView,
    TaskRetractFromSTACView,
    TaskLabelsImportGeoJSONView,
    LabelStudioWebhookView,
    LabelClassesView,
    SitesView,
)

# First implementation increment of the design spec at
# docs/design/2026-07-22-geospatial-embeddings-classification.md
# ("Status: Approved", v3.0). This wires up the plugin's mounting/registration
# structure only -- see the module docstrings in views.py/api_views.py for what
# is real vs. stubbed in this increment.


class Plugin(PluginBase):

    def main_menu(self):
        # Wireframe 3 / Decision 6: a real top-level navbar entry, independent
        # of any single project or task, linking to the Embeddings & Classifier
        # page below. Same mechanism as coreplugins/projects-charts.
        return [Menu(_("Embeddings"), self.public_url(""), "fa fa-layer-group")]

    def include_js_files(self):
        return ['load_buttons.js']

    def app_mount_points(self):
        plugin = self

        # Rendered dynamically (rather than served as a static /public asset)
        # so it can gate itself on whether the supporting infrastructure is
        # configured -- same pattern as coreplugins/ckan's own
        # load_buttons_view (WO_DSO_AGENT_URL there, WO_EMBEDDINGS_DB_URL/
        # WO_LABEL_STUDIO_URL here).
        def load_buttons_view(request):
            infra_configured = bool(getattr(settings, 'WO_EMBEDDINGS_DB_URL', '')) and \
                bool(getattr(settings, 'WO_LABEL_STUDIO_URL', ''))
            # Decision 46: restricted to superusers only while the plugin
            # is still being validated in production -- the task-detail
            # button itself never even registers for non-admins.
            is_admin = bool(request.user and request.user.is_authenticated and request.user.is_superuser)
            return render(
                request,
                plugin.template_path('load_buttons.js'),
                {'infra_configured': infra_configured, 'is_admin': is_admin},
                content_type='text/javascript',
            )

        # Decision 6/18: two distinct top-level pages, both via app_mount_points()
        # -- the cross-project Embeddings & Classifier workspace, and the
        # separate per-model Diagnostics page. Neither requires a restart
        # (requires_restart() only checks root_mount_points()).
        return [
            MountPoint('$', views.workspace_index),
            MountPoint(r'models/(?P<model_id>[^/.]+)/$', views.model_diagnostics),
            MountPoint('load_buttons.js$', load_buttons_view),
        ]

    def api_mount_points(self):
        # Task-detail panel action endpoints (see "API Endpoints" > "Task-detail
        # panel (per-task)" in the design spec). Stub implementations only for
        # this increment -- see api_views.py. URL nesting follows the same
        # task/(?P<pk>[^/.]+)/<action> convention already used by
        # coreplugins/ckan and coreplugins/objdetect, backed by
        # app.api.tasks.TaskNestedView.get_and_check_task(request, pk), which
        # resolves permissions from the task's own project -- no separate
        # project_pk segment is used anywhere else in this codebase for
        # task-nested plugin routes.
        # Every pattern below is anchored with a trailing $. Without it, a
        # leaf URLPattern's resolve() doesn't require the whole path to
        # match (Django only checks match.end() for include()d resolvers,
        # not final view patterns) -- so an earlier, shorter pattern that's
        # a prefix of a later one silently wins. Discovered for real: task/
        # {pk}/embed (POST-only) was shadowing task/{pk}/embed-status (GET),
        # producing "Method Not Allowed" on every status poll, and task/
        # {pk}/label was shadowing task/{pk}/labels/import-geojson even more
        # dangerously -- silently misrouting a GeoJSON import to the wrong
        # view instead of erroring. `load_buttons.js$` (below) already had
        # this right; the task-scoped ones didn't.
        return [
            MountPoint('task/(?P<pk>[^/.]+)/tiles$', TaskTilesView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/label$', TaskLabelView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/embed$', TaskEmbedView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/embed-status$', TaskEmbedStatusView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/publish-to-stac$', TaskPublishToSTACView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/retract-from-stac$', TaskRetractFromSTACView.as_view()),
            MountPoint('task/(?P<pk>[^/.]+)/labels/import-geojson$', TaskLabelsImportGeoJSONView.as_view()),
            # Not task-scoped: the webhook is called by Label Studio itself
            # (shared-secret auth, Decisions 10/29), label-classes is
            # site-scoped falling back to instance-wide defaults (Decision 12),
            # and sites are global to the whole embeddings system, not to any
            # one task/project (Decision 38).
            MountPoint('labelstudio-webhook$', LabelStudioWebhookView.as_view()),
            MountPoint('label-classes$', LabelClassesView.as_view()),
            MountPoint('sites$', SitesView.as_view()),
        ]

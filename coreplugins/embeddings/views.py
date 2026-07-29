"""
Django views for the two app_mount_points() routes this plugin registers
(design spec "Plugin File Structure": views.py). Both routes are real and
reachable, per Decisions 6/18, but render a minimal placeholder shell in this
increment -- the full EmbeddingsWorkspace.jsx/ModelDiagnostics.jsx React
surfaces are a later increment (out of scope here, see the design spec's
"Plugin File Structure" > public/).
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

# Template paths mirror PluginBase.template_path()'s output for a coreplugin
# (coreplugins/<name>/templates/<path>) -- computed directly here rather than
# via app.plugins.functions.get_plugin_by_name(), which re-scans installed
# plugins on every call (see its own TODO comment in app/plugins/views.py).
_TEMPLATE_DIR = "coreplugins/embeddings/templates"


def _forbidden_response():
    # Decision 46: the embeddings plugin is restricted to superusers only
    # while it's still being validated in production. `PluginBase.
    # main_menu()` has no access to `request` (confirmed by reading its
    # real signature, app/plugins/plugin_base.py), so the top-nav
    # "Embeddings" link itself cannot be conditionally hidden per-user --
    # real enforcement happens here instead (a 403 for non-admins), which
    # achieves the same practical restriction even though the nav entry
    # stays visible to everyone.
    return HttpResponseForbidden(
        "The Embeddings & Classifier workspace is currently limited to "
        "administrators while it's being validated."
    )


def _infra_configured():
    # Rollout gate (design spec "Rollout / Rollback"): same pattern as the
    # CKAN plugin's WO_DSO_AGENT_URL gate -- the plugin always mounts, but its
    # pages/actions report themselves as not-yet-configured until the
    # supporting Tapis infrastructure (embeddingsdb Pod, Label Studio Pod)
    # actually exists.
    return bool(getattr(settings, 'WO_EMBEDDINGS_DB_URL', '')) and \
        bool(getattr(settings, 'WO_LABEL_STUDIO_URL', ''))


@login_required
def workspace_index(request):
    """
    The Embeddings & Classifier page (design spec: cross-project task/site
    picker, aggregate embedded/labeled counts, train action, predictions).
    Decision 6: instance-wide, not scoped to any single project or task.

    This increment renders a placeholder shell only, confirming the route
    mounts and is reachable -- no cross-project browse query, no training
    trigger. Those depend on the embeddingsdb Pod and model-train Actor,
    which do not exist yet per the spec's own infrastructure sequencing.
    """
    if not request.user.is_superuser:
        return _forbidden_response()
    template_args = {
        'title': 'Embeddings & Classifier',
        'infra_configured': _infra_configured(),
    }
    return render(request, "{}/index.html".format(_TEMPLATE_DIR), template_args)


@login_required
def model_diagnostics(request, model_id=None):
    """
    The separate per-model Diagnostics page (Decision 18): split strategy,
    tuned hyperparameters, ROC-AUC, confusion matrix, feature importance,
    calibration curve for one trained model, proxied server-side from
    MLflow via models.mlflow_run_id.

    Placeholder shell only in this increment -- no MLflow proxy call yet
    (mlflow_client.py is out of scope; the mlflow Pod does not exist yet).
    """
    if not request.user.is_superuser:
        return _forbidden_response()
    template_args = {
        'title': 'Model Diagnostics',
        'model_id': model_id,
        'infra_configured': _infra_configured(),
    }
    return render(request, "{}/model_diagnostics.html".format(_TEMPLATE_DIR), template_args)

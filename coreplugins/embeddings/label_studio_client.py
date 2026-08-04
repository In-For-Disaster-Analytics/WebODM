"""
Server-to-server client for Label Studio's own REST API.

Decision 32 (docs/design/2026-07-22-geospatial-embeddings-classification.md),
CORRECTED below (found via a real, live 401 -- "Authentication credentials
were not provided" -- see `_refresh_access_token()`'s own comment): Label
Studio's REST API authenticates via `Authorization: Bearer <token>`, but
that token is NOT the Personal Access Token itself -- a PAT is a JWT
REFRESH token, and must be exchanged for a short-lived access token via
`POST /api/token/refresh` first (confirmed against Label Studio's own docs,
https://labelstud.io/guide/access_tokens, not guessed -- the original
Decision 32 text asserted the PAT went directly in the Bearer header, which
is wrong). It does NOT accept a Tapis JWT either way. The human deep-link
SSO login (handled entirely by the separate `label-studio-tapis-auth`
repo's `TapisOAuth2Backend`) is a completely different code path from the
server-to-server calls this module makes: project create, task import, and
webhook registration all run with no human in the loop. Every method here
ultimately authenticates via `settings.WO_LABEL_STUDIO_API_TOKEN` -- a
Label Studio Personal Access Token generated once by an admin user in the
Label Studio instance itself, and configured server-side only (never sent
to the browser) -- NOT the requesting WebODM user's own Tapis credential,
which is a completely separate thing used only for the human deep-link
login.

Endpoints and payload shapes below were verified against Label Studio's real,
current REST API reference (not guessed from memory):
- Create project:  POST /api/projects/            https://api.labelstud.io/api-reference/api-reference/projects/create
- Bulk task import: POST /api/projects/{id}/import https://api.labelstud.io/api-reference/api-reference/projects/import-tasks
- Create webhook:  POST /api/webhooks/             https://api.labelstud.io/api-reference/api-reference/webhooks/create
- Project deep-link URL pattern (`/projects/{id}/data`): confirmed directly
  against Label Studio's own frontend source, not guessed --
  `web/apps/labelstudio/src/pages/Projects/Projects.jsx` (HumanSignal/label-studio)
  redirects bare `/projects/:id` to `/projects/${id}/data` (the Data Manager tab).

Structure and error-handling style mirror coreplugins/ckan/publisher.py -- the
existing precedent in this repo for a plugin's HTTP client module talking to
an external service server-side -- not its specific API (CKAN vs. Label
Studio are unrelated services).
"""

import logging
import threading
import time
from xml.sax.saxutils import quoteattr

import requests
from django.conf import settings

logger = logging.getLogger('app.logger')

# Project create/import/webhook-register are all small, synchronous calls --
# no long-running work happens inside Label Studio for any of them.
DEFAULT_REQUEST_TIMEOUT = 30  # seconds

# Decision 32 CORRECTION (found via a real 401 -- "Authentication
# credentials were not provided" -- from sending the raw Personal Access
# Token as a Bearer header): a Label Studio PAT is a JWT REFRESH token, not
# a usable Bearer access token on its own. It must be exchanged for a
# short-lived access token via POST /api/token/refresh first (confirmed
# against Label Studio's own docs, not guessed -- see
# https://labelstud.io/guide/access_tokens); the ORIGINAL Decision 32
# comment's "Authorization: Bearer <PAT>" claim was wrong about which token
# goes there. `_get_access_token()`/`_refresh_access_token()` below do that
# exchange; `_auth_headers()` now sends the exchanged access token, not the
# PAT itself.
#
# Label Studio's own docs don't state an exact access-token TTL beyond
# "around 5 minutes" -- ACCESS_TOKEN_SAFETY_MARGIN_SECONDS refreshes a bit
# early rather than exactly at that assumed boundary, and _request()'s own
# retry-once-on-401 covers the case where the real server-side expiry is
# earlier than assumed (e.g. clock skew, an admin revoking the PAT).
ACCESS_TOKEN_ASSUMED_LIFETIME_SECONDS = 5 * 60
ACCESS_TOKEN_SAFETY_MARGIN_SECONDS = 30

# Cached across calls within this process -- create_project()/import_tasks()/
# register_webhook() run back-to-back in one request (api_views.py's
# TaskEmbedView.post()), so this avoids exchanging a fresh access token 3
# times for what's really one logical operation. Lock-protected: a Django
# WSGI worker can serve more than one request thread concurrently, and this
# dict is mutated (not just read) on refresh.
_access_token_cache = {'token': None, 'expires_at': 0.0}
_access_token_lock = threading.Lock()


class LabelStudioConfigError(RuntimeError):
    """Raised when WO_LABEL_STUDIO_URL / WO_LABEL_STUDIO_API_TOKEN aren't configured."""


class LabelStudioAPIError(RuntimeError):
    """Raised when Label Studio's API returns a non-2xx response, or the request
    could not be sent at all (network error). Mirrors the "raise a clear
    exception rather than fail silently" style of coreplugins/ckan/publisher.py.
    """

    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


# ── Config / low-level request helper ─────────────────────────────────────────

def _base_url():
    url = (getattr(settings, 'WO_LABEL_STUDIO_URL', '') or '').strip()
    if not url:
        raise LabelStudioConfigError(
            "WO_LABEL_STUDIO_URL is not configured -- the embeddings plugin's "
            "Label Studio integration is inactive until it is set."
        )
    return url.rstrip('/')


def _personal_access_token():
    token = (getattr(settings, 'WO_LABEL_STUDIO_API_TOKEN', '') or '').strip()
    if not token:
        raise LabelStudioConfigError(
            "WO_LABEL_STUDIO_API_TOKEN is not configured -- see Decision 32 in "
            "docs/design/2026-07-22-geospatial-embeddings-classification.md. "
            "This must be a Label Studio Personal Access Token generated by an "
            "admin inside the Label Studio instance itself -- it is NOT the "
            "requesting user's Tapis JWT."
        )
    return token


def _refresh_access_token():
    """
    POST /api/token/refresh -- exchanges the long-lived Personal Access
    Token for a short-lived access token (see this module's own comment on
    ACCESS_TOKEN_ASSUMED_LIFETIME_SECONDS for why this exchange is required
    at all). Deliberately NOT routed through `_request()` -- that function
    calls `_auth_headers()`, which is what needs THIS result, so going
    through it here would recurse.
    """
    url = f'{_base_url()}/api/token/refresh'
    try:
        response = requests.post(
            url, json={'refresh': _personal_access_token()}, timeout=DEFAULT_REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.exception('Label Studio access-token refresh failed: %s', url)
        raise LabelStudioAPIError(f'Could not reach Label Studio at {url}: {e}') from e

    if not response.ok:
        # The response body is logged server-side only, never put into the
        # raised exception's message -- unlike every other _request() error
        # path in this module. Every OTHER LabelStudioAPIError eventually
        # reaches api_views.py's Response({'error': str(e)}, ...) and is
        # returned to the browser verbatim (existing pattern, not changed
        # here); THIS endpoint's request body is the Personal Access Token
        # itself, so a JWT-library error response that happens to echo the
        # submitted (invalid/expired) token back would otherwise leak it to
        # the client. A generic message is raised instead; response_body is
        # still attached to the exception object (not its message) for any
        # server-side caller that wants it.
        body_snippet = (response.text or '')[:500]
        logger.error('Label Studio access-token refresh error %s: %s', response.status_code, body_snippet)
        raise LabelStudioAPIError(
            f'Label Studio access-token refresh returned {response.status_code} '
            f'-- see server logs for the response body.',
            status_code=response.status_code,
            response_body=body_snippet,
        )
    try:
        return response.json()['access']
    except (ValueError, KeyError) as e:
        body_snippet = (response.text or '')[:500]
        logger.error("Label Studio access-token refresh response did not contain 'access': %s", body_snippet)
        raise LabelStudioAPIError(
            "Label Studio access-token refresh response did not contain 'access' "
            "-- see server logs for the response body.",
            response_body=body_snippet,
        ) from e


def _invalidate_access_token():
    with _access_token_lock:
        _access_token_cache['token'] = None
        _access_token_cache['expires_at'] = 0.0


def _get_access_token():
    """
    Returns a real Label Studio access token, refreshing it from the
    configured Personal Access Token if the cached one is missing or past
    its assumed expiry. See this module's own top-of-file comment (Decision
    32 correction) for why this exchange step exists at all.
    """
    with _access_token_lock:
        now = time.monotonic()
        if _access_token_cache['token'] and now < _access_token_cache['expires_at']:
            return _access_token_cache['token']

        access_token = _refresh_access_token()
        _access_token_cache['token'] = access_token
        _access_token_cache['expires_at'] = (
            now + ACCESS_TOKEN_ASSUMED_LIFETIME_SECONDS - ACCESS_TOKEN_SAFETY_MARGIN_SECONDS
        )
        return access_token


def _auth_headers():
    return {'Authorization': f'Bearer {_get_access_token()}'}


def _request(method, path, **kwargs):
    """
    Real HTTP call to Label Studio's own REST API (`requests`, not mocked).
    Raises LabelStudioAPIError on any non-2xx response or network failure --
    callers should not have to guess success from a None/False return.

    Retries exactly once on a 401: the cached access token's real
    server-side expiry isn't stated by Label Studio's own docs beyond
    "around 5 minutes," so ACCESS_TOKEN_ASSUMED_LIFETIME_SECONDS is an
    assumption, not a guarantee -- a 401 forces one fresh
    refresh-and-retry before this is treated as a real failure.
    """
    url = f'{_base_url()}{path}'
    extra_headers = kwargs.pop('headers', None) or {}
    timeout = kwargs.pop('timeout', DEFAULT_REQUEST_TIMEOUT)

    for attempt in (1, 2):
        headers = _auth_headers()
        headers.update(extra_headers)
        try:
            response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except requests.RequestException as e:
            logger.exception('Label Studio API request failed: %s %s', method, url)
            raise LabelStudioAPIError(f'Could not reach Label Studio at {url}: {e}') from e

        if response.status_code == 401 and attempt == 1:
            logger.warning(
                'Label Studio API returned 401 on first attempt -- forcing an '
                'access-token refresh and retrying once: %s %s', method, url,
            )
            _invalidate_access_token()
            continue
        break

    if not response.ok:
        body_snippet = (response.text or '')[:500]
        logger.error(
            'Label Studio API error %s on %s %s: %s',
            response.status_code, method, url, body_snippet,
        )
        raise LabelStudioAPIError(
            f'Label Studio API returned {response.status_code} for {method} {url}: {body_snippet}',
            status_code=response.status_code,
            response_body=body_snippet,
        )

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


# ── label_config generation ────────────────────────────────────────────────────

def build_label_config(label_classes, image_data_key='image', choice_mode='single'):
    """
    Build the XML `label_config` string Label Studio's project-create API
    expects, from a PLAIN LIST of label-class dicts -- NOT from a
    `label_classes` DB query. The real `label_classes` table (site-scoped,
    falling back to instance-wide defaults -- design spec "Embeddings DB
    Schema" / Decision 12) lives in `embeddingsdb`, which does not exist yet.
    Until it does, the CALLER is responsible for sourcing this list:
      - today: a hardcoded Phase 1 default 7-class taxonomy (see
        api_views.py's TaskLabelView, clearly commented as a placeholder)
      - later: a real `label_classes` query, once embeddingsdb exists
    This function does not hardcode any taxonomy itself.

    Args:
        label_classes: list of dicts, each with:
            - 'value' (str, required): canonical vocabulary key -- must match
              a real `label_classes.value` once that table exists; this is
              what a `labels` row's `value` should be set to after annotation.
            - 'display_name' (str, optional): human-readable text shown to
              the annotator; falls back to 'value' if omitted.
            - 'color_hex' (str, optional): CSS color (e.g. '#e6194b') Label
              Studio renders as the choice's background swatch.
        image_data_key: the task `data` field name the generated interface
            reads the tile image URL from (interpolated as `$<image_data_key>`
            in the XML). Every task object passed to `import_tasks()` must
            set `data[image_data_key]` to match, or Label Studio's import
            will reject it (task data is validated against label_config).
        choice_mode: the `<Choices>` tag's `choice` attribute -- 'single'
            (default: one label per tile) or 'multiple'.

    Label Studio's `<Choice>` tag only ever shows one attribute (`value`) to
    the annotator, but separately supports an `alias` attribute that -- per
    Label Studio's own docs -- "replaces the choice value in the annotation
    results" when set, and is never shown in the UI. So this generator renders
    `display_name` as `value` (what the human annotator sees) and the
    canonical `value` as `alias` (what actually comes back in the
    ANNOTATION_CREATED/UPDATED webhook payload) -- this is what lets a real
    webhook handler upsert `labels.value` as the true taxonomy key rather than
    whatever human-readable text happened to be on screen.

    Returns a well-formed XML string. Not schema-validated against Label
    Studio itself here (no such endpoint is called) -- see this module's own
    tests for an `xml.etree.ElementTree.fromstring()` well-formedness check.
    """
    if not label_classes:
        raise ValueError('build_label_config() requires at least one label class.')

    choice_tags = []
    for lc in label_classes:
        value = lc.get('value')
        if not value:
            raise ValueError(f"label class {lc!r} is missing required 'value'.")
        display_name = lc.get('display_name') or value
        color_hex = lc.get('color_hex')

        attrs = f'value={quoteattr(str(display_name))} alias={quoteattr(str(value))}'
        if color_hex:
            attrs += f' background={quoteattr(str(color_hex))}'
        choice_tags.append(f'    <Choice {attrs}/>')

    return (
        '<View>\n'
        f'  <Image name="image" value="${image_data_key}"/>\n'
        f'  <Choices name="label" toName="image" choice="{choice_mode}">\n'
        + '\n'.join(choice_tags) + '\n'
        '  </Choices>\n'
        '</View>'
    )


# ── API calls ──────────────────────────────────────────────────────────────────

def create_project(title, label_config):
    """
    POST /api/projects/ -- create a new Label Studio project.

    Design spec, "Label Studio Integration: Full Mechanics" step 1: `title`
    is the task name + timestamp; `label_config` is generated by
    `build_label_config()` above (from whatever label classes the caller
    sourced -- see that function's docstring).

    Returns Label Studio's own response dict, including at least 'id' (the
    new project's integer id, needed by import_tasks()/register_webhook()
    and to build the deep-link URL).
    """
    payload = {'title': title, 'label_config': label_config}
    return _request('POST', '/api/projects/', json=payload)


def import_tasks(project_id, tasks):
    """
    POST /api/projects/{id}/import -- bulk task import (Label Studio's real
    bulk-import endpoint; accepts a JSON array of task objects directly).

    Design spec, "Label Studio Integration: Full Mechanics" step 2: one
    Label Studio task per selected tile. Each task dict must already be
    shaped for Label Studio's own import API:
      - 'data' (dict, required): validated against label_config on import --
        must include the image_data_key used when building label_config
        (default 'image') pointing at a fetchable image URL for that tile.
      - 'meta' (dict, optional but expected in practice): arbitrary JSON --
        this is where OUR OWN join key belongs. Per the design spec, this
        must carry `tile_observation_id` (and `webodm_task_id`) so the
        ANNOTATION_CREATED/UPDATED webhook payload can be matched back to
        the right row -- NOT inferred from image filenames.

    Building the 'data'/'meta' contents is the CALLER's job -- this module
    knows nothing about tiles, WebODM tasks, or tile_observation_ids; it only
    forwards whatever task list it's given to Label Studio's import endpoint.

    Returns Label Studio's own import response (Community edition returns
    task/annotation counts synchronously; other editions return an
    `import_id` for async polling against /api/projects/{id}/imports/{id} --
    not distinguished here, since either shape is just passed through as-is).
    """
    if not tasks:
        raise ValueError('import_tasks() requires at least one task.')
    for i, task in enumerate(tasks):
        if 'data' not in task:
            raise ValueError(f'tasks[{i}] is missing the required "data" field.')
    return _request('POST', f'/api/projects/{project_id}/import', json=tasks)


def list_tasks(project_id, page_size=1000):
    """
    GET /api/tasks/?project={project_id}&page_size={page_size} -- lists a
    project's tasks, echoing back each task's own 'data'/'meta' exactly as
    submitted at import time (confirmed against Label Studio's real API
    reference, not guessed) alongside its real, Label-Studio-assigned
    integer 'id'.

    Used by TaskLabelView.post() right after import_tasks() to recover each
    task's real id, matched back to our own tile_observation_id via
    task['meta'] -- deliberately NOT relying on import_tasks()'s own
    response containing task ids in the same order as the submitted list
    (not documented anywhere in Label Studio's API reference as an
    ordering guarantee).

    Response shape is Label Studio's own `PaginatedRoleBasedTaskList`:
    `{"tasks": [...], "total": int, ...}` -- NOT a plain array, and NOT
    DRF's usual "results"/"next" shape. `page_size` defaults generously
    large (1000) to cover one label batch (a "sample," not a whole task) in
    a single call; if a project ever has more tasks than that, only the
    first page is returned -- callers should compare against the response's
    own 'total' and log if some tasks were missed, not silently proceed as
    if everything was fetched.

    Returns the response dict as-is (callers read 'tasks' and 'total').
    """
    return _request('GET', '/api/tasks/', params={'project': project_id, 'page_size': page_size})


def create_annotation(task_id, result):
    """
    POST /api/tasks/{task_id}/annotations/ -- creates a real annotation on
    an existing Label Studio task, server-side, on the user's behalf (not
    via Label Studio's own UI). Confirmed against Label Studio's real API
    reference, not guessed.

    This is what makes "paint a label directly in WebODM's modal" a genuine
    Label Studio integration rather than a bypass: Label Studio remains the
    real system of record for every label regardless of whether a human
    opened its own UI or painted a tile from inside WebODM. The
    corresponding `labels` row is written separately, immediately, by the
    caller (`embeddings_client.upsert_label()`) rather than waiting on the
    ANNOTATION_CREATED webhook round-trip -- the webhook still fires (Label
    Studio doesn't distinguish API-created annotations from UI-created
    ones for webhook purposes) and will harmlessly re-upsert the same value
    when it arrives, per that view's own idempotent upsert semantics.

    `result`: Label Studio's own annotation result array shape. For a
    single Choices classification (the only kind this plugin builds via
    `build_label_config()`):
        [{"from_name": "label", "to_name": "image", "type": "choices",
          "value": {"choices": ["<canonical label_classes.value>"]}}]
    `from_name`/`to_name` match `build_label_config()`'s own
    `<Choices name="label" toName="image">` tag exactly -- the value sent
    here should already be the canonical `label_classes.value` (the
    alias), not display text, matching what the webhook path itself reads.

    Returns Label Studio's own response dict (includes 'id', the new
    annotation's id).
    """
    if not result:
        raise ValueError('create_annotation() requires a non-empty result.')
    return _request('POST', f'/api/tasks/{task_id}/annotations/', json={'result': result})


def delete_annotation(annotation_id):
    """
    DELETE /api/annotations/{annotation_id}/ -- deletes a real annotation
    (confirmed against Label Studio's real API reference: 204 No Content
    on success). Used by the "eraser" flow (Decision 53) to undo a
    mistakenly painted label -- deletes the EXACT annotation
    `create_annotation()` created for it (tracked via
    `labels.label_studio_annotation_id`), not every annotation on the
    task, since one Label Studio task can accumulate several annotations
    across repeated repaints.
    """
    _request('DELETE', f'/api/annotations/{annotation_id}/')


def register_webhook(project_id, webhook_url, secret):
    """
    POST /api/webhooks/ -- register a webhook scoped to `project_id` (via the
    'project' field, so it fires only for this project's annotations, not
    organization-wide), for ANNOTATION_CREATED/ANNOTATION_UPDATED (Decision
    10). `send_for_all_actions=False` + explicit `actions` ensures only those
    two events are sent, not every supported webhook action.

    `secret` is sent as a custom header (via the webhook's own 'headers'
    field) rather than an HMAC signature -- Label Studio's webhook API has no
    built-in payload-signing mechanism, so a shared-secret header is the real
    mechanism `.../labelstudio-webhook` verifies via `hmac.compare_digest`
    per Decisions 10/29 (that handler is still a stub -- see
    LabelStudioWebhookView in api_views.py -- this call only registers the
    webhook, it doesn't implement the receiving side).
    """
    payload = {
        'url': webhook_url,
        'project': project_id,
        'actions': ['ANNOTATION_CREATED', 'ANNOTATION_UPDATED'],
        'send_payload': True,
        'send_for_all_actions': False,
        'is_active': True,
        'headers': {'X-WebODM-Embeddings-Secret': secret},
    }
    return _request('POST', '/api/webhooks/', json=payload)


def project_url(project_id):
    """
    Deep-link URL to a project's Data Manager page in Label Studio's own UI --
    the real URL its UI uses to open a project (confirmed against Label
    Studio's own frontend source, not guessed -- see module docstring).
    """
    return f'{_base_url()}/projects/{project_id}/data'

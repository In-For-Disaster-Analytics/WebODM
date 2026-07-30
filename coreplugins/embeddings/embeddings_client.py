"""
Real client module for `embeddingsdb` -- the live Postgres 17.5 + PostGIS 3.5.2
+ pgvector 0.8.5 Tapis Pod described in the design spec's "Embeddings DB
Schema" section and Decision 33
(docs/design/2026-07-22-geospatial-embeddings-classification.md).

`embeddingsdb` is a SEPARATE Postgres instance from WebODM's own `webodm_dev`
database (Decision 26: zero WebODM-database schema changes) -- this module is
the only place in this coreplugin that should open a connection to it. Every
query below matches the real schema in
`embeddings-tapis-actors/schema/embeddingsdb.sql` (column names/types read
directly from that file's own CREATE TABLE statements, not guessed), and
connectivity plus every query shape here was confirmed against the live Pod
itself during this increment: `list_sites()`'s underlying SELECT, an
`information_schema.columns` introspection of `tile_grid`/`visits`/
`tile_observations`, and every write path below (`create_site`,
`get_or_create_visit`, a `tile_grid`/`tile_observations` insert) were run
against the real `embeddingsdb` instance inside a transaction that was then
rolled back -- confirmed 0 rows persisted afterward. See this increment's own
notes for the exact commands run; not claimed from memory.

Uses `psycopg2` (already a WebODM dependency -- see `requirements.txt`:
`psycopg2-binary==2.9.9`, used for WebODM's own `webodm_dev` connection --
reused here rather than adding a second Postgres driver). Bumped from
2.8.6 after a real, confirmed production failure: that version's bundled
libpq (11.5) predates Postgres 17's newer "direct SSL"/ALPN connection
negotiation, which embeddingsdb (Postgres 17.5) uses -- causing
`psycopg2.connect()` to fail with an ambiguous "SSL SYSCALL error: Success"
while the system's own (newer) `psql` connected fine with the identical
DSN, on the same host, same container.

Structure and error-handling style mirror `label_studio_client.py` /
`coreplugins/ckan/publisher.py` -- the existing precedents in this repo for a
plugin's own client module talking to an external service, raising clear,
typed exceptions rather than swallowing errors or returning None/False for a
real failure.

Scope of this module, this increment (Decision 45 -- embed-generate moved
off the Actor onto a Tapis Job on ls6):
  - REAL, working queries: list_sites, create_site, get_site_zoom,
    get_visit_for_task, get_or_create_visit, count_tile_observations.
  - REAL Tapis Job submission: apply_embed_generate() -- embed-generate no
    longer runs as a Tapis Actor (Abaco) at all. Live testing (Decision 45)
    found Abaco's worker pool cannot provision for this workload's image
    size on this tenant (confirmed with two differently-sized real images,
    both failing identically -- zero workers ever provisioned). It now
    submits a real Tapis Job against TACC's `ls6` system instead
    (`WO_EMBED_GENERATE_APP_ID`/`WO_EMBED_GENERATE_APP_VERSION`,
    webodm/settings.py; see `embeddings-tapis-actors/ls6/` for the App
    definition and job script, mirroring the working `nodeodm-ls6`
    pattern). apply_embed_generate() is a fully self-contained Celery task
    function -- queued via app.plugins.worker.run_function_async, NOT
    called directly -- that resolves Decision 30's previously-open
    credential question by mirroring coreplugins/ckan/publisher.py's
    apply_ckan_publish() EXACTLY: a per-USER stored, refreshable
    TapisOAuth2Token (app/models/oauth2.py), not a generic "service account"
    (Decision 30's original speculation was corrected -- see design spec
    Decision 37). It builds a real tapipy `Tapis(base_url=..., access_token=
    ...)` client from that token and calls `t.jobs.submitJob(...)` (method/
    kwarg shape confirmed against the installed tapipy the same way
    Decision 43 confirmed sendMessage's shape, before this decision replaced
    sendMessage with submitJob entirely).
  - `model-train`'s Actor (`WO_MODEL_ACTOR_ID`) is untouched by Decision 45
    -- it has no evidence of the same image-size problem (it isn't
    implemented yet at all). queue_model_train() remains a stub -- see its
    own docstring for why (no `POST .../workspace/train` endpoint exists
    yet to call it from).
"""

import logging

import psycopg2
from django.conf import settings

logger = logging.getLogger('app.logger')

# embeddingsdb is a small Tapis Pod handling low-volume plugin traffic (a
# handful of task-panel/workspace actions) -- a short connect timeout is
# enough to fail fast rather than hang a Django request thread.
DEFAULT_CONNECT_TIMEOUT = 10  # seconds


class EmbeddingsDBConfigError(RuntimeError):
    """Raised when WO_EMBEDDINGS_DB_URL isn't configured."""


class EmbeddingsDBError(RuntimeError):
    """Raised on a real connection/query failure against embeddingsdb.
    Mirrors label_studio_client.LabelStudioAPIError's "raise a clear
    exception, don't fail silently" style.
    """


# ── Config / low-level connection + query helpers ──────────────────────────

def _connect():
    """
    Opens a new connection to embeddingsdb. One short-lived connection per
    call -- this plugin's call volume does not justify a pool, matching
    label_studio_client.py's per-call `requests.request()` simplicity.
    """
    url = (getattr(settings, 'WO_EMBEDDINGS_DB_URL', '') or '').strip()
    if not url:
        raise EmbeddingsDBConfigError(
            "WO_EMBEDDINGS_DB_URL is not configured -- the embeddings plugin's "
            "database-backed features are inactive until it is set."
        )
    try:
        return psycopg2.connect(url, connect_timeout=DEFAULT_CONNECT_TIMEOUT)
    except psycopg2.Error as e:
        logger.exception('Could not connect to embeddingsdb')
        raise EmbeddingsDBError(f'Could not connect to embeddingsdb: {e}') from e


def _execute(query, params=None, fetch=None, commit=False):
    """
    Shared cursor/error-handling helper for every query below.
    fetch: None | 'one' | 'all'. Raises EmbeddingsDBError on any psycopg2
    failure -- callers never have to guess whether a None/[] return means
    "no rows" or "the query actually failed".
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(query, params or ())
            except psycopg2.Error as e:
                conn.rollback()
                logger.exception('embeddingsdb query failed: %s', query)
                raise EmbeddingsDBError(f'embeddingsdb query failed: {e}') from e

            result = None
            if fetch == 'one':
                result = cur.fetchone()
            elif fetch == 'all':
                result = cur.fetchall()

            if commit:
                conn.commit()
            return result
    finally:
        conn.close()


# ── sites ───────────────────────────────────────────────────────────────────

def list_sites():
    """
    SELECT id, name FROM sites -- for the "existing site" dropdown
    (Decision 27: site_id is required and user-chosen at embed time, an
    existing site or a new one, never inferred).

    Returns a list of (id, name) tuples, id as str (uuid), ordered by name.
    """
    rows = _execute('SELECT id, name FROM sites ORDER BY name;', fetch='all')
    return [(str(row[0]), row[1]) for row in (rows or [])]


def create_site(name):
    """
    INSERT INTO sites (name) VALUES (...) RETURNING id -- the "new site" path
    of Decision 27's required site_id selection.

    Returns the new site's id (str, uuid).
    """
    if not name or not str(name).strip():
        raise ValueError('create_site() requires a non-empty name.')
    row = _execute(
        'INSERT INTO sites (name) VALUES (%s) RETURNING id;',
        (str(name).strip(),),
        fetch='one',
        commit=True,
    )
    return str(row[0])


def get_site_zoom(site_id):
    """
    Returns the zoom level already used by any existing `tile_grid` rows for
    this site, or None if the site has no `tile_grid` rows yet -- this is
    what makes Decision 24's zoom-lock check possible ("tile_grid zoom is
    locked per site once set by its first visit").

    `tile_grid` has UNIQUE(site_id, z, x, y) but nothing at the DB level
    prevents distinct z values across rows for the same site if a caller
    ever bypassed the lock -- ORDER BY created_at ASC LIMIT 1 deliberately
    returns the zoom of the EARLIEST tile_grid row (the site's original,
    locked-in zoom), matching Decision 24's "set by whichever visit is
    embedded first" framing, rather than an arbitrary row.
    """
    row = _execute(
        'SELECT z FROM tile_grid WHERE site_id = %s ORDER BY created_at ASC LIMIT 1;',
        (site_id,),
        fetch='one',
    )
    return row[0] if row else None


# ── visits ──────────────────────────────────────────────────────────────────

def get_visit_for_task(webodm_task_id):
    """
    Read-only lookup: the most recently created `visits` row for this WebODM
    task (source='webodm'), or None if embed-generate has never been
    triggered for this task yet. Does NOT insert a row -- deliberately
    distinct from get_or_create_visit() below, so a polling GET
    (TaskEmbedStatusView) never has the side effect of creating database rows.

    Returns a dict {'id': str, 'site_id': str, 'capture_date': date|None} or
    None.

    Looked up by webodm_task_id alone (no site_id param): GET
    .../task/{pk}/embed-status (design spec "API Endpoints") does not carry a
    site_id, and the v1 UI flow triggers at most one "Generate Embeddings"
    site selection per task. ORDER BY created_at DESC LIMIT 1 is a
    deliberate tie-breaker if that assumption is ever violated (e.g. the same
    task embedded against two different sites), not a claim that it can't
    happen.
    """
    row = _execute(
        "SELECT id, site_id, capture_date FROM visits "
        "WHERE webodm_task_id = %s AND source = 'webodm' "
        "ORDER BY created_at DESC LIMIT 1;",
        (webodm_task_id,),
        fetch='one',
    )
    if not row:
        return None
    return {'id': str(row[0]), 'site_id': str(row[1]), 'capture_date': row[2]}


def get_or_create_visit(site_id, webodm_task_id, project_pk, capture_date=None):
    """
    Real upsert-style logic (Decision 26): find the existing `visits` row for
    this (site_id, webodm_task_id) pair with source='webodm', or insert a new
    one if none exists. This is the only function in this module that
    creates a `visits` row for a WebODM task -- called from
    TaskEmbedView.post(), never from a GET/polling path.

    `visits.webodm_task_id` maps to WebODM's own Task.id (a UUIDField,
    app/models/task.py) but is NOT a real FK -- separate Postgres instance
    from webodm_dev (Decision 26). There is no DB-level
    UNIQUE(site_id, webodm_task_id) constraint on `visits` (see
    embeddingsdb.sql) -- this function's own SELECT-then-INSERT is what keeps
    one (site_id, webodm_task_id, source='webodm') combination from silently
    multiplying into duplicate `visits` rows across repeated calls.

    `project_pk` (Decision 41, new column) is the WebODM Project.id this task
    belongs to -- required so embed-generate can construct WebODM's
    project-nested tiler URL from visit_id alone. Only set on INSERT, not
    backfilled onto an existing row (a task cannot move projects mid-flight
    in a way this function needs to react to).

    Returns the visit's id (str, uuid).
    """
    existing = _execute(
        "SELECT id FROM visits WHERE site_id = %s AND webodm_task_id = %s "
        "AND source = 'webodm' LIMIT 1;",
        (site_id, webodm_task_id),
        fetch='one',
    )
    if existing:
        return str(existing[0])

    row = _execute(
        "INSERT INTO visits (site_id, source, webodm_task_id, project_pk, capture_date) "
        "VALUES (%s, 'webodm', %s, %s, %s) RETURNING id;",
        (site_id, webodm_task_id, project_pk, capture_date),
        fetch='one',
        commit=True,
    )
    return str(row[0])


# ── tile_observations ────────────────────────────────────────────────────────

def count_tile_observations(visit_id):
    """
    SELECT COUNT(*) FROM tile_observations WHERE visit_id = %s -- the real
    query TaskEmbedStatusView needs for embed-status polling ("N of M tiles
    processed").

    Note on scope: this returns N (tiles actually processed so far), which is
    a real, live count. M (the total tile count expected at the requested
    zoom) is NOT computed here -- that requires enumerating WebODM's own
    tiler coverage (app/api/tiler.py's tile_exists(z, x, y), per Decision 9),
    a WebODM-side computation this DB-client module has no part in. Callers
    that want a real "N of M" should compute M separately; this increment
    only makes N real.

    Returns an int (0 if the visit has no tile_observations rows, including
    if visit_id is falsy).
    """
    if not visit_id:
        return 0
    row = _execute(
        'SELECT COUNT(*) FROM tile_observations WHERE visit_id = %s;',
        (visit_id,),
        fetch='one',
    )
    return int(row[0]) if row else 0


# ── embed-generate Tapis Job submission -- REAL (Decision 45) ──────────────

def apply_embed_generate(task_id, user_id, site_id, visit_id, zoom, encoder, project_pk, zoom_override=False):
    """
    Celery task function, called ONLY via
    `app.plugins.worker.run_function_async(embeddings_client.apply_embed_generate,
    ...)` from `TaskEmbedView.post()` -- never call this directly.

    Must be fully self-contained -- run_function_async serialises only this
    function's own source via `inspect.getsource()` and `exec()`s it fresh in
    a Celery worker (see app/plugins/worker.py's own docstring: "Functions
    should import any required library at the top of the function body").
    Every import used below is therefore INSIDE this function body, not at
    module level -- this is not stylistic, it will break at runtime
    otherwise, exactly as coreplugins/ckan/publisher.py's apply_ckan_publish()
    (the precedent this mirrors) already documents.

    Resolves Decision 30 (previously unresolved: what credential authorizes
    the async embed-generate/model-train calls) for real, by mirroring
    apply_ckan_publish()'s existing pattern EXACTLY rather than inventing a
    new one: looks up the active TapisOAuth2Client, the triggering user's own
    TapisOAuth2Token, and calls get_or_refresh_access_token() to get a live,
    refreshed JWT -- even though this runs asynchronously via Celery with no
    live HTTP request in flight. This is a per-USER stored, refreshable
    OAuth2 token, NOT a generic "service account" (the design spec's original
    Decision 30 wording speculated the latter -- corrected in Decision 37).

    Builds a real tapipy `Tapis(base_url=..., access_token=<jwt>)` client
    (confirmed against the actually-installed tapipy package's own
    `Tapis.__init__` signature, not just its docs -- see Decision 37) and
    submits a real Tapis Job via `t.jobs.submitJob(**job_spec)` against
    `WO_EMBED_GENERATE_APP_ID` on TACC's `ls6` system -- **not** an Actor
    invocation, per Decision 45: live testing found Abaco's worker pool
    cannot provision for this workload's image size on this tenant
    (confirmed with two differently-sized real images, both failing
    identically -- zero workers ever provisioned). `submitJob`'s call shape
    (each top-level job-spec key as its own kwarg, not a single
    `request_body=`) was confirmed against the installed tapipy the same way
    Decision 43 confirmed `sendMessage`'s shape.

    The message payload set as the Job's `MSG` environment variable
    (`parameterSet.envVariables`) is byte-for-byte
    `embed_generate/main.py`'s unchanged `read_actor_message()` contract
    (Decision 41's fields: visit_id, site_id, zoom, zoom_override, encoder,
    project_pk, webodm_jwt) -- `main.py` itself needed zero changes for this
    move, since it already read its whole payload from a single `MSG` env
    var (Abaco's convention, but nothing about the code was Abaco-specific
    once the message was in `os.environ`). `webodm_jwt` (Decision 44,
    correcting Decision 41) is a genuine WebODM-native JWT minted for this
    SAME Django `user` below -- NOT the Tapis access token used to submit
    the job itself; those are different tokens with different signing
    secrets (confirmed directly: the Tapis token fails against WebODM's own
    tiler endpoint).

    Does not touch GlobalDataStore for status tracking -- unlike
    apply_ckan_publish() (which has no other way to report async progress to
    the frontend), embed-generate's progress already has a real, non-redundant
    channel: `TaskEmbedStatusView.get()` polls embeddingsdb directly via
    `count_tile_observations()` (see that view + get_visit_for_task() above).
    Adding a second, GlobalDataStore-based status mechanism here would just
    be two sources of truth for the same fact -- skipped deliberately, not
    an oversight.

    Raises RuntimeError with a message mirroring apply_ckan_publish()'s own
    error style if the user/client/token/app-id lookups fail. Runs
    fire-and-forget from the caller's perspective (TaskEmbedView.post()
    returns 202 without waiting on this) -- any exception here surfaces only
    in the Celery worker's own logs, matching apply_ckan_publish()'s
    fire-and-forget shape (that one also has no caller waiting on its return
    value; unlike apply_ckan_publish, this function does not currently write
    a GlobalDataStore error record either -- see note above on why a second
    status channel was skipped).
    """
    import base64
    import json
    import logging

    from django.conf import settings as _settings
    from django.contrib.auth.models import User

    from tapipy.tapis import Tapis

    from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token

    _logger = logging.getLogger('app.logger')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise RuntimeError(f'No such WebODM user (id={user_id!r}) to authorize embed-generate.')

    client = TapisOAuth2Client.objects.filter(is_active=True).first()
    if not client:
        raise RuntimeError('No active Tapis OAuth2 client is configured in WebODM.')

    try:
        token_obj = TapisOAuth2Token.objects.get(user=user, client=client)
    except TapisOAuth2Token.DoesNotExist:
        raise RuntimeError(
            f'No Tapis token found for user {user.username}. '
            'Please re-authenticate with Tapis before generating embeddings.'
        )

    jwt = token_obj.get_or_refresh_access_token()
    if not jwt:
        raise RuntimeError(
            f'Tapis token for {user.username} is expired and could not be refreshed.'
        )

    app_id = getattr(_settings, 'WO_EMBED_GENERATE_APP_ID', '')
    if not app_id:
        raise RuntimeError('WO_EMBED_GENERATE_APP_ID is not configured -- cannot invoke embed-generate.')
    app_version = getattr(_settings, 'WO_EMBED_GENERATE_APP_VERSION', '1.0.0')

    t = Tapis(base_url=_settings.TAPIS_BASE_URL, access_token=jwt)

    # Decision 44 correction to Decision 41: the per-user TAPIS access token
    # (`jwt` above) authorizes calling the *Tapis Actors API* (t.actors.
    # sendMessage) -- it is NOT accepted by WebODM's own tiler endpoint.
    # Confirmed directly: forwarding the raw Tapis token as
    # .../tiles.json?jwt=<tapis token> returns "Incorrect authentication
    # credentials." WebODM's `JSONWebTokenAuthenticationQS` (app/api/
    # authentication.py) verifies a JWT signed with WebODM's OWN
    # SECRET_KEY (via rest_framework_jwt) -- a fundamentally different
    # token from a Tapis OAuth2 access token, not an interchangeable one.
    # Fix: mint a genuine, short-lived WebODM JWT for this SAME Django
    # `user` (already resolved above) using rest_framework_jwt's own
    # encode helpers -- the identical mechanism WebODM's own
    # `/api/token-auth/` login view uses (`app/api/urls.py`) -- and send
    # THAT to the Actor as `webodm_jwt`, distinct from the Tapis `jwt`
    # field name to avoid re-confusing the two again. Verified for real:
    # a token minted this way was confirmed to authenticate successfully
    # against a live task's `tiles.json` endpoint.
    from rest_framework_jwt.settings import api_settings as _jwt_settings
    webodm_jwt_payload = _jwt_settings.JWT_PAYLOAD_HANDLER(user)
    webodm_jwt = _jwt_settings.JWT_ENCODE_HANDLER(webodm_jwt_payload)

    message = {
        'visit_id': visit_id,
        'site_id': site_id,
        'zoom': zoom,
        'zoom_override': bool(zoom_override),
        'encoder': encoder,
        'project_pk': project_pk,
        'webodm_jwt': webodm_jwt,
    }

    _logger.info(
        'Submitting embed-generate ls6 Job for task %s (visit %s, site %s, '
        'project %s, zoom %s)',
        task_id, visit_id, site_id, project_pk, zoom,
    )
    # Decision 45: moved off the Actor (Abaco) entirely -- live testing found
    # Abaco's worker pool cannot provision for this workload's image size on
    # this tenant (confirmed: both an ~11.4GB image with the Clay v1.5
    # checkpoint baked in, and a ~6.21GB image without it, failed identically
    # -- zero workers ever provisioned, empty logs, per getExecution()/
    # listWorkers()). Runs as a real Tapis Job on TACC's ls6 instead
    # (embeddings-tapis-actors/ls6/, mirroring the working nodeodm-ls6
    # pattern), submitted via t.jobs.submitJob(**job_spec) -- confirmed
    # against the installed tapipy the same way Decision 43 confirmed
    # sendMessage's shape: submitJob's requestBody schema has non-empty
    # `properties` (name, appId, execSystemId, parameterSet, ...), so each
    # top-level job-spec key is its own kwarg, not a single `request_body=`.
    #
    # embed_generate/main.py needed no changes to its OWN logic for this
    # move -- it already reads its whole invocation payload from a single
    # MSG environment variable (Abaco's convention), and a Tapis Job's
    # parameterSet.envVariables sets that exact same variable inside the
    # SINGULARITY-run container (Tapis pulls & runs
    # ghcr.io/.../embed-generate-latest directly via Apptainer, executing
    # its own ENTRYPOINT -- no wrapper script, see ls6/app.json).
    #
    # MSG is base64-encoded here, NOT plain JSON -- a real bug found via a
    # live ls6 Job run, not assumed: Tapis's SINGULARITY runtime joins
    # EVERY env var (its own _tapisXxx ones plus ours) into a single
    # comma-separated `apptainer run --env k1=v1,k2=v2,...` argument. A
    # plain-JSON MSG value (commas between keys, quoted strings) breaks
    # that naive join -- confirmed from the failed job's own tapisjob.out:
    # "parse error ... bare \" in non-quoted-field". Abaco never had this
    # problem (a real standalone process env var, no joining) -- this is
    # specific to the SINGULARITY/Tapis-Job delivery path. Base64 has no
    # commas/quotes, so it survives untouched; embed_generate/main.py's
    # read_actor_message() decodes it back before json.loads().
    encoded_message = base64.b64encode(json.dumps(message).encode('utf-8')).decode('ascii')

    job_spec = {
        'name': f'embed-generate-{task_id}-{visit_id}',
        'appId': app_id,
        'appVersion': app_version,
        'execSystemId': 'ls6',
        'execSystemLogicalQueue': 'vm-small',
        'archiveOnAppError': True,
        'parameterSet': {
            'envVariables': [
                {'key': 'MSG', 'value': encoded_message},
                {'key': 'EMBEDDINGSDB_URL', 'value': _settings.WO_EMBEDDINGS_DB_URL},
                {'key': 'WEBODM_URL', 'value': _settings.WO_URL},
            ],
            'schedulerOptions': [
                {'arg': f'-A {_settings.TAS_DEFAULT_ALLOCATION}'},
            ],
        },
    }
    t.jobs.submitJob(**job_spec)


# ── model-train Actor invocation -- NOT IMPLEMENTED ─────────────────────────

def queue_model_train(task_type, algorithm, encoder, tile_observation_ids, split_strategy):
    """
    NOT IMPLEMENTED -- there is no `POST .../workspace/train` API endpoint
    yet to call this from (only TaskEmbedView/TaskEmbedStatusView are wired
    so far; see design spec "Files Likely Affected" -- api_views.py's
    workspace/* views don't exist in this increment).

    Decision 30's credential question IS now resolved in principle for this
    function too (Decision 37): the same pattern apply_embed_generate() uses
    -- a per-user, stored, refreshable TapisOAuth2Token, mirroring
    apply_ckan_publish() -- would apply here as well, invoking
    `t.actors.sendMessage(actor_id=settings.WO_MODEL_ACTOR_ID, message=...)`
    (Decision 43's corrected call shape). Wiring it for real (as its own
    `apply_model_train()` self-contained Celery task
    function, called via run_function_async from a future `.../workspace/train`
    view) is later work, not done in this increment.
    """
    raise NotImplementedError(
        'queue_model_train() cannot run yet: there is no POST '
        '.../workspace/train endpoint yet to call it from. Decision 30\'s '
        'credential question is resolved in principle (see Decision 37 and '
        'apply_embed_generate() above) -- only the wiring itself is later work.'
    )

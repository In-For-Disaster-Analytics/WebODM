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
`psycopg2-binary==2.8.6`, used for WebODM's own `webodm_dev` connection --
reused here rather than adding a second Postgres driver).

Structure and error-handling style mirror `label_studio_client.py` /
`coreplugins/ckan/publisher.py` -- the existing precedents in this repo for a
plugin's own client module talking to an external service, raising clear,
typed exceptions rather than swallowing errors or returning None/False for a
real failure.

Scope of this module, this increment:
  - REAL, working queries: list_sites, create_site, get_site_zoom,
    get_visit_for_task, get_or_create_visit, count_tile_observations.
  - Explicitly OUT of scope: queue_embed_generate()/queue_model_train() stay
    NotImplementedError stubs -- the `embed-generate`/`model-train` Tapis
    Actors are not registered with Tapis yet (Actor registration is a
    distinct Tapis subsystem from the Pod registration already done for
    embeddingsdb itself -- see embeddings-tapis-actors/README.md's own "What
    is NOT in this increment" / "How a future implementer should proceed",
    steps 6-7). There is no Actor ID anywhere in WebODM's settings to invoke,
    so faking a queued call here would be indistinguishable from a real one
    to a caller -- these raise clearly instead of silently no-op'ing.
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


def get_or_create_visit(site_id, webodm_task_id, capture_date=None):
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
        "INSERT INTO visits (site_id, source, webodm_task_id, capture_date) "
        "VALUES (%s, 'webodm', %s, %s) RETURNING id;",
        (site_id, webodm_task_id, capture_date),
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


# ── embed-generate / model-train Actor invocation -- NOT IMPLEMENTED ────────

def queue_embed_generate(webodm_task_id, visit_id, zoom, encoder='clay-v1.5-large-rgb'):
    """
    NOT IMPLEMENTED. Queuing the `embed-generate` Tapis Actor requires a real
    Tapis Actor ID (`WO_EMBEDDINGS_ACTOR_ID` in the design spec's "New Django
    settings" list) -- but the Actor itself is not registered with Tapis yet.
    Actor registration is a distinct Tapis subsystem from the Pod
    registration already done for embeddingsdb (Decision 33); see
    `embeddings-tapis-actors/README.md`'s own "What is NOT in this
    increment" / "How a future implementer should proceed" steps 6-7 for
    what's still missing before this can be real.

    Deliberately raises rather than silently no-op'ing or faking a queued
    job -- a caller (TaskEmbedView.post()) must be able to tell the
    difference between "this is genuinely queued" and "there is nothing to
    queue yet".
    """
    raise NotImplementedError(
        'queue_embed_generate() cannot run yet: the embed-generate Tapis '
        'Actor is not registered with Tapis, so there is no Actor ID to '
        'invoke. embeddingsdb itself is live (Decision 33) and the visit '
        'this call would have queued embedding for has already been '
        'recorded -- only the Actor invocation itself is not implemented. '
        'See embeddings-tapis-actors/README.md "How a future implementer '
        'should proceed", steps 6-7.'
    )


def queue_model_train(task_type, algorithm, encoder, tile_observation_ids, split_strategy):
    """
    NOT IMPLEMENTED, for the same reason as queue_embed_generate() above: the
    model-train Tapis Actor is not registered with Tapis yet (no
    `WO_MODEL_ACTOR_ID` exists to invoke).
    """
    raise NotImplementedError(
        'queue_model_train() cannot run yet: the model-train Tapis Actor is '
        'not registered with Tapis, so there is no Actor ID to invoke. See '
        'embeddings-tapis-actors/README.md "How a future implementer should '
        'proceed", steps 6-7.'
    )

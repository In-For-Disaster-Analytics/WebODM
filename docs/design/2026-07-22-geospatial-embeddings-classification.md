# Geospatial Embeddings & Classification System — Design Spec

## Status

**Implementing** — passed a 5-reviewer spec-review pass (Decisions 26-31); implementation underway. See Decision 38 for the frontend's real-vs-stub scope (`EmbeddingsPanel.jsx`, task-detail panel only). See Decision 44 for `embed-generate`'s real pipeline (WebODM-sourced visits only, per Decision 40) — code-complete; live-verified against real services up through tile enumeration, but the per-tile Clay inference loop is **not yet confirmed working on either candidate execution backend**: local Docker (OOM, Docker Desktop's memory cap) or the registered Tapis Actor (real live test: Abaco's worker pool never provisions for images ≥~6GB — confirmed with two differently-sized real images, both failing identically). **See Decision 45 (PROPOSED, not yet approved)** for a plan to move `embed-generate` off Actors entirely onto a Tapis Job on TACC's ls6 HPC system, mirroring the already-working `nodeodm-ls6` pattern — do not implement until that decision is approved. Still not built at all: the cross-project Embeddings & Classifier workspace, `model-train`'s real logic, the Label Studio webhook receiver, and the `mlflow` Pod.

## Objective

Add a WebODM coreplugin and supporting Tapis infrastructure (Postgres+pgvector Pod, an MLflow Pod for experiment tracking/model registry, an embedding-generation Actor, a model-training Actor) with two distinct surfaces: (1) a task-detail panel where a user selects tiles and either sends them to Label Studio for labeling or generates embeddings from a foundation encoder, and (2) a new top-level "Embeddings & Classifier" page — reached via its own navbar entry, independent of any single project or task — where a user pools embeddings/labels/covariates across any combination of tasks and projects, trains a model via a rigorous train/test/tune/diagnostics pipeline, and reviews predictions. The system also integrates with the real DSO STAC API as a second raster source — browsing/importing external STAC-cataloged imagery alongside WebODM tasks, and (opt-in, gated on WebODM's own public/private flags) publishing WebODM tasks' own imagery back to that catalog. This is Phase 2 of issue #9, scoped against the Phase 1 research recommendation on #18 (go with Clay v1.5, RGB-only, no custom training yet).

## User Need

**Primary user** — Same as the labeling/embeddings research: a team member reviewing completed WebODM tasks who wants to classify features (structures, vegetation, damage indicators, water extent), and — as this design was pushed to generalize — potentially regress a continuous quantity or detect change between surveys of the same site over time, without hand-labeling every tile or building a bespoke ML pipeline per site.

**Job-to-be-done** — From a task's detail view, select tiles, label them or generate embeddings for them. Separately, from a dedicated Embeddings page, pick whatever set of tasks (from any project) are relevant, train against their pooled data, and review results — without that pooling being artificially capped at "tasks in the same project."

**Current pain** — No integration exists today. The Phase 1 research validated an encoder (Clay v1.5) and a labeling tool (Label Studio, deployed and working — see `label-studio-tapis-auth` repo) independently, but nothing connects them to WebODM, to each other, or across tasks/projects.

**Definition of success** — A user can: (1) select tiles on a task, label them or generate embeddings; (2) from the Embeddings page, select any combination of tasks/projects whose embeddings and labels exist, train a model, and see predictions, with low-confidence ones flagged for a return trip to Label Studio.

**Assumptions** —
- Encoder choice is Clay v1.5, RGB-only, per the approved Phase 1 recommendation (#18). DSM/multispectral fusion directly into the embedding vector was tested and found to hurt (Clay base 53.3%→20%, Clay large 40%→33.3%, Galileo nano 13.3%) — out of scope for the embedding itself; DSM/DTM instead feed the separate `covariates` table (see schema).
- Task-level actions (select tiles, label, generate embeddings) are user-triggered, never automatic on task completion — matches `objdetect`'s manual-trigger pattern, avoids the corral-backup-incident failure mode of unthrottled automatic jobs.
- Model training and prediction review are **not** project-scoped. Real evidence: Phase 1's own bake-off pooled labeled tiles from Bethel and Austin — two different WebODM projects. A project-scoped training feature couldn't even reproduce research already done.
- Embeddings DB is a new, separate Postgres+pgvector Tapis Pod, decoupled from `webodm_dev` — **zero schema changes to WebODM's own database** (see Decision 26): the `webodm_task_id`/`visit_id` mapping lives entirely inside `embeddingsdb` as a column on `visits`, not as a new field on WebODM's own `Task` model.
- Label Studio integration is a deep link + API call (project create/import), not an iframe embed or shared domain — same reasoning as the CKAN plugin: proxy credentials server-side, don't merge infrastructure that doesn't need merging.
- **v1 implementation ships classification only.** The schema below is deliberately generalized (continuous values, change detection, external data sources) because retrofitting it later is expensive and the need was concretely identified this round — but the training Actor, UI, and test plan in this spec build and validate the classification path only. Regression and change-detection are schema-ready, not feature-complete; see Decisions and Open Questions.

---

## Current Code/System Summary

### Plugin Architecture

Same extensible plugin system used by every other coreplugin (`app/plugins/__init__.py`: `PluginBase`, `MountPoint`, `Menu`, `GlobalDataStore`, Celery async via `app/plugins/worker.py`).

Two `PluginBase` hooks matter here beyond what earlier plugins in this repo have needed:
- **`main_menu()`** — returns `Menu` objects that add a real entry to WebODM's top-level navbar. Confirmed working precedent: `coreplugins/projects-charts/plugin.py` — `return [Menu(_("Charts"), self.public_url(""), "fa fa-chart-bar")]`.
- **`app_mount_points()`** — registers full Django views (not just DRF API endpoints) at the plugin's own URLs, independent of any task/project route, and can return more than one `MountPoint`. Same `projects-charts` plugin uses this to query `Project.objects` and `Task.objects` directly, across the whole instance, and render a standalone page. This is the exact mechanism both the Embeddings & Classifier page **and** the separate per-model Diagnostics page need (`.../embeddings/`, `.../embeddings/models/<id>/`) — one nav entry via `main_menu()`, two pages via two `app_mount_points()` routes. Already proven in production — no restart required either, since `requires_restart()` is only triggered by `root_mount_points()`, not `app_mount_points()`.

### Task Model (`app/models/task.py`)

- `ASSETS_MAP` (line ~178) maps friendly asset names (`orthophoto.tif`, `dsm.tif`, `dtm.tif`, `georeferenced_model.laz`, etc.) to their on-disk paths.
- `get_asset_download_path(asset)` / asset download URL: `/api/projects/{project_pk}/tasks/{task_pk}/download/{asset}` — same mechanism the CKAN plugin already uses for remote resource links.
- `available_assets` (ArrayField) tells the plugin which of DSM/DTM/orthophoto actually exist for a given task — relevant since Phase 1 research found DSM/DTM are commonly available (confirmed for Bethel) even when multispectral bands are not (confirmed absent in 4/4 checked tasks).

### Existing Plugin Precedents

- **`objdetect`** (`coreplugins/objdetect/`): task-level `MountPoint`s (`task/(?P<pk>[^/.]+)/detect`), async Celery job, results attached to the task. This is the shape for the per-task embedding-generation action. Its UI mounts via `PluginsAPI.Map.willAddControls` (a map control), same as `upstream` — noted here because an earlier draft of this spec incorrectly implied `upstream` had its own project-level UI surface; it doesn't, its config is merely project-scoped on the backend.
- **`projects-charts`** (`coreplugins/projects-charts/`): the real precedent for the new top-level page — see above.
- **`ckan`** (`coreplugins/ckan/`, see `docs/design/2026-07-08-publish-to-ckan.md`): the precedent for proxying an external Tapis-authenticated service server-side rather than exposing credentials to the browser, and for the modal-overlay pattern (`position: fixed`, dimmed backdrop, centered panel) the task-detail Embeddings panel reuses directly.

### Label Studio Integration (already live, separate repo)

`In-For-Disaster-Analytics/label-studio-tapis-auth` — self-hosted Label Studio with a custom `TapisOAuth2Backend` (RS256-verified, unlike WebODM's own unverified `app/auth/tapis_oauth2.py` — see that repo's README for the gap this closes). Deployed as a Tapis Pod (`https://labelstudio.pods.portals.tapis.io`), session-persistence bug fixed and verified (see that repo's `tapis_auth/views.py`/`backend.py`). This plugin calls its REST API (project create, task import) using the requesting user's existing Tapis identity — no separate Label Studio account.

### Phase 1 Research Findings This Design Is Scoped Against (#18)

- Encoder: **Clay v1.5, RGB-only** — validated on two real sites (53.3%/40% base/large leave-one-out accuracy at Bethel vs. MOSAIKS' 20% baseline).
- Model size: dead tie (base ≈ large, 37.1% combined) — no evidence larger helps.
- DSM/multispectral fusion **directly into the embedding**: tested and found to hurt in every configuration (Clay base/large, Galileo nano). Feeds the `covariates` table instead, not the embedding.
- Own task history has a real multispectral-processing gap (4/4 checked WebODM tasks came back RGB-only despite multispectral-capable sensors) — tracked as a separate follow-up.
- The bake-off itself pooled labeled tiles across two different projects (Bethel, Austin) — direct evidence that model training cannot be project-scoped.

---

## Proposed Design

### Architecture Overview

Two UI surfaces, deliberately different scopes:

```
Task detail panel (per-task, via Dashboard.addTaskActionButton)
  ├─ Select tiles from THIS task's imagery
  ├─ "Label in Label Studio"   → proxies to label-studio-tapis-auth's API, deep-links user in (SSO, no second login)
  ├─ "Generate Embeddings"     → Celery-queued call to a Tapis Actor running Clay v1.5 over selected tiles
  │                                  → vectors written to the embeddings Pod (Postgres+pgvector)
  │                                  → covariates (elevation/slope/aspect/CHM/NDVI) computed independently, when DSM/DTM/multispectral exist
  │                                  → labels (from either path) join to the same tile_observation
  └─ "Publish to STAC" (opt-in, gated on task/project already public — Decision 21)
                                    → creates/reuses a per-site collection + item in the real DSO STAC API
                                    → asset href reuses WebODM's own existing download endpoint (Decision 23)
                                    → "Retract from STAC" becomes available once published (Decision 31)

Embeddings & Classifier page (instance-wide, via main_menu() + app_mount_points())
  ├─ Browse/select ANY tasks across ANY projects (queries Project/Task directly, like projects-charts does)
  ├─ Browse/import external imagery from the DSO STAC API as an additional raster source (Decision 19)
  ├─ See aggregate embedded/labeled tile counts across the selection
  ├─ Train a model (task_type: classification in v1; regression/change_detection schema-ready, not built)
  │    → Tapis Actor trains over the pooled (embeddings ⨝ covariates ⨝ labels) for the selected observations
  │    → real train/test split, hyperparameter tuning, and diagnostics, tracked in MLflow (Decisions 16-17)
  └─ Review predictions, with low-confidence rows linking back to Label Studio for review
```

### New Infrastructure (Tapis)

| Component | Type | Purpose |
|---|---|---|
| `embeddingsdb` | Pod (Postgres+PostGIS+pgvector) — **live, 2026-07-23** | Stores the schema below. Decoupled from `webodm_dev`. Real provisioning path differs from the original plan — see Decision 33. |
| `mlflow` | Pod (MLflow Tracking Server) | Experiment tracking + Model Registry for everything `model-train` trains — params, metrics, diagnostic-plot artifacts, versioned model objects. Backend store on Postgres (own database, can share the `embeddingsdb` instance); artifact store on a persistent Tapis Volume. |
| `embed-generate` | Actor **(execution backend under review — see Decision 45, PROPOSED)** | Given a task and a zoom level, runs Clay v1.5 over **every** tile WebODM's own tiler produces for that task's orthophoto at that zoom (see `tile_grid` below) — not a hand-picked subset — writes `embeddings` rows, and separately computes `covariates` from DSM/DTM/multispectral where available. User-triggered only. Real live testing (Decision 45) found Abaco's worker pool cannot provision for this image's size (≥~6GB) on this tenant — a pivot to a Tapis Job on TACC's `ls6` (mirroring the working `nodeodm-ls6` pattern) is proposed, not yet approved. |
| `model-train` | Actor | Given an arbitrary set of `tile_observation`s (spanning any tasks/projects) and a `task_type`, trains a model (split → tune → fit → diagnostics, all logged to MLflow), writes `models`/`model_inputs`/`predictions` rows to embeddingsdb with a pointer (`mlflow_run_id`) into the tracked run. v1 implements `task_type=classification` only. |
| `encoder-bakeoff` | Workflow | Reruns the Phase 1 bake-off methodology against new sites/labels as they accumulate — not a v1 requirement, listed for completeness against #19's original scope. |
| DSO STAC API *(existing, not new)* | External service | Real, already-running DSO service (`modflow-suite/stac-platform`, pgSTAC/`stac_fastapi`, prod `https://stacapi.pods.portals.tapis.io/api/v1`) — consumed read-only as a second raster source alongside WebODM tasks. No new Pod/Actor to stand up for this; see "Raster Source Independence" below. |

### Embeddings DB Schema

The previous draft of this schema tied `tiles` to a single `visit`, and `classifiers` to a single `project_id`. Both were real bugs: the first makes change detection (comparing the same location across dates) impossible to express; the second directly contradicts Phase 1's own cross-project bake-off. Rewritten:

```
sites             (id, name, ...)

tile_grid         (id, site_id FK, z, x, y, bounds geometry)
                    -- a STABLE spatial cell for a site, independent of any one survey date.
                    -- Exists so "the same location, observed on different dates" is a real,
                    -- queryable relationship, not something inferred after the fact.
                    -- (z, x, y) are WebODM's OWN tile coordinates -- see "Tile coverage" below.
                    -- Not a bespoke grid; reuses infrastructure that already exists.

visits            (id, site_id FK, source, webodm_task_id [nullable],
                     stac_collection_id [nullable], stac_item_id [nullable], capture_date)
                    -- source: 'webodm' | 'stac' | 'openaerialmap' | 'dronedb' | ...
                    -- webodm_task_id is null for non-WebODM visits.
                    -- stac_collection_id/stac_item_id reference a real collection/item in the
                    -- DSO STAC API (https://stacapi.pods.portals.tapis.io/api/v1, pgSTAC-backed,
                    -- reads anonymous) -- see "Raster Source Independence" below. NOT exclusive
                    -- to source='stac': a source='webodm' visit gets these populated too, once
                    -- its task is opted into "Publish to STAC" (Decision 20) -- `source` records
                    -- true origin, stac_collection_id/stac_item_id record "also cataloged here,"
                    -- independently. A source='stac' visit is one imported FROM the catalog with
                    -- no WebODM task behind it at all (webodm_task_id stays null).

tile_observations (id, tile_grid_id FK, visit_id FK, pixel_size, ...)
                    -- ONE observation of a grid cell, at one point in time. This is what
                    -- embeddings/covariates/labels actually key off -- NOT a flat "tile."

encoders          (id, name, version, size, band_config)
                    -- e.g. "clay-v1.5-large-rgb"; each distinct band/modality config is its
                    -- own row -- Phase 1 proved these are not interchangeable.

embeddings        (id, tile_observation_id FK, encoder_id FK, vector)   -- pgvector column

covariates        (id, tile_observation_id FK, elevation, slope, aspect, chm, ndvi, ndwi, ...)
                    -- plain raster-derived features, independent of any encoder; populated
                    -- whenever DSM/DTM/multispectral exist for that observation. The SAME
                    -- computed value (e.g. NDVI) can serve as a covariate for one model and
                    -- as the regression TARGET (via `labels`) for another -- the schema doesn't
                    -- hard-code which role a derived layer plays.

label_classes     (id, site_id [nullable = instance-wide default], value, display_name, color_hex, created_by, created_at)
                    -- controlled vocabulary for category labels. NOT hardcoded to Phase 1's
                    -- 7 land-cover classes -- those ship as the instance-wide default
                    -- (site_id=null) rows, but any site can add its own on top. Exists so
                    -- a classifier trained across many tasks/projects has a consistent label
                    -- vocabulary, not whatever string each labeler happened to type.

labels            (id, tile_observation_id FK, value_type, value, source, created_by, ...)
                    -- value_type: 'category' | 'continuous'. Tied to the observation, not to
                    -- any vector, so labels survive encoder swaps.
                    -- source: 'label_studio' | 'manual' | 'geojson_import'. For value_type=
                    -- 'category', `value` should reference a `label_classes.value` -- enforced
                    -- at the application layer (import/label endpoints), not a hard DB FK,
                    -- since continuous labels don't have a taxonomy row to point at.

model_algorithms  (id, task_type, key, display_name, hyperparameters_schema [JSON, nullable], is_default)
                    -- e.g. task_type='classification', key='random_forest'. Registry of what
                    -- model-train's code actually implements -- NOT user-extensible the way
                    -- label_classes is. Adding a row here requires adding the corresponding
                    -- training function to the Actor; the table just tracks what's deployed
                    -- and lets the UI populate an "Algorithm" choice without a schema change
                    -- next time one is added. hyperparameters_schema is a future hook (e.g.
                    -- n_estimators for RF) -- v1 exposes no tunable hyperparameters in the UI,
                    -- ships one sensible default per task_type.

models            (id, task_type, algorithm, encoder_id FK, mlflow_run_id, split_strategy,
                     split_params [JSON], trained_at, ...)
                    -- task_type: 'classification' (v1) | 'regression' | 'change_detection'
                    -- (schema-ready, not implemented). algorithm references model_algorithms.key.
                    -- mlflow_run_id: pointer into MLflow -- see "Experiment Tracking and Model
                    -- Registry: MLflow" below. Hyperparameters, metrics, and the serialized
                    -- model artifact itself live in MLflow, NOT duplicated as embeddingsdb
                    -- columns -- this table stays a thin join between "a model that predicts on
                    -- our tile_observations" and "the actual tracked experiment run."
                    -- split_strategy: 'random_stratified' | 'spatial_block' | 'temporal_holdout'
                    -- -- see "Train/Test Split, Tuning, and Diagnostics" below for why this is
                    -- a real, named choice and not always plain random. No project_id -- see
                    -- model_inputs.

model_inputs      (model_id FK, tile_observation_id FK, pair_tile_observation_id [nullable], split)
                    -- explicit set of observations a model trained on, regardless of which
                    -- project(s)/task(s) they came from. `pair_tile_observation_id` is set only
                    -- for change_detection models, linking two observations of the same
                    -- tile_grid_id at different dates. `split`: 'train' | 'test' -- which side of
                    -- the holdout each observation landed on, recorded per-model so a reported
                    -- accuracy is auditable, not just asserted.

-- (no model_metrics table -- superseded by MLflow, see "Experiment Tracking and Model
-- Registry: MLflow" below. An earlier draft of this schema had a generic model_metrics
-- key/value table for exactly this; once MLflow is the system of record there's no reason
-- to duplicate what it already tracks natively.)

predictions       (id, tile_observation_id FK, model_id FK, value_type, value, confidence)
```

### Tile Coverage: All Tiles, Not a Hand-Picked Subset

Phase 1's sparse ~100m-spaced sampling grid was a research artifact of needing a human to label each one — not a production tiling scheme, and it doesn't need to be invented for v1. WebODM already tiles every orthophoto exhaustively for its own Leaflet map viewer: `app/api/tiler.py` uses `rio_tiler`/`COGReader` behind a standard XYZ endpoint (`class Tiles: def get(..., z, x, y, ...)`, checking `src.tile_exists(z, x, y)` against the raster's real bounds). At a given zoom level, the full set of `(x, y)` where `tile_exists()` is true is already exhaustive, gapless coverage of the whole orthophoto.

So `tile_grid` reuses this directly instead of defining a new grid: a `tile_observation` is created for every `(z, x, y)` WebODM's own tiler reports as valid for that task, at a configurable zoom level — not a client-side checklist of hand-picked tiles. This resolves what was Open Question 4 in the previous draft.

This also sharpens what tile *selection* actually means, because embedding generation and labeling have different costs and should not share one selection mechanism:
- **Embedding generation** — cheap-ish (batched GPU inference, no human involved). Default: all tiles in the task at the chosen zoom. No manual picking.
- **Labeling** — a human is in the loop; still needs a small, curated subset. This is what the tile checklist in the task-detail panel is actually for (see Wireframe 2) — it was previously drawn as if the same checklist also gated embedding generation, which it shouldn't.

Zoom level is a real cost lever, not a free parameter to max out: finer zoom means more, smaller tiles — more compute, more storage, a larger pgvector index. It should be a deliberate, configurable choice (with a sensible default), not implicitly "highest resolution available."

### Raster Source Independence: WebODM Orthophotos vs. the DSO STAC API

Almost none of the schema above is actually WebODM-specific — `sites`/`tile_grid`/`tile_observations`/`embeddings`/`covariates`/`label_classes`/`labels`/`models`/`model_inputs`/`predictions` all key off `tile_observation_id`, not off a `Task`. Clay v1.5 itself doesn't care whether pixels came from a WebODM orthophoto or a Sentinel-2 scene — it just wants a chip plus band/wavelength/GSD metadata. The one real coupling point is **how a tile's pixels get fetched**: today `embed-generate` only knows how to call WebODM's own `/tiles/{z}/{x}/{y}` endpoint (Decision 9), which serves `task.orthophoto`/`dsm`/`dtm` for a `webodm_task_id`.

The DSO STAC API (`modflow-suite/stac-platform`, real and already running — see `docs/services/stac-api.md`) is the second raster source, not a hypothetical one:

- **Consumed read-only, no new infra.** Its own docs state reads are anonymous (`GET /api/v1/collections`, `/collections/{id}/items`, `/search`); only its write routes need a Tapis Bearer token, and this plugin never writes to it. No new Tapis Pod, no new auth wiring beyond a base URL.
- **Same tile scheme, different pixel source.** `(z, x, y)` is a public web-mercator convention, not WebODM's — so a STAC item's COG asset (resolved via `GET /collections/{id}/items/{id}` → its asset href) can be tiled into the *same* `tile_grid` cells using `rio_tiler` directly (the exact library `app/api/tiler.py` already depends on), instead of WebODM's endpoint. `embed-generate` branches on **whether the visit has a `stac_item_id`** (Decision 20's refinement) — not on `visits.source` directly.
- **Covariates become source-dependent, not schema-dependent.** A STAC item may have no co-located DSM/DTM asset at all (common for optical-only collections) — those `covariates` rows are simply absent, same principle as the existing multispectral-gap row in Risks. NDVI-type covariates are often *easier* from STAC sources that carry NIR+Red bands natively.
- **Band metadata is often better-specified than WebODM's own RGB tiles.** STAC items commonly carry per-band wavelength (`eo:bands`/`raster:bands` extensions) — a more direct match to Clay's conditioning inputs than the closest-sensor-match heuristic (`linz`) used for plain WebODM RGB.
- **Convergence path: approved, see Decisions 20-21, 23.** WebODM tasks now also *publish* to the same DSO STAC API that Subside already dual-publishes to (per its own Integrations) — user-triggered, and only available once the task is already public (Decision 21). Once published, `embed-generate`'s branch condition simplifies from "`visits.source`" to "does this visit have a `stac_item_id`" — a `webodm`-origin visit that's been published takes the same `rio_tiler`-on-asset tiling path as a genuinely `stac`-origin one; only never-published `webodm` visits still use WebODM's own `/tiles/{z}/{x}/{y}` endpoint. The asset href itself reuses WebODM's own existing task-download endpoint — see Decision 23, grounded in the CKAN plugin's identical existing pattern.

Net: the data model was already source-agnostic by design (Decision 7); STAC support is a second `embed-generate` code path plus a browse/import UI, not a schema rewrite.

### Tile Selection UI: Map, Not a Flat Thumbnail Grid

The "Label a Sample" checklist was originally drawn as a flat grid of disconnected tile thumbnails — no spatial context, no relationship between adjacent tiles visible. Corrected: this should be a real map, reusing WebODM's own tile-serving endpoint (the same `rio_tiler`/COG tiler from "Tile Coverage" above) with a `tile_grid` overlay at the selected zoom level. The user clicks cells directly on the map to toggle them into the labeling sample — the same interaction model as WebODM's existing `MapView`, not a new paradigm. This matters beyond cosmetics: choosing *which* tiles to label benefits from seeing where they sit relative to each other and to visible features (e.g., "label a few tiles along this treeline, and a few near the water") — a flat thumbnail grid throws that context away.

### Label Studio Integration: Full Mechanics

Previously specified only as "proxies to label-studio-tapis-auth's API." Fleshed out, grounded in Label Studio's real API (`POST /api/projects/`, project-scoped task import, and a real webhook API supporting `ANNOTATION_CREATED`/`ANNOTATION_UPDATED` events — confirmed against Label Studio's own docs):

1. **Project creation** — on "Label Selected in Label Studio," `label_studio_client.py` calls `POST /api/projects/` with `title` (task name + timestamp) and a `label_config` (the XML labeling-interface definition) **generated from the `label_classes` table** for that site (falling back to the instance-wide defaults) — not a hardcoded string. Adding a class in WebODM before labeling regenerates the choice list Label Studio actually shows.
2. **Task import** — one Label Studio task per selected tile, via the project's bulk import endpoint. Critically, each task's `meta` carries our own `tile_observation_id` (and `webodm_task_id`) — this is the join key for getting labels back to the right row, not something inferred from image filenames.
3. **Webhook registration** — at project-creation time, also register a webhook (`url: {WO_URL}/api/plugins/embeddings/labelstudio-webhook`, `actions: ["ANNOTATION_CREATED", "ANNOTATION_UPDATED"]`, `send_payload: true`). This resolves Open Question 1 concretely: **webhook, not polling** — Label Studio's real API supports per-project webhooks, so there's no need to guess or poll.
4. **Receiving the webhook** — new endpoint, `POST /api/plugins/embeddings/labelstudio-webhook`, reads `task.meta.tile_observation_id` and the annotation `result` from the payload, and upserts a `labels` row (`value_type='category'`, `source='label_studio'`).
5. **Progress surfaced back in WebODM** — the task panel's map selector shows a live count (e.g., "6 selected · 3 labeled so far"), from the `labels` table for the selected `tile_observation_id`s — not from polling Label Studio itself.
6. **Webhook authentication** — the endpoint in (4) must verify the request actually came from our Label Studio instance (shared-secret header at minimum) before writing labels. An open, unauthenticated webhook endpoint that writes to `embeddingsdb` is a real write-path that needs to be closed off, not an afterthought.

### Label Classes and Alternative Label Sources: Not Just Label Studio

Label Studio's manual annotation UI was implicitly treated as the only way labels enter the system, with a fixed 7-class taxonomy. Both are wrong:

- **The taxonomy is extensible, not hardcoded.** `label_classes` ships Phase 1's 7 classes as instance-wide defaults (`site_id = null`), but any site can add its own on top — a new option in the "Label a Sample" section (`+ Add label class`), not a code change. Label Studio's `label_config` is generated from this table at project-creation time, so a newly-added class is immediately labelable.
- **GeoJSON import is a real, separate label source, not a Label Studio workaround.** A user with existing labeled data — field-collected GPS points, an existing GIS layer of building footprints, prior survey annotations — shouldn't have to re-click through Label Studio to re-produce labels that already exist. New endpoint: `POST /api/plugins/embeddings/task/{task_pk}/labels/import-geojson`, accepting a GeoJSON FeatureCollection where each feature carries a label property (configurable key, default `label`). Each feature is spatially matched to a `tile_grid` cell (point-in-cell, or polygon centroid for polygon features — same matching-tolerance question as Open Question 6, not a new problem), and a `labels` row is upserted with `source='geojson_import'`.
- **Unrecognized label values on import are not silently accepted or silently dropped.** If a GeoJSON's label values don't match existing `label_classes` rows, the import flags them for the user to confirm (register as new classes) or remap (merge into an existing class, e.g. "Building" → `building_rooftop`) before anything is committed — a basic data-quality gate against label drift (typos, inconsistent casing, near-duplicate class names) across a system meant to pool labels from many sources.

### Review Loop: Low-Confidence Predictions Back to Label Studio

"Clicking a low-confidence prediction links back to Label Studio" was stated conceptually earlier without mechanics. It reuses the exact same project-creation flow from "Label Studio Integration: Full Mechanics" above, with two differences:

1. **Input set comes from `predictions`, not a manual map selection.** On the Predictions view (List or Map), flagged/low-confidence tiles are selectable the same way tiles are selected in "Label a Sample" — click to toggle on the map, or check a row in the list. A running "N tiles selected for review" count and a **"Send to Label Studio for Review"** button trigger the batch, rather than opening Label Studio per tile (impractical once there are more than a handful of flagged tiles).
2. **The batch can span multiple tasks/projects.** Unlike the task-panel's `.../label` endpoint (scoped to one task), a review batch drawn from the Embeddings page's cross-project predictions may include tiles from several different `webodm_task_id`s. New endpoint: `POST /api/plugins/embeddings/workspace/review`, body `{tile_observation_ids: [...]}` — not nested under a single `task_pk}`. Each imported Label Studio task's `meta` still carries its own `tile_observation_id` (and originating `webodm_task_id`), so labels sync back to the correct row regardless of which task/project each tile came from.

Once new labels land from a review batch (same webhook path, `source='label_studio'`), the Embeddings page should surface "N new labels since this model was trained — retrain?" rather than leaving a stale classifier silently in place. This is what actually closes the active-learning loop: predict → flag low-confidence → review in Label Studio → retrain → predict again.

### Configuring Which Models Can Be Trained

The Task type selector (Classification / Regression (soon) / Change Detection (soon)) picks the *problem type*, but says nothing about *which algorithm* actually trains — that gap is `model_algorithms`. This is deliberately **not** the same kind of "configurable" as `label_classes`:

- **`label_classes` is user-extensible** — it's just a vocabulary string; any site can add one from the UI with no code involved.
- **`model_algorithms` is developer-extensible** — adding "Gradient Boosted Trees" as a classification option means writing the actual training function in `model-train`'s code. The table is a registry of what's been implemented and deployed, not an open-ended user setting. Conflating the two would misrepresent what actually requires engineering work versus what's just data entry.

Mechanically: `GET /api/plugins/embeddings/workspace/algorithms?task_type=classification` returns the available `model_algorithms` rows (v1 ships Random Forest for classification, with Gradient Boosted Trees a straightforward second addition — see below); the Embeddings page renders these as an "Algorithm" dropdown next to Task type, defaulting to `is_default=true`. `models.algorithm` records which one actually trained a given model, so results stay attributable as more algorithms are added later. `hyperparameters_schema` is no longer just a future hook — see the next section for how it's actually used.

### Train/Test Split, Tuning, and Diagnostics

Once training means real ensemble methods (Random Forest, Gradient Boosted Trees) rather than a 1-NN research probe, reporting "it works" without a held-out test set, tuned hyperparameters, and real diagnostics isn't credible — this needs the same rigor as the reference methodology in [Wing et al. 2021, NHESS](https://nhess.copernicus.org/articles/21/807/2021/nhess-21-807-2021.html) (flood-claims Random Forest susceptibility modeling): a 70/30 train/test split, stratified 10-fold cross-validation to tune `n_estimators` and `max_depth`, and diagnostics via ROC-AUC, out-of-bag (OOB) error-based feature importance, and calibration curves. None of this needs to be built from scratch — it's exactly what `scikit-learn` already provides, and `model-train` should call it directly rather than reimplementing any of it:

- **Split**: `sklearn.model_selection.train_test_split(..., test_size=0.3, stratify=labels)` — recorded per-observation in `model_inputs.split`, so which tiles were held out is auditable after the fact, not just asserted.
- **Tuning**: `GridSearchCV` (or `RandomizedSearchCV` once the parameter grid from `model_algorithms.hyperparameters_schema` gets large) with `StratifiedKFold(n_splits=10)`, run **only on the training split** — the test set is never touched until final evaluation, matching the reference paper exactly. The winning combination and per-fold CV scores are logged to MLflow (see next section), not a custom table.
- **Diagnostics**: `RandomForestClassifier(oob_score=True)` gives OOB error and `.feature_importances_` for free; `sklearn.metrics.roc_auc_score`/`roc_curve`, `confusion_matrix`, and `sklearn.calibration.calibration_curve` cover the rest. All of it logged as MLflow params/metrics/artifacts, not embeddingsdb rows.

**One geospatial-specific correction to the reference methodology, not just a copy of it**: a naive random split of individual tiles risks leakage — adjacent tiles are spatially autocorrelated, so a randomly-held-out test tile can still be "easy" because its neighbor was in training, inflating reported accuracy. This is exactly why `tile_grid` (stable spatial cells) and `visits` (dates) exist as first-class schema concepts already (Decision 7) — they're what make **`spatial_block`** (hold out whole contiguous regions of `tile_grid`, not scattered individual tiles) and **`temporal_holdout`** (hold out an entire `visit`, mirroring the reference paper's year-by-year validation) real, selectable `split_strategy` options, not just random. `random_stratified` remains available for small pilot datasets where a spatial/temporal holdout would leave too little data to train on either side.

Surfaced in the UI as **its own page** — `.../models/{model_id}/`, linked from the model name in the Predictions heading ("classification model #7 →") rather than a third tab crammed alongside Predictions' List/Map toggle. Diagnostics is a different concern from picking data or reviewing tile-level predictions: it's "is this specific trained model any good," which deserves its own reviewable surface (split strategy and size, tuned hyperparameters, ROC-AUC, confusion matrix, feature importance, calibration plot), not a scroll-competing tab on the main workspace page. Its data comes from MLflow, proxied server-side — see next section.

### Experiment Tracking and Model Registry: MLflow

The mechanics above need somewhere to actually log params/metrics/artifacts and version trained model objects — building that ourselves (a `model_metrics` key/value table, hand-rolled model-file storage) would be reinventing a solved problem. **MLflow** is the chosen system, not a custom table:

- **New infrastructure**: an `mlflow` Tapis Pod, same pattern as `embeddingsdb` and `label-studio-tapis-auth` — a self-hosted MLflow Tracking Server, backend store on Postgres (a separate database, can share the `embeddingsdb` Postgres instance), artifact store on a persistent Tapis Volume (model pickles, confusion-matrix/ROC/calibration plot images) rather than requiring S3-compatible object storage.
- **`model-train` Actor integration**: wraps training in `mlflow.start_run()`; `mlflow.sklearn.autolog()` (or explicit `log_param`/`log_metric`/`log_figure` calls) captures the `GridSearchCV` search, the winning hyperparameters, per-fold CV scores, and the diagnostic plots as MLflow artifacts. `mlflow.sklearn.log_model(...)` registers the fitted estimator itself in MLflow's Model Registry — giving real model versioning almost for free, rather than a bespoke "which pickle file is this" scheme.
- **`models.mlflow_run_id`** is the only new column needed on our side — a thin join between "a model that predicts on our `tile_observations`" (which MLflow knows nothing about) and "the tracked experiment run" (which embeddingsdb doesn't need to duplicate).
- **Diagnostics endpoint proxies MLflow server-side** (`GET /workspace/models/{model_id}/diagnostics` calls MLflow's REST API using `models.mlflow_run_id`, same "credentials never reach the browser" pattern as the CKAN and Label Studio integrations) rather than the frontend talking to MLflow directly.
- **ClearML considered and not chosen for this piece**, despite real existing precedent in this ecosystem (`embeddings-research/maestro-model/clearml.conf.dist`, from earlier MAESTRO encoder work) — ClearML's differentiator is task orchestration, which is redundant here since Tapis Workflows/Actors already fill that role. MLflow is lighter to self-host for tracking-and-registry alone and has the more direct scikit-learn integration this Actor actually needs.
- New env var: `WO_MLFLOW_TRACKING_URI` (or equivalent on the `model-train` Actor's own config, since the Actor talks to MLflow directly — WebODM's Django side only needs it for the diagnostics-proxy endpoint).

### Plugin File Structure

```
coreplugins/embeddings/
  __init__.py
  manifest.json
  plugin.py                     # PluginBase subclass: main_menu() + app_mount_points() for the
                                 #   new page, api_mount_points() for the task-panel actions
  views.py                      # Django views (app_mount_points): the Embeddings & Classifier
                                 #   page AND the separate per-model Diagnostics page
  api_views.py                  # DRF endpoints: tile selection, label-studio proxy, embed trigger,
                                 #   status, cross-project browse, train, predictions
  label_studio_client.py        # Server-to-server client for Label Studio's own REST API,
                                 #   authenticated with WO_LABEL_STUDIO_API_TOKEN (Decision 32,
                                 #   NOT a Tapis JWT -- that's only for the human deep-link login)
  embeddings_client.py          # Tapis Actor invocation (embed-generate, model-train) + pgvector queries
  mlflow_client.py               # Proxies the Diagnostics page/endpoint to the mlflow Pod server-side
  stac_client.py                 # DSO STAC API client: anonymous reads (browse/import) + Tapis-JWT
                                 #   writes (publish, retract) — see Decisions 19-23, 31
  public/
    EmbeddingsPanel.jsx          # Task-detail: tile checklist + Label/Generate Embeddings actions ONLY
    EmbeddingsWorkspace.jsx      # NEW top-level page: cross-project task picker, aggregate stats,
                                 #   train action, predictions (List/Map only)
    ModelDiagnostics.jsx         # NEW separate page: split/hyperparameters/confusion matrix/ROC/
                                 #   feature importance/calibration for one model_id
  templates/
    load_buttons.js              # PluginsAPI.Dashboard.addTaskActionButton registration
    index.html                   # Server-rendered shell for the Embeddings & Classifier page
    model_diagnostics.html       # Server-rendered shell for the Diagnostics page
```

### API Endpoints

All require an authenticated WebODM user. Task-level endpoints require task ownership; the workspace endpoints below filter to projects/tasks the requesting user has permission to see (same permission model `projects-charts` relies on via Django's ORM + auth). All external calls proxy server-side (Tapis JWT never reaches the browser) — same model as the CKAN plugin.

**Task-detail panel (per-task):**
- `GET  /api/plugins/embeddings/task/{task_pk}/tiles` — candidate tiles for **labeling only** (orthophoto extent, at the same zoom as `embed`, for display in the checklist).
- `POST /api/plugins/embeddings/task/{task_pk}/label` — body `{tile_ids: [...]}`; proxies to `label-studio-tapis-auth`, returns the deep-link URL. Selective, by design.
- `POST /api/plugins/embeddings/task/{task_pk}/embed` — body `{zoom: 19, encoder: "clay-v1.5-large-rgb", site_id: "...", zoom_override: false}` — **no `tile_ids`**; queues `embed-generate` over every valid `(z, x, y)` WebODM's tiler reports for this task at that zoom, returns 202. `site_id` is **required and user-chosen** (Decision 27) — an existing site or a new one, never inferred. If the chosen site already has `tile_grid` rows at a different zoom, the request must set `zoom_override: true` to proceed (surfaced in the UI as an explicit confirmation warning, not a silent override or a hard block).
- `GET  /api/plugins/embeddings/task/{task_pk}/embed-status` — polled by frontend; includes total tile count at the selected zoom.
- `POST /api/plugins/embeddings/labelstudio-webhook` — receives `ANNOTATION_CREATED`/`ANNOTATION_UPDATED` from Label Studio (shared-secret header required); upserts `labels` rows keyed by `task.meta.tile_observation_id`. Not user-facing.
- `GET/POST /api/plugins/embeddings/label-classes` — list/add `label_classes` rows (site-scoped, falling back to instance-wide defaults).
- `POST /api/plugins/embeddings/task/{task_pk}/labels/import-geojson` — body: multipart GeoJSON file + label-property key; spatially matches features to `tile_grid` cells, flags unrecognized label values for confirm/remap, then upserts `labels` rows with `source='geojson_import'`.
- `POST /api/plugins/embeddings/task/{task_pk}/publish-to-stac` — user-triggered (see Decision 20), and **only available when `task.public or task.project.public` is true** (Decision 21) — returns 403 otherwise, since publishing an imagery a user hasn't already made anonymously viewable in WebODM would create new exposure, not just surface existing exposure elsewhere. Creates/reuses a per-site `collection` and a new `item` in the DSO STAC API for the task's orthophoto (and DSM/DTM if present), using the requesting user's own Tapis JWT for the write (same "credentials never reach the browser" pattern as the CKAN/Label Studio proxies — no new secret). Populates `stac_collection_id`/`stac_item_id` on the task's `visit` row. Returns 202; not run automatically alongside `embed`/`label`.
- `POST /api/plugins/embeddings/task/{task_pk}/retract-from-stac` — **new, see Decision 31**; available once the task has been published (`stac_item_id` set). Callable by the task owner or an admin. Calls `DELETE {WO_STAC_API_URL}/collections/{id}/items/{id}` and clears the visit's `stac_collection_id`/`stac_item_id`. Manual by design — a full automatic reconciliation job is a fast-follow, not a v1 requirement.

**Embeddings & Classifier page (cross-project):**
- `GET  /api/plugins/embeddings/workspace/browse` — returns every project/task the user can see, with embedded/labeled tile counts, for the picker.
- `GET  /api/plugins/embeddings/workspace/algorithms?task_type=classification` — returns available `model_algorithms` for the selected task_type, for the Algorithm dropdown.
- `POST /api/plugins/embeddings/workspace/train` — body `{task_type: "classification", algorithm: "random_forest", encoder: "...", tile_observation_ids: [...], split_strategy: "spatial_block"}`; queues `model-train` (train/test split → `GridSearchCV` tuning on the training split → fit → diagnostics), returns 202. `task_type` other than `"classification"` returns 501 in v1.
- `GET  /api/plugins/embeddings/workspace/models/{model_id}/predictions` — returns predictions for display, flagging low-confidence rows.
- `GET  /api/plugins/embeddings/workspace/models/{model_id}/diagnostics` — looks up `models.mlflow_run_id`, proxies MLflow's REST API server-side, returns the Diagnostics tab's data: split summary, tuned hyperparameters, ROC-AUC, confusion matrix, feature importance, calibration curve.
- `POST /api/plugins/embeddings/workspace/review` — body `{tile_observation_ids: [...]}`, may span multiple tasks/projects; creates/imports a Label Studio project the same way `.../task/{pk}/label` does, for a review batch drawn from flagged predictions rather than a manual selection.
- `GET  /api/plugins/embeddings/workspace/stac/collections` — proxies `GET {WO_STAC_API_URL}/collections` (anonymous read), for the "Browse STAC" side of the picker alongside WebODM projects/tasks.
- `GET  /api/plugins/embeddings/workspace/stac/collections/{collection_id}/items` — proxies `GET {WO_STAC_API_URL}/collections/{collection_id}/items` (optionally forwarding a bbox/datetime filter to `/search`).
- `POST /api/plugins/embeddings/workspace/stac/import` — body `{site_id, collection_id, item_id}`; creates a `visits` row (`source='stac'`) referencing the chosen item, so it becomes selectable for embedding generation exactly like a WebODM task's visit.

---

## Files Likely Affected

### Create

1. `coreplugins/embeddings/__init__.py`
2. `coreplugins/embeddings/manifest.json`
3. `coreplugins/embeddings/plugin.py`
4. `coreplugins/embeddings/views.py`
5. `coreplugins/embeddings/api_views.py`
6. `coreplugins/embeddings/label_studio_client.py`
7. `coreplugins/embeddings/embeddings_client.py`
8. `coreplugins/embeddings/mlflow_client.py` — proxies the Diagnostics endpoint to the `mlflow` Pod server-side.
9. `coreplugins/embeddings/stac_client.py` — client for the existing DSO STAC API: anonymous reads (`workspace/stac/*` browse/import) plus Tapis-JWT-authenticated writes (`publish-to-stac`, see Decision 20).
10. `coreplugins/embeddings/public/EmbeddingsPanel.jsx`
11. `coreplugins/embeddings/public/EmbeddingsWorkspace.jsx`
12. `coreplugins/embeddings/public/ModelDiagnostics.jsx` — separate page, not a tab on the Embeddings page.
13. `coreplugins/embeddings/templates/load_buttons.js`
14. `coreplugins/embeddings/templates/index.html`
15. `coreplugins/embeddings/templates/model_diagnostics.html`
16. New repo for the Tapis Actors (`embed-generate`, `model-train`) — **resolved, see Decision 22**: real repo now exists at https://github.com/In-For-Disaster-Analytics/embeddings-tapis-actors, mirroring `label-studio-tapis-auth`'s pattern rather than a `tapis/` directory in this repo. Scaffolded (README, `.env.example`, `Dockerfile`, `requirements.txt`, stub `embed_generate`/`model_train` modules) — no working Actor logic yet, see that repo's own README "Next steps."

### Modify

1. `webodm/settings.py` — new env vars (see below).
2. DSO-Architecture docs (`docs/services/`, `docs/dev/port-reference.md`) once the `embeddingsdb` Pod and Actors exist.

---

## API/Schema Changes

### New Django settings

```python
WO_EMBEDDINGS_DB_URL   = os.environ.get('WO_EMBEDDINGS_DB_URL', '')     # pgvector Pod connection string
WO_EMBEDDINGS_ACTOR_ID = os.environ.get('WO_EMBEDDINGS_ACTOR_ID', '')   # embed-generate Actor
WO_MODEL_ACTOR_ID      = os.environ.get('WO_MODEL_ACTOR_ID', '')       # model-train Actor
WO_LABEL_STUDIO_URL    = os.environ.get('WO_LABEL_STUDIO_URL', '')     # https://labelstudio.pods.portals.tapis.io
WO_LABEL_STUDIO_API_TOKEN = os.environ.get('WO_LABEL_STUDIO_API_TOKEN', '')  # Label Studio's OWN Personal Access Token (Bearer) -- see Decision 32. NOT a Tapis JWT.
WO_LABELSTUDIO_WEBHOOK_SECRET = os.environ.get('WO_LABELSTUDIO_WEBHOOK_SECRET', '')  # shared secret, verifies inbound webhook calls
WO_MLFLOW_TRACKING_URI = os.environ.get('WO_MLFLOW_TRACKING_URI', '')  # MLflow Pod, used by the diagnostics-proxy endpoint (model-train's own config points its Actor runtime at the same URI)
WO_STAC_API_URL        = os.environ.get('WO_STAC_API_URL', 'https://stacapi.pods.portals.tapis.io/api/v1')  # DSO STAC API, existing service, read-only from this plugin
```

### New schema

The `sites`/`tile_grid`/`visits`/`tile_observations`/`encoders`/`embeddings`/`covariates`/`labels`/`models`/`model_inputs`/`predictions` tables above, in the new `embeddingsdb` Pod — not a WebODM/`webodm_dev` migration. WebODM's own DB only needs enough to look up a `visit_id` for a given `task.id` (a mapping table or a stored field on `Task`, TBD — see Open Questions).

---

## Data Flow

```
Task detail panel — two independent actions, different selection granularity:
  ├─ "Label a sample" → map view, click tiles to select → "Label in Label Studio"
  │    → POST .../label {tile_ids}   -- selective, human-in-the-loop
  │    → WO_LABEL_STUDIO_API_TOKEN (Label Studio's own Personal Access Token,
  │      server-side only — Decision 32, NOT the user's Tapis JWT)
  │    → POST Label Studio's own /api/projects/ (label_config) + task import
  │      (each task's meta carries tile_observation_id) + webhook registration
  │    → deep-link opens in a new tab, carrying the user's own Tapis access
  │      token so label-studio-tapis-auth's TapisOAuth2Backend logs them in
  │      (SSO, no second login) -- a separate credential from the line above
  │    → user labels tiles; Label Studio POSTs ANNOTATION_CREATED/UPDATED to
  │      .../labelstudio-webhook (shared-secret verified) → upserts `labels` rows
  │    → map view polls the `labels` count for progress ("6 selected · 3 labeled so far")
  │
  ├─ "Generate Embeddings" (no tile picker — whole task, by zoom level)
  │    → POST .../embed {zoom, encoder}
  │    → Celery queues embed-generate Actor
  │    → if the visit has a stac_item_id (published or genuinely STAC-sourced), Actor reads
  │      the asset href via rio_tiler directly; otherwise hits WebODM's own tiler
  │    → writes `tile_observations` (if not already present) + `embeddings` + `covariates`
  │    → frontend polls /embed-status, shows total tile count processed
  │
  └─ "Publish to STAC" (opt-in, unchecked by default — see Decision 20)
       → POST .../publish-to-stac
       → Tapis JWT (user's existing token) → POST {WO_STAC_API_URL}/collections (if the
         site's collection doesn't exist yet) + POST .../collections/{id}/items
       → visit's stac_collection_id/stac_item_id populated; source stays 'webodm'

Embeddings & Classifier page (separate, instance-wide):
User opens the page from the navbar (no task/project context required)
  → GET .../workspace/browse — every project/task the user can see, with embedded/labeled counts
  → user checks any combination (may span multiple projects, e.g. Bethel Survey 2026 + Austin Water Utility)
  → POST .../workspace/train {task_type: "classification", encoder, tile_observation_ids}
  → model-train Actor joins embeddings ⨝ covariates ⨝ labels for exactly those observations,
    trains a classifier, writes `models` + `model_inputs` + `predictions`
  → GET .../workspace/models/{id}/predictions — low-confidence rows link back to Label Studio
```

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| **Two Tapis Actors + a new Pod is real new infrastructure**, not a small plugin change | Scoped explicitly as Major-tier; this spec exists because of that, not despite it. |
| **Label sync mechanism** | **Resolved, see Decision 10**: real Label Studio webhook (`ANNOTATION_CREATED`/`ANNOTATION_UPDATED`), not polling. |
| **An unauthenticated webhook endpoint would be a real write-path into `embeddingsdb`** | `.../labelstudio-webhook` requires a shared-secret header (`WO_LABELSTUDIO_WEBHOOK_SECRET`); requests without it are rejected before touching `labels`. Hardened further by Decision 29 after security review: constant-time comparison (`hmac.compare_digest`, not `==`) and validation that the incoming `tile_observation_id` corresponds to a session WebODM actually created — the secret alone was instance-wide and didn't scope which `tile_observation_id`s a caller could legitimately write. |
| **No cascade-delete story for `embeddingsdb` rows when a WebODM Task/Project is deleted** | Resolved by Decision 26: `ON DELETE CASCADE` within `embeddingsdb`, triggered by a Django delete signal on `Task`. Signal wiring details and whether a shrinking `model_inputs` set on source-data deletion is the right behavior are tracked as Open Question 16, not blocking. |
| **No stated credential model for the async Tapis Actors (`embed-generate`, `model-train`)** | Resolved by Decision 30: a stored, refreshable service token (mirroring the CKAN plugin's own `apply_ckan_publish` pattern), not a live request JWT — there is no request in flight by the time a Celery-queued Actor actually runs. |
| **Embedding vectors from different encoder configs are not comparable** | `encoders` table treats each band/modality config as a distinct row; `embeddings` always joins through it. |
| **DSM/multispectral fusion temptation in v2** | Explicitly not attempted — Phase 1 measured it hurting. `covariates` exists as the safe outlet for this. |
| **Zoom is locked per site once set by its first visit (Decision 24)** | Not a spatial-join problem — `(z,x,y)` is a fixed global grid, so matching across visits is an exact `(site_id, z, x, y)` lookup once zoom is consistent. The real tradeoff is that a site's zoom becomes effectively permanent after the first embed; mitigated by an explicit override param + UI warning (Decision 27), not by loosening the exactness of matching itself. |
| **Site identity assignment has no described mechanism** | Nothing in v1 said how a WebODM task gets associated with a `site_id` in the first place, or how two tasks re-surveying the same physical location would be recognized as the same site rather than silently becoming two unrelated ones. Resolved by Decision 27: explicit, user-chosen site assignment at `embed-generate` time. |
| **Schema generalization (task_type, change detection, external sources) outruns v1 implementation** | Deliberate: schema is cheap to get right now, expensive to migrate later. v1 *implements* classification only — regression/change-detection are explicitly not built, tracked as Decision 6 and Open Questions, not silently implied as done. |
| **External data sources (`visits.source != 'webodm'`) bring their own licensing obligations** | OpenAerialMap requires CC-BY attribution; DroneDB needs per-dataset review (both already identified in Phase 1). `visits.source` makes provenance queryable, but attribution/compliance enforcement itself is not designed here — open question. |
| **Actor compute cost / Tapis quota** | User-triggered only, never automatic — matches `objdetect`'s manual-trigger precedent. |
| **Own task history's multispectral gap could silently degrade `covariates` completeness** | `covariates` rows are simply absent where source bands don't exist — not backfilled or faked. |
| **A third Tapis Pod (MLflow) is more real infrastructure to stand up and operate** | Deliberate tradeoff over hand-rolling tracking/versioning — see Decision 17. Backend store can share the `embeddingsdb` Postgres instance to avoid a second DB to operate. |
| **STAC items may lack a co-located DSM/DTM asset, or reference assets needing signed/temporary URLs** | Applies to *browsed/imported* STAC items only (Open Question 12, still open); `covariates` rows are simply absent when the source asset doesn't exist. Does not apply to *published* WebODM assets — see Decision 23. |
| **Publishing to the DSO STAC API makes a task's imagery readable by anyone — its reads are anonymous, but WebODM tasks/projects are permissioned** | Real exposure risk, not a plumbing detail. Mitigated by Decision 21: publish is only *available* when `task.public or task.project.public` is already true — the same anonymous-exposure decision the user already makes via WebODM's existing public share-link flags, not a separate consent gate. The asset-href mechanism itself is resolved (Decision 23: reuses WebODM's own existing task-download endpoint, exactly the CKAN plugin's precedent) — this endpoint should still get a security-reviewer pass before implementation, same as any other external write with data-exposure implications. |
| **A task/project can flip from public back to private after being published — the STAC item doesn't retract itself** | Not resolved: `DELETE /collections/{id}/items/{id}` exists on the DSO STAC API, but which credential performs that call on a non-request-driven `public` flip (vs. publish's own live user-JWT-on-request pattern) is unsolved — see Open Question 15 (Decision 21). |

---

## Alternatives Considered

### Two separate plugins (labeling deep-link vs. embeddings UI)

**Rejected** (recorded on issue #19, 2026-07-22): both are entry points into the same loop — pick tiles, route to a human or a model, converge on the same store.

### Fuse DSM/multispectral directly into the embedding vector

**Rejected for v1**, with real evidence: tested via a placeholder-wavelength hack on Clay and via Galileo's native elevation modality; both hurt accuracy relative to RGB-only in every configuration tried. Explicit `covariates` table chosen instead.

### `models` (classifiers) scoped by a single `project_id`

**Rejected**, caught during this design's own review: Phase 1's real bake-off pooled labeled tiles from Bethel and Austin — two different WebODM projects. A `project_id` FK on `models` would make that impossible to represent. Replaced with `model_inputs`, an explicit join table over `tile_observation`s regardless of project.

### Flat `tiles` table tied to one `visit` (no `tile_grid`/`tile_observations` split)

**Rejected**, for change detection specifically: without a stable, time-invariant spatial cell, there's no way to express "the same location, two different dates" as a queryable relationship. The split costs one extra join for every other use case but is required for this one.

### Hand-picked tile checklist for embedding generation

**Rejected**, in favor of all tiles at a configurable zoom level. A manual checklist is the right tool for labeling (a human has to look at each one), but embedding generation has no human in the loop and a manual subset would silently cap coverage — no full classification map, no reliable change detection, no SDM/hazard-modeling use case, all of which want continuous spatial coverage, not sparse points. WebODM's own `rio_tiler`-based `/tiles/{z}/{x}/{y}` endpoint already provides exhaustive, gapless tile enumeration for free — no new grid to invent.

### Custom-trained encoder instead of Clay v1.5

**Deferred**, per the Phase 1 go/no-go: no evidence Clay's transfer is insufficient at production scale. Mechanics discussed in the #18 research thread, not designed here.

### Reverse proxy / shared domain with Label Studio ("true Level 2")

**Deferred**, per the earlier README note in `label-studio-tapis-auth` — a separate nginx/infra step, not needed for the deep-link model this spec uses.

### Bespoke external-imagery importer (arbitrary URLs/uploads) instead of the DSO STAC API

**Rejected**: a generic "paste a raster URL" importer would have to invent its own catalog metadata (bbox, datetime, band/wavelength info) from scratch, and would sit outside the ecosystem's existing dual-publish path (Subside API → STAC + CKAN). The DSO STAC API is real, already running, already the ecosystem's catalog of record for non-WebODM raster outputs, standard (`stac_fastapi`/pgSTAC), and reads require no auth — strictly less work than a bespoke importer for the same result. See "Raster Source Independence" above and Decision 19.

---

## Test Plan

### Unit tests

1. `label_studio_client.py` — mock the Label Studio API; verify project create/import payload and the `Authorization: Bearer {WO_LABEL_STUDIO_API_TOKEN}` header (Decision 32 — not a Tapis JWT).
2. `embeddings_client.py` — mock Actor invocation for both `embed-generate` and `model-train`; verify payload shape, including multi-project `tile_observation_ids` in the train payload.
3. Encoder registry lookups — verify distinct `(model, version, size, band_config)` tuples never silently collide.
4. `model_inputs` — verify a model trained across two different `webodm_task_id`s (different projects) is representable and queryable.
5. **[Added per spec review, Decision 29]** Webhook secret comparison uses `hmac.compare_digest`, not `==` — a targeted unit test isn't strictly necessary for a stdlib call, but the code review for this PR should confirm it's actually used, not just documented.

### Integration tests

1. POST `.../task/{pk}/label` with valid tile selection → 200 + deep-link URL.
2. POST `.../task/{pk}/embed` with valid selection → 202, Celery task queued.
3. GET `.../task/{pk}/embed-status` while running → `status="running"`; after completion → `status="done"`.
4. GET `.../workspace/browse` → returns tasks from multiple projects the user can see, with correct embedded/labeled counts.
5. POST `.../workspace/train` with `tile_observation_ids` spanning two different projects → 202, and — **expanded per tester review**: confirm both projects' `tile_observation_id`s actually land in `model_inputs` (not just that the request is accepted), and that `GET .../workspace/models/{id}/predictions` returns rows for tiles from *both* projects, not just one.
6. POST `.../workspace/train` with `task_type="regression"` → 501 (not implemented in v1, confirms the schema/API distinguishes this rather than silently accepting it).
7. POST `.../workspace/train` with insufficient labels → 400 with actionable message (minimum label count: 30 total + 5 per class, see Decisions 25 and 28).
8. **[Added per spec review]** POST `.../labelstudio-webhook` with a missing/wrong shared-secret header → 401/403, no `labels` row written. Same request with the correct secret and a `tile_observation_id` WebODM never registered → rejected (Decision 29), not silently upserted.
9. **[Added per spec review]** POST `.../task/{pk}/publish-to-stac` when `task.public` and `task.project.public` are both false → 403. Same task after setting `task.public = true` → 202, `visits.stac_collection_id`/`stac_item_id` populated.
10. **[Added per spec review]** POST `.../task/{pk}/retract-from-stac` after a successful publish → 200, `stac_collection_id`/`stac_item_id` cleared, and the DSO STAC API's item is confirmed gone (or the delete call is confirmed issued, against a test double).
11. **[Added per spec review]** Split-strategy leakage check (Decision 16): construct a `site_id` with two adjacent `tile_grid` cells in one visit plus one earlier-visit observation of one of those cells; train with `spatial_block` and confirm the adjacent cell is never in both train and test; train with `temporal_holdout` and confirm every observation from a given `visit` lands entirely on one side of the split, never split across train/test.
12. **[Added per spec review]** POST `.../task/{pk}/labels/import-geojson` with unrecognized label values → 400/422 with the conflicting values returned for confirm/remap, not silently accepted or dropped (Decision 12).

### End-to-end (manual, once Actors/Pod are live)

1. Select tiles on a task → Label in Label Studio → label a few → confirm labels land in `labels` table.
2. Select tiles → Generate Embeddings → confirm `embeddings`/`covariates` rows appear with correct `encoder_id`.
3. From the Embeddings page, select tasks spanning two different projects → Train Classifier → confirm predictions appear, correctly attributed via `model_inputs`.
4. **[Added per spec review]** Publish a public task to STAC → confirm the item is queryable via the real DSO STAC API's own `/search` → Retract it → confirm it's gone.

---

## Documentation Plan

1. `coreplugins/embeddings/README.md` — config, required env vars, Actor/Pod dependencies, and an explicit note that `task_type` in the schema supports more than v1 implements.
2. DSO-Architecture: new service pages for `embeddingsdb` and `mlflow` Pods + Actors, port-reference entries.
3. Settings reference: the `WO_EMBEDDINGS_*`/`WO_MODEL_ACTOR_ID`/`WO_LABEL_STUDIO_URL`/`WO_LABELSTUDIO_WEBHOOK_SECRET`/`WO_MLFLOW_TRACKING_URI` env vars.

---

## Rollout / Rollback

**Rollout gate**: plugin inactive unless `WO_EMBEDDINGS_DB_URL` and `WO_LABEL_STUDIO_URL` are set — same pattern as the CKAN plugin's `WO_DSO_AGENT_URL` gate.

**Rollback**: remove `coreplugins/embeddings/` or unset the env vars; restart WebODM. The `embeddingsdb` and `mlflow` Pods and their data persist independently.

**Dependency**: `label-studio-tapis-auth` pod must be live (already is); `embeddingsdb`, `mlflow`, and both Actors must exist before either path is testable end-to-end.

---

## Open Questions

1. ~~Label sync mechanism~~ — **Resolved, see Decision 10**: real Label Studio webhook (`ANNOTATION_CREATED`/`ANNOTATION_UPDATED`), shared-secret verified.
2. ~~Where do the Tapis Actors live?~~ — **Resolved, see Decision 22**: https://github.com/In-For-Disaster-Analytics/embeddings-tapis-actors, mirroring `label-studio-tapis-auth` rather than a `tapis/` directory in this repo. Created and scaffolded.
3. ~~Minimum label count before training is allowed~~ — **Resolved, see Decision 25**: 30 total, plus a per-class minimum (Decision 28).
4. ~~Grid/tile size for the candidate-tiles endpoint~~ — **Resolved, see Decision 9**: reuse WebODM's existing `rio_tiler` XYZ tile scheme at a configurable zoom level, not a bespoke grid.
5. ~~`covariates` population trigger~~ — **Resolved, see Decision 25**: inside `embed-generate` itself, not a separate Actor.
6. ~~`tile_grid` cell matching tolerance~~ — **Resolved, see Decision 24**: not actually a footprint/spatial-join problem — `(z,x,y)` is a fixed global grid, so matching is exact once zoom is locked per `site_id` (set by the first visit, reused by every later visit at that site).
7. **External data source ingestion + licensing enforcement** — `visits.source` makes OpenAerialMap/DroneDB provenance representable, but the actual ingestion pipeline and attribution/compliance tracking (CC-BY notice generation, DroneDB per-dataset license review workflow) is undesigned.
8. **When do regression and change_detection move from schema-ready to implemented?** Needs real labels/use cases to justify — not scheduled here. Note (from the spec review round): the schema (`model_inputs.pair_tile_observation_id`, `task_type`) is generalized, but the Diagnostics pipeline (ROC-AUC, confusion matrix, OOB feature importance, calibration curve — Decisions 16/18) is classification-specific and would need real rework, not a `task_type` flip. "Schema-ready" should not be read as "methodology-ready."
9. ~~Default `label_config` taxonomy~~ — **Resolved, see Decision 12**: `label_classes` table, instance-wide defaults + per-site additions, editable from the UI.
10. ~~Label-property key convention for GeoJSON import~~ — **Confirmed, see Decision 25**: `label` stays the only default in v1, no per-upload key picker.
11. ~~Should WebODM eventually publish its own finished orthophotos to the DSO STAC API~~ — **Resolved, see Decision 20**: yes, via a user-triggered "Publish to STAC" action.
12. **STAC asset access mechanics for browsed/imported items** — some collections may require signed/temporary URLs or different auth than a plain public COG fetch; not resolved until `stac_client.py` is actually built against real collections.
13. ~~STAC asset href mechanics for published WebODM tasks~~ — **Resolved, see Decision 23**: reuses WebODM's own existing `.../download/{asset}` endpoint, exactly the CKAN plugin's already-working precedent — safe because Decision 21 already requires the task to be public first.
14. ~~Minimum floor before "Publish to STAC" is safe to expose in the UI at all~~ — **Resolved, see Decision 21**: gated on `task.public or task.project.public` (WebODM's own existing share-link flags) rather than a standalone consent checkbox — the action is unavailable, not just unchecked, until the task is already anonymously viewable.
15. ~~Retraction on public→private~~ — **Resolved, see Decision 31**: the imagery itself already self-protects (WebODM's `get_and_check_task` re-checks `public` per request, confirmed by the security-review pass), narrowing the real gap to the STAC item's *metadata* persisting after a public→private flip. Closed via a lightweight, admin/task-owner-invocable "Retract from STAC" endpoint — not a full reconciliation job, which remains a legitimate fast-follow, not a blocker.
16. **Cross-database cascade delete** — new from the spec review round: when a WebODM `Task`/`Project` is deleted, what happens to its `embeddingsdb` rows (`visits`, `tile_observations`, `embeddings`, `covariates`, `labels`, `model_inputs`)? Resolved in principle by Decision 26 (`ON DELETE CASCADE` within `embeddingsdb`, triggered by a Django delete signal on `Task`), but the exact signal wiring and whether a trained model's `model_inputs` silently shrinking when source data is deleted later is acceptable (vs. blocking deletion, vs. soft-delete) is not fully designed — flagged, not blocking implementation of the rest of the plugin.

---

## Decisions

### Decision 1: One coreplugin, not two (Approved — 2026-07-22)
The Label Studio deep-link action and the embeddings-generation UI are the same deliverable. Recorded on issue #19.

### Decision 2: `covariates` stored separately from `embeddings`, never fused (Approved — 2026-07-22)
Injecting DSM elevation into Clay (placeholder wavelength) and Galileo (native elevation modality) both hurt accuracy relative to RGB-only, in every configuration tried. Explicit, non-learned terrain/spectral covariates are stored as their own table.

### Decision 3: Encoder registry keyed on full band/modality config, not just model name (Approved — 2026-07-22)
Clay-base ≠ Clay-large ≠ Clay+DSM ≠ Galileo+DSM produce non-interchangeable vectors. Each distinct configuration is its own `encoders` row.

### Decision 4: Trigger is user-selected and task-level, never automatic (Approved — 2026-07-22)
Matches `objdetect`'s manual-trigger pattern; avoids the corral-backup-incident failure mode.

### Decision 5: Custom encoder training is out of scope for this spec (Approved — 2026-07-22)
Clay v1.5 RGB-only is the v1 encoder. Custom training remains a documented fallback path.

### Decision 6: Model training and prediction review live on a NEW top-level page, not the task panel or a project page (Approved — 2026-07-22, supersedes the original "project-level" framing)
Real evidence: Phase 1's bake-off pooled Bethel + Austin, two different projects. Neither "task-scoped" nor "project-scoped" training could represent that. Uses `main_menu()` + `app_mount_points()`, the same real mechanism `coreplugins/projects-charts` already uses to query across the whole instance.

### Decision 7: Schema generalized for value type, temporal comparison, and external data — before it was strictly needed (Approved — 2026-07-22)
`labels`/`predictions` carry a `value_type` (category/continuous) rather than being classification-only; `tile_grid`/`tile_observations` split enables change detection (same location, different dates); `visits.source` allows non-WebODM imagery (OpenAerialMap, DroneDB) to be pooled identically to WebODM tasks. None of this is implemented beyond classification in v1 — the schema is intentionally ahead of the Actor/UI so the expensive part (a data model migration) doesn't have to happen twice.

### Decision 8: `models.project_id` removed in favor of `model_inputs` (Approved — 2026-07-22)
Direct consequence of Decision 6 — caught as a real inconsistency between the written schema and the already-corrected UI wireframes.

### Decision 9: Embedding generation covers all tiles at a configurable zoom level, reusing WebODM's existing tiler — not a hand-picked checklist (Approved — 2026-07-22)
Phase 1's sparse sampling grid was a research artifact of needing a human to label each tile; it was never meant to be the production tiling scheme. WebODM already tiles every orthophoto exhaustively for its Leaflet viewer (`app/api/tiler.py`, `rio_tiler`/`COGReader`, a standard `/tiles/{z}/{x}/{y}` endpoint checking `tile_exists(z,x,y)`). `tile_grid` reuses those same `(z,x,y)` coordinates directly rather than inventing a new grid. The task-detail tile checklist remains, but only for labeling selection (`.../label`) — `.../embed` takes a zoom level, not `tile_ids`, and processes the whole task. See "Tile Coverage" in Proposed Design and the corresponding Alternatives Considered entry.

### Decision 10: Label sync via a real Label Studio webhook, not polling — with explicit auth (Approved — 2026-07-22)
Label Studio's own API supports per-project webhooks (`ANNOTATION_CREATED`/`ANNOTATION_UPDATED`, confirmed against its docs) — no need to poll or guess. `.../labelstudio-webhook` requires a shared-secret header (`WO_LABELSTUDIO_WEBHOOK_SECRET`) before writing to `labels`, since an unauthenticated write-path into `embeddingsdb` is a real risk, not a hypothetical one.

### Decision 11: "Label a Sample" is a map, not a flat thumbnail grid (Approved — 2026-07-22)
Reuses WebODM's own tile-serving endpoint with a `tile_grid` overlay at the selected zoom; clicking a cell on the map toggles it into the sample. A flat grid of thumbnails throws away spatial context (adjacency, proximity to visible features) that's genuinely useful when deciding which tiles are worth a human's time to label.

### Decision 12: Label taxonomy is extensible (`label_classes` table), and GeoJSON import is a first-class label source alongside Label Studio (Approved — 2026-07-22)
Phase 1's 7 land-cover classes ship as instance-wide defaults, not a hardcoded ceiling — any site can add its own via `label_classes`, and Label Studio's `label_config` is generated from that table rather than a fixed string. Separately, `POST .../labels/import-geojson` lets existing labeled data (field GPS points, GIS layers) become `labels` rows directly, spatially matched to `tile_grid` cells, without re-annotating in Label Studio. Unrecognized label values on import are flagged for the user to confirm or remap — not silently accepted (label drift) or silently dropped (lost data).

### Decision 13: Predictions view is also a map, per-site with tabs — not one unified map (Approved — 2026-07-22)
Same principle as Decision 11, applied to reviewing predictions instead of selecting tiles to label. But predictions pool across projects (Decision 6), and real sites in this system are not spatially contiguous (Bethel, AK and Austin, TX are thousands of miles apart) — a single zoomed-out map would show disconnected dots, not something reviewable. Map view is per-site with a tab switcher; tiles are colored by predicted class using the same `label_classes` colors as the labeling side, with amber borders marking low-confidence predictions.

### Decision 14: Low-confidence review reuses the Label Studio project-creation flow as a batch, via a new workspace-level endpoint (Approved — 2026-07-22)
Clicking a flagged prediction doesn't open Label Studio per-tile (impractical past a handful of flags) — tiles are selected the same way as "Label a Sample" (click on the map, or check rows in the list), then sent as one batch via `POST /workspace/review`. Unlike `.../task/{pk}/label`, this endpoint is not scoped to a single task, since a review batch drawn from cross-project predictions may span several `webodm_task_id`s. New labels from a review batch should prompt a retrain suggestion — otherwise the classifier goes stale with no signal that better data is available.

### Decision 15: Trainable models are a registry (`model_algorithms`), distinct in kind from `label_classes` (Approved — 2026-07-22)
Task type picks the problem (classification/regression/change detection); `model_algorithms` picks the specific trained-model implementation within it (e.g. Random Forest). Unlike `label_classes`, this registry is developer-extensible, not user-extensible — adding an algorithm means writing real training code in `model-train`, so the table tracks what's actually deployed rather than accepting arbitrary user input. v1 ships one default algorithm per implemented task_type.

### Decision 16: Real train/test split, hyperparameter tuning, and diagnostics — via scikit-learn, not bespoke code (Approved — 2026-07-22)
Once training means actual ensemble methods rather than a research probe, an unvalidated accuracy number isn't credible. Methodology grounded in [Wing et al. 2021, NHESS](https://nhess.copernicus.org/articles/21/807/2021/nhess-21-807-2021.html): 70/30 train/test split, stratified k-fold CV for tuning (`n_estimators`, `max_depth`), ROC-AUC/OOB-error feature importance/calibration curves for diagnostics — all via `scikit-learn`'s existing `train_test_split`, `GridSearchCV`, `StratifiedKFold`, and `sklearn.metrics`/`sklearn.calibration`, not reimplemented. One correction to the reference methodology rather than a copy of it: naive random splitting risks spatial-autocorrelation leakage between adjacent tiles, so `spatial_block` (hold out contiguous `tile_grid` regions) and `temporal_holdout` (hold out a whole `visit`, mirroring the paper's year-by-year validation) are named, selectable `split_strategy` options — made possible because `tile_grid`/`visits` already exist as first-class schema concepts (Decision 7). Surfaced as a new Diagnostics page (see Decision 18), not just a bare accuracy number in the UI.

### Decision 17: MLflow is the system of record for experiment tracking and model versioning — not a custom `model_metrics` table (Approved — 2026-07-22)
Building bespoke params/metrics/artifact storage would be reinventing a solved problem. MLflow self-hosts as its own Tapis Pod (same pattern as `embeddingsdb`/Label Studio); `model-train` logs to it directly (`mlflow.sklearn.autolog()`, `mlflow.sklearn.log_model()` for real model versioning); embeddingsdb keeps only `models.mlflow_run_id` as a thin join, not a duplicate of what MLflow already tracks. The Diagnostics endpoint proxies MLflow's API server-side, same credential-handling pattern as the CKAN/Label Studio integrations. **ClearML was considered and not chosen for this**, despite real existing precedent in this codebase (`embeddings-research/maestro-model/clearml.conf.dist`) — its differentiator is orchestration, which Tapis Actors/Workflows already cover here; MLflow is lighter for tracking-and-registry alone and has more direct scikit-learn integration.

### Decision 18: Diagnostics is its own page, not a third tab on the Embeddings & Classifier page (Approved — 2026-07-22)
Picking data/training (the Embeddings page) and judging whether a specific trained model is trustworthy (Diagnostics) are different jobs — the first is about assembling a training set, the second is about one model's validation results. Squeezing split/hyperparameters/confusion-matrix/ROC/feature-importance/calibration into a tab alongside Predictions' List/Map competes for the same scroll and conflates two concerns. `app_mount_points()` already supports multiple routes (Decision 6 established the mechanism; this just uses it twice) — `.../models/{model_id}/` is a real separate page, linked from the model name in the Predictions heading, not a mode switch on the main workspace page.

### Decision 19: The DSO STAC API is a first-class second raster source, consumed read-only — not a hypothetical future integration (Approved — 2026-07-22)
Prompted by asking how much of the system depends on WebODM orthophotos versus what could come from STAC-cataloged rasters. Finding: the schema was already almost entirely source-agnostic (Decision 7's `visits.source`); the one real coupling point is `embed-generate`'s pixel-fetching, which only knows WebODM's own `/tiles/{z}/{x}/{y}` endpoint. Rather than design against a generic/hypothetical STAC source, this targets the real, already-running DSO STAC API (`modflow-suite/stac-platform`, `docs/services/stac-api.md`) — anonymous reads, no new infra. `visits` gains `stac_collection_id`/`stac_item_id` (nullable) alongside `webodm_task_id`; `embed-generate` gains a second tiling path using `rio_tiler` directly against a STAC item's asset href, same `(z,x,y)` scheme, same downstream `tile_grid`/`embeddings`/`covariates`. New endpoints: `workspace/stac/collections`, `workspace/stac/collections/{id}/items`, `workspace/stac/import`. Whether WebODM should eventually *publish* to this same STAC API (converging the two sources) is noted as a real future direction and left as Open Question 11, not decided now.

### Decision 20: WebODM tasks can publish to the DSO STAC API, opt-in per task — converging the two raster sources, with an explicit, unresolved exposure risk (Approved — 2026-07-22)
Approved direction for Open Question 11, mirroring Subside's own existing dual-publish pattern (per its Integrations). New endpoint `POST .../task/{task_pk}/publish-to-stac`, using the requesting user's own Tapis JWT for the write (STAC's write routes require a Bearer token; reads stay anonymous) — no new secret, same server-side-only credential pattern as the CKAN/Label Studio proxies. On success, populates the task's `visit.stac_collection_id`/`stac_item_id` (`source` stays `'webodm'` — see the revised `visits` schema comment). This refines Decision 19's `embed-generate` branch condition: rather than branching on `visits.source`, it should branch on **whether `stac_item_id` is set** — a published `webodm` visit and a genuinely `stac`-origin visit both take the `rio_tiler`-on-asset path; only never-published `webodm` visits still use WebODM's own tiler endpoint.

**Deliberately NOT resolved here, and flagged rather than glossed over**: STAC API reads are anonymous, but WebODM tasks/projects are permissioned — publishing makes a task's imagery readable by anyone who can query the catalog. Mitigated for now by making publish opt-in and off by default (same "user-selected, never automatic" principle as Decision 4), but (a) the actual asset-href mechanism for exposing Corral-backed files is unresolved (Open Question 13), and (b) this endpoint should get a `security-reviewer` pass before implementation, not just a design-spec sign-off, given it's a genuine external write with data-exposure implications. *(Both (a) and the gating question are now resolved — see Decisions 21 and 23.)*

### Decision 21: "Publish to STAC" is gated on WebODM's own existing `public`/`public_edit` flag, not a standalone consent checkbox (Approved — 2026-07-22)
Resolves the exposure risk in Decision 20 more precisely than "opt-in and off by default" alone. WebODM already has a real, shipped notion of "anonymously viewable" — `Task.public`/`Task.public_edit` (`app/models/task.py:266-267`) and `Project.public`/`public_edit`/`public_id` (`app/models/project.py:33-35`), the same flags behind WebODM's existing public map/3D-viewer share links. Publishing a task's imagery to an anonymous-read STAC catalog is the same exposure decision the user already makes when they mark a task or project public — so `.../publish-to-stac` is only *available* (button enabled, not just checked/unchecked) when `task.public or task.project.public` is already true, rather than introducing a second, STAC-specific consent gate a user could tick without connecting it to the same risk. If the task/project isn't public, the UI states why the action is disabled (e.g., "Make this task public first — see Project Settings") rather than silently hiding it.

This resolves Open Question 14 (yes, there should be more than a bare unchecked-by-default toggle) but opens one new mechanical question, not glossed over: **retraction**. If a task or project later flips from public back to private, the already-published STAC item doesn't retract itself — the catalog would keep serving imagery the user just made private in WebODM, defeating the point of gating on `public` at all. The STAC API's own `DELETE /collections/{id}/items/{id}` (`docs/services/stac-api.md`) makes retraction mechanically possible, but *who* performs that call is unresolved: publish itself reuses the requesting user's live Tapis JWT (Decision 20), but a public→private flip isn't necessarily a request in progress with a JWT attached — tracked as Open Question 15, **left open deliberately** (not a blocker for the rest of this spec).

### Decision 22: Tapis Actors live in a new repo (Approved — 2026-07-22)
Resolves Open Question 2. Mirrors `label-studio-tapis-auth`'s own precedent (a dedicated repo for Tapis-side code) rather than a `tapis/` directory inside `odm-suite`/`WebODM` (the alternative, modeled on `subside`'s layout). Created at https://github.com/In-For-Disaster-Analytics/embeddings-tapis-actors, holding both `embed-generate` and `model-train` — scaffolded with README/`.env.example`/`Dockerfile`/`requirements.txt`/stub modules, no working Actor logic yet (blocked on the `embeddingsdb`/`mlflow` Pods and a deployed Clay v1.5 checkpoint, none of which exist yet).

### Decision 23: The STAC asset href for published WebODM tasks reuses WebODM's own existing task-download endpoint — grounded in the CKAN plugin's identical, already-working precedent (Approved — 2026-07-22)
Resolves Open Question 13. Checked `coreplugins/ckan/publisher.py`'s `build_remote_resources()`: it already builds CKAN resource URLs as `{WO_URL}/api/projects/{pid}/tasks/{tid}/download/{asset}` and explicitly sets `Task.objects.filter(id=task_id).update(public=True)` before registering, specifically so that URL is fetchable without auth. Confirmed why this works by reading `TaskDownloads`' permission path — `get_and_check_task()` (`app/api/tasks.py:453-463`) skips all permission checks outright when `task.public or task.project.public`, which is real, already-shipped, unconditional anonymous-read behavior, not something built new for this plugin.

This is a direct answer, not a variant of the three candidates in the original open question: `publish-to-stac`'s STAC item asset href is simply `{WO_URL}/api/projects/{pid}/tasks/{tid}/download/{asset}` — the exact same URL the CKAN plugin already publishes today. No Corral path is ever exposed directly, no copy-on-publish step, no signed URLs. It is safe specifically *because* Decision 21 already requires `task.public or task.project.public` before `publish-to-stac` is even available — by the time the STAC item is created, that URL is already anonymously fetchable, so cataloging it creates no new exposure surface beyond what Decision 21 already gates.

### Decision 24: `tile_grid` zoom is locked per site once set by its first visit — matching across visits is exact, not approximate (Approved — 2026-07-22)
Resolves Open Question 6, restated more precisely than the original framing. The real question wasn't footprint alignment — WebODM's `(z, x, y)` is a standard, fixed, global web-mercator grid (Decision 9), so two tiles at the same `(z, x, y)` are the *same* real-world cell by construction, regardless of which orthophoto's pixels fill them. The actual ambiguity is **zoom level**: if visit A at a site embeds at zoom 19 and a later re-survey (visit B) embeds at zoom 18, their tiles don't correspond 1:1 — a `tile_grid` row from one can't be matched to the other without real reprojection, not a simple lookup.

Resolution: **zoom is locked per `site_id`**, set by whichever visit is embedded first. `embed-generate` reads the site's existing zoom (if any `tile_grid` rows already exist for that `site_id`) and uses it for every subsequent visit at that site, rather than accepting an independently-chosen zoom per call. This makes cross-visit `tile_grid` matching an exact `(site_id, z, x, y)` lookup — no IoU threshold, no centroid-in-cell heuristic, no spatial join at all. The original Risks-table framing ("different survey flights rarely produce pixel-identical footprints... needs a real spatial-join tolerance") no longer applies once zoom is fixed per site; it was solving a problem that a global tile grid doesn't actually have. Tradeoff, stated plainly: a site's zoom choice is effectively permanent after the first embed — changing it later means either living with two incompatible `tile_grid` generations for that site, or a real (not designed here) reprojection/migration step.

### Decision 25: Three implementation-parameter resolutions (Approved — 2026-07-22)
Batched together as parameter-level, not architectural, choices:
- **Resolves Open Question 3**: minimum label count before training is allowed is **30** (a firmer floor than Phase 1's research-scale 15-20/site, since v1 trains real ensemble methods with an actual held-out test set, not a research probe).
- **Resolves Open Question 5**: `covariates` are computed **inside `embed-generate` itself**, not a separate Actor — matches how the New Infrastructure table already described `embed-generate` ("writes `embeddings` rows, and separately computes `covariates`"), so no schema or infrastructure change, just confirms the existing description over the alternative floated in the open question.
- **Confirms Open Question 10** as designed: GeoJSON label import keeps `label` as the default property key, no per-upload key picker in v1 — revisit only if real-world files actually need it.

### Decision 26: Zero WebODM-database schema changes — the `webodm_task_id` mapping lives entirely inside `embeddingsdb`, with explicit `ON DELETE CASCADE` for task/project deletion (Approved — 2026-07-22)
A 5-reviewer spec-review pass (design-reviewer, architect, skeptic, security-reviewer, tester, synthesized by team-discourse) caught a real self-contradiction: the Assumptions section said "no schema changes to WebODM's own database," but Files Likely Affected said the `visit_id`-to-`task.id` lookup might be "a mapping table or a stored field on `Task`, TBD" — the latter option would have been a `webodm_dev` migration, directly contradicting the Assumption. Resolved per the architect's recommendation: the mapping is a plain column (`webodm_task_id`) on `visits`, inside `embeddingsdb` — WebODM's own database is never touched.

This also closes a real gap the review surfaced: nothing previously described what happens to `embeddingsdb` rows when a WebODM `Task`/`Project` is deleted. Resolved: `visits.webodm_task_id`-keyed rows cascade via `ON DELETE CASCADE` down through `tile_observations` → `embeddings`/`covariates`/`labels`/`model_inputs`, triggered by a Django `post_delete` signal on `Task` that issues the delete against `embeddingsdb`. Left deliberately unresolved (Open Question 16, not blocking): the exact signal-wiring mechanics, and whether a trained model's `model_inputs` silently shrinking when its source task is deleted later is the right behavior versus blocking the deletion or soft-deleting instead.

### Decision 27: Zoom-lock gets an explicit override, and site assignment is user-chosen, not inferred (Approved — 2026-07-22)
Amends Decision 24 following the architect's and skeptic's review feedback, which — while agreeing on the underlying problem — surfaced two distinct issues Decision 24 alone didn't separate:
- **The architect's point**: `tile_grid` already stores `z` per row, so the schema doesn't actually forbid multiple zoom generations at a site — it's `embed-generate`'s *policy* of always reusing the site's first zoom that makes it feel permanent. Fix: `.../task/{task_pk}/embed` gains an explicit `zoom_override` param; using it against a site that already has `tile_grid` rows at a different zoom requires an explicit UI confirmation warning ("This site already has embeddings at zoom 19 — using zoom 21 will not match existing tiles for change detection"), rather than silently accepting a mismatched zoom or hard-blocking it.
- **The skeptic's distinct point**: nothing described how a task gets assigned a `site_id` in the first place, or how a re-survey of the same physical location would be recognized as the same site rather than silently becoming a new, unrelated one — which would quietly defeat the entire point of `tile_grid`/`visits` (change detection, cross-visit matching). Fix: site assignment is **explicit and user-chosen at `embed-generate` time**, not inferred from task/project metadata — the "Generate Embeddings" action gains a required "Site" selection (existing site from a dropdown, or "New site" with a name field), matching the same "explicit over silently inferred" principle already used for GeoJSON label-value confirmation (Decision 12).

### Decision 28: Minimum label count gets a per-class floor, not just a total (Approved — 2026-07-22)
Amends Decision 25 per the skeptic's finding: 30 total labels across a 7-class taxonomy can still fail stratified k-fold CV outright if one class has only 1-2 examples. `.../workspace/train` now also requires **at least 5 examples per distinct `label_classes` value actually present** in the selected `tile_observation_ids`, in addition to the 30-total floor — both checked before queuing `model-train`, both returned in the same 400 response if violated.

### Decision 29: Webhook hardening — constant-time comparison and scope validation (Approved — 2026-07-22)
The security-reviewer found a real gap in Decision 10's webhook: shared-secret header verification alone doesn't specify constant-time comparison, and — more significantly — the secret is instance-wide, not scoped per Label Studio project/session, meaning anyone holding it could upsert `labels` for *any* `tile_observation_id` system-wide, including tasks/projects they otherwise can't access. `.../labelstudio-webhook` now: (1) compares the shared secret via `hmac.compare_digest`, not `==`; (2) validates that the incoming `tile_observation_id` corresponds to a Label Studio project/task WebODM itself created and is still tracking (rejecting IDs it never registered), not just that *some* valid-looking ID was supplied.

### Decision 30: Tapis Actors use a stored, refreshable service token — not a live request JWT (Approved — 2026-07-22; corrected 2026-07-23, see Decision 37)
The security-reviewer flagged a real, previously-unaddressed gap: `embed-generate`/`model-train` are Celery-queued and run asynchronously, so there is no live per-request Tapis JWT available to authorize them the way `publish-to-stac`'s synchronous handler has one. The CKAN plugin already solved this exact problem for its own async publish task (`apply_ckan_publish`, via a stored `TapisOAuth2Token` rather than a live request JWT) — this plugin adopts the same pattern rather than inventing a new one: Actor invocation is authorized by a stored, refreshable token associated with the triggering user, managed the same way the CKAN plugin already manages its own.

**Correction (Decision 37, 2026-07-23):** this decision's own wording ("a stored, refreshable *service* token") was imprecise and has been superseded by the real implementation. It is not a generic service-account credential — it is the per-**user** `TapisOAuth2Token` (`app/models/oauth2.py`), looked up for the specific user who triggered the request, exactly as `apply_ckan_publish` already does for its own async CKAN publish. See Decision 37 for the resolved, implemented mechanism.

### Decision 31: "Retract from STAC" ships as a lightweight, manual endpoint — not a full reconciliation job (Approved — 2026-07-22)
Resolves Open Question 15, revisiting the earlier "leave it open" call with new information from the security-review pass: `get_and_check_task` (the same function Decision 23 already leans on) re-evaluates `task.public`/`task.project.public` **on every request** — so the STAC-published asset's *bytes* already self-protect the instant a task flips back to private; there is no durable imagery-exposure gap. The one thing that doesn't self-protect is the STAC item's own *metadata* (its existence, bbox, capture date, item id) persisting anonymously-discoverable after the flip.

Given that narrower, confirmed scope, a full nightly reconciliation job is more than v1 needs. New endpoint, `POST /api/plugins/embeddings/task/{task_pk}/retract-from-stac` — available once a task has been published (`stac_item_id` set), callable by the task owner or an admin — calls `DELETE {WO_STAC_API_URL}/collections/{id}/items/{id}` and clears `visits.stac_collection_id`/`stac_item_id`. A full nightly reconciliation job (comparing every `visits.stac_item_id` against current `public` flags and auto-retracting) remains a legitimate fast-follow, not a v1 blocker — `publish-to-stac` should not ship without this manual endpoint existing alongside it, but does not need to wait for automatic reconciliation.

### Decision 32: `label_studio_client.py`'s server-to-server calls use a Label Studio Personal Access Token, not a Tapis JWT (Approved — 2026-07-22)
Caught while starting to implement `label_studio_client.py`, the same way Decision 30 caught the missing Actor-credential model: this spec's language throughout (Assumptions, "Label Studio Integration: Full Mechanics", the Plugin File Structure comment) described the project-create/task-import/webhook-registration calls as a "Tapis-authenticated proxy" verifying a "Tapis JWT header" — checked against Label Studio's actual REST API docs, and that's not correct. Label Studio's REST API only accepts its own **Personal Access Token** (`Authorization: Bearer <token>`) or **Legacy Token** (`Authorization: Token <token>`) — it has no support for an external OAuth2/JWT bearer token from a third-party identity provider like Tapis.

This does not contradict the deep-link SSO flow — that part of the spec is correct as written: `label-studio-tapis-auth`'s custom `TapisOAuth2Backend` really does let a human log into Label Studio's *UI* via a Tapis-verified token, with no second login. But that's a completely different code path from `label_studio_client.py`'s server-to-server API calls (create project, import tasks, register webhook), which run with no human in the loop and need a credential Label Studio's REST API actually understands.

Resolution: a new setting, `WO_LABEL_STUDIO_API_TOKEN` — a Label Studio Personal Access Token, generated once by an admin user in the Label Studio instance itself and configured server-side, same "credentials never reach the browser" pattern as everything else in this plugin. `label_studio_client.py` sends it as `Authorization: Bearer {WO_LABEL_STUDIO_API_TOKEN}` on every project/task/webhook API call. The user-facing deep-link URL itself still carries the user's own Tapis access token (query param or session, per `label-studio-tapis-auth`'s own login flow) so the human lands in Label Studio without a second login — that mechanism is unchanged.

### Decision 33: `embeddingsdb` is live — provisioned from Tapis's own `17postgis3.5` Pod template, with pgvector added afterward via `exec_pod_commands`, not the originally-planned custom image (Approved — 2026-07-23)
The New Infrastructure table originally planned `embeddingsdb` as a custom `pgvector/pgvector:pg16` image (`embeddings-tapis-actors/tapis/register_pod.py`'s first version) — this table also requires PostGIS (`tile_grid.bounds geometry`), which that plan hadn't accounted for at all. In practice, the Pod was created directly from Tapis's own `17postgis3.5` template (Postgres 17 + PostGIS 3.5 pre-installed) — confirmed live via `psql` that pgvector is genuinely absent from that template (`CREATE EXTENSION vector` fails with "could not open extension control file," not just "not yet enabled").

Real fix, verified end-to-end rather than assumed: `postgresql-17-pgvector` is a real PGDG apt package, installable on top of the template's own Debian/Postgres 17 base — confirmed first in a local Docker build (`postgis/postgis:17-3.5` + the same apt package, both `CREATE EXTENSION postgis` and `CREATE EXTENSION vector` working, including a real vector distance query), then for real against the live Pod itself via Tapis's `exec_pod_commands` API (`embeddings-tapis-actors/tapis/install_pgvector.py`), which turned out to have root/apt access inside the container — not guaranteed by Tapis's own docs, verified empirically before relying on it. `schema/embeddingsdb.sql` was then applied via a plain `psql -f`; all 13 tables and 11 indexes confirmed present.

One real, unresolved discrepancy worth flagging rather than smoothing over: the Pod's actual external hostname (`embeddingsdb.pods.portals.tapis.io`, no suffix) doesn't match what Tapis's generic Pods networking docs implied for a non-`"default"`-keyed interface (a `-postgres` suffix) — `embeddings-tapis-actors/tapis/register_pod.py` and `.env.example` were corrected to the observed value, but *why* a template-created Pod's hostname doesn't follow that pattern isn't explained, just documented as fact. `register_pod.py` itself has been rewritten to use `template="17postgis3.5"` (matching reality) so it stays useful if the Pod ever needs recreating, but is explicitly marked as not itself live-tested — only the manually-created Pod and `install_pgvector.py` have been.

### Decision 34: `embeddings_client.py` implemented for real against the live `embeddingsdb`, Actor invocation stays a stub (Approved — 2026-07-23)

Implementation increment following Decision 33 (`embeddingsdb` going live): `coreplugins/embeddings/embeddings_client.py` was added with real, working `psycopg2` queries against the live Pod (`WO_EMBEDDINGS_DB_URL`, added to `webodm/settings.py` matching the `WO_LABEL_STUDIO_URL` block's style) — `list_sites`, `create_site`, `get_site_zoom` (Decision 24's zoom-lock check), `get_visit_for_task` (read-only, for polling), `get_or_create_visit`, and `count_tile_observations`. Every query's column names/types were read directly from `embeddings-tapis-actors/schema/embeddingsdb.sql`, and connectivity plus every query shape (including both write paths) were verified against the real, live Pod in a transaction that was rolled back afterward — confirmed 0 rows persisted.

`psycopg2` needed no new dependency: WebODM's own `requirements.txt` already pins `psycopg2-binary==2.8.6` (used for `webodm_dev`) and `embeddings_client.py` reuses it.

`TaskEmbedView.post()` and `TaskEmbedStatusView.get()` (`coreplugins/embeddings/api_views.py`) were wired to this client for real: site resolution (existing `site_id` or `new_site_name`), the Decision 24/27 zoom-lock check (409 on mismatch without `zoom_override: true`), and a real `visits` row via `get_or_create_visit()`. `TaskEmbedStatusView` uses the read-only `get_visit_for_task()` (never creates a row on a GET) plus a real `count_tile_observations()`; it does not yet report the total tile count expected at a zoom (`M` in "N of M") since that requires enumerating WebODM's own tiler coverage (Decision 9), out of scope for this increment.

Deliberately still a stub, per this increment's own scoping: `embeddings_client.queue_embed_generate()`/`queue_model_train()` raise `NotImplementedError` — the `embed-generate`/`model-train` Tapis Actors are not registered with Tapis yet (a separate Tapis subsystem from the Pod registration Decision 33 already completed), so there is no Actor ID anywhere to invoke. `TaskEmbedView.post()` calls this last, after the real `visits` row is already committed — a 501 from the Actor-queuing step does not roll back the visit, since a user has genuinely committed to embedding a task at a site regardless of whether the Actor call itself can run yet.

### Decision 35: Both Tapis Actors get a real, confirmed Abaco message contract; `embed-generate` gets real embeddingsdb writes and a real (dry-run-only) registration script; `model-train` stays otherwise a stub (Approved — 2026-07-23)

Implementation increment following Decision 34 (`embeddings_client.py` going live against `embeddingsdb`): the next real gap was that neither Actor had a confirmed invocation contract, and `embed-generate`'s own `write_tile_observation`/`write_embedding`/`write_covariates` were still `NotImplementedError` stubs even though `embeddingsdb` itself has been live since Decision 33.

**Real facts grounding this increment, confirmed against Tapis's own Actors docs (not re-derived):** Abaco injects the invocation payload as the `MSG` environment variable (a JSON string), plus context values (`_abaco_execution_id`, `_abaco_username`, etc.) as their own env vars; registration is `t.actors.create_actor(image=..., name=..., description=..., default_environment={...}, stateless=True, hints=[...])` via tapipy; invocation is `t.actors.send_message(actor_id=..., request_body={'message': ...})`; and — critically, a real divergence from the Pods precedent — **Abaco pulls Actor images from public Docker Hub only**, not GHCR (`label-studio-tapis-auth`'s working Pod precedent does not carry over unchanged).

**What's real now:**
- `embed_generate/main.py` and `model_train/main.py`'s `read_actor_message()` both read `os.environ['MSG']` and `json.loads()` it for real, raising a clear `RuntimeError` (unset) or `ValueError` (malformed) rather than a bare `KeyError`/`JSONDecodeError`. Verified end-to-end: built both Docker images (`docker build --build-arg ACTOR=embed_generate|model_train`), ran each with a realistic `MSG` payload matching the design spec's `.../embed` and `.../workspace/train` body shapes, and confirmed each container starts, parses `MSG`, dispatches into `run()`, and fails with the *expected* `NotImplementedError` (tile enumeration / end-to-end orchestration, not a message-parsing crash) — plus confirmed the unset-`MSG` and malformed-`MSG` cases fail with the new, specific errors, not tracebacks from deep inside `json`.
- A new `embed_generate/db.py` module implements `write_tile_observation` (real upsert, keyed on `tile_observations`' own `UNIQUE(tile_grid_id, visit_id)` constraint), `write_embedding` (real INSERT, vector formatted as pgvector's own text input syntax and cast `%s::vector` — no `pgvector` python package added, since this is the only call site), and `write_covariates` (real INSERT, or a genuine no-op returning `None` when `covariates` is falsy, matching Decision 25 precisely). Every column name/type was read directly from `schema/embeddingsdb.sql`, mirroring `coreplugins/embeddings/embeddings_client.py`'s own style (Decision 34) so both sides of the system talk to `embeddingsdb` the same way. Verified for real against the live Pod: ran all three functions (including the upsert re-run and the `covariates=None` no-op) inside a transaction via the built Docker image (psycopg2 isn't installed on the host; the image already has `psycopg2-binary` from `requirements.txt`), then rolled back and reconnected fresh to confirm 0 rows persisted — same verification discipline as `embeddings_client.py`'s own increment.
- `tapis/register_actor.py` — mirrors `register_pod.py`'s conventions (argparse, `--dry-run`, `.env` loading), adapted for the Actors API. `--dockerhub-org` is a required CLI arg with no default (no established Docker Hub org exists for this project, unlike GHCR's `in-for-disaster-analytics` — deliberately not invented). `default_environment` is built only from env vars the Actor's own code actually calls `os.environ.get()` for today: `EMBEDDINGSDB_URL` for `embed-generate` (via the new `db.py`); genuinely empty for `model-train`, since none of its functions read any env var yet (only its message contract was fixed this increment, per explicit scope — its DB/MLflow un-stubbing is a separate, later increment). `--dry-run` was actually run and confirmed to print both actors' specs (secrets masked) without importing `tapipy` or touching Tapis at all.

**What's still a stub, unchanged in scope:** `embed_generate/main.py`'s tile enumeration, pixel fetching, and Clay v1.5 inference (no checkpoint, no live WebODM/STAC pixel access reachable from an Actor container) — `run()` still raises `NotImplementedError` before ever reaching the now-real write functions. `model_train/main.py` is untouched beyond its message-contract fix, per this increment's explicit scope (un-stubbing it is later work). `tapis/register_actor.py`'s non-dry-run path, and the `docker push` to Docker Hub it depends on, were not run — no Docker Hub or Tapis credentials exist in this environment. `find_existing_actor_id()`'s assumption about `t.actors.list_actors()`'s return shape (needed because, unlike Pods' caller-chosen `pod_id`, Actor ids are server-generated — there is no direct existence check the way `get_pod(pod_id=...)` provides) is a stated judgment call, not one of the facts confirmed against Tapis's docs this session.

**Decision 30's credential question is explicitly NOT resolved by this increment** — `tapis/register_actor.py`'s `default_environment` is static configuration baked in at registration time, not a live per-request credential; it cannot by itself determine how `embed-generate`/`model-train` authorize themselves against embeddingsdb/Tapis once Celery queues them asynchronously (stored service token vs. some other mechanism). The script's own docstring and `--dry-run` output both state this rather than silently implying otherwise.

### Decision 36: Correction to Decision 35 — Actor images use GHCR, not Docker Hub (Approved — 2026-07-23)
Decision 35 stated, citing Tapis's own readthedocs page verbatim, that Abaco requires Actor images on public Docker Hub. **Directly corrected by the project owner**, who has real, hands-on Tapis account experience this session's own doc fetches don't have — the same readthedocs page had already proven wrong or incomplete elsewhere in this project (it didn't know about the real `17postgis3.5` Pod template, Decision 33, or the real Pod hostname behavior, both only discovered by direct experimentation against a live tenant). GHCR works for Actors the same way it already does for Pods (`label-studio-tapis-auth`).

Resolution: `tapis/register_actor.py`'s image references switched from a required `--dockerhub-org` placeholder to a real default, `ghcr.io/in-for-disaster-analytics/embeddings-tapis-actors`, tagged `embed-generate-latest`/`model-train-latest`. A new `.github/workflows/docker-build.yml`, mirroring `label-studio-tapis-auth`'s own proven workflow, builds and pushes both Actor images to GHCR on push to `main` (matrixed over the `ACTOR` build-arg, since both Actors share one Dockerfile). The GHCR package still needs to be set public after the first push (Abaco pulls anonymously, same requirement as the Pods precedent) — the exact `gh api` command is documented in the workflow file's own comments. Neither the push nor a real Tapis registration has been run yet — this increment only corrects the plan and prepares the real mechanism (CI-driven build, not a manual local push) to execute it.

**Lesson worth stating plainly**: a docs page being explicit and quoted verbatim twice is not the same as it being current or complete — this is the second time in this project a generic Tapis doc fetch was superseded by someone's real, direct account experience (the first being the Pod hostname/template discrepancy in Decision 33). Prefer direct verification or a domain expert's correction over a re-fetched doc page when the two conflict.

### Decision 37: Real `embed-generate` Actor invocation wired for real; Decision 30's credential question resolved for real, not just in principle (Approved — 2026-07-23)

Implementation increment following Decision 36 (both Actors genuinely registered — `embed-generate`=`zO6oAZ488yxGk`, `model-train`=`PrGMpgkVzENbp`). This increment makes `TaskEmbedView.post()` genuinely queue `embed-generate`, and resolves Decision 30's previously-open credential question for real rather than leaving it as a description of an intended pattern.

**Correction to Decision 30's own wording**: Decision 30 described the credential as "a stored, refreshable *service* token." That is imprecise and is corrected here: it is not a service account at all — it is the per-**USER** `TapisOAuth2Token`/`TapisOAuth2Client` (`app/models/oauth2.py`), looked up for the specific user who triggered the request (`TaskEmbedView.post()`'s `request.user`), exactly mirroring `coreplugins/ckan/publisher.py`'s `apply_ckan_publish()` — which already solves this exact "no live request JWT once Celery runs the job" problem for CKAN's own async publish, using `TapisOAuth2Client.objects.filter(is_active=True).first()` → `TapisOAuth2Token.objects.get(user=user, client=client)` → `token_obj.get_or_refresh_access_token()`. This plugin's `coreplugins/embeddings/embeddings_client.py:apply_embed_generate()` mirrors that exact lookup/refresh sequence and error-handling style (clear `RuntimeError`s on missing client/token/expired-unrefreshable-token), rather than inventing a different credential model.

**What's real now:**
- `webodm/settings.py` gains `WO_EMBEDDINGS_ACTOR_ID` (default `zO6oAZ488yxGk`) and `WO_MODEL_ACTOR_ID` (default `PrGMpgkVzENbp`) — real, confirmed actor_ids, env-var-overridable, matching the design spec's own "New Django settings" naming exactly.
- `embeddings_client.apply_embed_generate(task_id, user_id, site_id, visit_id, zoom, encoder, zoom_override)` replaces the `queue_embed_generate()` stub: a fully self-contained Celery task function (every import inside its own body — verified via AST inspection this increment that no name it references is defined outside its own body, the same self-containment `run_function_async`/`eval_async` themselves depend on), queued via `app.plugins.worker.run_function_async` from `TaskEmbedView.post()` — never called directly. It resolves the token exactly as described above, builds a real `tapipy` `Tapis(base_url=settings.TAPIS_BASE_URL, access_token=jwt)` client (`TAPIS_BASE_URL` — the existing `WO_TAPIS_BASE_URL`-backed setting already used by `app/auth/tapis_oauth2.py`/`coreplugins/upstream`, reused rather than inventing a second Tapis-base-URL setting), and calls `t.actors.send_message(actor_id=settings.WO_EMBEDDINGS_ACTOR_ID, request_body={'message': json.dumps({...})})`. The message payload matches `embed_generate/main.py`'s own `read_actor_message()` docstring in `embeddings-tapis-actors` exactly: `visit_id`, `site_id`, `zoom`, `zoom_override`, `encoder` — no invented extra keys (`webodm_task_id` is deliberately not part of the message; the Actor resolves it via `visit_id` → `visits.webodm_task_id` in embeddingsdb, not from the invocation payload).
- `TaskEmbedView.post()` (`coreplugins/embeddings/api_views.py`) now queues `apply_embed_generate` via `run_function_async` instead of catching `NotImplementedError` and returning 501 — the same fire-and-forget shape as the CKAN plugin's own `PublishView.post()`. A new guard returns 503 if `WO_EMBEDDINGS_ACTOR_ID` is unset, mirroring the existing `WO_EMBEDDINGS_DB_URL` guard already in this view. The real `visits` row (Decision 33/34) is still created before the Actor call is queued, and is not rolled back based on the queued call's (unobserved, async) outcome.
- `tapipy` is added to `requirements.txt` (unpinned — no existing Tapis code in this repo or in the sibling `embeddings-tapis-actors` repo pins a version either; this is the first place in WebODM's own codebase that uses `tapipy` directly rather than plain `requests` + Bearer JWT).
- Both the `Tapis(base_url=..., access_token=...)` constructor and `t.actors.send_message(actor_id=..., request_body={'message': ...})` call shapes were independently re-verified this increment against the actually-installed `tapipy` package (`inspect.signature(Tapis.__init__)`, and the real *pickled* OpenAPI spec bundled in the wheel that tapipy loads at runtime — not just the `.yml` source file) — both confirmed to match what this increment implements.

**Explicitly NOT done in this increment:**
- No live invocation test was run or could be run — this environment has no logged-in user session with a real, stored `TapisOAuth2Token`, so `apply_embed_generate()` has not been exercised end-to-end against the live `embed-generate` Actor. Only structural/static verification was performed (AST self-containment check; independent `tapipy` signature/spec confirmation).
- `model-train`'s equivalent (`apply_model_train()`) is NOT implemented this increment — there is still no `POST .../workspace/train` endpoint to call it from (only `TaskEmbedView`/`TaskEmbedStatusView` exist so far). `queue_model_train()`'s docstring is updated to note Decision 30's credential question is resolved *in principle* for it too (same per-user-token pattern would apply), but the wiring itself remains later work.
- `embed_generate/main.py`'s own `run()` (tile enumeration, pixel fetching, Clay v1.5 inference) is untouched by this increment — it still raises `NotImplementedError` on the Actor side once invoked; this increment only makes the invocation itself (WebODM → Tapis Actors API) real.

### Decision 38: First real frontend component — `EmbeddingsPanel.jsx`, scoped to the task-detail panel only; a real `GET /sites` endpoint added to close a gap in `embeddings_client.py`'s existing functions (Approved — 2026-07-23)

Implementation increment following Decision 37 (real `embed-generate` invocation): everything built in this plugin so far was backend (Django views, `embeddingsdb` client, Tapis Actor invocation) — this increment adds the first actual UI, `coreplugins/embeddings/public/EmbeddingsPanel.jsx`, mirroring `coreplugins/ckan/public/CKANPublishPanel.jsx`'s structure/build tooling/registration mechanism exactly (class component, `$.ajax` not `fetch`, `setInterval`-based status polling, `ReactDOM.createPortal` modal, plain inline `styles` object, identical `webpack.config.js` with entry swapped to `EmbeddingsPanel`).

**Scope, explicit**: task-detail panel only — the top-level "Embeddings & Classifier" workspace page and the separate Diagnostics page (Decisions 6/18) are NOT built in this increment, since their own endpoints (`workspace/browse`, `workspace/train`, etc.) don't exist yet.

**What's real:**
- `GET /api/plugins/embeddings/sites` — a new, NOT task-scoped `SitesView` (mirrors `LabelClassesView`'s non-task-scoped registration), wired into `plugin.py`'s `api_mount_points()`. Closes a real gap: `embeddings_client.list_sites()` has worked against the live `embeddingsdb` since Decision 34 but was never exposed via an API endpoint — needed so the panel's "existing site" dropdown has something real to populate itself from. `create_site()` (also live since Decision 34) is exercised indirectly via the existing `.../embed` endpoint's `new_site_name` path — no new endpoint needed for it.
- "Generate Embeddings" — a real form (zoom number input, existing/new site radio toggle backed by the new `/sites` endpoint) that `POST`s to the real `.../embed` endpoint exactly per its documented contract (400/409/503/202). On `202`, starts polling the real `.../embed-status` endpoint and shows live `tile_observation_count` — continuing indefinitely while the panel stays open, since the endpoint's own contract (Decision 34) has no terminal "done" state yet (the Actor's `run()` itself still raises `NotImplementedError`, Decision 35). On `409`, shows the server's exact conflict message and reveals a "Use zoom anyway" checkbox that sets `zoom_override: true` on resubmit.
- "Label a Sample" — a real form that `POST`s comma-separated tile identifiers to the real, working `.../label` endpoint and renders the returned `label_studio_url` as a clickable `target="_blank"` link on success.
- `templates/load_buttons.js` — replaced the disabled-`<span>` placeholder with the real SystemJS deps-array registration form (`PluginsAPI.Dashboard.addTaskActionButton(['embeddings/build/EmbeddingsPanel.js'], ...)`), mirroring the CKAN plugin's own registration exactly.

**Explicit judgment calls, not silent choices:**
- **Task-status gating**: `load_buttons.js` gates the button on `task.status === 40` (COMPLETED), matching the CKAN plugin's own precedent exactly. Rationale: both "Generate Embeddings" (needs a finished orthophoto to tile) and "Label a Sample" (needs real tiles to reference) depend on a task actually having completed processing — there's no meaningful action to take against an in-progress or failed task.
- **"Label a Sample" is deliberately simplified**, not under-delivered without explanation: the design spec's real UI (a map with a `tile_grid` overlay, click-to-select, "Tile Selection UI" section) depends on `GET .../task/{pk}/tiles`, which still returns 501, and a Leaflet integration — both out of scope for this increment. The shipped UI is a plain text input for comma-separated tile ids (hint text shows the `z/x/y` format the backend special-cases), with an explicit code comment and an in-UI note stating this is an interim simplification, not the final design.

**Build tooling — NOT verified to actually run in this environment, stated plainly rather than assumed:** `coreplugins/embeddings/public/webpack.config.js` was created (copied from CKAN's, entry changed to `EmbeddingsPanel`). Root `node_modules` has `webpack` itself but **not** `webpack-cli` — the exact binary `app/plugins/functions.py`'s `build_plugins()` invokes (`subprocess.call(['webpack-cli'], cwd=plugin.get_path("public"))`) to build any plugin's `public/webpack.config.js`, CKAN's included. Running `node node_modules/.bin/webpack` directly (bypassing the missing CLI) prompts to auto-install `webpack-cli` via npm; declining (or letting `npx --yes webpack-cli` attempt the same) produced no successful install in this sandboxed environment (no clear network access to the npm registry). A `build/EmbeddingsPanel.js` artifact briefly appeared in `public/build/` immediately after the source files were written, byte-identical in content to what this source would compile to — but no webpack/node build process was observed running to produce it, so it is not trusted or claimed as a verified build; it was deleted rather than left in place as an unverified stand-in. **A real environment would run**, from `coreplugins/embeddings/public/`: `npx webpack-cli` (after `npm install -D webpack-cli` at the WebODM repo root, if not already present) — or, from the WebODM repo root, `python manage.py rebuildplugins`, which orchestrates this same build for every plugin (`app/plugins/functions.py:build_plugins()`). Worth flagging as a possible pre-existing repo gap, not something introduced here: `webpack-cli` isn't listed anywhere in the root `package.json`, even though `functions.py` depends on it by name for every plugin's build, CKAN's included.

**Update, later session**: the build was in fact completed for real in a subsequent session (commit `1337cc7f`, "Build real EmbeddingsPanel.jsx — first actual plugin UI, not a placeholder") — `coreplugins/embeddings/public/build/EmbeddingsPanel.js` is a genuine compiled bundle, confirmed by grepping the minified output for source-specific strings (`"Generate Embeddings"`, `"Label a Sample"`, `"zoom_override"`, `"Use zoom anyway"`), not the untrusted stand-in described above. This paragraph is left in place rather than deleted so the record of what was and wasn't verified at each point in time stays honest.

### Decision 39: `embed-generate`'s Clay v1.5 checkpoint and vendored `claymodel` source are baked into the Actor's Docker image, not mounted via a Tapis Volume (Approved — 2026-07-24)

The next implementation increment (real `resolve_site_zoom`/`enumerate_tiles`/`fetch_tile_pixels`/`embed_tile`/`compute_covariates`/`run()` in `embeddings-tapis-actors/embed_generate/main.py`) needs a real decision on where the ~4.8 GB `clay-v1.5.ckpt` checkpoint and the vendored `embeddings-research/clay-model-src` (`claymodel`, not published to PyPI — see `embeddings-tapis-actors/requirements.txt`'s existing comment) actually live at runtime. Two options were on the table: bake both into the Actor's Docker image (`pip install -e` the vendored source, `COPY` the checkpoint in), or mount them from a persistent Tapis Volume (the pattern already planned for MLflow's artifact store).

**User's explicit choice: bake into the image.** Tradeoff, stated plainly: this makes the `embed-generate` image large (multi-GB) and means any checkpoint update requires a full image rebuild and re-push (the existing `.github/workflows/docker-build.yml` → GHCR pipeline from Decision 36), rather than swapping a mounted volume's contents. Chosen anyway for simplicity — no new Tapis Volume needs to be provisioned or mounted for this Actor specifically. Not yet implemented as of this decision; affects `embeddings-tapis-actors/Dockerfile` (needs `COPY`/`pip install -e` steps for `clay-model-src`, plus the checkpoint file) and confirms `.env.example`'s existing `CLAY_CHECKPOINT_PATH`/`CLAY_MODEL_DIR` variables should point at in-image paths, not a mounted volume path.

### Decision 40: This increment's `embed-generate` implementation covers WebODM-sourced visits only; the STAC-asset tiling branch is explicitly deferred (Approved — 2026-07-24)

`enumerate_tiles`/`fetch_tile_pixels` were designed (Decisions 19/20) to branch on whether a `visit` has a `stac_item_id` — WebODM's own tiler endpoint for `webodm`-origin visits, `rio_tiler` directly against a STAC asset href otherwise. Implementing both branches in one increment is more surface area than necessary to get the core pipeline (tile → Clay embedding → `embeddingsdb` write) working end-to-end for the first time.

**Decision**: this increment implements the `visits.stac_item_id IS NULL` branch only (WebODM's own `/tiles/{z}/{x}/{y}` endpoint via `rio_tiler`/`COGReader` server-side, per `app/api/tiler.py`). The STAC-asset branch (Decisions 19/20/23) remains a real, designed, but unimplemented code path — `enumerate_tiles`/`fetch_tile_pixels` should raise `NotImplementedError` explicitly for a `stac_item_id`-bearing visit rather than silently mishandling it, until that branch is built as a later increment.

### Decision 41: Added `visits.project_pk` and a per-invocation JWT to close a real gap found while grounding the implementation plan — the Actor previously had no way to construct WebODM's tiler URL or authenticate to it (Approved — 2026-07-24)

Grounding the plan against the real code (`app/api/tiler.py`, `app/api/tasks.py`, `coreplugins/embeddings/embeddings_client.py`) surfaced a gap none of Decisions 9/19/20/23/35/37 had actually resolved: WebODM's tiler endpoint is project-nested (`projects/{project_pk}/tasks/{pk}/orthophoto/tiles/{z}/{x}/{y}`), but the Actor's invocation message (Decision 37) only carries `visit_id`/`site_id`/`zoom`/`zoom_override`/`encoder`, and `embeddingsdb`'s `visits` table (Embeddings DB Schema section) only stores `webodm_task_id` — not which project that task belongs to. Separately, `app/api/tasks.py`'s `get_and_check_task()` requires an authenticated request unless `task.public or task.project.public` is true (confirmed by reading it directly), and the Actor had no credential of any kind to present for a private task's tiles.

**Resolution:**
- Add a `project_pk` column to `embeddingsdb`'s `visits` table (an `embeddingsdb`-only schema change — consistent with Decision 26's "zero WebODM-database schema changes," since this lives entirely in the separate Postgres instance) — populated at `get_or_create_visit()` time from the same project/task-nested request `TaskEmbedView.post()` already has.
- Add a `jwt` field to the Actor invocation message payload, carrying the same per-user Tapis access token `apply_embed_generate()` already resolves (via `TapisOAuth2Token`/`TapisOAuth2Client`, Decision 37) to invoke the Actor itself — reused, not a second credential lookup.
- `fetch_tile_pixels` passes that JWT as a query-string parameter to WebODM's tiler endpoint, using the already-existing `JSONWebTokenAuthenticationQS` authentication class (`webodm/settings.py`) — no new auth mechanism on the WebODM side.

**Alternative considered and rejected**: gating "Generate Embeddings" on the task already being public (mirroring Decision 21's "Publish to STAC" gate), which would let the Actor hit the tiler endpoint anonymously with no credential and no `project_pk`-resolution problem beyond still needing the column. Rejected because it would make embedding generation — a core, frequently-used feature — unusable for the common case of a private task, unlike STAC publishing, which is opt-in and rare.

**Implemented, same day.** `visits.project_pk integer` was added to the live `embeddingsdb` Pod via a real `ALTER TABLE` (verified via `\d visits` before and after — confirmed absent, then confirmed present), not just the `schema/embeddingsdb.sql` source file (which was updated to match). `get_or_create_visit()` now takes `project_pk` and includes it on `INSERT` only (not backfilled onto existing rows); verified against the live Pod in a rolled-back transaction (`INSERT ... RETURNING id, project_pk` inside `BEGIN`/`ROLLBACK`, confirmed 0 rows persisted afterward). `apply_embed_generate()`'s message payload now includes `project_pk` and `jwt` (the same per-user token already resolved to invoke the Actor — no second credential lookup). `TaskEmbedView.post()` passes `task.project_id` (WebODM's own FK id, confirmed a plain integer via `app/models/project.py` — no explicit `id` field means Django's default `AutoField`) to both call sites.

**Not yet implemented**: `embed_generate/main.py`'s `fetch_tile_pixels()` (and the rest of `run()`) still don't exist on the Actor side — this decision only makes the *inputs* (`project_pk`, `jwt`) available to that future code, per the two-step plan (WebODM-side contract change first, Actor logic second).

### Decision 42: Fixed a real routing bug in `plugin.py`'s `api_mount_points()` — task-scoped regex fragments weren't anchored with `$`, so shorter patterns silently shadowed longer ones sharing a prefix (Approved — 2026-07-24)

Found while diagnosing an unrelated local-dev restart: the running WebODM instance logged a steady stream of `WARNING Method Not Allowed: /api/plugins/embeddings/task/{pk}/embed-status` while `EmbeddingsPanel.jsx` was polling that endpoint. Traced to `app/plugins/views.py`'s `api_view_handler`, which iterates `plugin.api_mount_points()` in order and returns the first `MountPoint` whose regex resolves — via a plain `url()`/`URLPattern`, whose `resolve()` does not require the entire path to be consumed (Django only enforces that for `include()`-chained resolvers, not a final view pattern). None of the task-scoped patterns in `api_mount_points()` were anchored with a trailing `$` (`load_buttons.js$` in `app_mount_points()` already had this right), so `task/(?P<pk>[^/.]+)/embed` — a regex prefix of `task/(?P<pk>[^/.]+)/embed-status` — was matching first and routing every `embed-status` request (GET) to the POST-only `TaskEmbedView`, hence 405. Confirmed via direct `re.match()` testing, not just inferred from the log.

**A second, more dangerous instance of the same bug was found by checking the other patterns for the same shape**: `task/(?P<pk>[^/.]+)/label` is also a regex prefix of `task/(?P<pk>[^/.]+)/labels/import-geojson` — meaning a GeoJSON label-import POST would have been silently routed to `TaskLabelView` (the Label Studio deep-link endpoint) instead of `TaskLabelsImportGeoJSONView`, with no error at all — a correctness bug, not just a 405.

**Fix**: anchored every task-scoped `MountPoint` regex in `api_mount_points()` with a trailing `$` (`tiles$`, `label$`, `embed$`, `embed-status$`, `publish-to-stac$`, `retract-from-stac$`, `labels/import-geojson$`), plus the non-task-scoped `labelstudio-webhook$`/`label-classes$`/`sites$`, matching the convention `load_buttons.js$` already used. Verified via `re.match()` before/after: `embed$` no longer matches `embed-status`, `label$` no longer matches `labels/import-geojson`, and `embed$` still matches plain `embed`. Confirmed the file compiles (`py_compile`) and restarted `webapp` to pick it up — the "Method Not Allowed" warning stopped recurring in fresh logs afterward.

**Environment note, not a code bug**: this fix genuinely had no effect for a while because `docker compose up`/`restart` were run against the plain `docker-compose.yml` alone. This repo's local dev setup requires the `docker-compose.dev.yml` overlay (`.:/webodm` bind-mounts the entire repo into `webapp`/`worker`) — without it, both containers run whatever was baked into the `opendronemap/webodm_webapp` image at its last local build, invisible to any live source edit. Every fix in this session (this one, Decision 39-41's code changes, Decision 43 below) only became live once containers were brought up via `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d webapp worker`.

### Decision 43: Fixed a real, previously-untested bug in `apply_embed_generate()`'s Tapis Actor invocation — `t.actors.send_message(request_body=...)` does not exist on the installed `tapipy`; the real method is `sendMessage(message=...)` (Approved — 2026-07-24)

Surfaced the first time `apply_embed_generate()` actually ran end-to-end (via a real "Generate Embeddings" click, after Decisions 39-42 got the local dev environment working): `AttributeError: 'Resource' object has no attribute 'send_message'`. Decision 37's original implementation claimed this call shape was "confirmed against tapipy's own bundled OpenAPI spec for the Actors API, operationId: send_message" — that confirmation was wrong, and (per Decision 37's own "Explicitly NOT done" section) the call had never actually been exercised against a running Actor before now, only statically reasoned about.

**Root cause, traced through the real installed package, not re-guessed:**
- `tapipy/actors.py`'s own `AbacoExecutor.submit()` (a working, real precedent already inside the installed package) calls `self.tp.actors.sendMessage(actor_id=..., message=..., headers=...)` — camelCase, not `send_message`.
- The generic resource dispatcher (`tapipy/tapis.py` `Operation.__call__`, ~line 1265-1290) only uses the `request_body=` convenience kwarg when a schema's `properties` dict is *empty* (no property names given by the spec). `sendMessage`'s `JSONMessage` request body schema has a non-empty `properties: {message: ...}` (confirmed by loading the real resource spec: `t.actors.sendMessage.op_desc.request_body.content['application/json'].schema.properties.keys()` → `dict_keys(['message'])`), so the dispatcher instead does `for p_name in schema.properties: if p_name in kwargs: data[p_name] = kwargs[p_name]` — meaning the correct kwarg is the property's own name, `message=`, not `request_body=`.
- Confirmed on the actually-installed `tapipy` (not just by reading source): constructed a real `Tapis` client offline (`tenant_id='portals'` passed explicitly to skip the live Tenants-API network call that `__init__` otherwise makes) and checked directly — `hasattr(t.actors, 'sendMessage')` → `True`, `hasattr(t.actors, 'send_message')` → `False`.

**Fix**: `t.actors.send_message(actor_id=actor_id, request_body={'message': json.dumps(message)})` → `t.actors.sendMessage(actor_id=actor_id, message=json.dumps(message))`. Kept the same "message value is a `json.dumps()`-encoded string" semantics Decision 37 already reasoned about (matching Decision 35's independently-verified expectation that the Actor's `MSG` env var is a JSON string) — only the method name and top-level kwarg were wrong, not the payload shape itself. Updated every stale docstring reference to the old call shape (module docstring, `apply_embed_generate()`'s own docstring, `queue_model_train()`'s docstring) to match.

### Decision 44: `embed-generate`'s full pipeline implemented for real — WebODM-sourced visits only (Decision 40's scope); a real bug in Decision 41's `jwt` design found and fixed along the way (Approved — 2026-07-24)

Following the two-step plan from Decisions 39-41 (WebODM-side contract change, then Actor logic), this increment implements `embed_generate/main.py`'s previously-`NotImplementedError` functions for real, grounded in facts gathered directly from the real code rather than re-derived from the spec alone (WebODM's `app/api/tiler.py`/`app/api/urls.py`/`app/api/authentication.py`, `embeddings-research/scripts/clay_embed_sized.py`, the installed `tapipy` package, and `clay-model-src/pyproject.toml`).

**New modules, `embeddings-tapis-actors` repo:**
- `embed_generate/webodm_client.py` — standard web-mercator tile math (`lonlat_to_tile`/`tile_to_lonlat`/`tile_bounds_lonlat`/`tile_center_lonlat`/`tile_bounds_wkt`/`meters_per_pixel`, OSM slippy-map conventions) plus `get_tile_coverage()` (`GET .../tiles.json`) and `fetch_tile()` (`GET .../tiles/{z}/{x}/{y}.png`), both `?jwt=`-authenticated per Decision 41. A real `TileNotFound` exception distinguishes "this tile isn't covered" (expected, matches Decision 9's "exhaustive coverage via tile_exists()") from `WebODMTilerError` (a genuine failure).
- `embed_generate/clay.py` — real Clay v1.5 loading/inference, mirroring `clay_embed_sized.py` exactly (`EmbeddingEncoder` instantiated directly with explicit `SIZE_ARGS`, not the config-hardcoding `Embedder` wrapper; same band wavelength/mean/std normalization, sin/cos time-of-year and lat/lon conditioning). Sensor profile is hardcoded to `linz` (Clay's only RGB-only, 3-band sensor profile — confirmed by reading every entry in `metadata.yaml`; matches WebODM's own RGB-only orthophoto tiles per Phase 1's own research finding). `parse_encoder_key()` splits `"clay-v1.5-large-rgb"` into the four `encoders` table columns. The loaded encoder is cached at module level (loading a ~4.8GB checkpoint via `torch.load()` is expensive; one invocation embeds many tiles from the same encoder).
- `embed_generate/db.py` gained `get_visit()`, `get_site_zoom()`, `get_or_create_tile_grid()`, `get_or_create_encoder()` — all four were real gaps: `run()` needs to resolve `webodm_task_id`/`project_pk`/`capture_date`/`stac_item_id` from `visit_id` alone (the message deliberately doesn't carry `webodm_task_id`, Decision 37), check the Decision 24/27 zoom lock, and upsert `tile_grid`/`encoders` rows that nothing previously wrote to (the `encoders` table has no seed data at all — confirmed by grepping `schema/embeddingsdb.sql` for `INSERT INTO encoders`, none exist).

**`main.py`'s six previously-stub functions, now real** (WebODM-sourced visits only — `visits.stac_item_id IS NULL` branch; a `stac_item_id`-bearing visit hits an explicit `NotImplementedError` in `enumerate_tiles()`, per Decision 40): `resolve_site_zoom()` (defense-in-depth re-check of Decision 24/27's zoom lock — WebODM's own `TaskEmbedView.post()` already gates this with a 409 before ever queuing the Actor), `enumerate_tiles()` (candidate `(x,y)` range from `tiles.json`'s bounds/zoom, not a reimplementation of per-tile coverage — that's still WebODM's own `tile_exists()`, discovered via a real 404), `fetch_tile_pixels()`, `embed_tile()` (delegates to `clay.py`), `compute_covariates()` (see below), and `run()` (orchestrates all of it, writing `tile_observations`/`embeddings`/`covariates`).

**`compute_covariates()` is an honest, stated scope cut, not a silent gap**: always returns `None` this increment. Real elevation/slope/aspect would need the RAW float DSM values, but WebODM's tiler renders DSM/DTM tiles as colormapped 8-bit PNGs for map display, not a raw-value format — approximating real values back out of a rendered PNG (via `/metadata`'s rescale range) was judged not worth doing as an approximation presented as real data. NDVI/NDWI need multispectral bands, which Phase 1's own research already found absent in every WebODM task checked — so these would be `None` regardless of this function's implementation state. `write_covariates()`'s existing no-op-on-falsy behavior (Decision 34) makes this a clean, real "no covariates row" outcome, not a crash.

**A real bug in Decision 41's own design, found while grounding this against the actual WebODM auth code — not just assumed correct:** Decision 41 said to forward the per-user Tapis access token (`apply_embed_generate()`'s `jwt` variable, used to invoke the Tapis Actor itself) to WebODM's tiler endpoint as `?jwt=`. Tested directly against a live, private task: **this fails** — `{"detail":"Incorrect authentication credentials."}`. Root cause: WebODM's `JSONWebTokenAuthenticationQS` (`app/api/authentication.py`) verifies a JWT signed with WebODM's own `SECRET_KEY` via `rest_framework_jwt` — a completely different token from a Tapis OAuth2 access token, not an interchangeable one. The Tapis token is only valid for calling *Tapis's own* Actors API.

**Fix, verified for real**: `apply_embed_generate()` now mints a genuine, short-lived WebODM-native JWT for the same Django `user` already resolved (via `rest_framework_jwt.settings.api_settings.JWT_PAYLOAD_HANDLER`/`JWT_ENCODE_HANDLER` — the identical mechanism WebODM's own `/api/token-auth/` login view uses) and sends that as a new `webodm_jwt` message field, distinct from nothing else being called `jwt` anymore (renamed throughout `embed_generate/main.py` too, to avoid the two tokens being confused again). Confirmed directly: a token minted this way, passed as `?jwt=<webodm_jwt>` to a live, private task's `.../orthophoto/tiles.json`, returned a real 200 with genuine `minzoom`/`maxzoom`/`bounds` — the same call that failed with the raw Tapis token.

**Docker image (Decision 39)**: `vendor/clay-model-src` (Clay Foundation's source, copied in — ~350KB, no large binaries, safe to commit) and `vendor/clay-v1.5.ckpt` (~4.8GB, copied in from `embeddings-research/models/`, gitignored — never committed) are both baked into the image via the Dockerfile. **Built successfully, real image, confirmed**: `docker build --build-arg ACTOR=embed_generate -t embed-generate:local .` completed, `pip install -e ./vendor/clay-model-src` resolved and installed its full real dependency tree (torch, torchvision, lightning, timm, etc.) without incident.

**Real, flagged gap, not smoothed over**: the GHCR CI pipeline (`.github/workflows/docker-build.yml`, `context: .`, single-repo checkout) has no way to obtain the 4.8GB checkpoint — a real CI build of this image will fail at the checkpoint `COPY` step until the checkpoint is fetched from somewhere CI can reach (a Tapis Files endpoint, a release asset, git-lfs, etc.). Not decided or solved here; documented in the Dockerfile's own comment and `.gitignore`.

**End-to-end verification: real, but incomplete — honestly reported, not rounded up to "fully verified."** Ran the built image against the actually-live `embeddingsdb` Pod and the local WebODM instance (via `host.docker.internal`), with a real `MSG` payload (an existing `visit_id`/`site_id`, a freshly-minted real `webodm_jwt`). **Confirmed working for real**: `MSG` parsing, `embeddingsdb` connectivity (`db.get_visit()`), `resolve_site_zoom()`, and `enumerate_tiles()` — the log shows a genuine `GET .../tiles.json?jwt=...` succeeding against a live, private task and returning "9 candidate tiles" from its real bounds/zoom. **Not confirmed**: the per-tile loop (`fetch_tile_pixels()` → `embed_tile()` → the embeddingsdb writes) — the container was OOM-killed (`Killed`, confirmed via `docker stats`: Docker Desktop's VM is capped at 7.65GB total, and loading the 4.8GB checkpoint via `torch.load()` needs more headroom than was available alongside WebODM's other running containers). This is a real local-environment resource constraint, not a code defect — but per this project's own repeated practice of stating exactly what was and wasn't exercised (Decisions 33/35/37's own precedents), the per-tile Clay inference path is **implemented and code-reviewed, not live-verified end-to-end**. Revisiting this (a larger Docker Desktop memory allocation, or testing against a real GPU-backed Tapis Actor deployment instead of locally) is a real, explicit follow-up, not assumed to already work.

### Decision 45 (PROPOSED, not yet approved): move `embed-generate`'s execution backend from a Tapis Actor (Abaco) to a Tapis Job on TACC Lonestar6 (ls6), mirroring the existing `nodeodm-ls6` pattern

**Status: Approved (2026-07-24)** — user confirmed the two open questions (queue tier, `WEBODM_URL` reachability) and approved implementation. This section documents a real, evidence-backed problem with the Actor architecture and a concrete plan grounded in existing, working infrastructure — not a hypothetical.

**The problem, confirmed against the real live Tapis tenant, not assumed:** `embed-generate`'s Actor (Abaco) never provisions a worker for images at or above ~6GB. Tested twice, both under a guaranteed-unique image tag (ruling out any stale-cache explanation):
- The full image (Clay checkpoint baked in, ~11.4GB): `status: ERROR`, `start_time: None`, `cpu: 0`, empty logs, zero entries from `listWorkers()`.
- A stripped image (same `claymodel`/torch/torchvision/lightning dependency tree, checkpoint removed, ~6.21GB): **identical failure mode** — same `ERROR`/`start_time: None`/`cpu: 0`/empty logs/zero workers.
- By contrast, the *original* pre-Clay skeleton image (minimal deps — `psycopg2`, `PyYAML`, `numpy`, `Pillow`, `requests`, almost certainly well under 1GB) provisioned and ran real code successfully (its execution produced real log output, including the expected `NotImplementedError` from before this increment's changes).

Conclusion: this is not specifically about the checkpoint (Decision 39's original concern) — it's a general size/pull-capacity ceiling on this tenant's Abaco worker pool somewhere between ~1GB and ~6GB, which Actors (a system meant for lightweight, quick containerized executions) were never sized for. Fixing this via Abaco tenant configuration would require access this project doesn't have visibility into; a different execution backend already exists and is proven for exactly this kind of large-image workload.

**The precedent: `nodeodm-ls6` (sibling repo in this monorepo-of-repos) already solves the identical problem for NodeODM's own large images**, submitting real Tapis Jobs (not Actors) to TACC's Lonestar6 (`ls6`) HPC system:
- `nodeodm-ls6/app.json` — a real, registered Tapis v3 App (`id: "nodeodm-ls62"`), `runtime: "ZIP"` (the App package itself is a ZIP of scripts, not a container — deliberately, "to avoid nested container issues," per that repo's own `CLAUDE.md`), `jobAttributes.execSystemId: "ls6"`, `execSystemLogicalQueue: "vm-small"` (its `notes.queueFilter` also lists `gpu-a100`/`gpu-a100-dev`/`gpu-a100-small` as selectable queues), `coresPerNode: 16`, `memoryMB: 30720` (30GB — an order of magnitude more headroom than whatever broke Abaco here), `maxMinutes: 240`.
- `nodeodm-ls6/tapisjob_app.sh` — the script Tapis actually executes on the compute node once the ZIP is unpacked. Does real GPU detection (`nvidia-smi` / `$SLURM_JOB_PARTITION` check), then `module load tacc-apptainer` and `apptainer pull "$SIF" "docker://$IMAGE"` (line 280) — pulling a real, large Docker image (`ghcr.io/wmobley/nodeodm:gpu`/`:latest` — the exact same GHCR-hosted-image pattern this project already uses for `embed-generate`) straight onto the HPC compute node's own local disk, then `apptainer exec $NV_FLAG ... "$SIF" ...` to run it. This is the direct, already-proven answer to "the image is too big to pull" — an HPC compute node's disk/memory envelope is not Abaco's.
- `ClusterODM/libs/asr-providers/tapis.js` (`submitJobWithoutData()`, ~line 821) and `ClusterODM/odm_job.json` — the real Tapis Jobs API v3 submission shape: `POST https://portals.tapis.io/v3/jobs` (or `t.jobs.submitJob(**job_def)` via tapipy) with `appId`, `appVersion`, `execSystemId`, `execSystemLogicalQueue`, `archiveSystemId`, `nodeCount`/`coresPerNode`/`memoryMB`/`maxMinutes`, `parameterSet.appArgs` (positional args), `parameterSet.schedulerOptions` (`-A PT2050-DataX` — this project's own already-active, working TACC allocation, confirmed live via `ClusterODM/tapis-config.json`/`odm_job.json`), and — the key mechanism for our purposes — `parameterSet.envVariables` (arbitrary per-job key/value pairs the job script sees as real environment variables).

**Why this is a small, not a large, code change on the embed-generate side**: `embed_generate/main.py`'s `read_actor_message()` already reads its entire invocation payload from a single environment variable, `MSG` (a JSON string) — that's Abaco's convention, but nothing about `main.py` itself is Abaco-specific once the message is in `os.environ['MSG']`. A Tapis Job's `parameterSet.envVariables` can set an env var named `MSG` to the exact same JSON payload `apply_embed_generate()` already builds. **This means `embed_generate/main.py`, `clay.py`, `webodm_client.py`, and `db.py` need ZERO changes** — the entire pipeline implemented in Decision 44 is execution-backend-agnostic already, by construction, not by luck (Abaco's own message contract happened to be a plain env var, which a Tapis Job's `envVariables` can reproduce exactly).

**What would actually need to be built (adapting `nodeodm-ls6`'s pattern, not inventing one):**
1. A new Tapis App, `embed-generate-ls6` — `runtime: "ZIP"`, `execSystemId: "ls6"`. Simpler than `nodeodm-ls6`'s: no TAP/reverse-tunnel web-access machinery (that's for NodeODM's long-running interactive service; `embed-generate` is a one-shot batch job that exits when done). **Resolved (user decision, 2026-07-24)**: start on `execSystemLogicalQueue: "vm-small"` (not a GPU queue) — CPU-only Clay v1.5 inference first, upgrade to `gpu-a100-dev`/`gpu-a100-small` (already selectable per `nodeodm-ls6`'s own `queueFilter`, so no new queue access to arrange) only if real runs show it's needed. Resource sizing (`memoryMB`/`maxMinutes`) still needs real numbers from actual runs — start conservative (e.g. `memoryMB: 32768`, `maxMinutes: 60`), same iterative approach `nodeodm-ls6`'s own resource-mapping table used.
2. A new job script (analogous to `tapisjob_app.sh`, much shorter — no TAP integration, no long-running service loop): `module load tacc-apptainer` → `apptainer pull` the same GHCR image (`ghcr.io/in-for-disaster-analytics/embeddings-tapis-actors:embed-generate-latest`) to a local `.sif` on the compute node → `apptainer exec "$SIF" python -m embed_generate.main` → exit (no `$NV_FLAG`/GPU detection needed yet, per the `vm-small`-first decision above — add it back if/when a GPU queue is used). Cache the `.sif` the same way `tapisjob_app.sh` does (skip re-pulling if already present) since repeat `embed-generate` runs are expected to be common.
3. Job-submission code replacing `apply_embed_generate()`'s `t.actors.sendMessage(...)` call with `t.jobs.submitJob(...)`, building the `envVariables` list (`MSG`, unchanged JSON shape) and reusing the proven `-A PT2050-DataX` allocation and `execSystemId: "ls6"`.
4. **Resolved (user decision, 2026-07-24)**: `WEBODM_URL` reachability from ls6 — confirmed accessible, same as the rest of ODM-Suite's own TACC-side integrations (`ClusterODM`/`nodeodm-ls6` already reach WebODM the same way). Real value: `https://webodm.tacc.utexas.edu` (`WebODM/.env.sample`'s own `WO_HOST`/`WO_URL` production values), not `localhost` — the local-dev value used in this session's local Actor tests. Note this does mean a real ls6 end-to-end test needs a `visit`/`task` that actually exists against the **production** WebODM's database, not the local dev rows used for the Actor tests above.
5. **Still open**: how job *completion* is observed. The existing design already doesn't depend on Actor-specific status polling — `TaskEmbedStatusView.get()` polls `embeddingsdb` directly via `count_tile_observations()` (Decision 34), which works identically regardless of execution backend — so this may need no change at all. Worth confirming rather than assuming once real jobs are running.

**Resolved by user decision (2026-07-24)**: start CPU-only on `vm-small`; `WEBODM_URL` is `https://webodm.tacc.utexas.edu`, confirmed reachable the same way the rest of ODM-Suite already reaches it. Still open: exact `memoryMB`/`maxMinutes` numbers (need real run data) and job-completion observation (likely already solved by the existing DB-polling design, not yet confirmed against a real ls6 run).

**Implemented, same day — code-complete, real App registration/end-to-end run still pending:**
- `embeddings-tapis-actors/ls6/app.json` — the real Tapis App spec (`id: "embed-generate-ls6"`, `runtime: "ZIP"`, `execSystemId: "ls6"`, `execSystemLogicalQueue: "vm-small"` per the resolved decision above, `memoryMB: 32768`/`maxMinutes: 60` as starting values, `parameterSet.envVariables` pre-declaring `MSG`/`EMBEDDINGSDB_URL`/`WEBODM_URL` — real per-job values are supplied at submission time by `apply_embed_generate()`, not baked in here).
- `embeddings-tapis-actors/ls6/tapisjob_app.sh` — the real job script, much shorter than `nodeodm-ls6`'s own (no TAP/reverse-tunnel, no GPU detection yet per the CPU-first decision): `module load tacc-apptainer` → `apptainer pull` the same GHCR image → `apptainer exec` → `python -m embed_generate.main`, with `MSG`/`EMBEDDINGSDB_URL`/`WEBODM_URL` passed through via `--env`. Bash-syntax-checked (`bash -n`), not yet run on a real ls6 node.
- `embeddings-tapis-actors/tapis/register_app.py` — mirrors `register_actor.py`'s structure, but Apps have a caller-chosen `id` (unlike Actors' server-generated one), so the upsert is a direct `getApp()` lookup, not the workaround `find_existing_actor_id()` needed. `createAppVersion`'s real call shape (each top-level JSON key as its own kwarg, confirmed via `op_desc.request_body...schema.properties` being non-empty — the identical rule Decision 43 found for `sendMessage`) was verified against the installed `tapipy` before writing this, not assumed. `--dry-run` exercised for real and produces the expected spec; the non-dry-run path has NOT been run (needs real Tapis credentials, and the App's `containerImage` ZIP still needs to be built and uploaded to `cloud.data` first — this script does not do that upload itself).
- `coreplugins/embeddings/embeddings_client.py`'s `apply_embed_generate()` — `t.actors.sendMessage(...)` replaced with `t.jobs.submitJob(**job_spec)`, reusing the exact same `message` dict (now delivered as the Job's `MSG` env var) and the exact same per-user JWT-minting logic from Decision 44, unchanged. Reuses `settings.TAS_DEFAULT_ALLOCATION` (already a real, working setting — `PT2050-DataX`, confirmed live via `ClusterODM`'s own config) for the scheduler allocation rather than inventing a new one, and `settings.WO_URL` for the Job's `WEBODM_URL` env var rather than hardcoding the production host.
- `webodm/settings.py` — `WO_EMBEDDINGS_ACTOR_ID` removed entirely (genuinely unused now, not kept as a dead setting); added `WO_EMBED_GENERATE_APP_ID` (default `'embed-generate-ls6'`) and `WO_EMBED_GENERATE_APP_VERSION` (default `'1.0.0'`). `WO_MODEL_ACTOR_ID` untouched — model-train's Actor path isn't implemented yet and has no evidence of the same problem.
- `coreplugins/embeddings/api_views.py`'s `TaskEmbedView` — its 503 guard now checks `WO_EMBED_GENERATE_APP_ID` instead of the removed setting.
- All changed/added Python files confirmed to compile (`py_compile`); `app.json` confirmed valid JSON; `tapisjob_app.sh` confirmed valid bash syntax.

**Not yet done — real, stated gaps, not glossed over:**
- The App has not actually been registered against the live Tapis tenant (`register_app.py`'s non-dry-run path).
- The `containerImage` ZIP (`ls6/app.json` + `ls6/tapisjob_app.sh`) has not been built or uploaded to the `cloud.data` path the App spec references.
- No real Tapis Job has been submitted or run on ls6 — the whole path is code-complete and internally consistent (confirmed call shapes, matching env var contracts) but not live-verified end to end, unlike the Actor path's earlier (if ultimately unsuccessful) live tests.
- A real ls6 test needs a `visit`/`task` that exists against **production** WebODM's database (`https://webodm.tacc.utexas.edu`), not the local dev rows used for this session's Actor tests.

---

## User Feedback / Decisions

- 2026-07-22: Confirmed the Label Studio and embeddings-UI work are one plugin, not two (posted to issue #19).
- 2026-07-22: Requested the model-size tradeoff and DSM/multispectral fusion actually be tested empirically before this spec was written — results directly shaped Decisions 2 and 3.
- 2026-07-22: Raised that SDM/hazard-susceptibility modeling may benefit from a *learned* spatial-context embedding for terrain, specifically for flood modeling. Left as a real, testable-later question, not asserted either way.
- 2026-07-22: Challenged whether classifier training was correctly scoped to "project" — caught that `classifiers.project_id` (as originally written) contradicted Phase 1's own cross-project bake-off. Led to Decision 6/8 and the wireframe correction (dedicated Embeddings page via `main_menu()`/`app_mount_points()`, not a task-modal or project page).
- 2026-07-22: Requested the system be more flexible than what was actually tested — labels shouldn't be classification-only (regression, change detection), and data from other locations/sources should be poolable. Led to Decision 7 (`tile_grid`/`tile_observations` split, `value_type`, `visits.source`).
- 2026-07-22: Requested "Label a Sample" become a map (not a thumbnail grid) so tile selection carries spatial context, and asked for the Label Studio integration to be fully specified end-to-end rather than left at "proxies to the API." Led to Decision 10 (real webhook, shared-secret auth) and Decision 11 (map-based selection).
- 2026-07-22: Asked whether embedding generation requires hand-identifying tiles or could cover the whole orthophoto. Led to Decision 9 — all tiles at a configurable zoom, reusing WebODM's existing `rio_tiler` XYZ tiling rather than a bespoke grid; the task-panel tile checklist is now scoped to labeling only.
- 2026-07-22: Pointed out the label taxonomy shouldn't be capped at Phase 1's 7 default classes, and that labels should be importable from GeoJSON, not only produced via Label Studio annotation. Led to Decision 12 (`label_classes` table, GeoJSON import endpoint with unrecognized-value confirm/remap step).
- 2026-07-22: Requested predictions also be shown as a map, and asked whether flagged predictions actually link back to Label Studio or just say so conceptually. Led to Decision 13 (per-site prediction map with tabs) and Decision 14 (review batches reuse the project-creation flow via a new cross-project `workspace/review` endpoint, distinct from the task-scoped `.../label` endpoint).
- 2026-07-22: Asked how the set of trainable models gets configured. Led to Decision 15 (`model_algorithms` registry, explicitly developer-extensible rather than user-extensible like `label_classes` — a distinction worth stating precisely rather than treating every "list of options" the same way).
- 2026-07-22: Pointed out that real ensemble methods (Random Forest, Gradient Boosted Trees) need a train/test split, hyperparameter tuning, and diagnostics to be credible, citing Wing et al. 2021 (NHESS) as a methodological reference, and noted existing systems should be leveraged rather than built from scratch. Led to Decision 16 — scikit-learn's own `train_test_split`/`GridSearchCV`/`StratifiedKFold`/metrics, `model_inputs.split` added to the schema, and `spatial_block`/`temporal_holdout` split strategies grounded in the `tile_grid`/`visits` split from Decision 7.
- 2026-07-22: Asked which software system to use for tracking/versioning models; compared MLflow against ClearML (noting ClearML's real existing precedent in `maestro-model/clearml.conf.dist`) and chose MLflow. Led to Decision 17 — MLflow as the system of record, `model_metrics` dropped from the schema in favor of `models.mlflow_run_id`, a new `mlflow` Tapis Pod, and a server-side diagnostics-proxy endpoint.
- 2026-07-22: Asked for Diagnostics to be its own page rather than a third tab at the bottom of the Embeddings & Classifier page. Led to Decision 18 — a separate `.../models/{model_id}/` route via a second `app_mount_points()` registration, linked from the model name rather than a mode switch alongside Predictions.
- 2026-07-22: Asked how much of the system depends on WebODM orthophotos versus what could be built from STAC-cataloged rasters, then asked to plan against the real DSO STAC API specifically (`docs/services/stac-api.md`) rather than a generic notion of STAC. Led to Decision 19 — `visits.stac_collection_id`/`stac_item_id`, a second `embed-generate` tiling path via `rio_tiler` direct-to-asset, and `workspace/stac/*` browse/import endpoints, all against the real, already-running, anonymous-read service.
- 2026-07-22: Confirmed WebODM should also publish to the DSO STAC API (converging the two raster sources), agreeing with the direction raised in Open Question 11. Led to Decision 20 — opt-in per-task `publish-to-stac` endpoint, reusing the requesting user's Tapis JWT, `embed-generate`'s branch condition refined to "has `stac_item_id`" rather than `visits.source` — with the private-task/anonymous-STAC-read exposure risk explicitly flagged as unresolved (Open Questions 13-14) rather than assumed safe.
- 2026-07-22: Proposed resolving that exposure risk by gating "Publish to STAC" on a task/project already being public, rather than a standalone opt-in checkbox. Led to Decision 21 — publish is only available when `task.public or task.project.public` (WebODM's own real, existing share-link flags, `app/models/task.py:266-267`/`project.py:33-35`) — the same anonymous-exposure decision the user already makes for a different purpose, reused rather than duplicated. Surfaced one new unresolved question in the process: retraction when a published task later flips back to private (Open Question 15).
- 2026-07-22: Agreed to leave retraction (Open Question 15) open, then worked through the remaining open questions: confirmed new repo for the Tapis Actors (Decision 22); pointed to WebODM's own public-URL precedent in the CKAN plugin for the STAC asset-href question, which — checked against `coreplugins/ckan/publisher.py` and `app/api/tasks.py`'s `get_and_check_task()` — resolved cleanly as reusing WebODM's existing `.../download/{asset}` endpoint (Decision 23); asked what the actual `tile_grid` matching question was, which reframed it as a zoom-consistency question rather than a spatial-join one, resolved by locking zoom per site (Decision 24); set the minimum label count to 30, confirmed covariates stay inside `embed-generate`, and confirmed the GeoJSON label-key default as designed (Decision 25, batched).
- 2026-07-23: Both Tapis Actors confirmed genuinely registered (real actor_ids), and asked to wire real `embed-generate` invocation into `TaskEmbedView.post()`, resolving Decision 30's credential question for real by mirroring `apply_ckan_publish()` exactly rather than inventing a new pattern. Led to Decision 37 — `apply_embed_generate()` (real, self-contained Celery task, per-user `TapisOAuth2Token`, real `tapipy` `Tapis`/`send_message` calls independently re-verified against the installed package), `WO_EMBEDDINGS_ACTOR_ID`/`WO_MODEL_ACTOR_ID` added to settings, `tapipy` added as a new WebODM dependency, and Decision 30's "service token" wording corrected to "per-user token." `model-train`'s equivalent explicitly deferred (no `workspace/train` endpoint exists yet).
- 2026-07-22: Asked to move toward implementation. Per this repo's Major-tier workflow, ran a 5-reviewer parallel pass (design-reviewer, architect, skeptic, security-reviewer, tester) against the full spec before approving it, synthesized by `team-discourse`. Findings converged on: a real Assumptions/Files-Affected self-contradiction about whether the WebODM database gets touched (Decision 26 — it doesn't; the mapping lives entirely in `embeddingsdb`, plus an explicit cascade-delete policy); Decision 24's zoom-lock needed a cheap override rather than a hard rule, and separately, site assignment had no described mechanism at all (Decision 27); the 30-label floor needed a per-class minimum too (Decision 28); the webhook needed constant-time comparison and scope validation (Decision 29); the async Tapis Actors had no stated credential model (Decision 30, resolved by matching CKAN's own existing async-publish pattern); and several mechanical staleness bugs (stale Objective, stale architecture diagram, a Risks-table row directly contradicting Decision 24, a missing file in the plugin tree, out-of-order Open Questions numbering) — all fixed. Re-raised Open Question 15 (retraction) given the security-reviewer's code-grounded nuance — `get_and_check_task` re-checks `public` per request, so the imagery itself already self-protects and only STAC item *metadata* persistence was the real residual gap — and the user chose a lightweight manual "Retract from STAC" endpoint over both the original "leave fully open" call and a full reconciliation job (Decision 31).

---

**Spec Version**: 3.0
**Date**: 2026-07-22
**Status**: Approved

# WebODM Upstream 3.1.2-Era Reconciliation

## Status

Implementing

## Objective

Create a maintained WebODM branch that reconciles the custom fork with the cached OpenDroneMap-era upstream `master` reference (`a4501835`) while preserving the fork's Tapis, ClusterODM, Corral, CKAN, embeddings, upload, viewer, and deployment behavior.

This milestone does not port ODX, NodeODX, ClusterODX, or OpenSplat.

## User need

**Primary user** — The WebODM maintainer responsible for the customized Tapis/Corral deployment.

**Secondary users** — Developers maintaining WebODM plugins and processing-node integrations; operators validating staging and production deployments.

**Job-to-be-done** — Bring the customized WebODM fork forward to a compatible upstream baseline without losing existing integrations or corrupting the production database/media state.

**Current pain** — The fork is substantially ahead of its 2025 merge base in custom commits but behind upstream in core WebODM code. The worktree also contains uncommitted Tapis changes, a NodeODM submodule pointer change, and an untracked `.ckg/` directory, so a direct merge risks accidental loss or ambiguous migration history.

**Definition of success** — A clean integration branch builds, migrates a copy of representative data, passes focused and full tests, preserves the existing custom feature contracts, and can be deployed to staging without changing production `master`.

## Current code/system summary

- Repository: `/Users/wmobley/Documents/Github/odm-suite/WebODM`.
- Current fork tip: `fdad2f69`, WebODM package version `2.9.1`.
- Cached upstream tip: `a4501835`, WebODM package version `3.1.2`.
- Merge base: `75179368`; the fork and cached upstream have 218 and 206 commits respectively since that base.
- Thirty-four paths overlap between fork and cached upstream changes, including `Dockerfile`, dependency manifests, settings, task/model/API code, viewers, upload UI, startup scripts, and worker code.
- Existing worktree changes must be preserved: `app/api/tapis_preferences.py`, `app/api/tapis_storage.py`, `setup_tapis_oauth2.py`, `nodeodm/external/NodeODM`, and untracked `.ckg/`.
- The fork uses the ODM processing path through NodeODM/ClusterODM and includes custom Tapis/LS6 deployment scripts.
- Existing fork migrations end at `0047_task_ckan_url.py`; cached upstream uses conflicting `0045`–`0047` migration filenames for different schema changes.

## Proposed design

1. Work on the already-created branch `upgrade/webodm-upstream-3.1.2`, leaving `master` unchanged.
2. Capture the current dirty worktree as an explicit preservation snapshot before merge resolution. Do not discard, reset, or overwrite the existing Tapis edits, NodeODM pointer, or `.ckg/` without inspection.
3. Merge the pinned cached upstream reference into the branch with a non-fast-forward merge. Resolve overlapping core files manually by preserving both upstream behavior and custom behavior; do not use blanket `ours` or `theirs` conflict resolution.
4. Keep existing migration files immutable. Re-express the cached upstream schema changes as new migrations after the fork head:
   - `0048_profile_cluster_id`
   - `0049_redirect`
   - `0050_task_wkt`
5. Preserve the ODM/NodeODM/ClusterODM processing contract in this milestone. Pin one tested NodeODM submodule revision and keep the current Tapis/LS6 path operational.
6. Reconcile dependency and build changes only after confirming they do not remove required Tapis, Corral, GDAL, PostGIS, Redis, Celery, or plugin behavior.
7. Validate the branch in Docker and staging before considering any merge back to `master`.

## Files likely affected

- Core reconciliation: `Dockerfile`, `requirements.txt`, `package.json`, `webodm/settings.py`, `start.sh`, `webodm.sh`, `worker/`, and `docker-compose*.yml`.
- Core application/API/UI: `app/models/`, `app/api/`, `app/views/`, `app/static/app/js/`, `app/templates/`, and `app/tests/`.
- Custom integration surface: `app/auth/`, `app/services/`, `coreplugins/`, `scripts/`, Tapis deployment documentation, and the NodeODM submodule pointer.
- Database compatibility: `app/migrations/0048_profile_cluster_id.py`, `app/migrations/0049_redirect.py`, and `app/migrations/0050_task_wkt.py`.

## API/schema changes

The existing custom API and environment-variable contracts remain in scope and must not be removed silently.

The compatible upstream schema additions are:

- `Profile.cluster_id` integer field.
- `Redirect` model for project/task redirects.
- `Task.wkt` text field for georeferencing when an EPSG code is unavailable.

No existing migration file is renamed or edited solely to resolve the filename collision. No destructive schema migration is planned.

## Data flow

1. The existing fork branch remains the source of truth for custom Tapis authentication, storage, TAS allocation, ClusterODM, Corral, CKAN, embeddings, upload, and viewer behavior.
2. Upstream core changes are merged into the WebODM application and build layers.
3. Existing fork migrations run through `0047_task_ckan_url`.
4. New compatibility migrations apply the upstream `cluster_id`, redirect, and WKT schema additions in sequence.
5. WebODM continues submitting processing work through the existing ODM/NodeODM/ClusterODM path.
6. Docker build/test and staging validation exercise both the core WebODM path and custom integrations against representative data.

## Risks and tradeoffs

- Core files have substantial two-sided edits, so automatic merge resolution could silently remove custom behavior.
- The migration filename collision can cause Django graph conflicts if upstream migrations are copied directly. New migrations after the fork head add safety at the cost of differing migration names from upstream.
- Dependency updates may change Python, Node, GDAL, raster, Celery, or browser-build behavior.
- The NodeODM submodule has both a committed fork pointer and an uncommitted working-tree pointer; the tested revision must be made explicit before integration is complete.
- Current tests may not cover all live Tapis, ClusterODM, Corral, CKAN, or embeddings paths; staging tests remain necessary.
- The current public WebODM/ODX architecture is intentionally deferred. Mixing ODX into this branch would make failures harder to attribute.

## Alternatives considered

- **Directly merge current WebODM master/3.3.x:** Rejected for this milestone because current WebODM has decoupled from OpenDroneMap and moved to the ODX/NodeODX ecosystem.
- **Rebase all custom commits onto upstream:** Rejected as the first integration mechanism because the fork is already shared and the number of overlapping commits/files is large; a merge preserves provenance and supports review of conflict resolutions.
- **Copy upstream migration files unchanged:** Rejected because migration filenames `0045`–`0047` already mean different things in the fork.
- **Use blanket conflict resolution:** Rejected because it could erase Tapis, Corral, plugin, or viewer behavior.

## Test plan

- Establish a baseline by running the existing backend/frontend test entry points before resolving merge conflicts.
- Validate the Django migration graph with `showmigrations`, `migrate --plan`, and a fresh database migration.
- Apply migrations to a restored staging database copy and verify existing users, projects, tasks, plugins, and task assets remain accessible.
- Build the Docker image and run the repository test suite.
- Run focused tests for Tapis OAuth/storage, ClusterODM/task submission, upload flows, viewer behavior, CKAN, embeddings, and relevant plugin builds.
- Exercise representative processing through the existing ODM/NodeODM/ClusterODM path, including shared-volume/import-path behavior and an LS6-backed job where available.
- Run staging smoke tests for authentication, task creation, processing, result display/download, CKAN/embeddings opt-in paths, and backup/ownership behavior.

## Documentation plan

- Update WebODM deployment and integration documentation only where the reconciled behavior changes.
- Document the migration-number reconciliation and the pinned NodeODM revision in this design spec and the relevant deployment notes.
- Do not update ODX/NodeODX documentation in this milestone.
- The DSO Architecture documentation path specified by repository guidance was not present in the current workspace; verify its service/auth pages separately before any deployment documentation change.

## Rollout/rollback plan

- Keep `master` and the existing production image unchanged during branch work.
- Build a uniquely tagged integration image from this branch and deploy it to staging with a database/media copy or representative fixture data.
- Before production consideration, take PostgreSQL and media backups and verify the backup contents.
- Production rollout, if separately approved, applies only additive migrations, starts the new image in a controlled maintenance window, and runs smoke tests before re-enabling workers.
- Roll back first to the previous application image. Restore database/media backups only if data corruption or an incompatible migration is observed.

## Open questions

- Whether `.ckg/` is a generated local artifact that should remain ignored or a project artifact that belongs in version control.
- Which NodeODM submodule commit is the intended production baseline: the committed fork pointer or the current uncommitted working-tree pointer.
- Whether staging has representative Tapis, ClusterODM, Corral, CKAN, embeddings, and LS6 access for end-to-end validation.

## Decisions

### 2026-10-05 - Use a dedicated compatibility branch

- **Decision:** Perform the first upgrade on `upgrade/webodm-upstream-3.1.2` and leave `master` unchanged.
- **Reason:** The fork has extensive custom work and the user requested separate branches.
- **Alternatives rejected:** Directly updating `master`; rejected because it would combine merge resolution and production risk.
- **User feedback:** User said to start with the WebODM branch and then explicitly authorized execution.
- **Impact on implementation:** All changes in this milestone remain on the upgrade branch until tests and staging validation pass.

### 2026-10-05 - Stage compatible upstream before ODX

- **Decision:** Reconcile the OpenDroneMap-era upstream first; defer ODX, NodeODX, ClusterODX, and OpenSplat.
- **Reason:** It isolates core WebODM/upstream conflicts from the later processing-stack migration.
- **Alternatives rejected:** Direct current-WebODM/ODX port; rejected as a separate architecture migration.
- **User feedback:** User approved the staged approach.
- **Impact on implementation:** Preserve and test the ODM/NodeODM/ClusterODM path in this branch.

### 2026-10-05 - Preserve existing migration history

- **Decision:** Add new migrations after the fork's `0047_task_ckan_url` rather than rename or replace existing migrations.
- **Reason:** The fork and upstream use conflicting migration filenames for different operations, and existing environments may already record the fork migrations as applied.
- **Alternatives rejected:** Copy upstream `0045`–`0047` unchanged; rejected because Django migration identity is filename-based.
- **Impact on implementation:** Add the three explicit compatibility migrations and validate the resulting graph on a database copy.

### 2026-10-05 - Complete the manual upstream reconciliation

- **Decision:** Merge the cached upstream reference `a4501835` with manual conflict resolution, retaining the fork's README, locale submodule, Tapis exports, Corral ownership/startup behavior, custom viewer controls, and task deletion path while incorporating upstream EPT, raster-unit, GLB, redirect, WKT, and frontend changes.
- **Reason:** These fork behaviors are deployment and product contracts; upstream's additions are compatible when the overlapping files are composed rather than replaced wholesale.
- **Implementation note:** The upstream migration files were reissued as `0048_profile_cluster_id`, `0049_redirect`, and `0050_task_wkt` after the fork's `0047_task_ckan_url`.

### 2026-10-05 - Pin legacy Python build prerequisites

- **Decision:** Pin `setuptools==69.5.1`, `Cython==0.29.36`, and `numpy==1.26.2` in the Docker build stage and use `--no-build-isolation` for the legacy geospatial requirements.
- **Reason:** The first image build exposed two real compatibility failures: a legacy rasterio setup script imported `pkg_resources`, and the aarch64 rasterio source package required Cython. The pinned build environment resolves both without changing runtime application dependencies.
- **Validation:** The rebuilt `webodm-upgrade-3.1.2:local` image completed Entwine, Python dependency, webpack, plugin, static, and translation build steps.

### 2026-10-05 - Test scope and current gap

- **Validation completed:** Compose syntax validation; AST parsing of 191 app Python files; frontend Jest execution with 39 of 48 suites passing (50 tests passing); production and test Docker image builds; Tapis/Redirect/Task model-import smoke test; Entwine presence smoke test; and a disposable PostGIS migration run through `0050_task_wkt`.
- **Backend validation:** With disposable PostGIS and Redis plus the repository's local-development authentication bypass, the cluster test passed. The task-import suite ran all three tests in the test image with embedded NodeODM retained; two passed, while one retained test failed because its permission-removal assertion conflicts with the default group's inherited `change_project` permission. The WKT integration test completed import/processing but its exact-string assertion differs under the upgraded GDAL serializer (`unknown_based_on_...` versus the older spaced label).
- **Known gap:** Nine Jest suites require generated `build/mocks/*.json` fixtures. Tapis, live ClusterODM/Corral/LS6, CKAN, embeddings, staging, and production-like migration/media validation remain follow-up work; no external or production systems were modified.

### 2026-10-05 - Use disposable infrastructure for backend validation

- **Decision:** Run migration and focused backend checks against named disposable PostGIS/Redis containers rather than the user's existing local data/services.
- **Reason:** This validates the migration graph and application boot path without risking unrelated local databases or volumes.
- **Validation:** All migrations through `app.0050_task_wkt` applied successfully after enabling `postgis` and `postgis_raster` in the disposable database template. Containers and the test network were removed after validation.
- **Impact:** Backend results are representative of a clean containerized environment, but staging and live integration tests are still required before deployment.

## User feedback / decisions

- The user approved a staged upgrade strategy: compatible WebODM/upstream reconciliation first, ODX stack later.
- The user approved separate branches/repositories for the WebODM, processing-cluster, NodeODX/LS6, and optional splat work.
- The user explicitly authorized starting the WebODM branch implementation on 2026-10-05.

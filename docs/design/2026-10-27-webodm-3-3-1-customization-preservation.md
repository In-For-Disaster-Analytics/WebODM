# WebODM 3.3.1 customization-preserving implementation addendum

## Status

Implemented — isolated local source reconciliation complete. Frontend build/tests and offline backend checks passed. Clean container build and focused container validation passed; database-backed backend validation and connected acceptance remain pending; no deployment readiness is claimed. Independent review was unavailable because the reviewer hit a usage limit.

## Objective

Integrate WebODM v3.3.1 at 51c8f98b35de920d347631bcb99ed06180a6cafd while preserving all 47 cataloged customizations. This addendum narrows the [parent design](../../../../docs/design/2026-10-09-webodm-clusterodm-odx-upgrade.md) to WebODM. ODX, NodeODX and ClusterODX are already implemented and require no backend upgrade work.

## User need

**Primary user:** The TACC WebODM maintainer/operator identified in the parent design.

**Secondary users:** Integration developers and operators relying on task submission, status, outputs and cleanup.

**Job-to-be-done:** Update WebODM without losing its custom workflows or compatibility with the established backend.

**Current pain:** The 3.1.2-era custom source contains integrations a wholesale upstream replacement would discard.

**Definition of success:** An isolated source upgrade integrates the release, accounts for every inventory ID, preserves migration history and passes available focused tests. Connected-runtime acceptance and production promotion remain separate gates.

## Current code/system summary

Custom baseline: 8fe74e8b5bd7353982c3b142d5f208ef424a1501. Old upstream comparison: a4501835a0544c1bcb3acca61e376e9e3a6a4b0b. Coordinator inspection records 484 upstream changed paths, 196 fork paths and 50 overlaps. Temporary three-way dry-run results include 466 automatic results, 16 text conflicts and five special cases; these are reconciliation results, not disjoint changed-path totals.

Read-only .wolf anatomy/memory and the [inventory](../upgrade/2026-10-27-webodm-customization-inventory.md) ground the preservation scope. Direct source inspection confirms pyodm ProcessingNode integration and the dirty JWT wrapper URL-redaction import. Catalog limitations include OAuth signature validation, partial discovery wiring, removed Potree experiments and embedding stubs. Preservation does not certify or complete these. DSO Architecture documentation is unavailable at its configured mount.

## Proposed design

1. Use the prepared isolated worktree .worktrees/webodm-3.3.1 on upgrade/webodm-3.3.1-tapis, based on the custom baseline. Preserve the original checkout and all dirty/untracked work. The coordinator recorded seven original file hashes in /tmp/webodm-upgrade-original-hashes.json. Copy only the explicitly identified wrapper/security helper/security tests overlay and inventory, with provenance checks. Do not edit .wolf or .ckg.
2. Reconcile per file using the cached old upstream as explicit comparison base, custom source plus overlay as ours and pinned v3.3.1 as theirs. Review automatic results and upstream-only changes; preserve fork-only paths. Never use wholesale replacement or a version-only bump.
3. Manually review the known conflicts: Dockerfile, README.md, app/api/tasks.py, app/api/urls.py, app/models/task.py, app/static/app/js/classes/plugins/API.js, the EditPresetDialog.jsx/Map.jsx/ProjectListItem.jsx components, registration/login.html, app/urls.py, nodeodm/models.py, webodm.sh, webodm/settings.py, worker.sh and worker/celery.py.
4. Handle .env without disclosing secrets, preserve the two intentionally removed fork CI workflows, and review submodule gitlinks explicitly. Recursive fetch failed on intermediate locale ref 369ea7d…; the release locale pin is dfef5f3a823b2eec721f153fd2b7d70dbb712fc1. Verify this exact pin rather than substituting silently. Verify the complete release NodeODX gitlink (reported prefix f1df8eae), without backend source changes.
5. Adapt WebODM consumer code to pyodx==1.5.14 while preserving JWT/HTTPS, import_path, status, restart, outputs and cleanup. Retain pyodm compatibility for immutable historical migration imports. Preserve custom PyJWT 1.7.1, psycopg2 2.9.9 and UTC compatibility adaptations pending dependency tests. Upstream remains Django 2.2.27.
6. Preserve historical migrations byte-for-byte and append reviewed new migrations as below. Preserve allocation-gate intent on new media write endpoints, with intended public reads retained.
7. Preserve the ten legacy bundled coreplugins that upstream moves to the plugin store, while integrating the upstream plugin-browser implementation. Verify plugin-update migration short-circuit conditions against retained bundles; do not claim this alone makes migration execution safe.
8. Account for every inventory ID below with reconciled source location and command/result evidence. Replacement requires comparative evidence; retirement requires approval. Do not complete discovery/embedding stubs.

### Proposed customization dispositions

Every entry refers to its baseline locations and specific checks in the inventory. Pending means no passing evidence is claimed. Before completion, record actual reconciled locations, tests and unresolved runtime checks for every ID.

- **AUTH-01** — preserve. Present; signature-validation limitation. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **AUTH-02** — preserve. Present; replaces refresh behavior. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **AUTH-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **NODE-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **NODE-02** — preserve. Present; superuser only. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-01** — preserve partial implementation; defer completion. Partial implementation. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-02** — preserve. Present configuration/task code; wiring needs validation. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-04** — preserve. Present; requires shared storage. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-05** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DATA-06** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **HPC-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **HPC-02** — preserve. Present; configuration dependent. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **HPC-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **HPC-04** — preserve. Present; legacy cluster values. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **TASK-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **TASK-02** — preserve. Present; best-effort bounded lock. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **TASK-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **MAP-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **MAP-02** — preserve. Present; temporary layers. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **MAP-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **VIEW-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **VIEW-02** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **VIEW-03** — preserve removed state (do not restore experiment). Removed/superseded. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **PLUGIN-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **PLUGIN-02** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **CKAN-01** — preserve. Present; opt-in integration. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **CKAN-02** — preserve. Present; publishing changes task visibility. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-01** — preserve. Present; infrastructure dependent. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-02** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-03** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-04** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-05** — preserve. Present; supersedes Actor invocation. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-06** — preserve. Present; completion inference limited. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **EMBED-07** — defer completion; preserve existing scaffolding. Scaffolding/stubs; not completed features. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **OPS-01** — preserve. Present; site-specific scripts. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **OPS-02** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **OPS-03** — preserve. Present scripts; deployment state unverified. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **OPS-04** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **BUILD-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **BUILD-02** — preserve. Present; version-specific adaptations. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DEV-01** — preserve. Present; local-only. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **DEV-02** — preserve. Present tooling/history changes. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **UPGRADE-01** — preserve. Present; earlier milestone. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **OPS-05** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **UI-01** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.
- **UI-02** — preserve. Present. Evidence: pending; use inventory source paths and entry-specific upgrade checks.

## Files likely affected

The upstream path manifest and overlap manifest govern scope: app models/APIs/migrations/frontend/viewers, nodeodm adapter/models/migrations, worker initialization, settings, dependencies/lockfiles, build scripts, documentation and gitlinks. Preserve fork-only auth, allocations, plugins and operational code. No backend repositories, production configuration or services are changed.

## API/schema changes

Integrate upstream media, OIDC-subject and basemap additions while retaining custom routes/fields. Check new media write actions for authentication, ownership and allocation permissions; preserve intended public reads.

Append upstream app migrations in order after custom 0050_task_wkt: upstream 0048_task_media becomes 0051_task_media; 0049 oidc_sub becomes 0052; 0050 basemap becomes 0053; 0051 initbasemaps becomes 0054; 0052 gridshift becomes 0055; 0053 update_plugins becomes 0056. Inspect exact suffixes and rewrite dependencies/references consistently. Preserve all old migration bytes. Retain pyodm for their historical imports instead of upstream import rewrites.

Gridshift downloads grids and changes existing extents; update_plugins fetches, unzips and installs plugins. Do not execute either. Review the new nodeodm 0010 default-node rename and its live-model use; use safe historical-model handling in that new migration if required, without rewriting existing history.

## Data flow

Browser → WebODM authentication/permissions → task/project/media APIs → consumer adapter → established ClusterODX/NodeODX backend. Preserve Tapis identity/token boundaries, shared Corral paths, polling and assets. Plugin transports are mocked for validation; no CKAN, Label Studio, Tapis or embedding-service writes occur.

## Risks and tradeoffs

Clean textual merges may still lose behavior across the 50 overlapping paths, requiring per-ID assertions. Retained pyodm and new pyodx may constrain dependency resolution. Historical imports limit dependency removal. New media APIs expand the permission surface. Locale availability can block reproducible builds. Gridshift and plugin migrations perform network/filesystem/data work that source and mocked tests cannot certify. Existing OAuth and partial-feature limitations remain documented rather than described as resolved.

## Alternatives considered

The parent design rejects blind merging because authentication, shared paths and migration identities must survive. Wholesale upstream checkout has the same preservation failure. A version-only bump does not integrate the release. Per-file reconciliation retains fork-only behavior and incorporates upstream-only changes with explicit overlap review. Backend upgrade work is excluded by the user’s scope correction.

## Test plan

- Record baseline/target/overlay checksums and path manifests; verify historical migration bytes and fork-only dispositions. Check syntax and conflict markers.
- Check migration graph dependencies without database access or application-boot side effects; assert renamed references resolve and historical imports remain available. Do not run migrate or RunPython operations.
- Run targeted Jest mocks for folder uploads, categorical options/presets, maps/viewers and plugin hooks. The existing qtest script invokes Jest directly; npm test first invokes Django mock generation and is not automatically database-free.
- Run targeted Python adapter/plugin tests with mocked transports/settings/storage: expiry/redaction, shared import_path, task status/restart/assets, allocation protection on media writes/public reads, CKAN visibility and embedding polling. No external calls or jobs.
- Build if available dependencies or existing local/test WebODM images support it. Docker is running; host Django is unavailable. Record exact commands/results and skipped checks. Parsing/mocks do not establish runtime acceptance.
- Leave connected OAuth, real shared storage, browser asset rendering, migration execution, Tapis canaries and production validation pending separate runtime authorization.

## Documentation plan

Maintain this addendum and per-ID implementation/evidence records without rewriting inventory historical claims. Update local usage/dependency notes only for verified changes. Record unavailable DSO docs rather than inventing URLs, ports or deployment details. Corresponding architecture documentation must be updated for verified endpoint/env/startup/integration changes before later production closure.

## Rollout/rollback plan

This slice produces isolated local source and evidence. Keep the original checkout and baseline as source rollback references. Stop on unresolved preservation failures, dependencies or pins. Roll back only isolated implementation changes while preserving user work and evidence. No database rollback is claimed: source rollback after migrations may be insufficient. A future deployment needs a separately reviewed backup, migration side-effect, plugin-install and runtime rollback plan. No pushes, deployment, database mutation, destructive cleanup or external writes are authorized here.

## Open questions

- Can the exact release locale and full NodeODX gitlinks be fetched reproducibly?
- Can pyodx and retained pyodm satisfy dependency constraints with custom JWT/database pins?
- Which inventory runtime checks remain pending after local tests?
- What runtime safeguards will cover downloaded grids, changed extents and plugin installation? These are later execution gates, not reasons to block authorized source reconciliation.

## Decisions

### 2026-10-27 — WebODM-only preservation reconciliation

- **Decision:** Pin v3.3.1; use isolated per-file reconciliation and all 47 IDs.
- **Reason:** Inventory and overlap evidence expose custom behavior that wholesale replacement would lose.
- **Alternatives rejected:** Blind merge, wholesale checkout and version-only bump.
- **User feedback:** “Perfect. lets update it”; subsequent “Continue”; explicit correction that backend implementation is already done.
- **Impact on implementation:** WebODM source only. This supersedes the parent’s WebODM 3.3.0 target for this slice; backend work and runtime/external mutations remain excluded.

### 2026-10-27 — Preserve migration history and dirty security work

- **Decision:** Keep historical migration bytes, append remapped migrations, retain required historical imports, and copy only the explicit security overlay.
- **Reason:** Existing database identities and user work must remain intact.
- **Alternatives rejected:** Renumbering old custom migrations, rewriting old imports, dropping dirty security changes.
- **User feedback:** Parent preservation constraints and current continuation authorization.
- **Impact on implementation:** Checksums, graph/dependency checks and redaction tests are required; migration execution remains gated.

## User feedback / decisions

The parent design remains Implementing and provides the broader historical reference. The user accepted the inventory, authorized updating WebODM, clarified that ODX/NodeODX/ClusterODX are already implemented, and instructed continuation. This addendum is Implementing after direct document, architecture, and security review. It records existing local source authorization without claiming authorization for deployment, external writes or database mutation. No unconfirmed end-user assumptions are introduced.

### 2026-10-27 — Direct review and implementation start

- **Decision:** Proceed with the authorized isolated WebODM source integration following direct document/architecture/security review; the independent design-review agent could not execute because of a usage limit. No independent review is claimed.
- **Reason:** Scope, provenance, preservation rules, migration mapping and no-write test boundaries are concrete. Architecture review requires retaining fork-only paths and manually resolving shared task/viewer routes. Security review requires preserving Tapis-only login/expiry/allocation gates and credential redaction, with new upload endpoints checked for the same gate.
- **Alternatives rejected:** Blocking all local work on reviewer availability; accepting a clean textual merge as proof of behavior.
- **User feedback:** User explicitly excluded backend upgrade work and again instructed “continue.”
- **Impact on implementation:** Resolve all conflicts deliberately, preserve historical migration checksums, retain legacy bundled plugins, and record any test/build gaps before claiming completion. Database execution and deployment remain excluded.

### 2026-10-27 — Local source reconciliation and validation result

- **Decision:** Complete the local source slice at the pinned v3.3.1 release; retain separate container/database/connected-runtime gates.
- **Reason:** Production webpack passed, 56 frontend suites/71 tests passed, 11 offline backend tests passed, all 63 historical migrations are byte-identical, and all 47 IDs have source dispositions in [the evidence report](../upgrade/2026-10-27-webodm-3.3.1-reconciliation.md). Docker Desktop is manually paused, preventing the full image/backend run.
- **Alternatives rejected:** Claiming deployment readiness from source tests; silently running migrations or changing the established backend.
- **User feedback:** Existing local upgrade authorization and explicit WebODM-only scope.
- **Impact on implementation:** Six new app migrations mapped to 0051–0056; new node rename migration uses the historical model. Ten moved plugin bundles remain available. Both custom Model and upstream ModelView hooks coexist. Range handling preserves suffix requests while adopting bounded closeable streams and416 responses. The release UTC timezone default replaces the old tzlocal-version fallback; the custom Django/psycopg2 UTC adaptation remains. Pinned locale content is included in the Docker build context. New external-import/media/splat upload endpoints retain allocation restrictions. No historical migration, original dirty file, or backend checkout was changed.
- **Remaining validation:** Clean dependency resolution/image build, full Django model/URL/backend checks, restored-copy migration execution, public/private browser workflows and real service integration acceptance. These gaps are not waived.

### 2026-10-27 — Container validation and default-field reconciliation

- **Decision:** Append `0057_setting_organization_website` for the upstream default URL change, preserving all historical migration files. Continue to gate migration execution separately.
- **Reason:** The real Django autodetector found one AlterField absent from upstream migration history; after the additive reconciliation migration it reports no drift and no graph conflicts.
- **Alternatives rejected:** Editing applied historical migrations; ignoring autodetector drift; running migrations on existing data.
- **User feedback:** User unpaused Docker and instructed continuation.
- **Impact on implementation:** App leaf is now0057. Thirty-five focused tests pass in the existing Linux test image with read-only source and no network/database. Model and mocked URL checks pass. The clean image build was attempted but Docker VM storage is full; it remains unvalidated until storage is available. No cleanup was performed because repository rules require explicit approval for destructive actions.

### 2026-10-27 — Approved unused build-cache cleanup

- **Decision:** Run `docker builder prune --force` to clear unused Docker build cache and retry the local image build.
- **Reason:** Docker’s VM disk was full; cache cleanup reclaimed7.188GB.
- **Alternatives rejected:** Removing images, containers or volumes; none were authorized or removed explicitly.
- **User feedback:** User said “yes clean it” in response to the scoped cache-cleanup request.
- **Impact on implementation:** Local image build restarted. Database migrations and deployment remain excluded.

### 2026-10-27 — Clean image build and container verification completed

- **Decision:** Pin the existing build-tool installation to wheel0.43.0, then rebuild and verify the final app image.
- **Reason:** Fresh wheel0.48 conflicts with the existing packaging16.8 requirement. The compatible pin passes `pip check` without changing application dependency requirements.
- **Alternatives rejected:** Ignoring a broken dependency check or upgrading the legacy packaging pin without compatibility review.
- **User feedback:** Existing local upgrade/testing authorization after approved cache cleanup.
- **Impact on implementation:** Image `webodm-upgrade-3.3.1:local` at `sha256:20bfd0e6c8174b46c45826e26b4a39c4a7f1db40d0b7cd6045f8cb3496176695` builds successfully. In that final image: dependency check passes;35 focused backend tests and56 frontend suites/71 tests pass; model/URL checks, graph conflicts and model-state drift are clear. No migrations, deployment or live external writes occurred. Full database-backed and connected-runtime acceptance remain separate gates.

### 2026-10-27 — Approve commit and branch push

- **Decision:** Commit the isolated WebODM upgrade and push `upgrade/webodm-3.3.1-tapis` to `In-For-Disaster-Analytics/WebODM`.
- **Reason:** User requested saving and publishing the validated local source work.
- **Alternatives rejected:** Changing master, pushing unrelated original-checkout edits, or deploying the image.
- **User feedback:** “Ok lets commit and push.”
- **Impact on implementation:** Git commit/push is authorized for the upgrade branch. Database migrations, deployment and live service writes remain outside this action.

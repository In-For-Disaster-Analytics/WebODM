# WebODM fork customization inventory

Prepared: 2026-10-27. Purpose: a traceable preservation checklist for upgrading the existing custom fork to the current WebODM/ODX ecosystem.

## Scope and evidence

- Repository: `WebODM/`, origin `In-For-Disaster-Analytics/WebODM`.
- Recorded branch: `upgrade/webodm-upstream-3.1.2`; committed baseline `8fe74e8b5bd7353982c3b142d5f208ef424a1501`.
- Comparison reference: locally cached `upstream/master` = `a4501835a0544c1bcb3acca61e376e9e3a6a4b0b` (the old OpenDroneMap-era upstream). **No fetch was performed**; this inventory does not claim to compare against the latest WebODM release.
- Earlier fork/upstream merge base: `75179368c16d605e6653087176c5ae273384e1c5`. The selected range `upstream/master..HEAD` contains **225 commits: 213 non-merge commits and 12 merges**. This includes the initial September 2025 integration through October 2026 reconciliation, across reachable branches rather than just first-parent history.
- **47 inventory entries** group related changes; commit count is not feature count. Baseline WebODM functionality is excluded unless the fork changed its behavior. The appendix includes every commit in the selected range and every path with a net difference from the cached upstream.
- Evidence comes from commit subjects/bodies, selected patch inspection, current source inspection, existing design specs and read-only `.wolf` context. “Present” means code exists at the recorded baseline, **not** freshly runtime-tested or confirmed deployed. Rationale is explicit where attributed to commits/decisions; otherwise it is inferred from implementation and named behavior. Minor iteration commits are grouped, not individually promoted to features.
- The committed baseline governs this inventory. Existing uncommitted `nodeodm/jwt_node_wrapper.py`, its new `url_security.py` and security tests, and the edited prior reconciliation spec are **excluded from committed feature claims**. `.ckg/` is untracked project tooling. Existing edits were not modified.
- The configured DSO architecture documentation root `/Volumes/Macintosh HD - Data/Github/DSO-Architecture/docs/` was unavailable here. No deployment URLs/ports were selected for new work, and no architecture documentation was changed.
- This is documentation and an upgrade checklist, not approval of upgrade implementation, schema migrations, deployment, or external writes. No credentials, certificate bodies, cookie contents or environment values were copied into the inventory.

## How to use during the upgrade

For each entry, record the new implementation location, relevant test evidence and one disposition: **preserve**, **replace with upstream equivalent**, **retire with approval**, or **defer**. All decisions are initially **unreviewed**. Use the stable IDs in upgrade specs, PRs and test plans. Partial/stub/removed entries are explicitly labeled to prevent them becoming false claims of working functionality.

Upgrade acceptance checklist, for every retained entry:

- [ ] Choose and record a disposition against the new upstream.
- [ ] Identify the implementation/API/schema equivalent.
- [ ] Run the entry-specific checks against representative data.
- [ ] Record evidence and resolve any regression before rollout.

Commit evidence links point to your fork; locally reachable commits might not be published. Use `git show <hash>` if a link is unavailable. Source paths below are relative to the WebODM repository and link to the current checkout, which may later change; the recorded commit identifies the historical baseline.

## Customization catalog

Navigation (stable IDs):

- [AUTH-01 — Tapis OAuth2 login and WebODM user provisioning](#auth-01)
- [AUTH-02 — Token normalization, expiration, warning, and reauthentication](#auth-02)
- [AUTH-03 — JWT-aware processing-node API adapter](#auth-03)
- [NODE-01 — Cluster node registration, HTTPS, metadata, and visibility](#node-01)
- [NODE-02 — Authenticated cluster admin shortcut](#node-02)
- [DATA-01 — Tapis flight discovery and project creation](#data-01)
- [DATA-02 — Discovery preferences and background task support](#data-02)
- [DATA-03 — Server-side file/directory import browser](#data-03)
- [DATA-04 — Shared-filesystem submission to processing nodes](#data-04)
- [DATA-05 — Browser folder upload and chained folder selection](#data-05)
- [DATA-06 — Large-image limits and temporary-directory resilience](#data-06)
- [HPC-01 — TAS allocation lookup and processing controls](#hpc-01)
- [HPC-02 — Allocation-based access control and caching](#hpc-02)
- [HPC-03 — Cluster-aware categorical processing options](#hpc-03)
- [HPC-04 — Customized default and LS6 Small processing presets](#hpc-04)
- [TASK-01 — Offline/missing-task restart fallback](#task-01)
- [TASK-02 — Duplicate submission guard](#task-02)
- [TASK-03 — Celery initialization and task discovery restructuring](#task-03)
- [MAP-01 — Interactive distance measurement](#map-01)
- [MAP-02 — Temporary WMS and XYZ tile overlays](#map-02)
- [MAP-03 — Raster tile/metadata caching and CPU-load reductions](#map-03)
- [VIEW-01 — EPT-first point-cloud loading with legacy fallback](#view-01)
- [VIEW-02 — HTTP byte-range asset responses](#view-02)
- [VIEW-03 — Potree v2 experiment and subsequent removal](#view-03)
- [PLUGIN-01 — Upstream sensor connections and 2D overlays](#plugin-01)
- [PLUGIN-02 — Upstream sensor overlay in the 3D viewer](#plugin-02)
- [CKAN-01 — Agent-assisted dataset metadata and publishing conversation](#ckan-01)
- [CKAN-02 — Published resource links, visibility, and republish tracking](#ckan-02)
- [EMBED-01 — Admin-only embeddings panel and site/visit storage](#embed-01)
- [EMBED-02 — Real tile candidates and map-based sample selection](#embed-02)
- [EMBED-03 — Inline label painting, class creation, and eraser](#embed-03)
- [EMBED-04 — Label Studio authentication and annotation webhooks](#embed-04)
- [EMBED-05 — LS6 embedding generation jobs](#embed-05)
- [EMBED-06 — Embedding job polling and Continue workflow](#embed-06)
- [EMBED-07 — Embeddings workspace, diagnostics, STAC, GeoJSON import and training](#embed-07)
- [OPS-01 — Tapis/Corral deployment bootstrap and configuration](#ops-01)
- [OPS-02 — Corral service-account ownership and group inheritance](#ops-02)
- [OPS-03 — Corral-safe backups, opt-in scheduling, and operator control](#ops-03)
- [OPS-04 — Nginx logging, compression, worker and status tuning](#ops-04)
- [BUILD-01 — Custom source builds and update behavior](#build-01)
- [BUILD-02 — Database/runtime dependency compatibility](#build-02)
- [DEV-01 — Isolated local connected stack and restart smoke harness](#dev-01)
- [DEV-02 — Project intelligence and fork CI workflow removals](#dev-02)
- [UPGRADE-01 — Prior 3.1.2-era upstream reconciliation and migration preservation](#upgrade-01)
- [OPS-05 — Restore missing application logo after media loss](#ops-05)
- [UI-01 — Theme color normalization and invalid-value handling](#ui-01)
- [UI-02 — Processing UUID visibility and console diagnostics](#ui-02)

<a id="auth-01"></a>

### AUTH-01 — Tapis OAuth2 login and WebODM user provisioning

- **State:** Present; signature-validation limitation.
- **What it does:** Replaces the ordinary interactive login experience with Tapis authorization, callback handling, and creation/update of the corresponding WebODM user.
- **Why:** Use TACC identities for access to WebODM and downstream Tapis resources (initial commit explicitly describes Tapis-only authentication).
- **How:** TapisOAuth2Backend, OAuth client/token/state models, authorization and callback views, login templates, admin registration, context processors, and environment-driven client bootstrap. The backend currently decodes JWT claims locally; its name/docstring must not be read as proof of cryptographic signature verification.
- **Commit evidence:** [`7ae29a4a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44), [`7d9fb7c0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7d9fb7c0d0ddf914d9d3e4d1e4f3389372534112), [`52e53e6a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/52e53e6a35309ba80899e438dbe63c77ac9b91d6), [`073037da`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/073037da48f11d3f7ffe26d1cd891e47a716cb14), [`4dbc16cc`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4dbc16cc095aafb612822f69a8ad2f250ba9b248).
- **Source:** [app/auth/tapis_oauth2.py](../../app/auth/tapis_oauth2.py), [app/api/tapis_oauth2.py](../../app/api/tapis_oauth2.py), [app/models/oauth2.py](../../app/models/oauth2.py), [app/views/tapis_auth.py](../../app/views/tapis_auth.py), [app/admin.py](../../app/admin.py), [app/templates/app/registration/login.html](../../app/templates/app/registration/login.html).
- **Upgrade checks:** Preserve identity mapping, state/callback behavior, user permissions, client configuration, and login/logout redirects. Explicitly review JWT verification before choosing what to port.
- **Upgrade disposition:** Unreviewed.

<a id="auth-02"></a>

### AUTH-02 — Token normalization, expiration, warning, and reauthentication

- **State:** Present; replaces refresh behavior.
- **What it does:** Warns users before Tapis session expiry, logs them out at expiry, and rejects expired tokens in downstream operations.
- **Why:** Prevent requests from continuing with expired credentials and treat expiry as a fresh-login boundary (341bdf94).
- **How:** Token helpers normalize nested access-token payloads, compute effective expiration from stored metadata/JWT claims, and apply an expiry skew. TapisTokenManager checks every 30 seconds and warns within ten minutes. August changes removed the Tapis refresh API/call sites; the legacy refresh_token field remains.
- **Commit evidence:** [`95cb7148`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/95cb714899d2f2ee4f94fa36e665819b24875e23), [`9d56fdc1`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9d56fdc1b56408e6681ef1a0cbaaafd31416b008), [`341bdf94`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/341bdf9436c149d918465fca4733698ec25ac4b8), [`b060790e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b060790ef31a5f5a5396090764552b594b425288).
- **Source:** [app/models/oauth2.py](../../app/models/oauth2.py), [app/static/app/js/classes/TapisTokenManager.js](../../app/static/app/js/classes/TapisTokenManager.js), [app/contexts/tapis.py](../../app/contexts/tapis.py), [app/api/tapis_oauth2.py](../../app/api/tapis_oauth2.py), [app/tests/test_tapis_oauth2_tokens.py](../../app/tests/test_tapis_oauth2_tokens.py).
- **Upgrade checks:** Check warning, logout once, malformed/expired tokens, near-expiry background requests, and absence of silent Tapis refresh. Label Studio PAT exchange is a separate mechanism.
- **Upgrade disposition:** Unreviewed.

<a id="auth-03"></a>

### AUTH-03 — JWT-aware processing-node API adapter

- **State:** Present.
- **What it does:** Carries the task owner’s Tapis credential through processing submission, status/output polling, restart, cancel/remove, and result download.
- **Why:** Stock processing-node calls did not satisfy the custom ClusterODM authentication contract.
- **How:** JWTNodeWrapper wraps pyodm and supplies the JWT as the token query parameter, with node-token fallback. ProcessingNode methods accept jwt_token and Task resolves the owner’s current stored token. The wrapper handles response compatibility and auth errors.
- **Commit evidence:** [`3da2d9cc`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3da2d9ccdf9a343afef3a574528c15508e1c3fee), [`932d8390`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/932d83908d7623e5e6b55ad52902b0a481995f97), [`21b8acff`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/21b8acff0783e1ac5ce421417b4ab37ed4ca17b2), [`bd7ade13`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd7ade13e5df90b131159f82994d9e3f118a703f), [`c3574267`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c3574267b0ffb64361bb272ed3d482acbe83fbdf), [`bb8ec216`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bb8ec216c11451a434963d10f7b4431f56c1bd5b), [`60bec30e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/60bec30e10f964f32d577e97497dd190a7758725), [`a452fe1b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a452fe1b8c46f59dd67af15a73492ca0c8c1595c).
- **Source:** [nodeodm/jwt_node_wrapper.py](../../nodeodm/jwt_node_wrapper.py), [nodeodm/models.py](../../nodeodm/models.py), [app/models/task.py](../../app/models/task.py), [app/api/tasks.py](../../app/api/tasks.py).
- **Upgrade checks:** Exercise the entire lifecycle against ClusterODX, including output and ZIP retrieval. Do not assume NodeODX/ClusterODX accepts identical credential transport or response envelopes.
- **Upgrade disposition:** Unreviewed.

<a id="node-01"></a>

### NODE-01 — Cluster node registration, HTTPS, metadata, and visibility

- **State:** Present.
- **What it does:** Connects WebODM to the primary cluster and makes it visible to ordinary members of the Default group.
- **Why:** Resolve cluster connection, HTTPS, missing metadata, image-limit, and object-permission problems.
- **How:** Connection/setup helpers register the node; ProcessingNode tolerates missing cluster engine fields and unlimited image counts, handles unavailable options, and selects the wrapper on port 443. Boot and node-save hooks grant object visibility for the configured primary cluster.
- **Commit evidence:** [`a24ecf0f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a24ecf0fe336a9b669a5383143cefc796227ead5), [`1ab34c2f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1ab34c2fd7b4d6bb98d1f37612560925048e1582), [`91a7037b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/91a7037ba46b4152c370fab55f9037817894c68a), [`07320a10`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/07320a105c9651d87fb7699f1856b72cf2556fc4), [`f8360c26`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f8360c26314e891995d68390f5acfcee7a65ed30), [`dc486272`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dc486272510f33962d125ebd91b09f1c2ce9bfa7), [`f4ed596b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f4ed596bbbaebd7d4f3cb4e11995aebe789fddbf), [`f3fca5d1`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f3fca5d136aaf135459db28f15b6e2f77bea80d8).
- **Source:** [connect_clusterodm.sh](../../connect_clusterodm.sh), [debug_clusterodm.py](../../debug_clusterodm.py), [fix_clusterodm.py](../../fix_clusterodm.py), [nodeodm/models.py](../../nodeodm/models.py), [app/boot.py](../../app/boot.py).
- **Upgrade checks:** Verify non-admin users can select ClusterODX; compare /info and /options response shapes, engine names, image limits, and HTTPS handling.
- **Upgrade disposition:** Unreviewed.

<a id="node-02"></a>

### NODE-02 — Authenticated cluster admin shortcut

- **State:** Present; superuser only.
- **What it does:** Adds a WebODM shortcut into the cluster administration UI.
- **Why:** Allow administrators to reach cluster management using their existing Tapis session.
- **How:** A protected WebODM view retrieves and checks the stored token and renders the cluster redirect template; navbar integration uses CLUSTERODM_URL.
- **Commit evidence:** [`08e22243`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/08e2224325f0cc9caf251c8293502f1748bfce18), [`6b4fef20`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6b4fef20cef24c7432eb054057887232d1b20432).
- **Source:** [app/views/app.py](../../app/views/app.py), [app/templates/app/clusterodm_redirect.html](../../app/templates/app/clusterodm_redirect.html), [app/templates/app/logged_in_base.html](../../app/templates/app/logged_in_base.html), [app/tests/test_clusterodm_admin.py](../../app/tests/test_clusterodm_admin.py).
- **Upgrade checks:** Verify superuser-only access, token expiry, destination URL, and the ClusterODX admin authentication contract.
- **Upgrade disposition:** Unreviewed.

<a id="data-01"></a>

### DATA-01 — Tapis flight discovery and project creation

- **State:** Partial implementation.
- **What it does:** Discovers accessible ptdatax.project.* systems and flight image directories, then creates flight-tagged WebODM projects/tasks.
- **Why:** Reduce manual project setup for imagery already organized in Tapis storage.
- **How:** TapisStorageService searches Systems/Files APIs for <Flight>/code/images, constructs project metadata, and checks existing owner/tags to avoid duplicate projects. APIs and a management command expose discovery. The automatic _schedule_image_download method only logs a TODO; automatic end-to-end import is not established.
- **Commit evidence:** [`7ae29a4a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44), [`004d0134`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d).
- **Source:** [app/services/tapis_storage.py](../../app/services/tapis_storage.py), [app/api/tapis_storage.py](../../app/api/tapis_storage.py), [app/management/commands/discover_tapis_flights.py](../../app/management/commands/discover_tapis_flights.py).
- **Upgrade checks:** Validate real storage layout, API request/response compatibility, duplicate handling, task creation, and which image-download path is actually invoked. Do not mark discovery-to-processing as complete from project creation alone.
- **Upgrade disposition:** Unreviewed.

<a id="data-02"></a>

### DATA-02 — Discovery preferences and background task support

- **State:** Present configuration/task code; wiring needs validation.
- **What it does:** Stores per-user discovery preferences and exposes controls plus discovery/download/sync/cleanup Celery tasks.
- **Why:** Make discovery opt-in and limit repeated scans and project creation.
- **How:** TapisUserPreferences stores login discovery, limits, cooldown, notification preferences, and preferred systems. Callback code can enqueue discovery with synchronous fallback; preference/control APIs and Celery tasks supply the supporting operations. Persisted notification options do not prove notification delivery exists.
- **Commit evidence:** [`7ae29a4a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44), [`004d0134`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d).
- **Source:** [app/models/tapis_preferences.py](../../app/models/tapis_preferences.py), [app/api/tapis_preferences.py](../../app/api/tapis_preferences.py), [app/tasks/tapis_storage.py](../../app/tasks/tapis_storage.py), [app/api/tapis_oauth2.py](../../app/api/tapis_oauth2.py).
- **Upgrade checks:** Verify cooldown/limits/system filters at actual execution points, Celery registration and scheduling, manual synchronization, and whether each exposed preference has a working consumer.
- **Upgrade disposition:** Unreviewed.

<a id="data-03"></a>

### DATA-03 — Server-side file/directory import browser

- **State:** Present.
- **What it does:** Lets users browse server imports and import existing task assets or create a new unprocessed task from a directory of source images.
- **Why:** Use imagery already on server/Corral storage without sending it through the browser again.
- **How:** TaskAssetsImport normalizes relative paths under the configured imports root and uses path traversal checks. Source-image imports recurse, resolve duplicate basenames, hard-link or copy files, copy recognized GCP files, and create a partial task for later configuration. Asset directories can be zipped for the existing import flow.
- **Commit evidence:** [`4fe0d77c`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4fe0d77c7084c98c642823d9e707ee5e3958632d), [`c3d0ba83`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c3d0ba833d8febda00c024eafe5be70a706d9c30), [`44e74602`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/44e74602a2aea267e6b1d711c54a87b9f818927e), [`b060790e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b060790ef31a5f5a5396090764552b594b425288).
- **Source:** [app/api/tasks.py](../../app/api/tasks.py), [app/static/app/js/components/ImportTaskPanel.jsx](../../app/static/app/js/components/ImportTaskPanel.jsx), [app/models/task.py](../../app/models/task.py), [app/tests/test_api_task_import.py](../../app/tests/test_api_task_import.py).
- **Upgrade checks:** Check permissions, root confinement, image versus result import, duplicate names, nested folders, GCP handling, and later commit/processing of the partial task.
- **Upgrade disposition:** Unreviewed.

<a id="data-04"></a>

### DATA-04 — Shared-filesystem submission to processing nodes

- **State:** Present; requires shared storage.
- **What it does:** Submits the task directory as import_path instead of uploading individual image bodies to the cluster.
- **Why:** Avoid redundant transfer of large image collections already accessible from the processing environment.
- **How:** When WO_SHARED_VOLUME_ROOT is configured, Task passes its directory, ProcessingNode maps MEDIA_ROOT-relative paths into the shared root, and JWTNodeWrapper calls the path-based creation API. This is distinct from both the server import picker and browser folder upload.
- **Commit evidence:** [`b6449eb4`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b6449eb4baf406859f7c7307a1a6bb67ba3075a5), [`24fa4bd3`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/24fa4bd3c54b6bea7614c62d04df4b387db98aec), [`50ee93df`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/50ee93dff0861a32762c52ef13f0e0f6df5d3b9a).
- **Source:** [app/models/task.py](../../app/models/task.py), [nodeodm/models.py](../../nodeodm/models.py), [nodeodm/jwt_node_wrapper.py](../../nodeodm/jwt_node_wrapper.py), [webodm/settings.py](../../webodm/settings.py).
- **Upgrade checks:** Verify container-to-Corral path mapping and ClusterODX import_path support, missing directories, root confinement, and multipart submission with shared mode disabled. Code fallback paths are not proof every fallback succeeds.
- **Upgrade disposition:** Unreviewed.

<a id="data-05"></a>

### DATA-05 — Browser folder upload and chained folder selection

- **State:** Present.
- **What it does:** Adds directory selection alongside file selection; successive picker invocations allow several directories to be added.
- **Why:** Make large flight uploads easier while retaining the ordinary upload pipeline.
- **How:** A webkitdirectory input filters accepted files and feeds Dropzone’s existing addFile/addedfiles events. The picker reopens after a successful selection; Cancel ends the chain.
- **Commit evidence:** [`41509ceb`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/41509cebe442ff8e4bddb0773ee0af9cf0f8dd3e), [`fdad2f69`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fdad2f698523003ced05222e70f24b9dc7be81dd).
- **Source:** [app/static/app/js/components/ProjectListItem.jsx](../../app/static/app/js/components/ProjectListItem.jsx), [app/static/app/js/components/tests/ProjectListItem.directoryUpload.test.jsx](../../app/static/app/js/components/tests/ProjectListItem.directoryUpload.test.jsx).
- **Upgrade checks:** Check supported browsers, Cancel, unsupported files, duplicate names, GCP files, progress, and chunked uploads.
- **Upgrade disposition:** Unreviewed.

<a id="data-06"></a>

### DATA-06 — Large-image limits and temporary-directory resilience

- **State:** Present.
- **What it does:** Raises Django upload memory thresholds and creates task/upload temporary directories before file operations.
- **Why:** Support drone imagery and avoid failures after fresh media mounts or missing temporary directories.
- **How:** Settings raise FILE_UPLOAD_MAX_MEMORY_SIZE and DATA_UPLOAD_MAX_MEMORY_SIZE to 100 MB; task file operations ensure relevant directories exist. These are request/memory thresholds, not a documented unlimited-upload guarantee.
- **Commit evidence:** [`7ae29a4a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44), [`a7009c67`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a7009c67e78576691152822509cc19b8cec85019).
- **Source:** [webodm/settings.py](../../webodm/settings.py), [app/models/task.py](../../app/models/task.py), [app/api/tasks.py](../../app/api/tasks.py).
- **Upgrade checks:** Verify large and chunked image/GCP uploads after a clean mount, permissions, and new upstream upload-limit behavior.
- **Upgrade disposition:** Unreviewed.

<a id="hpc-01"></a>

### HPC-01 — TAS allocation lookup and processing controls

- **State:** Present.
- **What it does:** Lists active allocations for the current user and provides allocation, runtime, node-count, and queue inputs in task configuration.
- **Why:** Submit TACC workloads with valid accounting information and appropriate resources.
- **How:** A TAS service-account client filters active projects/resources, deduplicates charge codes, chooses a default, and exposes a user API. EditTaskForm loads allocations and inserts the scheduling options; Compose propagates TAS configuration to application services.
- **Commit evidence:** [`7ff6e4c8`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ff6e4c8cb8fbbe90a403eddcfe9746786888d0a), [`40c6f4de`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40c6f4def0be886ab35da15f538a8e6f708de22b), [`f6929fc0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f6929fc03a0b89e032edba9142b7b22756fc6634).
- **Source:** [app/services/tas_allocations.py](../../app/services/tas_allocations.py), [app/api/tas_allocations.py](../../app/api/tas_allocations.py), [app/static/app/js/components/EditTaskForm.jsx](../../app/static/app/js/components/EditTaskForm.jsx), [docker-compose.yml](../../docker-compose.yml), [app/tests/test_tas_allocations.py](../../app/tests/test_tas_allocations.py).
- **Upgrade checks:** Verify user-to-TAS mapping, active allocations, API failures, selected charge code, and option names accepted by the new cluster/LS6 path.
- **Upgrade disposition:** Unreviewed.

<a id="hpc-02"></a>

### HPC-02 — Allocation-based access control and caching

- **State:** Present; configuration dependent.
- **What it does:** Restricts selected project/task write operations to users with an approved active allocation.
- **Why:** Prevent unauthorized uploads and job submissions without repeatedly querying TAS for each chunk.
- **How:** HasRequiredAllocation applies to project creation and task create/upload/commit. An empty required-allocation list disables the gate; superusers bypass it. Enabled checks fail closed on configuration/service errors. Charge-code results are cached, with a configurable lifetime defaulting to the WebODM JWT lifetime.
- **Commit evidence:** [`9a1948b4`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9a1948b49a2da6dec0a462a8f5c14ff95357251c), [`1ba6a303`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1ba6a3033e264227045dc1e0dda599609dd6e553).
- **Source:** [app/api/permissions.py](../../app/api/permissions.py), [app/api/projects.py](../../app/api/projects.py), [app/api/tasks.py](../../app/api/tasks.py), [app/services/tas_allocations.py](../../app/services/tas_allocations.py), [webodm/settings.py](../../webodm/settings.py).
- **Upgrade checks:** Check allowed/denied users, expired/revoked allocations, outage behavior, superuser bypass, and actual action coverage; current guard placement is not proof every write endpoint is covered.
- **Upgrade disposition:** Unreviewed.

<a id="hpc-03"></a>

### HPC-03 — Cluster-aware categorical processing options

- **State:** Present.
- **What it does:** Renders categorical processing options and cluster destinations as selectable values instead of unsuitable free-text controls.
- **Why:** Handle cluster option metadata and stringified enum domains consistently.
- **How:** PresetUtils normalizes known categorical domains, parses serialized lists, preserves current values, and injects discovered cluster URLs; preset/task forms pass cluster-node information.
- **Commit evidence:** [`757e2e18`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/757e2e18a53943dd71d81d62b02de493e4e8e47b).
- **Source:** [app/static/app/js/classes/PresetUtils.js](../../app/static/app/js/classes/PresetUtils.js), [app/static/app/js/components/EditTaskForm.jsx](../../app/static/app/js/components/EditTaskForm.jsx), [app/static/app/js/components/EditPresetDialog.jsx](../../app/static/app/js/components/EditPresetDialog.jsx), [app/static/app/js/components/ProcessingNodeOption.jsx](../../app/static/app/js/components/ProcessingNodeOption.jsx).
- **Upgrade checks:** Compare new ODX option domains and stage names; preserve unknown existing values and verify cluster URL selection.
- **Upgrade disposition:** Unreviewed.

<a id="hpc-04"></a>

### HPC-04 — Customized default and LS6 Small processing presets

- **State:** Present; legacy cluster values.
- **What it does:** Provides tuned default processing and an LS6 Small preset with scheduling/allocation settings.
- **Why:** Offer repeatable processing profiles for the deployed HPC environment.
- **How:** Boot creates/updates system presets with DSM/DTM/classification, quality/resolution, split/merge, concurrency, cluster URL, allocation, runtime, node-count, and queue settings. Default uses three nodes/normal; LS6 Small uses one node/vm-small.
- **Commit evidence:** [`c9425af8`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c9425af8fc1b79aa87242e3f39d8f2fcb340429d).
- **Source:** [app/boot.py](../../app/boot.py).
- **Upgrade checks:** Review every option against ODX, especially sm-cluster, split/merge, queue, concurrency, hard-coded destination/allocation, and bootstrap overwrite behavior.
- **Upgrade disposition:** Unreviewed.

<a id="task-01"></a>

### TASK-01 — Offline/missing-task restart fallback

- **State:** Present.
- **What it does:** Attempts restart with the existing task UUID and falls back to creating a replacement when restart fails, while treating expired authentication separately.
- **Why:** Recover tasks whose processing node or retained remote task is unavailable.
- **How:** Task.process restart handling passes the owner JWT, separates authentication expiry from other failures, and sets the reprocessing path when necessary. The main Restart button now passes rerunFrom=null, requesting restart from the beginning; explicit stage choices remain in its submenu (2805c9cd).
- **Commit evidence:** [`4b8da204`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4b8da2043876e24674e9b8e6379bf78af274f686), [`2805c9cd`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2805c9cda52fc288dd0241f825fed4af5ae63e5e).
- **Source:** [app/models/task.py](../../app/models/task.py), [local-dev/restart-nodeodm-smoke.py](../../local-dev/restart-nodeodm-smoke.py).
- **Upgrade checks:** Exercise restart on surviving, purged, offline, and expired-token tasks; distinguish resubmission from true checkpoint restoration in the external LS6 worker.
- **Upgrade disposition:** Unreviewed.

<a id="task-02"></a>

### TASK-02 — Duplicate submission guard

- **State:** Present; best-effort bounded lock.
- **What it does:** Reduces simultaneous duplicate processing submissions by different Celery workers.
- **Why:** Slow cluster requests could outlive the existing task lock and permit a second submission (commit rationale).
- **How:** A second Redis SET NX lock named task_submit_<id> surrounds task.process with a 120-second TTL and finally cleanup. Redis errors allow best-effort processing without the extra guard.
- **Commit evidence:** [`fa3927cb`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fa3927cb174c7354d0f2bffea63e21b458c8fd05).
- **Source:** [worker/tasks.py](../../worker/tasks.py).
- **Upgrade checks:** Check concurrent workers, submissions exceeding TTL, cleanup, and Redis outage behavior; this is not an exactly-once guarantee.
- **Upgrade disposition:** Unreviewed.

<a id="task-03"></a>

### TASK-03 — Celery initialization and task discovery restructuring

- **State:** Present.
- **What it does:** Moves the Celery application setup into the worker package and exposes a compatibility module.
- **Why:** Resolve initialization/import problems in background processing and support Tapis tasks.
- **How:** worker/__init__.py configures the app, result handling, schedules, autodiscovery, and explicit Tapis-task import fallback; worker/celery.py re-exports the app and mock result helper.
- **Commit evidence:** [`0bec2a11`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0bec2a111cf18d7745dee5c59b86a0e91a99d0de), [`2c6a09d1`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2c6a09d11515307dc20308bf122beac43c21fdbc), [`3ba7261b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3ba7261b835be4a3b30d4e2afeef739c2516fa7a), [`2ba7cb6d`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ba7cb6d8c6e104896b223cf6ccba1bd7bf158bd).
- **Source:** [worker/__init__.py](../../worker/__init__.py), [worker/celery.py](../../worker/celery.py), [app/tasks/tapis_storage.py](../../app/tasks/tapis_storage.py).
- **Upgrade checks:** Verify which Celery entry point actually loads schedules and all tasks, and prevent duplicate app/scheduler setup when reconciling upstream.
- **Upgrade disposition:** Unreviewed.

<a id="map-01"></a>

### MAP-01 — Interactive distance measurement

- **State:** Present.
- **What it does:** Adds a ruler workflow with multiple points, live distance, finish/cancel/clear controls, and a retained summary.
- **Why:** Measure distances directly on orthophoto/maps (intent inferred from implementation).
- **How:** Map.jsx manages a Leaflet measurement layer, click/double-click/Escape state, segment distances, and metric plus selected-unit display; Map.scss styles controls and labels.
- **Commit evidence:** [`06dbfadd`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/06dbfadd8bc1e36311d9be1293d0770e1c7a433a).
- **Source:** [app/static/app/js/components/Map.jsx](../../app/static/app/js/components/Map.jsx), [app/static/app/js/css/Map.scss](../../app/static/app/js/css/Map.scss).
- **Upgrade checks:** Check multi-segment measurements, units, zoom/pan interactions, double-click finish, Escape, clear, and read-only/public maps.
- **Upgrade disposition:** Unreviewed.

<a id="map-02"></a>

### MAP-02 — Temporary WMS and XYZ tile overlays

- **State:** Present; temporary layers.
- **What it does:** Lets users add external WMS or tile layers to a map and adjust their visibility/ordering controls.
- **Why:** Compare imagery with other map services without creating a permanent project integration.
- **How:** TemporaryMapLayerDialog validates layer settings; Map constructs Leaflet layers and LayersControlLayer supplies controls. A follow-up changes layer placement.
- **Commit evidence:** [`864caf55`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/864caf5540a4c271172ab2b14b5fcfe6953537e5), [`92a5407f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/92a5407f1dc7a43e7512e6e27a02cb1f6dc275b4).
- **Source:** [app/static/app/js/components/TemporaryMapLayerDialog.jsx](../../app/static/app/js/components/TemporaryMapLayerDialog.jsx), [app/static/app/js/components/Map.jsx](../../app/static/app/js/components/Map.jsx), [app/static/app/js/components/LayersControlLayer.jsx](../../app/static/app/js/components/LayersControlLayer.jsx).
- **Upgrade checks:** Check WMS parameters, XYZ URL templates, layer order, opacity/removal, external-service failures and CORS; do not assume persistence across reloads.
- **Upgrade disposition:** Unreviewed.

<a id="map-03"></a>

### MAP-03 — Raster tile/metadata caching and CPU-load reductions

- **State:** Present.
- **What it does:** Reuses expensive raster metadata/tile responses and reduces concurrent raster computation.
- **Why:** Address slow public-map requests from thread oversubscription, repeated rendering, and HiDPI tile amplification (commit bodies).
- **How:** Thread-pool caps are configured in Compose; imagery layers disable detectRetina. Tiler cache keys incorporate raster mtime, relevant query/output parameters and crop geometry, excluding random cache-busting input; TTL is seven days. Cache failures are treated as misses/skipped writes; follow-ups addressed unpicklable values.
- **Commit evidence:** [`be4214c3`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/be4214c3e3389056e75a3f54c1a4614e560c50a1), [`42663435`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/42663435ddf847065a537587fb2b2de4905e972d), [`dffcf1f6`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dffcf1f6bd2334bf1456851410d2ac0e11087286), [`3ee22ed9`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3ee22ed9a903a09a67780e39bb0e3f772eda7cc2), [`2ab89b75`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ab89b751e262443205161cfe5a8656a45255136).
- **Source:** [docker-compose.yml](../../docker-compose.yml), [app/static/app/js/components/Map.jsx](../../app/static/app/js/components/Map.jsx), [app/api/tiler.py](../../app/api/tiler.py).
- **Upgrade checks:** Verify cache invalidation after reprocessing/crop changes, variant separation, Redis failures, serialization, and concurrency under the upgraded raster stack.
- **Upgrade disposition:** Unreviewed.

<a id="view-01"></a>

### VIEW-01 — EPT-first point-cloud loading with legacy fallback

- **State:** Present.
- **What it does:** Loads entwine_pointcloud/ept.json when available and otherwise loads legacy potree_pointcloud/cloud.js.
- **Why:** Support streaming large point clouds while retaining access to older task outputs.
- **How:** ModelView.pointCloudSource probes EPT, loads it through Potree, and passes the loaded cloud onward; the legacy path loads later. Scene saving is guarded until a viewer exists. EPT support already existed in upstream; this entry describes the fork’s changed loading/control sequence.
- **Commit evidence:** [`0c279a46`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0c279a46d1b16aad035825b9224a51c40e7c4e33).
- **Source:** [app/static/app/js/ModelView.jsx](../../app/static/app/js/ModelView.jsx).
- **Upgrade checks:** Test EPT, legacy cloud.js, missing/corrupt clouds, scene save/restore, and the new upstream viewer implementation. Preserve behavior without blindly transplanting loader internals.
- **Upgrade disposition:** Unreviewed.

<a id="view-02"></a>

### VIEW-02 — HTTP byte-range asset responses

- **State:** Present.
- **What it does:** Serves requested portions of assets using HTTP 206 and range/content-length headers.
- **Why:** Originally introduced for Potree v2 streaming; the HTTP helper remained after that viewer experiment was removed.
- **How:** download_file_response parses start/end and suffix byte ranges and yields bounded chunks from the file.
- **Commit evidence:** [`c43adc87`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c43adc87c274e6a115151f8454ecaad12dfff003), [`73432709`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/73432709c0dc433286301945d950b5e6096a68d9).
- **Source:** [app/api/tasks.py](../../app/api/tasks.py).
- **Upgrade checks:** Check start/end/suffix and invalid/unsatisfiable ranges against upstream behavior, large assets, authorization, and resource cleanup; do not infer complete RFC compliance.
- **Upgrade disposition:** Unreviewed.

<a id="view-03"></a>

### VIEW-03 — Potree v2 experiment and subsequent removal

- **State:** Removed/superseded.
- **What it does:** History added metadata.json/Potree-v2 preference and then explicitly removed it.
- **Why:** Record an abandoned experiment so it is not mistakenly counted as a feature that must be restored.
- **How:** February viewer/template commits iterated on format loading; 73432709 removes v2 functionality. Current loader uses EPT and legacy cloud.js.
- **Commit evidence:** [`3e78d438`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3e78d4382880003f43c027dbe6da0b991156a810), [`9539781d`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/9539781ddb0c04317363328fad0f457aa22d8708), [`f5f4a322`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f5f4a32298b06a6a2d718c7991d15358e97d040e), [`e014d48e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e014d48e2001b8e5d9b1377d597a99cc853ddae9), [`c43adc87`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c43adc87c274e6a115151f8454ecaad12dfff003), [`ebc7b4c5`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ebc7b4c5d321c7b904bb4e79ba212426f37e47ea), [`73432709`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/73432709c0dc433286301945d950b5e6096a68d9).
- **Source:** [app/static/app/js/ModelView.jsx](../../app/static/app/js/ModelView.jsx), [app/templates/app/3d_model_js.html](../../app/templates/app/3d_model_js.html).
- **Upgrade checks:** Treat the latest upstream format/viewer choice as a new compatibility decision; retain old-output readability rather than reviving removed code by default.
- **Upgrade disposition:** Unreviewed.

<a id="plugin-01"></a>

### PLUGIN-01 — Upstream sensor connections and 2D overlays

- **State:** Present.
- **What it does:** Connects a WebODM project to an Upstream sensor service and displays campaign/station measurements alongside imagery.
- **Why:** Bring environmental sensor context into the imagery workflow.
- **How:** A coreplugin stores project connection settings in GlobalDataStore, probes a fixed list of known API stacks, proxies campaigns/stations/measurements using the user Tapis token, and renders map controls/overlays. Login guidance is supplied when no token is available. Discovery is not arbitrary enumeration of all Tapis Pods.
- **Commit evidence:** [`f0ba3a43`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f0ba3a4349b4b1d67afe30350c7d4bcecfec3c50), [`b318e6ec`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b318e6ecfee5766ed7c3d146d130b724f430b721).
- **Source:** [coreplugins/upstream/plugin.py](../../coreplugins/upstream/plugin.py), [coreplugins/upstream/api.py](../../coreplugins/upstream/api.py), [coreplugins/upstream/public/app.jsx](../../coreplugins/upstream/public/app.jsx).
- **Upgrade checks:** Verify project permissions, service selection/config persistence, login guidance, measurement rendering, and updated upstream plugin hooks.
- **Upgrade disposition:** Unreviewed.

<a id="plugin-02"></a>

### PLUGIN-02 — Upstream sensor overlay in the 3D viewer

- **State:** Present.
- **What it does:** Adds sensor context and time controls inside the point-cloud viewer.
- **Why:** Compare station measurements with the reconstructed site in three dimensions.
- **How:** A new Model plugin API hook fires when viewer controls can be added. The sensor plugin converts WGS84 positions into local model coordinates using georeferencing offsets and proj4, and supplies time/measurement display controls.
- **Commit evidence:** [`f0ba3a43`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f0ba3a4349b4b1d67afe30350c7d4bcecfec3c50), [`0c279a46`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0c279a46d1b16aad035825b9224a51c40e7c4e33).
- **Source:** [app/static/app/js/classes/plugins/Model.js](../../app/static/app/js/classes/plugins/Model.js), [app/static/app/js/classes/plugins/API.js](../../app/static/app/js/classes/plugins/API.js), [app/static/app/js/ModelView.jsx](../../app/static/app/js/ModelView.jsx), [coreplugins/upstream/public/model.jsx](../../coreplugins/upstream/public/model.jsx).
- **Upgrade checks:** Verify hook timing, coordinates, georeferencing asset paths, time selection and cleanup with the upgraded 3D viewer.
- **Upgrade disposition:** Unreviewed.

<a id="ckan-01"></a>

### CKAN-01 — Agent-assisted dataset metadata and publishing conversation

- **State:** Present; opt-in integration.
- **What it does:** Adds a task-level CKAN publishing panel that prepares metadata, starts a DSO agent conversation, accepts user edits, and requests confirmation.
- **Why:** Reduce manual catalog entry while retaining a user review step.
- **How:** The plugin derives title/notes/tags/temporal coverage/spatial metadata from task assets and user context, calls the DSO agent with the user Tapis credential, and stores conversation/publish state. Follow-ups repair timeouts, source URL instructions, phase messages and error reporting.
- **Commit evidence:** [`c0b20497`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c0b204974bb25e90f8c2bebbc7bad859e7d3eef6), [`4c34f581`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4c34f58146d45db07132d8ddb49ded19c9496fb5), [`f5bcdcae`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f5bcdcae5ffd0267f5e0ef4e8ca014a3dca03f43), [`688858a5`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/688858a564795c043b892211cf2e5834573f8376), [`7db3b4ee`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7db3b4ee8771dc460e28b37b9dea0b239393a761), [`7b68b3b2`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7b68b3b237779f4f4d689347e7220d66dafc1e4a), [`ff9c7478`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ff9c7478553d5178583f67147a4ef9be017e3a69), [`189facec`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/189facec4fbc905e7c329ff6cdc1f0662b0f5e4e), [`0b9a1325`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0b9a13259b298762913070dd1ff8222ee2236715).
- **Source:** [coreplugins/ckan/plugin.py](../../coreplugins/ckan/plugin.py), [coreplugins/ckan/api_views.py](../../coreplugins/ckan/api_views.py), [coreplugins/ckan/publisher.py](../../coreplugins/ckan/publisher.py), [coreplugins/ckan/public/CKANPublishPanel.jsx](../../coreplugins/ckan/public/CKANPublishPanel.jsx), [coreplugins/ckan/README.md](../../coreplugins/ckan/README.md).
- **Upgrade checks:** Check metadata accuracy, report URL access, agent contract, confirmation, timeouts/error recovery and configured enablement. Validate external publishing only under separate approval.
- **Upgrade disposition:** Unreviewed.

<a id="ckan-02"></a>

### CKAN-02 — Published resource links, visibility, and republish tracking

- **State:** Present; publishing changes task visibility.
- **What it does:** Publishes selected downloadable assets plus map/3D links and records the resulting CKAN dataset URL.
- **Why:** Make catalog resources reachable and permit subsequent publishing to reuse the correct organization.
- **How:** Resource generation uses the externally reachable/request-derived WebODM base URL and public viewer routes; publishing makes the task public. Task.ckan_url is stored through migration 0047 and exposed read-only. Plugin state retains owner_org and asynchronous apply/error status.
- **Commit evidence:** [`ca9fd1e4`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ca9fd1e4c8dda9428677cbe00f15c29c2ca83316), [`fc5b8a88`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/fc5b8a88ca3f1e2967926e366e9df3f0a1119d36), [`829d2bb5`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/829d2bb5d177836f3509940badb19d0e37203692), [`ff9c7478`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ff9c7478553d5178583f67147a4ef9be017e3a69), [`0122b947`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0122b947908b407ee281ac12103d766e0fdb6575).
- **Source:** [coreplugins/ckan/publisher.py](../../coreplugins/ckan/publisher.py), [coreplugins/ckan/api_views.py](../../coreplugins/ckan/api_views.py), [app/models/task.py](../../app/models/task.py), [app/api/tasks.py](../../app/api/tasks.py), [app/migrations/0047_task_ckan_url.py](../../app/migrations/0047_task_ckan_url.py), [app/tests/test_ckan_plugin.py](../../app/tests/test_ckan_plugin.py).
- **Upgrade checks:** Preserve explicit public-visibility behavior and review it with the user; check anonymous resource/viewer access, asset filtering, URL provenance, organization persistence and republish behavior.
- **Upgrade disposition:** Unreviewed.

<a id="embed-01"></a>

### EMBED-01 — Admin-only embeddings panel and site/visit storage

- **State:** Present; infrastructure dependent.
- **What it does:** Adds a task panel for generating embeddings and labeling tiles, with shared site/visit identifiers and label classes.
- **Why:** Organize imagery observations for repeat visits and supervised classification work.
- **How:** A coreplugin exposes task/site/class routes and a React panel, backed by a separate Postgres/PostGIS/pgvector database via psycopg2. API permission and task-button checks restrict current functionality to superusers; task imagery determines the highest-resolution zoom.
- **Commit evidence:** [`df9681a0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df9681a0a5d2039edbbaf855be8ebe120a042cde), [`40f18d48`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40f18d4858f02ab2934216a7313fe812b8820b54), [`1337cc7f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1337cc7f25dc3b5b593cf483fa359dcf007b1170), [`3f178647`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f17864758daa72209a619d750e0f46fb73d1d75), [`e105fb48`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e105fb483d5616557fc52f03a6ca123384077b67), [`ba561511`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba5615110e7b0c68e6589dd568a346781189bd60).
- **Source:** [coreplugins/embeddings/plugin.py](../../coreplugins/embeddings/plugin.py), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py), [coreplugins/embeddings/public/EmbeddingsPanel.jsx](../../coreplugins/embeddings/public/EmbeddingsPanel.jsx).
- **Upgrade checks:** Verify infrastructure enablement, admin restrictions, task/project permissions, existing site/visit reuse, zoom calculation, new-site naming, and separate database compatibility.
- **Upgrade disposition:** Unreviewed.

<a id="embed-02"></a>

### EMBED-02 — Real tile candidates and map-based sample selection

- **State:** Present.
- **What it does:** Lists imagery-backed tile candidates and lets users select sample tiles geographically.
- **Why:** Replace coordinate text entry/placeholders with usable imagery selection.
- **How:** TaskTilesView derives tile grids from raster bounds/zoom; Python/JavaScript tile math helpers and the panel map present selectable tiles linked to site/visit observations.
- **Commit evidence:** [`0e146bf9`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0e146bf97eb08b78fb1efd5ec715f90f53aac120), [`2ad37286`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/2ad372862dbcde0d5d3b036cd0dc5748d35a3bdc).
- **Source:** [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/tile_math.py](../../coreplugins/embeddings/tile_math.py), [coreplugins/embeddings/public/tileMath.js](../../coreplugins/embeddings/public/tileMath.js), [coreplugins/embeddings/public/EmbeddingsPanel.jsx](../../coreplugins/embeddings/public/EmbeddingsPanel.jsx).
- **Upgrade checks:** Check grid/bounds/zoom alignment, candidate imagery, coordinate conversions, selection persistence and large-site performance.
- **Upgrade disposition:** Unreviewed.

<a id="embed-03"></a>

### EMBED-03 — Inline label painting, class creation, and eraser

- **State:** Present.
- **What it does:** Allows labeling inside the task modal using a class palette and drag painting, plus adding classes and clearing mistaken labels.
- **Why:** Make sample labeling usable without repeatedly switching tools.
- **How:** Two panel tabs drive label apply/clear endpoints; backend code creates/reuses Label Studio projects/tasks and writes site-scoped labels/observations to embeddingsdb. Follow-ups add the class UI, task-name defaults and eraser.
- **Commit evidence:** [`c2935995`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c2935995ddf70f14038724602847f56d91add0eb), [`e105fb48`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e105fb483d5616557fc52f03a6ca123384077b67), [`ba561511`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba5615110e7b0c68e6589dd568a346781189bd60), [`f1cd738a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f1cd738a74c0e066fc2d312cf2d46224bfdb7abe).
- **Source:** [coreplugins/embeddings/public/EmbeddingsPanel.jsx](../../coreplugins/embeddings/public/EmbeddingsPanel.jsx), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py).
- **Upgrade checks:** Verify drag behavior, class scope, applying/clearing labels, site separation, errors and synchronization with existing Label Studio tasks.
- **Upgrade disposition:** Unreviewed.

<a id="embed-04"></a>

### EMBED-04 — Label Studio authentication and annotation webhooks

- **State:** Present.
- **What it does:** Creates Label Studio projects/tasks and imports submitted annotations back into embeddings labels.
- **Why:** Connect imagery selection with a real labeling service and correct the earlier credential mismatch.
- **How:** The server exchanges the Label Studio PAT for an access token, caches it and retries on 401. Webhook registration/receiver use a per-project HMAC-derived shared secret, throttling and task mappings; later code caps project titles to the service limit. These credentials are separate from Tapis login.
- **Commit evidence:** [`32763117`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3276311720ae92598db29d226529abec6943e448), [`0e146bf9`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/0e146bf97eb08b78fb1efd5ec715f90f53aac120), [`3f002ec7`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f002ec77815aace70538ca685c61d3b5af9172d), [`bd1f8974`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf).
- **Source:** [coreplugins/embeddings/label_studio_client.py](../../coreplugins/embeddings/label_studio_client.py), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py), [coreplugins/embeddings/tests.py](../../coreplugins/embeddings/tests.py).
- **Upgrade checks:** Check PAT exchange/expiry, title limits, server-side secret handling, webhook rejection/acceptance, project/task mappings, and annotation ingestion.
- **Upgrade disposition:** Unreviewed.

<a id="embed-05"></a>

### EMBED-05 — LS6 embedding generation jobs

- **State:** Present; supersedes Actor invocation.
- **What it does:** Queues embedding generation as a Tapis Job on LS6 using the logged-in user’s stored token.
- **Why:** The Actor worker pool could not provision the large generation image; moving to LS6 follows the working HPC execution pattern (recorded design decisions).
- **How:** apply_embed_generate builds a Tapis Job referencing the configured app/version and site/visit/encoder/task/tile context. Follow-ups base64-encode MSG, shorten job names to Tapis limits, and correct runtime/payload details. The companion execution code lives outside WebODM.
- **Commit evidence:** [`df6f09ff`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df6f09ffc929115b0e97c5122d670d8ba93ba749), [`d1ae3985`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d1ae3985640c8250503ce0a16e97784dc4374529), [`15a33275`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/15a33275bc176aaaf5a41b7907995d8fe0f752e8), [`652ebb81`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/652ebb81e0d2201d5c20586e500728665d3c24fe), [`e1b4f2f0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e1b4f2f08de2a01fd0ca977c7221231cae7b4a7a).
- **Source:** [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [webodm/settings.py](../../webodm/settings.py), [docs/design/2026-07-22-geospatial-embeddings-classification.md](../../docs/design/2026-07-22-geospatial-embeddings-classification.md).
- **Upgrade checks:** Verify job specification, current app/version, payload, allocation/runtime, imagery access and database writes across repositories. Do not restore the superseded embed-generate Actor path.
- **Upgrade disposition:** Unreviewed.

<a id="embed-06"></a>

### EMBED-06 — Embedding job polling and Continue workflow

- **State:** Present; completion inference limited.
- **What it does:** Polls the actual Tapis job and offers continuation after a stopped/incomplete run.
- **Why:** Avoid permanently displaying running after LS6 jobs finish or fail; user feedback explicitly preferred real job polling over timeout guesses.
- **How:** Submission stores job UUID by visit in GlobalDataStore. Status queries Tapis getJobStatus; activity timeout is fallback only when UUID/polling is unavailable. The panel stops polling and offers Continue for timed_out. A terminal FINISHED job is not proof every expected tile exists.
- **Commit evidence:** [`bd1f8974`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf).
- **Source:** [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/public/EmbeddingsPanel.jsx](../../coreplugins/embeddings/public/EmbeddingsPanel.jsx), [coreplugins/embeddings/tests.py](../../coreplugins/embeddings/tests.py).
- **Upgrade checks:** Test queued/running/terminal/error states, missing UUIDs, auth/network failures and safe resubmission. Cross-check companion job upsert/idempotency before claiming full continuation guarantees.
- **Upgrade disposition:** Unreviewed.

<a id="embed-07"></a>

### EMBED-07 — Embeddings workspace, diagnostics, STAC, GeoJSON import and training

- **State:** Scaffolding/stubs; not completed features.
- **What it does:** Registers workspace/diagnostics pages and several future-action routes, but does not implement the full classifier workflow.
- **Why:** Capture the intended extension points without treating the design document as proof of delivered functionality.
- **How:** workspace_index/model_diagnostics render placeholder shells. Publish/retract STAC and GeoJSON label import explicitly return not-implemented responses; queue_model_train raises NotImplementedError and lacks a workspace/train endpoint.
- **Commit evidence:** [`df9681a0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df9681a0a5d2039edbbaf855be8ebe120a042cde), [`40f18d48`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40f18d4858f02ab2934216a7313fe812b8820b54), [`df6f09ff`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/df6f09ffc929115b0e97c5122d670d8ba93ba749).
- **Source:** [coreplugins/embeddings/views.py](../../coreplugins/embeddings/views.py), [coreplugins/embeddings/templates/index.html](../../coreplugins/embeddings/templates/index.html), [coreplugins/embeddings/templates/model_diagnostics.html](../../coreplugins/embeddings/templates/model_diagnostics.html), [coreplugins/embeddings/api_views.py](../../coreplugins/embeddings/api_views.py), [coreplugins/embeddings/embeddings_client.py](../../coreplugins/embeddings/embeddings_client.py).
- **Upgrade checks:** Preserve or deliberately retire entry points; track unfinished work separately. Do not claim working STAC publishing, model training/inference, or diagnostics from route registration alone.
- **Upgrade disposition:** Unreviewed.

<a id="ops-01"></a>

### OPS-01 — Tapis/Corral deployment bootstrap and configuration

- **State:** Present; site-specific scripts.
- **What it does:** Automates deployment configuration for the custom Tapis, cluster and Corral environment.
- **Why:** Make the integrated deployment reproducible and reduce manual setup errors.
- **How:** setup.sh plus OAuth bootstrap/entrypoint scripts coordinate environment/configuration, mounts, accounts/permissions, reverse proxy/SSL setup, node connection and startup. Boot can upsert the OAuth client from configured environment values. Historical .env/certificate/cookie artifacts also exist and are not feature requirements.
- **Commit evidence:** [`ecd7c007`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ecd7c007d28f367c2ca2a3005aeda15d927501b8), [`6b5da3b1`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/6b5da3b1e6b2114a7bdcfe689d7983192b8dbd53), [`7e655e28`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7e655e280df8a6b9ad97ac6bfc7a3a450f2d523d), [`073037da`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/073037da48f11d3f7ffe26d1cd891e47a716cb14), [`28a44929`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/28a44929138715e0a6783dd2ac8a2a8b74f10966), [`4e07f88d`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4e07f88deb53e519779ae5570e23f574e9f27719), [`004d0134`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d).
- **Source:** [setup.sh](../../setup.sh), [setup_tapis_oauth2.py](../../setup_tapis_oauth2.py), [scripts/setup_tapis_oauth2.py](../../scripts/setup_tapis_oauth2.py), [scripts/entrypoint-tapis.sh](../../scripts/entrypoint-tapis.sh), [app/boot.py](../../app/boot.py), [docker-compose.yml](../../docker-compose.yml).
- **Upgrade checks:** Review scripts against current infrastructure docs before execution, preserve required configuration names/mounts, and avoid replaying historical secrets/certificates or running setup during inventory review.
- **Upgrade disposition:** Unreviewed.

<a id="ops-02"></a>

### OPS-02 — Corral service-account ownership and group inheritance

- **State:** Present.
- **What it does:** Runs media-writing application/worker processes as the configured service UID/GID and keeps shared files group writable.
- **Why:** Avoid nobody-owned files and permissions failures on root-squashed Corral NFS.
- **How:** gosu privilege drop uses WO_RUN_AS_USER, numeric UID:GID support, umask 002, setup ownership/group inheritance and throttled permission sweeps. Plugin build directories are made writable before dropping privileges. Nginx group membership is made persistent across worker forks.
- **Commit evidence:** [`d6252e13`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/d6252e13e24e2f46b7231dce37e8615223396954), [`5b370bc0`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b370bc029fdea454d7b2e770a28184f7b050fe5), [`bbe12add`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bbe12adda61b9db1791042ca334205c445f1a87a), [`5b7a2a13`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b7a2a13abd97c32c7a22f51e6b6ba2cf0c33a12), [`8e0a58e4`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8e0a58e46099114fd3fda1cc027d94822378b8d5).
- **Source:** [start.sh](../../start.sh), [worker.sh](../../worker.sh), [setup.sh](../../setup.sh), [Dockerfile](../../Dockerfile), [docker-compose.yml](../../docker-compose.yml).
- **Upgrade checks:** Verify ownership of uploads, task outputs, cache/logo and rebuilt plugins on the actual mount; check numeric group propagation and nginx reads after restart.
- **Upgrade disposition:** Unreviewed.

<a id="ops-03"></a>

### OPS-03 — Corral-safe backups, opt-in scheduling, and operator control

- **State:** Present scripts; deployment state unverified.
- **What it does:** Provides database/media backups and a separate control script for installation, scheduling, execution, status and removal.
- **Why:** Avoid wedging Corral with overlapping or same-mount backup I/O and allow backup maintenance without full setup.
- **How:** Backups stage dumps/media locally before pushing snapshots to Corral, use locks/timeouts/retention/logging and bounded mount preflight, and run as the current user. Cron installation is opt-in through WEBODM_ENABLE_BACKUP_CRON; backup-ctl supports explicit enable/disable and db-only runs.
- **Commit evidence:** [`b4065c7b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b4065c7b823cbb60457b9e9d6a7a6e46d6860c19), [`4578543c`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/4578543c3c4ac25ebc242c671875d650cb917def), [`56db916e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/56db916e3e0221608276bcd06963dba6025913ea), [`1d198eb9`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/1d198eb95b2e735cca4b51cffcd4c246ffad30c4), [`b4db21c5`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b4db21c5f1e8f41fc457f611ee21ee36a1598240).
- **Source:** [scripts/backup-ctl.sh](../../scripts/backup-ctl.sh), [setup.sh](../../setup.sh).
- **Upgrade checks:** Review backup destinations, local capacity, ownership, retention, failed mounts, stale locks and restore procedure. Inventory did not run backups or inspect deployed cron state.
- **Upgrade disposition:** Unreviewed.

<a id="ops-04"></a>

### OPS-04 — Nginx logging, compression, worker and status tuning

- **State:** Present.
- **What it does:** Adjusts proxy worker behavior, request logging/compression and local status inspection.
- **Why:** Improve serving behavior and visibility during public-map and asset workloads (intent partly inferred).
- **How:** nginx.conf.template sets worker_processes auto, accept_mutex, detailed access logs, gzip types and loopback-only nginx_status. Related history pins an nginx image and fixes mount-group behavior.
- **Commit evidence:** [`f4ed596b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f4ed596bbbaebd7d4f3cb4e11995aebe789fddbf), [`dbc55f2d`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/dbc55f2d7ba8e52d12f22f0566a568259ade6b93), [`ff72166f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ff72166f12338cae9b316b4bfa68036428e8e4a1), [`8e0a58e4`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8e0a58e46099114fd3fda1cc027d94822378b8d5).
- **Source:** [nginx/nginx.conf.template](../../nginx/nginx.conf.template), [docker-compose.yml](../../docker-compose.yml), [start.sh](../../start.sh).
- **Upgrade checks:** Check proxy headers/timeouts, asset delivery, status access restriction, compression, image compatibility and shared-mount reads.
- **Upgrade disposition:** Unreviewed.

<a id="build-01"></a>

### BUILD-01 — Custom source builds and update behavior

- **State:** Present.
- **What it does:** Builds the customized WebODM image locally instead of replacing it with the public stock image during update.
- **Why:** Keep fork-specific integrations present after webodm.sh update (a0473f2f).
- **How:** webodm.sh update invokes the build path; Dockerfile/Compose include custom dependencies, plugin builds and an app build target. Dockerignore excludes runtime/media/local-dev state. Locale and processing submodule references are pinned/updated in later commits.
- **Commit evidence:** [`a0473f2f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a0473f2fa7200c6baea3c1f49d33cbb38a3e043b), [`ba28b8e8`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba28b8e8e5571294ca77d9612460c49e50e920b0), [`bd1f8974`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf), [`ba134a99`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/ba134a99a52ab94a0ea15c63f6a60d07cbe56726), [`004d0134`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d), [`8fe74e8b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8fe74e8b5bd7353982c3b142d5f208ef424a1501).
- **Source:** [webodm.sh](../../webodm.sh), [Dockerfile](../../Dockerfile), [docker-compose.build.yml](../../docker-compose.build.yml), [.dockerignore](../../.dockerignore), [.gitmodules](../../.gitmodules).
- **Upgrade checks:** Verify update/build produces the customized image, worker uses the same source, plugin assets exist, and submodule pins resolve. Do not run stock update blindly on this fork.
- **Upgrade disposition:** Unreviewed.

<a id="build-02"></a>

### BUILD-02 — Database/runtime dependency compatibility

- **State:** Present; version-specific adaptations.
- **What it does:** Adapts dependencies/settings to Tapis integration and the separate newer embeddings database.
- **Why:** Resolve tapipy/PyJWT compatibility and psycopg2/libpq/Postgres SSL and timezone failures documented in commits.
- **How:** History pins PyJWT 1.7.1, raises psycopg2-binary to 2.9.9, and patches Django 2.2 utc_tzinfo_factory for timedelta offsets. Settings tolerate newer tzlocal APIs; Dockerfile contains custom system/runtime dependencies.
- **Commit evidence:** [`981413d3`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/981413d331a686218484873750c8fe89c4618abf), [`808d6199`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/808d61998c4c823b290374e300318ceff0241b89), [`32471240`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3247124010bdccfdd2aa94b7d48e5f81d4f4b0d1), [`7ae29a4a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/7ae29a4ad0a6b8285a90f1655ac74051040f8d44), [`bd1f8974`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf).
- **Source:** [requirements.txt](../../requirements.txt), [webodm/settings.py](../../webodm/settings.py), [Dockerfile](../../Dockerfile), [db/Dockerfile](../../db/Dockerfile).
- **Upgrade checks:** Reevaluate adaptations against new Python/Django/JWT/GDAL versions; preserve the behavior need rather than blindly retaining obsolete monkeypatches/pins.
- **Upgrade disposition:** Unreviewed.

<a id="dev-01"></a>

### DEV-01 — Isolated local connected stack and restart smoke harness

- **State:** Present; local-only.
- **What it does:** Runs a disposable WebODM → ClusterODM → NodeODM stack with connectivity checks and a restart smoke script.
- **Why:** Test control-plane/restart flows without production Corral or Tapis.
- **How:** local-dev Compose/scripts build the fork image, bind offset ports to localhost, persist isolated state, register the local node and support low-memory smoke profiles. Debug-gated WO_LOCAL_DEV_SKIP_AUTH creates/authenticates a localdev superuser. June/October commits improve startup and routing/restart handling.
- **Commit evidence:** [`f44673ee`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/f44673ee073aaf8f30ec0d250a182a63f6175e0e), [`e60b44c3`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e60b44c39f4936590558ac62cd1d3ff7652a97c3), [`038268b9`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/038268b94dc19d9a2c46a8a0ce58739e95711fd1), [`3f957889`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f95788942d49259de1ff210d1295292a6d1c98b).
- **Source:** [local-dev/README.md](../../local-dev/README.md), [local-dev/docker-compose.local.yml](../../local-dev/docker-compose.local.yml), [local-dev/up.sh](../../local-dev/up.sh), [local-dev/restart-nodeodm-smoke.py](../../local-dev/restart-nodeodm-smoke.py), [app/localdev.py](../../app/localdev.py), [app/api/authentication.py](../../app/api/authentication.py).
- **Upgrade checks:** Adapt the harness to ClusterODX/NodeODX, preserve localhost/debug safeguards, and keep real LS6 checkpoint validation separate from local node restart checks.
- **Upgrade disposition:** Unreviewed.

<a id="dev-02"></a>

### DEV-02 — Project intelligence and fork CI workflow removals

- **State:** Present tooling/history changes.
- **What it does:** Adds OpenWolf/Claude project guidance and removes inherited public Docker publishing/test workflows.
- **Why:** Maintain project-specific context; the precise reason for deleting inherited workflows is not recorded in the short remove-actions commit.
- **How:** .wolf and .claude contain project memory/hooks; 5b8c8622 deletes .github/workflows/build-and-publish.yml and test-docker.yml. These are contributor/automation changes, not end-user application functionality.
- **Commit evidence:** [`86b39d90`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/86b39d9038a35b9f6a593d75553a1cc97e4e75f7), [`bd1f8974`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd1f8974ce120b199e8163b1e96ab463f2910fdf), [`5b8c8622`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/5b8c8622747d0bfb0ed79fdfe31db85d4afb64de).
- **Source:** [.wolf/OPENWOLF.md](../../.wolf/OPENWOLF.md), [.wolf/anatomy.md](../../.wolf/anatomy.md), [.claude/settings.json](../../.claude/settings.json), [CLAUDE.md](../../CLAUDE.md).
- **Upgrade checks:** Keep project memory read-only during upgrade unless asked; deliberately choose replacement test/build CI and image ownership rather than restoring upstream publishing credentials/targets.
- **Upgrade disposition:** Unreviewed.

<a id="upgrade-01"></a>

### UPGRADE-01 — Prior 3.1.2-era upstream reconciliation and migration preservation

- **State:** Present; earlier milestone.
- **What it does:** Merges cached old upstream into the custom branch and resolves migration-number collisions without replacing existing fork migrations.
- **Why:** Bring core WebODM forward while retaining OAuth models, preferences, CKAN field, and integrations.
- **How:** c79c488e merges a4501835. Upstream Profile.cluster_id, Redirect and Task.wkt migrations are carried as 0048/0049/0050 after fork 0047; initial Tapis migration/merge history remains. Later commits adjust tests, local stack and locale revision. These schema features originate upstream, while their reconciliation/order is custom.
- **Commit evidence:** [`a3e9c41f`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/a3e9c41f262309a0c5ee1f0cc4e74df217f5721e), [`004d0134`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/004d0134048a4dc406eb5b85c1e6eb54bdd58f8d), [`c79c488e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/c79c488e5659bc90bfbf12583baa7155816eecb2), [`40023433`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/40023433361102d49ce72f37aab3c7c47803db69), [`b060790e`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/b060790ef31a5f5a5396090764552b594b425288), [`3f957889`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/3f95788942d49259de1ff210d1295292a6d1c98b), [`8fe74e8b`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/8fe74e8b5bd7353982c3b142d5f208ef424a1501).
- **Source:** [app/migrations/0002_tapis_oauth2_models.py](../../app/migrations/0002_tapis_oauth2_models.py), [app/migrations/0045_merge_20250910_1747.py](../../app/migrations/0045_merge_20250910_1747.py), [app/migrations/0046_auto_20250910_1902.py](../../app/migrations/0046_auto_20250910_1902.py), [app/migrations/0047_task_ckan_url.py](../../app/migrations/0047_task_ckan_url.py), [app/migrations/0048_profile_cluster_id.py](../../app/migrations/0048_profile_cluster_id.py), [app/migrations/0049_redirect.py](../../app/migrations/0049_redirect.py), [app/migrations/0050_task_wkt.py](../../app/migrations/0050_task_wkt.py), [docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md](../../docs/design/2026-10-05-webodm-upstream-3-1-2-reconciliation.md).
- **Upgrade checks:** Compare full migration graphs with new upstream, keep applied migrations immutable, test clean and restored databases, and preserve model/data compatibility. Earlier recorded test results are historical evidence, not a fresh validation run.
- **Upgrade disposition:** Unreviewed.

<a id="ops-05"></a>

### OPS-05 — Restore missing application logo after media loss

- **State:** Present.
- **What it does:** Restores the default application logo when a settings record survives but its media file is missing.
- **Why:** Avoid a broken application logo after a wiped/replaced media volume (explicit code comment).
- **How:** Boot checks the existing Setting logo path and writes APP_DEFAULT_LOGO when the path is absent or invalid; file handles are managed with a context manager.
- **Commit evidence:** [`058d5a0d`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/058d5a0dbafc94b7e9d0a824fe2e4531260bd45f).
- **Source:** [app/boot.py](../../app/boot.py).
- **Upgrade checks:** Verify startup with existing settings and missing media, fresh settings creation, and preservation of a valid custom logo.
- **Upgrade disposition:** Unreviewed.

<a id="ui-01"></a>

### UI-01 — Theme color normalization and invalid-value handling

- **State:** Present.
- **What it does:** Keeps template color calculations from failing on empty/invalid colors and accepts short three-digit hex colors.
- **Why:** Avoid template errors from nonstandard theme values (inferred from validation changes).
- **How:** _normalize_hexcolor validates/expands hex values; complementary and scaleby return the original input and log a warning when normalization fails.
- **Commit evidence:** [`163b0148`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/163b0148a06392ac8a36fc7f08e3975fcd3062a3), [`e4624e69`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/e4624e69c05c8548ce0251c33841029e452e6c1d).
- **Source:** [app/templatetags/settings.py](../../app/templatetags/settings.py).
- **Upgrade checks:** Check empty, malformed, three-digit and six-digit theme colors, and compare equivalent upstream helpers before porting.
- **Upgrade disposition:** Unreviewed.

<a id="ui-02"></a>

### UI-02 — Processing UUID visibility and console diagnostics

- **State:** Present.
- **What it does:** Shows the remote Processing UUID in task details and adds request/output diagnostics useful for correlating cluster activity.
- **Why:** Connect the WebODM task a user sees to the task tracked by the remote cluster (intent inferred from display/log changes).
- **How:** TaskListItem conditionally renders task.uuid and logs the output request URL; task API and JWT adapter history add output/path diagnostics. The adjacent Task ID display has upstream provenance and is not claimed as a new fork feature.
- **Commit evidence:** [`bd7ade13`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/bd7ade13e5df90b131159f82994d9e3f118a703f), [`aceb725a`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/aceb725acc1521f8de442e22caba8f673db083b8), [`50ee93df`](https://github.com/In-For-Disaster-Analytics/WebODM/commit/50ee93dff0861a32762c52ef13f0e0f6df5d3b9a).
- **Source:** [app/static/app/js/components/TaskListItem.jsx](../../app/static/app/js/components/TaskListItem.jsx), [app/static/app/js/css/TaskListItem.scss](../../app/static/app/js/css/TaskListItem.scss), [app/api/tasks.py](../../app/api/tasks.py), [nodeodm/jwt_node_wrapper.py](../../nodeodm/jwt_node_wrapper.py).
- **Upgrade checks:** Verify WebODM ID versus remote UUID display and console correlation; retain useful diagnostics without exposing tokens or sensitive paths in logs.
- **Upgrade disposition:** Unreviewed.

## Items requiring an explicit decision

1. **Tapis JWT trust:** local JWT claim decoding in the committed backend does not establish signature verification. Preserve the identity workflow while reviewing the trust boundary; this inventory is not a security audit.
2. **Dirty authentication adapter changes:** preserve and review existing uncommitted JWT wrapper/security work separately before any branch/merge operation.
3. **Automatic Tapis downloads:** discovery has real code, but `_schedule_image_download` is a logging placeholder. Do not confuse that path with working server-side image imports.
4. **Embeddings delivery boundary:** task embedding/labeling operations have implementations; global workspace/diagnostics, STAC actions, GeoJSON import and model training remain incomplete.
5. **CKAN visibility:** current publishing makes the task public. This is an intentional behavior to review and test, not just a link-format change.
6. **Version-bound code:** Django/psycopg2 timezone adaptation, JWT pins, old ODM option names and loader internals may be superseded upstream. Preserve requirements and data, not every line of implementation.
7. **Migration identities:** OAuth/preferences and CKAN changes coexist with renamed upstream compatibility migrations. Applied historical migrations must be reconciled as a graph, not copied by filename.
8. **External dependencies:** this repository’s history does not inventory custom code inside ClusterODM/ClusterODX, NodeODM/NodeODX, LS6 jobs, the DSO agent, Upstream, embeddings actors/database, or Label Studio auth. Their interface compatibility is in scope for upgrade checks; a complete inventory of those repositories is separate work.
9. **Historical operational artifacts:** `.env`, cookies, and certificate/key files appear in history. Their contents are deliberately omitted; they must not be treated as reusable configuration or required features.
10. **Historical versus new validation:** prior reconciliation notes record successful builds/migrations/tests, but this inventory runs documentation/evidence checks only. It does not certify the old or new stack at runtime.

## Evidence appendices

- [Complete commit ledger](2026-10-27-webodm-customization-commits.md): every selected commit, date, subject, changed paths and explicit/path-based catalog cross-references.
- [Machine-readable inventory](2026-10-27-webodm-customization-inventory.json): catalog fields, full commit IDs, commit bodies/path lists, provenance and mapping basis.

## Review record

- 2026-10-27: Created from local Git/source evidence at the recorded baseline. No upgrade dispositions approved yet.

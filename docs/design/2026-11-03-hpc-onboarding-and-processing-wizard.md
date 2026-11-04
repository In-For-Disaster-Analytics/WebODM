# HPC onboarding check and guided processing wizard for WebODM

## Status

Implementing — approved by the user 2026-11-03. All three phases are code-complete and in review as separate pull requests (see Decisions): Phase C (WebODM #24), Phase A (WebODM #25, stacked on master), Phase B (WebODM, stacked on #25) plus its ClusterODX half (wmobley/ClusterODX #7). Fork `master` was pushed to `origin/master` with the user's approval. Connected acceptance (Test plan 6) and the production env/config changes remain to be done.

Items marked `[ASSUMPTION — confirm]` are not yet verified and must be confirmed before the section that depends on them is built.

## Objective

Make WebODM usable by a TACC user who has never touched Lonestar6 directly:

1. After login, confirm the user has a Tapis system credential for the ClusterODX execution system (`ls6` in the `portals` tenant). If it is missing, prompt them to create it with one click (Tapis TMS keys) instead of letting the first job fail with `SYSTEMS_MISSING_CREDENTIALS`.
2. Replace the one-shot "pick a preset, click Review" task form with a short wizard: choose what to produce, confirm the compute plan (allocation, queue, nodes, run time) with recommendations driven by image count, then review and optionally adjust individual options.
3. Default the allocation to `BCS26030` ("Open Drone Map Suite", confirmed in TAS 2026-11-03) wherever a default is chosen, and make sure the allocation gate admits its members.

### Non-goals

- No automatic credential creation at login or anywhere without an explicit click.
- No persistence of credential state in the WebODM database.
- No Stampede3 support and no automatic GPU queue selection (one-line hint only).
- No change to `ImportTaskPanel` (imports do not run Tapis compute).
- No new ODM options or changes to option semantics; the wizard only chooses among existing presets and the four `tapis-*` options.
- No JWT signature verification work (known gap, tracked separately in `.wolf/cerebrum.md`).
- No shared service account for job submission.
- ClusterODX code changes are limited to the one sizing fix in Part B.5 if the user approves it; otherwise none.

## User need

**Primary user:** A researcher with a TACC account and membership in BCS26030 who logs into `webodm.tacc.utexas.edu`, uploads a flight, and expects a map. They do not know what a Tapis credential, a SLURM queue, or an SU is.

**Secondary user:** The operator (Will) who today has to diagnose "job failed with status 400" reports by hand.

**Current pain (observed 2026-11-03):** A new user signed in through Tapis OAuth, uploaded images, and ClusterODX returned `SYSTEMS_MISSING_CREDENTIALS ... system ls6 ... tenant portals`. Login proves identity but never provisions the SSH credential Tapis Jobs needs to act as that user on ls6. The operator confirmed the diagnosis and created the TMS key through the Tapis portal, which fixed submission. Separately, queue, run time, node count and allocation are buried in the preset editor with no guidance, the allocation default is `PT2050-DataX`, and the local environment's allocation gate (`WO_TAS_REQUIRED_ALLOCATIONS`) lists only `PT2050-DataX`, which would block a BCS26030-only member from creating projects at all.

**Definition of success:**

- A brand-new portals-tenant user can go from first login to a submitted job without operator help.
- The dashboard tells them within a few seconds of login whether HPC access is ready, and one click fixes it.
- The new-task flow proposes a queue, node count, run time and allocation that match the image count and chosen output, explains why, and lets them change it without producing a job ClusterODX or SLURM will reject.
- `BCS26030` is the preselected allocation for anyone who holds it, and holding it is enough to pass the allocation gate.

## Current code/system summary

Code facts were read on 2026-11-03 from the fork `master` worktree at `odm-suite/.worktrees/webodm-master` (HEAD `a725bfc8`, which equals `upgrade/webodm-3.3.1-tapis`) unless a line number says otherwise. They are inspection notes, not test results.

**Authentication and tokens**

- `app/api/tapis_oauth2.py` `TapisOAuth2CallbackView` exchanges the code, stores the JWT in `TapisOAuth2Token` (`app/models/oauth2.py`), optionally kicks off flight discovery in a background thread, then redirects to `/dashboard/`. Nothing checks system credentials. It also logs `jwt_token[:50]` and `response.text` (lines ~123 and ~198); the new code must not copy that pattern.
- `TapisOAuth2Token.get_valid_access_token()` returns the user's JWT for server-side calls; `app/services/tapis_storage.py` and `app/models/task.py:_get_tapis_jwt_token` already use it. `TapisStorageService._make_request` calls `raise_for_status()` then `.json()` with no timeout, so it discards the status codes and bodies the credential probe needs and is not reusable here.
- Token expiry is terminal in the portals tenant; `TapisTokenManager.js` redirects to logout on expiry.
- Settings: `TAPIS_BASE_URL` (`WO_TAPIS_BASE_URL`, prod `https://portals.tapis.io`, code default `''`), `TAPIS_TENANT_ID`. The OAuth client row also carries `base_url` and `tenant_id`.
- REST defaults: `DEFAULT_AUTHENTICATION_CLASSES` includes Session, Basic and JWT; the global permission default is `DjangoObjectPermissions`; the cache under `TESTING` is Redis on the Celery broker instance.

**Job submission path**

- WebODM passes the user's JWT to ClusterODX (`nodeodm/jwt_node_wrapper.py`). ClusterODX `libs/asr-providers/tapis.js:611-617` validates it and submits the Tapis job *as that user*, so Tapis evaluates the user's own credential on `system.executionSystemId` (`ls6`). ClusterODX does not publish the system id through `/info` or `/options`.
- ClusterODX job shape (`tapis.js:539-575`): `tapis-queue` is passed straight through as `execSystemLogicalQueue` with no check against `queueFilter`; `tapis-max-run-time` is parsed with no clamp; `tapis-node` is clamped to `job.maxNodesPerJob`; **`coresPerNode` and `memoryMB` always come from the `imageSizeMapping` tier selected by image count, never from the chosen queue**; the allocation becomes `-A <code>` in `schedulerOptions` and is validated only by SLURM at run time. One Tapis job is submitted per task.

**Allocation handling**

- `app/services/tas_allocations.py` lists active allocations via TAS (filtered by `TAS_RESOURCE_FILTER`) and `choose_default_allocation` prefers `TAS_DEFAULT_ALLOCATION` then falls back to the user's first allocation. `app/api/tas_allocations.py` serves `GET /api/tas/allocations/` returning `{allocations:[{chargeCode,title,resource,...}], default}`.
- `app/api/permissions.py` `HasRequiredAllocation` gates project/upload/job writes when `TAS_REQUIRED_ALLOCATIONS` is non-empty and fails closed.
- Local `WebODM/.env` (read for variable names and non-secret values only): `WO_TAS_DEFAULT_ALLOCATION=PT2050-DataX`, `WO_TAS_REQUIRED_ALLOCATIONS=PT2050-DataX`, `WO_TAS_RESOURCE_FILTER=LS6,Lonestar6,lonestar6`. `[ASSUMPTION — confirm]` production uses the same values.
- TAS query for the operator's account on 2026-11-03 (read-only, service credentials from `.env`): `BCS26030` "Open Drone Map Suite" has an **Active Lonestar6 allocation 2026-06-23 → 2027-06-30, 0 of 12,500 SU used**, plus Corral2. `PT2050-DataX` "PT2050 DataX" has an Active Lonestar6 allocation 2026-02-01 → 2027-01-31 with 3,575 of 5,000 SU used.
- `EditTaskForm.jsx:403-452` detects a node that advertises `tapis-allocation`, fetches allocations, rewrites that option into an enum of charge codes with the default selected. `withDefaultTapisOptions` (line ~490) silently injects `tapis-queue`, `tapis-allocation`, `tapis-max-run-time` defaults into the saved options at `getTaskInfo()` time.
- `app/boot.py` system presets on master: Multispectral, Volume Analysis, 3D Model, Buildings, Forest, DSM + DTM, Field, Fast Orthophoto, High Resolution, Default, LS6 Small. **Default and LS6 Small carry legacy keys `allocation: PT2050-DataX`, `queue`, `num-nodes`, `max-run-time`.** ClusterODX advertises none of these names, so `getAvailableOptionsOnly` drops them before submission; they are dead but misleading, and the preservation inventory lists them as HPC-04 "legacy cluster values".

**Task creation UI**

- `NewTaskPanel.jsx` renders name, processing node, preset selector, optional resize/alignment, plugin items (`PluginsAPI.Dashboard.triggerAddNewTaskPanelItem`), and a two-click "Review" then "Start Processing" button (`inReview` state). It reaches the form imperatively through `this.taskForm` and calls bare `$.getJSON`.
- `EditTaskForm.jsx` owns presets, node selection and option filtering. `EditPresetDialog.jsx` on master groups options through `OPTION_GROUP_MAP` (line ~130) with group/subgroup entries; it has **no entry for the four `tapis-*` options**. (The 3.1.2-only commit `633b8480` added a different grouping with a "Tapis Job Settings" group; it conflicts with master and is not being cherry-picked, see Decisions.)
- ClusterODX `getClusterOptions()` (`tapis.js:225-234`) publishes the four Tapis options with `domain` (queue list from `system.queueFilter`, run time `1..2880` minutes, nodes `1..maxNodesPerJob`) and a `defaultByImages` array derived from `imageSizeMapping` (docs example: `≤200 images → vm-small, 1 node, 240 min; ≤1000 → normal, 2 nodes, 360 min`). WebODM's JS does not read `defaultByImages` anywhere today.

**Lonestar6 queue facts** (TACC Lonestar6 user guide, "Production Queues" Table 5, <https://docs.tacc.utexas.edu/hpc/lonestar6/>, read 2026-11-03; the ~29 GB figure is the guide's own `vm-small` guidance)

| Queue | Max nodes/job | Max duration | Max jobs/user | SU per node-hour | Notes |
|---|---|---|---|---|---|
| `vm-small` | 1 (16 cores, ~29 GB usable) | 48 h | 4 | 0.143 | virtual node, shared host |
| `development` | 8 | 2 h | 1 | 1 | |
| `normal` | 64 | 48 h | 20 | 1 | 128 cores, 256 GB per node |
| `large` | 65–256 | 48 h | 1 | 1 | restricted |
| `gpu-a100-small` | 1 | 48 h | 3 | 1.5 | |
| `gpu-a100-dev` | 2 | 2 h | 1 | 3 | |
| `gpu-a100` | 8 | 48 h | 8 | 3 | |
| `gpu-h100` | 1 | 48 h | 1 | 6 | |

**Tapis credential facts** (Tapis Systems docs, <https://tapis.readthedocs.io/en/latest/technical/systems.html>, read 2026-11-03)

- `POST /v3/systems/credential/{systemId}/user/{userName}?createTmsKeys=true` with an empty body makes Tapis generate and register an SSH keypair through the Trust Manager System. Requires the system's `defaultAuthnMethod` to be `TMS_KEYS` and a dynamic `effectiveUserId`. One credential set per user per system; success returns `SYSAPI_CRED_UPDATED`. Confirmed in practice 2026-11-03: creating the TMS key for the affected user (via the Tapis portal) made ClusterODX submission work, so the per-user credential is compatible with ClusterODX's submission path.
- `[ASSUMPTION — confirm]` A user's own JWT is authorized to POST their own TMS credential through the API (the portal did it on the user's behalf; the docs do not state who may call the endpoint). Verified by Test plan step 0b.
- The docs do not state the return shape of `GET /v3/systems/credential/{systemId}/user/{userName}` for a user reading their own record, nor whether a `.../check` endpoint exists in the deployed version. No credential-less account is currently available to test against. See Part A.2 for how the design copes.

## Proposed design

### Part A — HPC access check and one-click credential setup

**Backend**

1. New settings in `webodm/settings.py` next to the other `TAPIS_*` entries: `TAPIS_EXEC_SYSTEM_ID` (`WO_TAPIS_EXEC_SYSTEM_ID`, default `ls6`, validated at import against `^[A-Za-z0-9._-]+$`), `TAPIS_CREDENTIAL_CACHE_SECONDS` (`WO_TAPIS_CREDENTIAL_CACHE_SECONDS`, default `600`). Log the system id once at boot and document that it must equal ClusterODX `system.executionSystemId`.
2. New service `app/services/tapis_credentials.py`, plain functions over `requests.request` (explicit `timeout=10`, `allow_redirects=False`, headers `X-Tapis-Token` and `X-Tapis-Tenant`), taking a token string plus username and system id so it is testable without a database:
   - `probe_credential(token, username, system_id) -> ProbeResult(status, code, detail)`. Status mapping lives in one module-level table and is deliberately conservative:
     - Single call (revised 2026-11-04, see Decisions): `GET /v3/files/ops/{system}/?limit=1` with the user's token, which makes Tapis SSH into the host as the user. HTTP 200 → `ready`. Body `message` containing `SSH_POOL_MISSING_CREDENTIALS`, `SYSTEMS_MISSING_CREDENTIALS` or `SYSAPI_CRED_NOT_FOUND` → `missing`, whatever the HTTP status (Files reports a missing credential as 401 or 500).
     - HTTP 401 whose message starts with a `TAPIS_SECURITY_JWT_*` code → `unknown`/`token_expired`. Any other 401 → `unknown`/`ssh_auth_failed`: Files could not log in to the host with the credential Tapis holds for the user (rejected or stale key).
     - Anything else (403, bare 404, other 4xx, 5xx, non-JSON body, timeout, connection error) → `unknown` with a code from {`not_authorized`, `tapis_unreachable`, `unexpected_response`}. **A bare 404 is never `missing`.**
     - The original two-stage design started with `GET /v3/systems/credential/{system}/user/{username}`. That endpoint is service-only in Tapis Systems (`SYSLIB_UNAUTH_GETCRED`, "Never a user"), so stage 1 always returned 403 for a user token and was removed.
   - `create_tms_credential(token, username, system_id)` issues the `createTmsKeys=true` POST with `{}` body and returns the Tapis result.
   - `detail` is the Tapis `message` field only, capped at 300 characters, never `response.text`. Nothing logs headers, the JWT, or bodies; an audit line logs user, system and result code.
3. New API `app/api/tapis_credentials.py` (`permission_classes = [IsAuthenticated]` set explicitly; DRF `UserRateThrottle` scopes `hpc_access_get` 10/min and `hpc_access_post` 3/min), routed in `app/api/urls.py`:
   - `GET /api/tapis/hpc-access/?system_id=<optional>&refresh=1` → always HTTP 200 with the payload below; `system_id` defaults to the setting and is validated against the same regex; `refresh=1` bypasses the cache but is honoured at most once per 15 s per user.
   - `POST /api/tapis/hpc-access/` → runs a **fresh, uncached** probe first; only a `missing` result proceeds to create. `ready` → 409 `code: already_ready`; `unknown` → 409 `code: cannot_verify` (never creates on an unverified state); Tapis failure → 502 with code and capped detail; success → re-probe and return 200 with the new status. A per-user lock via `cache.add("hpc:lock:{user.pk}", ttl=30)` rejects concurrent POSTs with 429.
   - Identity: the Tapis username is `request.user.username` (the OAuth backend creates users from the Tapis username claim; the implementer re-confirms case/normalisation in `app/auth/tapis_oauth2.py`). It is never read from a request parameter. The token row is the `TapisOAuth2Token` whose client `tenant_id == settings.TAPIS_TENANT_ID`; a user without one gets `unknown`/`no_tapis_token` without any outbound call. The base URL is `client.base_url`; if it is empty or differs from `settings.TAPIS_BASE_URL`, fail closed with `unknown`/`misconfigured` and log once.
   - Cache: key `hpc:v1:{tenant}:{system}:{user.pk}`; only `ready` is cached (10 min); cleared on logout (`tapis_logout_view`) and after a successful POST. No browser-side cache.
4. No change to the OAuth callback.

**Frontend**

5. New `app/static/app/js/components/HpcAccessBanner.jsx` (+ `css/HpcAccessBanner.scss`), mounted at the top of `Dashboard.jsx` and reused inside `NewTaskPanel`:
   - On mount, `GET /api/tapis/hpc-access/` and `GET /api/tas/allocations/` (the latter is already cached server-side).
   - `missing` and the user has at least one active allocation → warning: "Your TACC account is not yet set up to run jobs on Lonestar6 from WebODM." with **Set up HPC access** (POST) and one sentence that WebODM will ask Tapis to create an SSH key for your account. Spinner, then success or an error with the friendly text for the code and a Retry button.
   - `missing` and no active allocation → dismissible info: "You need an active Lonestar6 allocation (for example BCS26030) before WebODM can set up HPC access. Contact the allocation owner." No button.
   - `ready` → renders nothing. `unknown` → one dismissible line keyed by code (`token_expired` → "Please log out and log in again"; others → "Could not confirm HPC access: …"). Never blocks.
   - Friendly-message mapping is keyed on `code`, never on substring matching of `detail`. Text is rendered as React text, never `dangerouslySetInnerHTML`.
6. **Release 1 is warn-only.** `Start Processing` is *not* disabled on `missing`. The banner is shown inline above the button in `NewTaskPanel` (both with and without the wizard flag). A Start-blocking rule is deferred until the probe has been verified against a credential-less account (Test plan 0a); when it ships it must include an "I've already set this up, continue anyway" escape hatch.
7. Failure recovery: `TaskListItem.jsx` already shows `last_error`. When the error text contains `SYSTEMS_MISSING_CREDENTIALS`, render the banner's button next to it and call `GET …?refresh=1` after a successful create. This covers a stale `ready` cache, a revoked key, and any probe false-positive.

### Part B — Guided processing wizard

The wizard lives inside `NewTaskPanel.jsx` and keeps `EditTaskForm.jsx` as the single source of truth for presets, nodes and options. The panel keeps its existing props and `onSave(taskInfo)` contract so `ProjectListItem`/upload code is untouched.

**Feature flag.** Part B ships behind `UI_TASK_WIZARD` (`WO_UI_TASK_WIZARD`, default `NO`), exposed through `app/contexts/tapis.py` as `window.__uiTaskWizard`. When off, `NewTaskPanel` renders exactly today's form plus the Part A inline banner, and `withDefaultTapisOptions` keeps injecting defaults as today.

**State ownership (architect review).**

- `EditTaskForm` stays mounted for the whole panel lifetime; steps hide it with CSS (as the current `disabled` wrapper does), never unmount it, so back navigation keeps presets, node and options.
- `EditTaskForm` gains one callback prop `onStateChange({selectedNode, selectedPreset, availableOptions, presets})` and one controlled prop `tapisOverrides` (`{queue, nodes, maxMinutes, allocation}` or `null`). `getTaskInfo()` merges `tapisOverrides` when present; when `null` the existing `withDefaultTapisOptions` fallback applies. `NewTaskPanel` is the single owner of the four `tapis-*` values while the wizard is on. The only imperative call kept is `selectPresetByName(name)`.
- `EditPresetDialog.jsx` gets a `tapis` group added to `OPTION_GROUP_MAP` and a `hiddenGroups` prop; the wizard passes `['tapis']` so there is exactly one place to set those values. With the flag off, the group is visible in the dialog (improvement over today, where the four options are ungrouped).

**Step 1 — What do you want to produce?**

- Cards, one per goal, mapped to existing system presets in `classes/ProcessingGoals.js`:

  | Goal card | Preset | Short help |
  |---|---|---|
  | Orthomosaic + elevation (fastest) | Fast Orthophoto | 2D map and DSM, skips 3D texturing |
  | Standard map, point cloud and 3D model | Default | Good balance for most flights |
  | Highest detail | High Resolution | Slow; use for small areas or when GSD matters |
  | 3D model focus | 3D Model | Dense cloud and textured mesh |
  | Terrain (DSM + DTM) | DSM + DTM | Classifies ground, generates bare-earth model |
  | Multispectral / thermal | Multispectral | Radiometric calibration on |
  | I know what I want (custom) | last used preset or Default | Skips to Step 3 with the option editor open |

  All six named presets exist in `app/boot.py` on master (confirmed). Presets are matched by name against the list `EditTaskForm` already loads; an absent preset hides its card; the custom card always remains. "LS6 Small" and the other system presets stay reachable through the custom path.
- Also on this step: task name, the existing GCP/image-count warnings, resize/alignment controls when `showResize`/`showAlign` apply, and plugin panel items (they render here, where they render today).

**Step 2 — Compute plan**

Shown only when the selected node advertises `tapis-allocation`. Skipped otherwise.

- **Allocation**: select built from `GET /api/tas/allocations/`, labelled `"<title> (<chargeCode>)"`. Preselect `BCS26030` when held; otherwise, if the user holds exactly one allocation, preselect it; otherwise preselect nothing and require a choice (no silent fallback to "first allocation"). No active allocation → the existing error and the Part A no-allocation message; cannot continue.
- **Recommendation engine** `classes/ComputeRecommender.js` (pure, no I/O, does not mutate inputs). Inputs: image count, the node's four Tapis options (`domain`, `value`, `defaultByImages`), the preset's effective options and name, and `classes/HpcQueueCatalog.js` (the table above, with source and date; a queue missing from the catalog means "no opinion", never an error). Output `{queue, nodes, maxMinutes, tierMaxImages, reasons[], warnings[], estimatedSU}`.
  - Rules, in order:
    1. **Baseline.** The first `defaultByImages` entry with `maxImages >= imagesCount` for queue, nodes, run time. None matches → use the last entry and add warning "this processing node is not configured for this many images" (the existing `checkFilesCount` still blocks Start when the node reports `max_images`). `defaultByImages` empty → the option `value` and reason "using the processing node's defaults".
    2. **Quality suggestion.** If the preset's options contain `pc-quality` or `feature-quality` at `high`/`ultra`, or the preset is named "High Resolution": *suggest* run time × 1.5 rounded up to 30 minutes, shown as a reason with an "Apply" link; not applied automatically. If applying would exceed the domain max or the queue cap, say so.
    3. **GPU hint.** If the queue domain contains a `gpu*` queue and the preset does not set `no-gpu: true`: reason only, no change.
    4. **Queue duration cap.** Run time above the catalog max for the queue → clamp and warn (`development` → 120 min; all → the `tapis-max-run-time` domain max).
    5. **Node cap.** Clamp nodes to min(catalog max nodes for the queue, `tapis-node` domain max); warn if clamped.
    6. **Cost estimate.** `estimatedSU = ceil(nodes × (maxMinutes / 60) × rate × 10) / 10`, unit SU, shown as "up to ~N SU"; unknown rate → "rate unknown".
  - Worked example: 468 images, Default preset, mapping (≤200 → `vm-small`/1/240; ≤1000 → `normal`/2/360), domain `[vm-small, normal]` → `{queue: normal, nodes: 2, maxMinutes: 360, estimatedSU: 12.0}`, one reason, no warnings. High Resolution → same plus a suggestion of 540 min (~18.0 SU).
- **Queue override and job shape (skeptic finding).** Because ClusterODX sizes `coresPerNode`/`memoryMB` from the image-count tier regardless of `tapis-queue`, a queue override to a *smaller* queue than the tier (for example 1000 images onto `vm-small`) produces a job Tapis or SLURM rejects, and an override to a larger queue runs with the small tier's core count. Two options, user decision required:
  - **B.5-restrict (no ClusterODX change):** the queue selector offers only the recommended tier's queue and the queues of tiers with `maxImages` ≥ the recommended tier (same or larger). Nodes and run time stay editable within caps.
  - **B.5-fix (small ClusterODX change, recommended):** in `submitJobWithoutData`, when `tapis-queue` names the `logicalQueue` of some `imageSizeMapping` entry, take `coresPerNode`/`memoryMB` from that entry instead of the image-count entry. Then any queue in the domain is safe and the UI can offer the whole domain. ~10 lines plus a unit test in `ClusterODX/test/test-tapis-provider.js`.
- UI: summary card ("Recommended: `normal`, 2 nodes, up to 6 h, ~12 SU on Open Drone Map Suite (BCS26030)") with the `reasons` list, then an **Adjust** disclosure with selects for queue, nodes and run time (minutes with hours shown). Live validation re-runs the rules; "Reset to recommended" restores the engine output.

**Step 3 — Review and start**

- Shows task name, goal/preset, node, compute plan summary, and the compact options text (existing `getAvailableOptionsOnlyText`).
- **Adjust processing options** opens the existing `EditPresetDialog` (grouped, Tapis group hidden) on a "(Custom)" copy of the preset, as today's Edit does.
- **Start Processing** calls the existing `save` path. The Part A banner appears above it when access is not `ready`; Start is not blocked in release 1.
- Last goal and compute overrides are remembered in `Storage` like `last_preset_id`.

### Part C — Default allocation BCS26030 and the allocation gate

1. `webodm/settings.py`: code default of `TAS_DEFAULT_ALLOCATION` becomes `BCS26030`; production `.env` sets `WO_TAS_DEFAULT_ALLOCATION=BCS26030`.
2. **Allocation gate:** production `WO_TAS_REQUIRED_ALLOCATIONS` must list both `PT2050-DataX` and `BCS26030` (comma-separated) or BCS26030-only members cannot create projects or upload. This is the most likely reason a new BCS26030 member would still be stuck after Part A. Ops change, same deploy as the default.
3. `choose_default_allocation` keeps preferring the configured code; the "first allocation" fallback is retained for API compatibility, but the wizard applies its own rule (Step 2) so no plan is silently charged to an arbitrary project.
4. `app/boot.py`: remove the dead legacy keys `allocation`, `queue`, `num-nodes`, `max-run-time` from the Default and LS6 Small system presets (ClusterODX never reads them; they advertise `PT2050-DataX`). Record as the resolution of preservation item HPC-04.
5. ClusterODX private `tapis-config.json` `scheduler.defaultAllocation` → `BCS26030` (ops; the fallback only applies when WebODM sends no allocation). Users outside BCS26030 who somehow send none fail at SLURM and are not charged.
6. DSO docs updated (Documentation plan).

## Files likely affected

WebODM, fork `master` (worktree `.worktrees/webodm-master`):

- `webodm/settings.py` — `TAPIS_EXEC_SYSTEM_ID`, `TAPIS_CREDENTIAL_CACHE_SECONDS`, `UI_TASK_WIZARD`, `TAS_DEFAULT_ALLOCATION` default, throttle scopes.
- `app/contexts/tapis.py` — expose the wizard flag.
- `app/services/tapis_credentials.py` — new.
- `app/api/tapis_credentials.py` — new; `app/api/urls.py` — route.
- `app/views/tapis_auth.py` — clear the credential cache entry on logout.
- `app/boot.py` — remove legacy preset keys.
- `app/tests/test_tapis_credentials.py` — new; `app/tests/test_tas_allocations.py` — default assertion.
- `app/static/app/js/Dashboard.jsx` — mount banner.
- `app/static/app/js/components/HpcAccessBanner.jsx`, `css/HpcAccessBanner.scss` — new.
- `app/static/app/js/classes/HpcAccess.js` — new shared fetch (no storage).
- `app/static/app/js/components/TaskListItem.jsx` — inline recovery button on `SYSTEMS_MISSING_CREDENTIALS`.
- `app/static/app/js/components/NewTaskPanel.jsx` — wizard steps behind the flag.
- `app/static/app/js/components/ProcessingGoalStep.jsx`, `ComputePlanStep.jsx` — new.
- `app/static/app/js/classes/ProcessingGoals.js`, `ComputeRecommender.js`, `HpcQueueCatalog.js` — new.
- `app/static/app/js/components/EditTaskForm.jsx` — `onStateChange`, `tapisOverrides`, `selectPresetByName`, allocation labels with titles.
- `app/static/app/js/components/EditPresetDialog.jsx` — `tapis` group in `OPTION_GROUP_MAP`, `hiddenGroups` prop.
- `app/static/app/js/tests/setup/browserMock.js` — no change needed once browser storage is dropped from the banner.
- Jest: new `tests/ComputeRecommender.test.js`, `tests/HpcAccess.test.js`, `tests/ProcessingGoals.test.js`, `components/tests/HpcAccessBanner.test.jsx`; modified `NewTaskPanel.test.jsx`, `EditTaskForm.test.jsx`, `EditPresetDialog.test.jsx`, `tests/Dashboard.test.jsx`, `ProjectListItem*.test.jsx` if the `onSave` assertions touch options.
- `app/static/app/js/css/NewTaskPanel.scss` — step styling.
- `TAPIS_OAUTH2_INTEGRATION.md` — new "HPC access (system credentials)" section.
- Locale strings: new `_()` strings; `python manage.py translate build --safe`.

ClusterODX (only if B.5-fix is approved):

- `ClusterODX/libs/asr-providers/tapis.js` — queue-aware cores/memory in `submitJobWithoutData`; `ClusterODX/test/test-tapis-provider.js` — test.
- `ClusterODX/docs/tapis.md` — note the behaviour.

Outside the repos:

- `DSO-Architecture/docs/services/webodm.md`, `docs/dev/environment-variables.md` — new env vars, endpoints, default allocation, gate list.
- Production `.env` and ClusterODX private `tapis-config.json` — ops.

## API/schema changes

- **New endpoints** (WebODM): `GET /api/tapis/hpc-access/` and `POST /api/tapis/hpc-access/`. Auth: session (CSRF enforced) or JWT, `IsAuthenticated`, throttled. Payload:

  ```json
  {"system_id": "ls6", "status": "ready|missing|unknown",
   "code": "ok|credential_missing|already_ready|cannot_verify|token_expired|not_authorized|tapis_unreachable|unexpected_response|no_tapis_token|misconfigured",
   "detail": "<Tapis message, ≤300 chars, may be empty>", "checked_at": "2026-11-03T15:04:05Z"}
  ```

  GET is always HTTP 200. POST: 200 on success, 409 (`already_ready`, `cannot_verify`), 429 (lock/throttle), 502 (Tapis create failed).
- **New env vars**: `WO_TAPIS_EXEC_SYSTEM_ID` (default `ls6`), `WO_TAPIS_CREDENTIAL_CACHE_SECONDS` (default `600`), `WO_UI_TASK_WIZARD` (default `NO`). Changed default: `WO_TAS_DEFAULT_ALLOCATION` → `BCS26030`. Changed production value: `WO_TAS_REQUIRED_ALLOCATIONS` gains `BCS26030`.
- **No database migrations.** System preset option lists change through `boot.py`'s `update_or_create`, which runs at startup.
- **Task option payload** to ClusterODX is unchanged in shape; with the wizard on, all four `tapis-*` options are sent explicitly.
- **ClusterODX** (B.5-fix only): behaviour change in how `coresPerNode`/`memoryMB` are chosen when `tapis-queue` matches a mapping entry; no API change.
- **External calls added**: WebODM server → `portals.tapis.io` Systems (GET, POST) and Files (GET) with the user's JWT.

## Data flow

```
Login (unchanged) ──► Dashboard mounts HpcAccessBanner
                          │ GET /api/tapis/hpc-access/  +  GET /api/tas/allocations/
                          ▼
            tapis_credentials.probe_credential(token, username, system)
                          │ token = TapisOAuth2Token (tenant-matched), base = client.base_url
                          ▼
   Systems GET credential ──(403/404 w/o code)──► Files ops probe
          │ 200 / SYSAPI_CRED_NOT_FOUND            │ 200 / SYSTEMS_MISSING_CREDENTIALS
          ▼                                        ▼
   ready (cache 10 min) | missing | unknown(code)  ── never blocks
                          │ missing + allocation → button
                          ▼
            POST /api/tapis/hpc-access/ ── lock ── fresh probe must be missing
                          │ POST …?createTmsKeys=true
                          ▼
            TMS generates key, Tapis stores it ── re-probe ── ready, cache cleared/set

Upload images ──► NewTaskPanel (flag on)
  Step 1 goal ──► EditTaskForm.selectPresetByName ──► onStateChange({node, preset, options})
  Step 2 plan ──► ComputeRecommender(imagesCount, node tapis options, preset, catalog)
                  + allocations (BCS26030 preselected) ──► tapisOverrides prop
  Step 3 review ──► save ──► getTaskInfo() merges tapisOverrides ──► onSave(taskInfo)
                 ──► existing task create ──► ClusterODX ──► Tapis job as user
Task fails with SYSTEMS_MISSING_CREDENTIALS ──► TaskListItem shows Set up HPC access
```

## Risks and tradeoffs

- **Unverified probe for the "missing" case.** Mitigated by requiring an explicit Tapis code/string for `missing`, warn-only release 1, the task-failure recovery path, and verification with the next new user before any blocking rule.
- **Credential creation is an external write by end users.** Scoped to their own account and system, explicit click, fresh-probe precondition, per-user lock, throttle, audit line. WebODM never sees key material. Residual: a false `missing` could rotate a working key; the fresh-probe-only rule and explicit-code rule make that require two independent Tapis misreports.
- **Job-shape mismatch on queue override.** Real today; addressed by B.5-restrict or B.5-fix (user decision). Until one ships, the wizard must not offer smaller-than-tier queues.
- **Allocation gate misconfiguration.** If production's required-allocation list is not updated, Part A succeeds and the user is still blocked at project creation with a 403. Part C.2 is therefore first in the rollout.
- **Token expiry mid-flow.** Terminal in portals; `token_expired` shows "log in again" once; the existing `TapisTokenManager` handles redirect.
- **Static queue catalog drifts.** Used only to explain and clamp; a stale value yields a stale warning, not a failed job. The skeptic would drop it; the architect would keep it. Kept, minimal.
- **Wizard touches the most-used form.** Flag default off, `EditTaskForm` kept mounted, controlled prop instead of imperative pokes, legacy path asserted in Jest, `withDefaultTapisOptions` retained as fallback.
- **Two WebODM lineages.** Resolved by working on fork `master` = 3.3.1; the old 3.1.2 checkout keeps uncommitted edits that are not part of this work.
- **Translations.** New strings need the locale build; English fallback acceptable initially.

## Alternatives considered

- **Create the credential automatically in the OAuth callback.** Rejected: external write users should see; slows login; failure there is confusing. Revisit after the explicit flow has run.
- **Switch `ls6` to a shared service identity.** Rejected: loses per-user accounting and ClusterODX's per-user job ownership; security and allocation policy change.
- **Have ClusterODX publish the execution system id.** Deferred; the API already accepts `system_id` so a per-node source can be added later without an API change.
- **Serve the queue catalog from the backend.** Deferred until a second system exists.
- **Lift all form state into `NewTaskPanel`.** Rejected (architect): a rewrite of the most-used form with no gain over a callback plus a controlled prop.
- **Cut goal cards, SU estimate and catalog for release 1** (skeptic). Not adopted: the goal cards and run-size guidance are the user's stated ask; the estimate is a pure function; the feature flag already limits exposure. The skeptic's ordering concern is recorded below.
- **Browser-side (`sessionStorage`) cache of the status.** Dropped: the server cache is enough and it removed a cross-user risk on shared browsers.

## Test plan

0. **Pre-implementation / pre-blocking verification (manual, gates only the deferred Start-blocking rule, not Phase A itself):**
   - 0a. With a portals JWT from an account that has **no** ls6 credential (next new user or a TACC test account), run the prepared probe script and record status codes and `message` fields for the Systems GET, the `/check` variant and the Files ops GET. Pass: at least one probe yields the explicit `SYSAPI_CRED_NOT_FOUND` or `SYSTEMS_MISSING_CREDENTIALS` signal.
   - 0b. Same account runs the `createTmsKeys=true` POST with its own token through WebODM's button; pass: `SYSAPI_CRED_UPDATED`, re-probe `ready`, one small job reaches `QUEUED` or later. (Root-cause and TMS-key efficacy already confirmed 2026-11-03 via the Tapis portal.)
1. **Backend unit tests** (`app/tests/test_tapis_credentials.py`, `django.test.SimpleTestCase`, `unittest.mock.patch('app.services.tapis_credentials.requests.request')`, `override_settings(CACHES=LocMemCache)` where the cache matters): mapping for 200 / `SYSAPI_CRED_NOT_FOUND` / 403→files 200 / 403→files `SYSTEMS_MISSING_CREDENTIALS` / 403→files 403 without code (= `unknown`) / bare 404 (= `unknown`) / 401 / 5xx / non-JSON / Timeout / ConnectionError; every outbound call passes `timeout=` and `allow_redirects=False`; username is URL-quoted; `system_id` override reaches the URL; create refuses on `ready` and on `unknown`; create success re-probes; only `ready` is cached; cache key includes tenant, system and user pk; log capture contains no JWT substring.
2. **API tests** (`BootTestCase`): unauthenticated → 401/403; GET returns the payload keys and HTTP 200 on upstream failure; POST 409 `already_ready`, 409 `cannot_verify`, 429 when locked, 502 on Tapis failure with capped `detail`; throttle scopes applied; users without a tenant-matched token get `no_tapis_token`.
3. **Jest** (`npm test`, which first generates `build/mocks`; tests set `global.$ = window.$ = require('jquery')` and `jest.spyOn($, 'getJSON')` as `TapisTokenManager.test.js` does):
   - `ComputeRecommender`: the 10-row table from the test review (worked example; High Resolution suggestion 540/18.0; 50 images → `vm-small`/1/240; 50 + High Resolution suggestion 360; empty `defaultByImages`; `development` clamp to 120 with warning; 1200 images → last tier + warning; 250 images with `vm-small` override → warning only; GPU hint when a `gpu*` queue is in the domain; unknown queue → `estimatedSU` null, no throw), plus boundaries 0/200/201/1000/1001, ceil to 0.1 SU, inputs not mutated.
   - `HpcAccessBanner`: nothing for `ready`; button for `missing` with allocations; no-allocation message for `missing` without; info line per `unknown` code; POST on click; Retry on 502.
   - `NewTaskPanel`: flag off → legacy form (explicit assertions, not snapshots), `withDefaultTapisOptions` still injects three options, plugin items render; flag on → steps 1→2→3, goal→preset by name, step 2 skipped for non-Tapis nodes, no-allocation stops at step 2, all four `tapis-*` present in `onSave` options, Start enabled regardless of access status, back navigation keeps state.
   - `EditTaskForm`: `tapisOverrides` wins over injection; `null` falls back; `onStateChange` fires on node/preset change.
   - `EditPresetDialog`: `tapis` group visible by default; hidden with `hiddenGroups=['tapis']`.
   - `Dashboard`: mount-time request mocked; banner present.
4. **Existing suites** (`./webodm.sh test backend app.tests.test_tapis_oauth2_tokens app.tests.test_tas_allocations`, Jest `EditTaskForm`, `EditPresetDialog`, `NewTaskPanel`, `ProjectListItem*`) keep passing; `test_tas_allocations` default assertion updated.
5. **ClusterODX** (B.5-fix only): `test-tapis-provider.js` case: 468 images with `tapis-queue=vm-small` → `coresPerNode 16`, `memoryMB 30720`; with `normal` → the normal entry's values.
6. **Connected acceptance (staging, approval required, consumes allocation):** new user logs in → banner `missing` → click → `ready`; upload ~50 images → wizard recommends `vm-small`/1/4 h on BCS26030 → job submits and runs; repeat with ~500 images → `normal`/2/6 h. Confirm a user outside BCS26030 who selects it fails at SLURM and is not charged.

## Documentation plan

- `TAPIS_OAUTH2_INTEGRATION.md`: "HPC access (Tapis system credentials)" section: what the check does, the TMS create call, the warn-only policy, env vars, endpoints and codes, the requirement that `WO_TAPIS_EXEC_SYSTEM_ID` equal ClusterODX `executionSystemId`.
- `DSO-Architecture/docs/services/webodm.md`: endpoints, env vars, default allocation and gate list; `docs/dev/environment-variables.md`: the new vars and changed values. Commit and push per the DSO docs rule (push requires approval).
- `ClusterODX/docs/tapis.md` if B.5-fix ships.
- Record the verified probe behaviour in `## Decisions` when 0a runs.

## Rollout/rollback plan

Phased, each phase its own PR and approval gate. No migrations in any phase.

1. **Phase C (allocation default, gate, dead preset keys).** Code default + `boot.py` cleanup; ops set `WO_TAS_DEFAULT_ALLOCATION=BCS26030` and `WO_TAS_REQUIRED_ALLOCATIONS=PT2050-DataX,BCS26030`; ClusterODX `scheduler.defaultAllocation`. Rollback: env vars; preset keys are inert either way.
2. **Phase A (HPC access check, warn-only).** Inert for users with credentials. Rollback: revert commit; nothing stored; created Tapis credentials are harmless to leave.
3. **Phase B (wizard, and B.5 if approved).** Ships with `WO_UI_TASK_WIZARD=NO`; staging first, production after Test plan 6. Rollback: flip the flag.
4. **Deferred:** Start-blocking on `missing`, only after Test plan 0a.

The skeptic preferred A before C because C's two config changes are not atomic. C is kept first because the gate fix is the only item that unblocks BCS26030-only members today, and the ClusterODX fallback only matters when WebODM sends no allocation.

## Open questions

Decided 2026-11-03 (see Decisions): target branch; root cause; BCS26030 is active on Lonestar6; all six goal presets exist.

Decisions needed from the user:

1. **Queue override handling:** B.5-restrict (no ClusterODX change) or B.5-fix (small ClusterODX change, recommended)?
2. **Allocation gate:** confirm production `WO_TAS_REQUIRED_ALLOCATIONS` currently equals the local value (`PT2050-DataX`) and approve adding `BCS26030`.
3. **Goal cards:** keep the seven as listed, or hide any further presets? (Skeptic suggested deferring cards to a later release; spec keeps them.)
4. **Dead preset keys:** approve removing `allocation`/`queue`/`num-nodes`/`max-run-time` from the Default and LS6 Small presets.
5. **Push:** approve pushing the fast-forwarded local `master` (a725bfc8) to `origin/master`, and retargeting PR #23 to `master`.

Proposed answers, confirm or override:

6. Release 1 is warn-only; Start is never blocked until the probe is verified (proposed by three reviewers; adopted).
7. `ImportTaskPanel` unchanged (proposed).
8. Credential creation stays a user click, never automatic (recorded).

## Decisions

- 2026-11-03 — Per-user TMS credential kept (no shared service account). Rationale: preserves accounting and ClusterODX's per-user job ownership; matches Tapis portals design.
- 2026-11-03 — Credential creation is user-initiated (button), not automatic at login. Rationale: external write; user visibility; login latency.
- 2026-11-03 — ClusterODX `defaultByImages` remains the authoritative sizing baseline; the queue catalog only validates and explains.
- 2026-11-03 — **Target branch: fork `master`, fast-forwarded locally to `origin/upgrade/webodm-3.3.1-tapis` (a725bfc8).** User decision: "bring 3.3.1 to our forked main if it hasn't, then start from there." `origin/master` (fdad2f69) contained none of the 3.1.2 or 3.3.1 work; the 3.3.1 branch was a strict descendant (224 commits), so the merge is a fast-forward; it already includes NodeSplat PRs #20–22. **Push to `origin/master` pending user approval.** Work happens in worktree `.worktrees/webodm-master`. The old `WebODM/` checkout stays on `upgrade/webodm-upstream-3.1.2` with its uncommitted edits untouched (its `jwt_node_wrapper.py` edit is the older pyodm variant, superseded on 3.3.1; its untracked `docs/upgrade/*inventory*` files and 2026-10-27 spec copy differ from the committed versions and were left alone). `origin/master` has no branch protection; the fork's only workflow on master after the push is `issue-triage.yml`, so the push triggers no deploy.
- 2026-11-03 — **Commit `633b8480` "Group NodeODX options in WebODM" (3.1.2 only) is not cherry-picked.** 3.3.1's `EditPresetDialog.jsx` already has `OPTION_GROUP_MAP`; a simulated cherry-pick conflicts in JSX and SCSS. Phase B adds a `tapis` group to `OPTION_GROUP_MAP` instead.
- 2026-11-03 — **Root cause confirmed by user:** the affected account lacked the ls6 TMS credential; creating it through the Tapis portal fixed submission. Test plan 0b's "TMS credential works end to end" is satisfied; 0a (probe shape for a credential-less account) remains open and gates only the deferred Start-blocking rule.
- 2026-11-03 — **TAS verified:** `BCS26030` "Open Drone Map Suite" Active Lonestar6 2026-06-23 → 2027-06-30, 0/12,500 SU. Resource filter already LS6-only. Local gate lists only `PT2050-DataX`.
- 2026-11-03 — **Team review synthesis.** Design reviewer: approvable after fixes (applied). Architect: revise, small; all five must-change items adopted (explicit-signal `missing`, keep `EditTaskForm` mounted + controlled prop + callback, `code` field + `system_id` param, dedicated request code with timeouts, double-submit guard). Security: acceptable with changes; items 1–3 adopted as hard requirements (fresh-probe precondition, lock and cooldown, identity from user/token, tenant-matched token and host binding, throttling), items 4–7 adopted (explicit permission class, URL quoting and regex, capped `detail`, keyed cache cleared on logout/POST). Tester: needs fixes; adopted (SimpleTestCase + `requests.request` patch target, LocMem cache override, `$` global pattern, rule-1 fallback, 10-row recommender table, at-risk test list). Skeptic: revise; adopted (a) warn-only, (b) job-shape issue surfaced as B.5 decision, (c) LS6-only filter confirmed and no silent allocation fallback in the wizard, (d) task-failure recovery, (f) rollout dissent recorded; (e) "shrink Phase B to node defaults only" **not adopted** because goal cards and run-size guidance are the user's stated ask and the flag limits exposure. Disagreement between architect (keep catalog) and skeptic (cut catalog) resolved in favour of keeping a minimal catalog.
- 2026-11-03 — Browser-side status cache dropped (security/architect): server cache only.

- 2026-11-03 — **Pushes approved and done:** `origin/master` fast-forwarded to a725bfc8; PR #23 retargeted to `master`; Phase C on `feature/allocation-default-bcs26030` → PR #24; DSO docs commits pushed.
- 2026-11-03 — **Phase A implemented** (`feature/hpc-access-check`, PR #25, stacked on master). Service `app/services/tapis_credentials.py`, API `GET/POST /api/tapis/hpc-access/`, `HpcAccessBanner` on the dashboard, above the new-task buttons and inside a failed task whose error mentions `SYSTEMS_MISSING_CREDENTIALS`. Warn-only as decided. QA pass applied: banner silent for `no_tapis_token`/`misconfigured`/throttled, allocations fetched only on `missing`, `create_failed` message, bounded echo of invalid `system_id`. Tests: 36 backend + Jest suites, all green. Deviations from the spec text: positive cache TTL default is 600 s (spec said 10 min — same); `sessionStorage` dropped per review; GET returns 400 for a malformed `system_id` and 429 when throttled (spec said "always 200"; docs updated).
- 2026-11-03 — **Phase B implemented** (`feature/task-wizard`, stacked on PR #25). `NewTaskPanel` keeps the legacy render when `WO_UI_TASK_WIZARD` is off; when on it adds a step header, `ProcessingGoalStep` cards, `ComputePlanStep` (allocation + `ComputeRecommender` plan with reasons/warnings/suggestions and an Adjust panel) and a review step. `EditTaskForm` stays mounted on every step and gains `onStateChange`, `tapisOverrides` (→ `applyTapisOverrides`) and `selectPresetByName`; `EditPresetDialog` gains a `tapis` group ("HPC Job Settings") and a `hiddenGroups` prop. `GET /api/tas/allocations/` now also returns `preferred` so the client can apply the "preferred if held, else the single allocation, else choose" rule without a silent first-allocation fallback. Recommender outputs structured codes; `ComputePlanText` renders them. Deviation: the quality uplift is a suggestion with an Apply link (never applied automatically), as the architect asked.
- 2026-11-03 — **B.5-fix implemented in ClusterODX** (`feature/tapis-queue-aware-job-shape`, wmobley/ClusterODX PR #7): `getJobShapeForQueue()`; `coresPerNode`/`memoryMB` follow the requested queue's mapping tier when one exists; `shapeSource` logged; provider test extended; `docs/tapis.md` updated. Done in a separate worktree because the main ClusterODX checkout carried another session's uncommitted work on a different branch.
- 2026-11-04 — **Probe fix (`fix/hpc-probe-files-401`).** In production wmobley saw "Could not confirm HPC access: Your TACC sign-in has expired" right after logging in. The webapp log showed `code=token_expired` *after* the local expiry check had passed, so the 401 came from Tapis. Reading the Tapis Systems and Files sources: `GET /v3/systems/credential/...` is denied for every user token (`AuthUtils.checkAuthUser`, `case getCred` → `ForbiddenException`, 403), so stage 1 never produced `ready` or `missing`; the Files listing then maps every SSH login failure to `NotAuthorizedException` (401), including `SSH_POOL_MISSING_CREDENTIALS` for a user with no credential. The probe therefore reported `token_expired` for both a missing and a rejected key, and the POST precondition (`missing`) could never be met, so one-click setup was unreachable. Fix: single Files probe; `SSH_POOL_MISSING_CREDENTIALS` added to the missing signals and checked before the status code; 401 is `token_expired` only for `TAPIS_SECURITY_JWT_*` messages, otherwise the new code `ssh_auth_failed` (unknown, advisory, detail shown). Test plan item 0a (probe shape for a credential-less account) is now derived from source rather than observed; still to confirm against a real credential-less account.
- 2026-11-03 — **Test harness notes (not in the repo):** no 3.3.1 Docker image exists locally; backend tests ran in the 3.1.2 image with `pyodx` and a few pure-Python deps installed into a throwaway container and the worktree mounted at `/src`. Jest ran with the old checkout's `node_modules` via `NODE_PATH` because the worktree has no `package-lock.json`. Pre-existing failures on `master`, unrelated to this work: `test_api_preset.test_preset` (password login) and two tests in `test_tapis_oauth2_tokens`.

## User feedback / decisions

- 2026-11-03 — User request, mapped to parts: (1) confirm credential at login and prompt to create → Part A; (2) wizard on upload to pick output and optionally change options → Part B steps 1 and 3; (3) default allocation BCS26030 → Part C; (4) tell users when to pick a different queue and time, with intelligence from run size and selections → Part B step 2.
- 2026-11-03 — User: "we can bring 3.3.1 to our forked main if it hasn't, then start from there." → target branch decision above.
- 2026-11-03 — User: already confirmed the issue was the TMS key and fixed it through Tapis's portal. → Test plan 0b satisfied; probe script not run.
- 2026-11-03 — User decisions: (1) B.5-fix approved (small ClusterODX change so cores/memory follow the chosen queue); (2) asked whether work stays on the fork — yes, `origin` is In-For-Disaster-Analytics/WebODM; explicit push approval still pending; (3) allocation gate: add `BCS26030`, approved; (4) seven goal cards kept "for now"; (5) removing the dead legacy preset keys approved. Proposals 6–8 (warn-only, import panel unchanged, click-to-create) stand unchallenged.
- 2026-11-03 — Phase C implementation started: `webodm/settings.py` and `app/services/tas_allocations.py` default → `BCS26030`; `app/boot.py` legacy keys removed from Default and LS6 Small; `.env.sample` and `README.md` updated; tests added in `test_tas_allocations.py` and `test_api_preset.py`; DSO docs (`services/webodm.md`, `dev/environment-variables.md`) updated locally, not yet committed. Note: `coreplugins/embeddings/embeddings_client.py` also charges `-A {TAS_DEFAULT_ALLOCATION}` for embedding jobs, so the default change moves those to BCS26030 wherever the env var is unset.
- 2026-11-03 — **Phase C tests.** Ran `app.tests.test_tas_allocations` and `app.tests.test_api_preset` against the worktree inside the local `webodm:ls6-checkpoint-local` image (3.1.2-era; `pyodx` and a few pure-Python deps installed into a throwaway container; worktree mounted at `/src` because a bind mount at `/webodm` is shadowed). Result: 8 of 9 pass, including the two new tests (`test_default_prefers_configured_allocation_regardless_of_order`, `test_system_presets_carry_no_legacy_cluster_keys`). The failure, `TestApiPreset.test_preset`, also fails identically on untouched `master` (verified in a scratch worktree): it uses `client.login(username, password)`, which Tapis-only authentication no longer honours, so the presets GET is anonymous and returns 403. Pre-existing, out of scope; candidate for a separate fix (log in via `force_login`). Phase C is on branch `feature/allocation-default-bcs26030` in the master worktree, uncommitted pending user approval.

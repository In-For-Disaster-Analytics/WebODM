# Submit OpenSplat LS6 jobs from WebODM

## Status
Implementing

## Objective
Connect the existing Splats dialog to LS6 training, status monitoring, and result attachment so users can test the complete round trip.

## User need
Select Train on LS6 on an existing processed task; see preparation, queue, training, and import status; view the resulting splat without downloading training ZIPs or manually uploading results.

## Current code/system summary
WebODM 3.3.1 has SplatsDialog, allocation-guarded upload, process_splats conversion, shared media task images/assets, and stored Tapis OAuth2 tokens. Existing tokens expose get_valid_access_token(). App opensplat-ls6/0.2.0 prepares WebODM manifests on LS6, but its fixed input allowlist accepts only one operator snapshot. Its archive currently targets the submitting user's Scratch. The live WebODM image has no new submission integration. Implementation checkout is .worktrees/webodm-3.3.1. DSO architecture docs at the prescribed external volume are unavailable.

## Proposed design
Add an opt-in Train on LS6 action to SplatsDialog. Use the logged-in user's existing valid Tapis token; never a registration/service token. Require both task project edit permission and existing allocation permission on every mutation. Only the submitting user may refresh/import their run; project readers may see a sanitized status summary. Do not accept client-supplied paths, app IDs, job UUIDs, or result URLs.

Persist one SplatRun record per attempt with task, submitting user, immutable run UUID, state, Tapis job UUID, settings, snapshot location, expected result location, conversion job ID, timestamps, and sanitized error. Enforce at most one active run per task using a transaction and task row lock. States: preparing, submitting, submission_unknown, queued, running, importing, ready, failed, canceled. Do not automatically retry ambiguous job submission: reconcile by a unique run identifier through the user's jobs before resubmitting. Prevent repeat imports with row locks/state transitions. Existing splats remain until successful conversion replaces them.

A Celery task stages only task-selected cameras, shots, colored point cloud, and registered JPEGs into a new shared MEDIA_ROOT/splats-runs/<run UUID>/input directory. Validate source paths against this task and existing authorized import roots; reject missing or changed assets, unknown cameras, duplicate filenames, oversized inputs, and symlink escapes. Copy files instead of hard links for immutable snapshots. Write the versioned manifest atomically, with the actual RTC offset from the same task. No photogrammetry or COLMAP conversion happens on WebODM. Default test settings: 100 iterations and 1920 maximum image size, bounded server-side. Disk usage must include source snapshots plus returned model; initial per-run input limit 10 GiB and 2000 images.

Map local shared paths to verified LS6 paths using explicit server settings. Deploy a distinct candidate app version for the WebODM staging root; retain 0.1.1 and 0.2.0. The candidate app writes its final PLY and provenance to a run-specific directory under shared storage accessible to WebODM and LS6. Keep training working data in Scratch. Validate that output-path overrides are supported by the registered Tapis contract; otherwise add an explicit validated output-directory argument to a new launcher/app version before integration. Do not assume Scratch is mounted on WebODM or mutate fixed input allowlists on existing versions.

Submit through the user's OAuth token using the existing configured Tapis tenant and bounded HTTP timeouts. Persist only run/job identifiers, never tokens in Celery arguments, manifests, browser responses, or logs. Background operations reload the user's token from the database and pause with a sign-in-required state if it has expired. The UI refreshes status through a POST sync endpoint; GET remains read-only. Sync verifies job ownership and app/version, maps Tapis status, and dispatches one import on successful completion. A scheduled reconciler can be added later; first milestone completes while the dialog is open and resumes on reopen.

Import only the expected run-local PLY after job success; require canonical containment, regular file, size limit, and provenance/task/run match. Reuse existing process_splats conversion through a helper that reports success/failure to SplatRun and atomically replaces model.rad only after conversion succeeds. Never infer success merely from a Celery task finishing. Refresh available_assets and size; UI exposes View Splats after ready. Cancel uses the owning user's token and does not delete already produced models.

## Files likely affected
WebODM: app/models/splat_run.py and models/__init__.py, app/migrations/0058_splat_run.py (verify actual leaf before writing), app/services/opensplat.py, app/api/splats.py and api/urls.py, worker/tasks.py, webodm/settings.py, SplatsDialog.jsx and its tests, backend tests, deployment documentation. OpenSplat: candidate app specification, launcher validated output argument if required, tests and docs. Existing unrelated edits must be preserved.

## API/schema changes
Add SplatRun model and migration. Proposed task-scoped endpoints: POST splats/runs (create), GET splats/runs (latest sanitized status), POST splats/runs/<run>/sync, POST splats/runs/<run>/cancel. Every run lookup is task-scoped and permission-checked. Add explicit enable, local/LS6 staging path mapping, app/version, input limits, and shared output settings. Return feature availability so an unconfigured deployment shows no submit action.

## Data flow
Authenticated task editor -> create run -> Celery snapshot -> user-token Tapis submission -> LS6 app-side COLMAP preparation and CUDA training -> shared run-local PLY/provenance -> authenticated sync -> Celery conversion -> task Splats viewer.

## Risks and tradeoffs
Snapshot copying can be large and remains WebODM I/O work; conversion moves to LS6. Shared storage permissions must work for WebODM service identity and Tapis execution identity without broadening unrelated task access. Token expiry must be recoverable without duplicate submission. Shared-output contract and Tapis app access must be validated before deployment. Existing process_splats suppresses exceptions into result dictionaries, requiring explicit error propagation. Schema rollout requires backup and migration. GPU training/visual alignment remain unverified.

## Alternatives considered
Manual app submission and upload: already supported but does not meet requested UI workflow. Putting run state in Task.media or plugin data: avoids migration but mixes unrelated state and weakens concurrency/ownership enforcement. Service-account submission: rejected because it bypasses user Tapis identity and allocation. Downloading Scratch results through Tapis Files API: possible fallback, but adds network transfer and credentials dependency; prefer verified shared output.

## Test plan
Backend: task/project/allocation authorization, cross-user runs, expired tokens, malicious paths, bounded staging, preserved offset, one active run under concurrency, submission ambiguity/reconciliation, status mapping, cancel, result containment/provenance, duplicate import, conversion failure preserving existing model. Mock Tapis for deterministic tests and use a database for locks/migration checks. Frontend: disabled/unavailable feature, submit/progress/error/re-auth, resume on reopen, cancellation, ready/view. Run existing splat and OAuth tests plus frontend tests/build. Verify candidate app contract with dry-run and then separately approved real UI submission, LS6 training, return import, and alignment against the original point cloud.

## Documentation plan
Document settings, exact mount mapping, job lifecycle, permissions, reauthentication, deployment commands, operator recovery, and cleanup. Update DSO service/auth/environment/startup docs when accessible before production rollout.

## Rollout/rollback plan
Implement and validate locally first. Feature disabled by default. Prepare a distinct versioned LS6 app and WebODM test image. Before live deployment: verify shared paths, backup database/config, inspect migration plan, apply migration and enable for an operator test. User approval required for concrete external deployment changes. Rollback disables feature; retain run records, source task assets, existing splats, old image, and existing app versions. Do not automatically delete shared snapshots or cancel jobs on rollback.

## Open questions
Verify Tapis output-directory override semantics versus explicit new launcher argument; choose one before implementation. Verify WebODM host/service and LS6 user can access the selected shared run root. Confirm exact allocation metadata required by Tapis job submission from existing deployment. Choose retention after measuring real snapshot sizes.

## Decisions
### 2026-10-28 - Connect the task dialog to the existing LS6 app
User requested WebODM submission integration for testing. Reuse user OAuth credentials, app-side preparation, and the existing viewer; use a durable run model and explicit shared result contract. No production deployment or new database migration has run.

### 2026-10-28 - Implementation (local, not deployed)
- User said "implement this"; treated as approval of the spec.
- Output-directory question resolved: the app already writes `opensplat-<job uuid>.ply` and `.manifest.json` to the job output dir, and Tapis lets a submission override `archiveSystemDir`, so no launcher or app change is needed. Unverified against the live tenant.
- Deviation: added an `awaiting_signin` state (the spec required pausing on expired tokens but listed no state for it).
- Deviation: shared-path settings are four explicit variables (staging local/LS6, output local/archive) rather than one mapping.
- Deviation: `process_splats` now delegates to a new raising `convert_splats`; its result-dict behavior is unchanged.
- Follow-up, also implemented: periodic reconciler task, re-queue of stale `importing` runs (10 min), and `cleanup_splat_runs` command.
- Not done: real LS6 submission/alignment acceptance.
- Existing backend tests that call `client.login(...)` fail in this Tapis-only fork; the new tests use `force_authenticate`.

## User feedback / decisions
User said “lets do that so we can test it” and “continue”. This concrete design is presented for the repository's Major-task design approval gate before implementation.

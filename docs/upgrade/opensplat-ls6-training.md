# Train on LS6 (OpenSplat via Tapis)

Adds a **Train on LS6** action to a task's Gaussian Splats dialog. It snapshots the task's
registered assets to shared storage, submits the `opensplat-ls6` Tapis app with the signed-in
user's own Tapis token, follows the job, and attaches the resulting splat to the task.
Disabled by default; an unconfigured deployment shows no action.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `WO_OPENSPLAT_ENABLED` | `NO` | Master switch. Also requires `WO_TAPIS_BASE_URL` and the four paths below. |
| `WO_OPENSPLAT_STAGING_ROOT` | – | Directory WebODM writes per-run input snapshots to (`<root>/<run uuid>/input`). |
| `WO_OPENSPLAT_STAGING_LS6_ROOT` | – | The same directory as seen from LS6. Must be inside the app version's `OPENSPLAT_IMPORT_PATH_ROOTS`. |
| `WO_OPENSPLAT_OUTPUT_ROOT` | – | Directory WebODM reads results from (`<root>/<run uuid>/`). |
| `WO_OPENSPLAT_OUTPUT_ARCHIVE_ROOT` | – | The same directory as the Tapis archive system sees it. Sent as `archiveSystemDir`. |
| `WO_OPENSPLAT_ARCHIVE_SYSTEM_ID` | `cloud.data` | Tapis archive system holding the output root. |
| `WO_OPENSPLAT_APP_ID` / `_APP_VERSION` | `opensplat-ls6` / `0.2.0` | App submitted. Use a candidate version registered for the staging root; 0.1.1 and 0.2.0 stay untouched. |
| `WO_OPENSPLAT_MAX_INPUT_BYTES` | 10 GiB | Per-run snapshot limit. |
| `WO_OPENSPLAT_MAX_IMAGES` | 2000 | Per-run image limit. |
| `WO_OPENSPLAT_MAX_RESULT_BYTES` | 8 GiB | Largest result that will be imported. |
| `WO_OPENSPLAT_HTTP_TIMEOUT` | 30 | Seconds for each Tapis request. |

The staging and output roots must be writable/readable by the WebODM web and worker
containers (the worker stages and imports), and the matching LS6/Tapis identities must be able
to read the snapshots and write the archive. Training working data stays in LS6 Scratch.

## Job lifecycle

`preparing` → `submitting` → `queued` → `running` → `importing` → `ready`, plus
`awaiting_signin`, `submission_unknown`, `failed`, `canceled`. At most one run per task is
active (enforced by a partial unique index).

* **Staging** copies (never hard-links) `cameras.json`, `shots.geojson`, the colored point
  cloud (`cloud.laz`) and the registered JPEGs into `<run>/input`, then writes
  `webodm-input.json` atomically, including the task's RTC offset. Missing/duplicate images,
  unknown cameras, non-JPEGs, symlink escapes and over-limit inputs are rejected.
* **Submission** uses the submitting user's valid Tapis token, loaded from the database inside
  the worker (tokens are never passed as Celery arguments or stored on the run). Training
  defaults to 100 iterations and 1920 px images; both are bounded server-side.
* **Ambiguous submissions** (timeout or 5xx) are never retried. The run enters
  `submission_unknown`; a sync looks the job up by its unique name `webodm-splat-<run uuid>`
  and either adopts it or fails the run so the user can start a new one.
* **Sync** is `POST …/splats/runs/<run>/sync`, called by the dialog every 15 s while open and on
  reopen. It verifies job name/app/version, maps the Tapis status and, on `FINISHED`, queues
  exactly one import. `GET` is read-only.
* **Import** only accepts `opensplat-<job uuid>.ply` plus its provenance manifest from the run's
  output directory: regular files within the directory, under the size limit, with matching
  app id, task id, run id and SHA-256. The existing `splats.rad` is replaced only after
  `splat-tools` succeeds; on failure the previous model is kept.

## Permissions and re-authentication

Every mutation requires the project `change_project` permission and the existing allocation
gate. Only the submitting user can sync or cancel a run. Other project viewers see a sanitized
status (no job id). If the user's Tapis token has expired, a new run is refused (401) and an
in-flight run pauses in `awaiting_signin` until the user signs in again and the dialog syncs.

## Deploying

1. Verify the staging/output roots exist and the path mappings are correct from both sides.
2. Back up the database, then run `python manage.py migrate` (adds `app_splatrun`, migration `0058`).
3. Set the variables above and restart web and worker; enable for an operator test first.
4. Roll back by setting `WO_OPENSPLAT_ENABLED=NO`. Run records, snapshots, results and existing
   splats are kept; nothing is deleted and no job is canceled automatically.

## Operator notes

* **Reconciler:** a Celery beat task (`reconcile_splat_runs`, every 60 s) syncs queued, running,
  unknown and importing runs with their owner's stored token, so runs finish with the dialog
  closed. Owners whose Tapis session expired are skipped until they sign in again.
* **Stuck imports:** an import with no progress for 10 minutes (e.g. after a worker restart) is
  re-queued by the next sync or reconciler pass. The import claim makes duplicates harmless.
* **Cleanup:** snapshots and results are kept until you remove them:
  `python manage.py cleanup_splat_runs --days 30 [--dry-run]` deletes the per-run directories of
  ready/failed/canceled runs older than that. Active runs are never touched.
* The Tapis job search (`name.eq.<name>`) and `archiveSystemDir` override are used as
  documented for Tapis Jobs v3 but have not yet been exercised against the live tenant.

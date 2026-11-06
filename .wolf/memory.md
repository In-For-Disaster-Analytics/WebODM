# Memory

> Chronological action log. Hooks and AI append to this file automatically.
> Old sessions are consolidated by the daemon weekly.

## Session: 2026-07-16 14:14

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|

## Session: 2026-07-22

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| 15:00 | Read app/auth/tapis_oauth2.py, app/api/tapis_oauth2.py, app/views/tapis_auth.py as reference; built equivalent Tapis OAuth2 backend for Label Studio (separate repo: ../label-studio-tapis-auth/) with real JWT signature verification; built+booted Docker image, verified login redirect + state-mismatch handling + forged-token rejection against live tacc.tapis.io | ../label-studio-tapis-auth/**, WebODM/.wolf/buglog.json (bug-003), WebODM/.wolf/cerebrum.md | Working, verified end-to-end except the live Tapis authorize/token round-trip (needs a real registered client) | ~large |

## Session: 2026-07-31

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| — | User reported live 401 "Authentication credentials were not provided" from Label Studio project-create; found via WebFetch/WebSearch against Label Studio's real docs that a Personal Access Token is a JWT refresh token, not a usable Bearer token -- must be exchanged via POST /api/token/refresh first. Added exchange+cache+retry-on-401 to label_studio_client.py; security-reviewer flagged that the refresh endpoint's raw error body could leak the token to the browser via api_views.py's Response({'error': str(e)}) pattern -- sanitized that one path. Added coreplugins/embeddings/tests.py (none existed before for this plugin). | coreplugins/embeddings/label_studio_client.py, coreplugins/embeddings/tests.py (new), WebODM/.wolf/buglog.json (bug-004), WebODM/.wolf/anatomy.md | Fixed and dry-run-verified locally (Django not installed in this environment, so verified via importlib path-loading + mocked requests/settings, not the real ./webodm.sh test backend runner) | ~medium |

## Session: 2026-08-07

| Time | Action | File(s) | Outcome | ~Tokens |
|------|--------|---------|---------|--------|
| — | User reported (via browser console) a 502 on POST .../labels/apply and embed-generate stuck showing 'running' forever with no way to restart. Got the exact Label Studio 400 body from the user, root-caused it to the 50-char title limit; added `_label_studio_title()` truncation helper, applied at both TaskLabelView and TaskLabelApplyView call sites (Trivial tier, applied directly). For the stuck-running bug, user's explicit instruction was "time out ... but if not all embeddings are complete we need to offer to continue" -- added `embeddings_client.get_last_embed_generate_activity()`, `WO_EMBED_GENERATE_TIMEOUT_MINUTES` setting (default 75, derived from ls6's real maxMinutes=60), and a pure `_embed_status_value()` helper returning 'timed_out' vs 'running'; frontend (EmbeddingsPanel.jsx) stops polling and shows a "Continue" button on timeout, re-POSTing /embed with the known site_id (safe/idempotent per Decision 56's upsert). Added unit tests (LabelStudioTitleTests, EmbedStatusValueTests) to tests.py. | coreplugins/embeddings/api_views.py, coreplugins/embeddings/embeddings_client.py, coreplugins/embeddings/public/EmbeddingsPanel.jsx, coreplugins/embeddings/tests.py, webodm/settings.py, WebODM/.wolf/buglog.json (bug-005), WebODM/.wolf/anatomy.md, WebODM/.wolf/cerebrum.md | Both fixed; verified via ast.parse (Python) + Babel parse (JSX) only -- could not run ./webodm.sh test backend (Django not installed locally, Docker not running in this environment) | ~large |
| 07:45 | Drafted output-driven wizard spec (supersedes Part B of 2026-11-03 spec); branch feature/output-driven-wizard off a3da83d7 | docs/design/2026-11-06-output-driven-task-wizard.md | spec In Review, pending design-reviewer + architect/skeptic | ~9k |
| 07:53 | Spec revision 2 after design-reviewer/architect/skeptic; ultra rule -> normal (development unreachable + no mapping shape), optionsOverride contract, edit mode has no base, two-PR split proposed; 7 user confirmations pending | docs/design/2026-11-06-output-driven-task-wizard.md | In Review | ~12k |
| 08:04 | Spec revision 3: Will approved items 1,3,4,6,7; ultra small jobs start on development (ClusterODX shapeOnly mapping prerequisite); factors ship at 1.0 pending calibration runs; Tapis failure forwarding proposed for PR 2 | docs/design/2026-11-06-output-driven-task-wizard.md | Approved for PR 1 | ~6k |
| 08:14 | Added Part D / PR 0 run records (TaskRun table, exportruns/backfillruns, log.json stage times) to the wizard spec at Will's request; pending approval | docs/design/2026-11-06-output-driven-task-wizard.md | spec updated | ~5k |
| 08:24 | PR 0 run records committed on feature/task-run-records (TaskRun model, 0060 migration, exportruns/backfillruns, 8 tests green); ClusterODX shapeOnly committed 6ddf38e | app/models/task_run.py, app/models/task.py, ClusterODX libs/asr-providers/tapis.js | done, not pushed | ~8k |
| 08:28 | PR 0 QA fixes (duplicate window, null processing time, CommandError) amended into 8bb40718 successor; 10/10 Django tests green via docker recipe | app/models/task_run.py, exportruns.py, test_task_run.py (run-records worktree) | done | ~5k |
| 08:40 | PR 1 wizard committed b36c4582 (224 Jest green); QA ship-with-fixes; 11 fixes sent to implementer incl. Point cloud<=>Fast mode binding, pc-filter in base, use-3dmesh drop, baseRemovals | app/static/app/js/{classes,components} | fixes in progress | ~14k |
| 09:13 | Provenance keys: TaskRun gets task_uuid/tapis_job_id/tapis_job_name via new ClusterODX GET /task/<uuid>/tapis (053d9c4 on feature/task-tapis-job-lookup); PR 0 amended, 12/12 tests | app/models/task_run.py, nodeodm/models.py, ClusterODX libs/proxy.js | done, unpushed | ~12k |
| 09:26 | Found LS6 partial restarts impossible (worker torn down 10 s after commit); Will chose to make them real + versions; drafted cross-repo spec odm-suite/docs/design/2026-11-06-task-versions-and-resumable-reruns.md on top of the existing nodeodx-ls6 checkpoint/resume library | docs/design (both) | Draft, unreviewed | ~20k |
| 09:36 | Resume/versions spec revision 2 after design-reviewer/architect/skeptic; found ClusterODM fork already has resume routing (1550e5b, 1d978a7) to port to ClusterODX | odm-suite/docs/design/2026-11-06-task-versions-and-resumable-reruns.md | In Review; 5 open questions for Will | ~25k |

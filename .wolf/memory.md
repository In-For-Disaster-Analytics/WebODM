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

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

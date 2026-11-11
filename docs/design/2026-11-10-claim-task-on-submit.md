# Claim a task on submit (run under the submitting user's Tapis identity)

## Status

Implementing (backend done and tested on branch feature/claim-task-on-submit; UI and submit-guard test pending)

## Objective

Let any project member with edit permission submit a task and have it run under *their own* Tapis
token, instead of failing when the project owner's token is missing or expired.

## User need

On 2026-11-10 a teammate tried to run "Nunapitchuk - 8/8/2026" (task `4645b29c-…`, project owner
`danielbutcher2010`). The worker logged `Could not obtain a valid JWT token for user
danielbutcher2010` ~12,000 times in 30 h (a ~5 s retry loop). ClusterODM answered HTTP 502, then
accepted a task with no Tapis job behind it ("no task found for this token"), and WebODM marked it
failed with `tapis_job=None` and an empty `last_error`. The teammate's own ls6 / cloud.data
credentials were `ready` and were never used.

## Current code/system summary

- `Task._get_tapis_jwt_token()` ([app/models/task.py:1558](../../app/models/task.py)) always
  resolves the token from `self.project.owner`. If none is valid it returns `None` and the caller
  proceeds unauthenticated.
- It is called for submit (`process_new_task`, ~L760), cancel (~L794), restart (~L812), remove
  (~L860) and the status poll (`get_task_info`, ~L888), all inside Celery `Task.process()`, which
  has no knowledge of the requesting user.
- API entry points (`commit`, `restart`, `cancel`, `remove` in
  [app/api/tasks.py](../../app/api/tasks.py)) know `request.user` and check project permissions
  with `check_project_perms`, then enqueue `process_task`. They do not record the actor.
- ClusterODM routes tasks per token ("no task found for this token"), so every later call for a
  task (info, cancel, remove, output download) must use the same identity that submitted it.
- `TapisOAuth2Token.get_valid_access_token()` ([app/models/oauth2.py:256](../../app/models/oauth2.py))
  already handles refresh via `refresh_token`.

## Proposed design

1. Add nullable `Task.submitted_by` (FK to `auth.User`, `SET_NULL`). It is the identity used for all
   node calls for that task.
2. Set `submitted_by = request.user` in the API actions that start work: `commit` (first
   submission) and `restart`. This is the "claim": acting on a task makes you its runner.
3. Change `_get_tapis_jwt_token()` to resolve the user as `submitted_by or project.owner`. All node
   calls (submit, poll, cancel, remove) go through it, so they stay on one identity.
4. Fail fast: if no valid token for the resolved user, do not call the node. Call `set_failure()`
   with a clear message ("Tapis session for <user> is missing or expired - <user> must log in to
   WebODM, then restart"). This removes the 5 s retry loop and the empty `last_error`.
5. UI: when a user submits/restarts a task whose `submitted_by`/owner is someone else, show a
   confirmation ("This task will run under your Tapis account and allocation"). Display
   "Submitted by" on the task card.
6. Cancel/remove by a *different* user than `submitted_by` keep using `submitted_by`'s token; if
   that is unavailable, fail with the same clear message (no silent fallback to another identity).

Corral input access is assumed fine for team members (they belong to G-829114); no change there.

## Files likely affected

- `app/models/task.py` (field, `_get_tapis_jwt_token`, fail-fast guard)
- `app/migrations/0062_task_submitted_by.py` (new)
- `app/api/tasks.py` (`commit`, `restart`; serializer exposes `submitted_by` read-only)
- `app/static/app/js/components/TaskListItem.jsx` and the submit/restart confirm flow
- `app/tests/test_api_task.py` (or the existing Tapis-token tests)
- `docs/` (user-facing note)

## API/schema changes

- DB: one nullable FK column, additive and backward compatible.
- API: `Task` serializer gains read-only `submitted_by` (username). No new endpoints.

## Data flow

User clicks Run/Restart -> API checks `change_project`, sets `submitted_by=request.user`, enqueues
`process_task` -> worker resolves token from `submitted_by` -> ClusterODM/Tapis job created under
that user -> later polls/cancel/remove use the same identity.

## Risks and tradeoffs

- Allocation/accounting: the submitting user's allocation is charged (intended, per the decision).
- Existing in-flight tasks have `submitted_by = NULL`, so they keep using the owner (no behavior
  change).
- If the submitter later loses their Tapis session, polling that task fails until they log in. The
  fail-fast message must say whose session is needed, not just "expired".
- Restart by a different user switches identity for a task that ClusterODM already knows under the
  old token. Needs verification (see Open questions); may require a fresh submit, not `restart_task`.
- The WebODM checkout has uncommitted changes in `nodeodm/jwt_node_wrapper.py`; this work must not
  clobber them.

## Alternatives considered

- Transfer project ownership on claim: larger permission surface; rejected for now.
- Fail-fast only (no claim): clearer errors but still blocks teammates; kept as part of this design.
- Always use the acting user's token per request (no stored `submitted_by`): breaks the Celery poll,
  which has no request context.

## Test plan

- Unit: token resolution prefers `submitted_by`, falls back to owner; fail-fast when the token is
  missing (no node call made, `last_error` set).
- API: `commit`/`restart` by a non-owner with `change_project` records `submitted_by`; without
  permission returns 404/403 and records nothing.
- Regression: owner-submitted tasks behave as before; `submitted_by=NULL` tasks use the owner.
- Manual (staging first): non-owner restarts a failed task and a Tapis job appears under their user.
- Local backend tests follow the docker recipe in the 3.3.1 notes.

## Documentation plan

User-facing note on "who runs a task and whose allocation is used". Update the DSO-Architecture
WebODM service page if the API surface changes (`submitted_by` field).

## Rollout/rollback plan

Additive migration, deployed with the normal WebODM release. Rollback: revert code; the column is
nullable and unused by older code, so it can stay.

## Open questions

1. Can ClusterODM `restart_task` be called with a different token than the original, or must a
   restart by a new user create a fresh task/job?
2. Should the confirmation also require the claimer to have a `ready` ls6 credential (reuse the
   existing HPC access check)? Recommended yes.
3. Is the UI confirmation needed on every cross-user submit, or only the first?

## Decisions

- 2026-11-10: Use option 1, claim on submit, ownership unchanged (user decision).
- 2026-11-10: Fail-fast guard included (option 3 from the discussion).
- 2026-11-10: Corral access for team members assumed via G-829114 (user statement).
- 2026-11-10: Spec approved by user ("Do it"). Open questions 1-3 not yet answered; defaults used.
- 2026-11-10 deviation: fail-fast applies only at *submit*, and only for the primary ClusterODM
  node (`is_primary_clusterodm_node`, renamed from the private helper). Poll/cancel/remove keep the
  old unauthenticated fallback, so a transient token expiry cannot mark a running task failed.
  Plain NodeODM nodes never require a token and are unaffected.
- 2026-11-10 deviation: `submitted_by` is set on `commit` and `restart` only (not cancel/remove).
- 2026-11-10: Implemented on a worktree off `master` (3.3.1, migrations to 0059), not the 3.1.2 upgrade branch; migration is therefore 0060.
- 2026-11-10 deferred: cross-user confirmation dialog and "Submitted by" label in the UI, and the
  ls6 credential check on claim (open question 2).

## User feedback / decisions

Approved to implement on 2026-11-10.

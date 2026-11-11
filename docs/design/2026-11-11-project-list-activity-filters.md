# Project list activity filters and per-row task counts

## Status

Implemented on the master base (WebODM 3.3.1), branch `feature/project-list-activity-filters`; re-applied by hand from the 3.1.2 branch (see D16 and D17). Uncommitted; backend/frontend test results are recorded in the implementer's hand-off.

> Approval note: the user confirmed the User need section, chose `created_at` for the failed window
> (Q1), confirmed the null-status rule (Q3), and accepted the recommended answer for every other open
> question (see D14). Remaining `[ASSUMPTION — confirm]` markers are technical (guardian behavior,
> deploy) and are verified by the test plan during implementation.

## Objective

Let any user with several WebODM projects quickly narrow the project list to the projects that
matter right now: hide empty projects, and/or show only projects with queued, running, or recently
failed tasks. Each project row shows its task-state counts (for example "2 running · 1 queued ·
1 failed") so the state is visible without expanding the row.

Visibility does not change. Users see the same projects they see today; admins see all projects.

## User need

- **Primary user:** any WebODM user who owns or can access several projects (approved requirement:
  "benefits any user with several projects"). Expertise: drone/imagery analyst, not necessarily a
  developer.
- **Secondary users:** WebODM administrators (they see all projects and use the same controls).
- **Job-to-be-done:** find, at a glance, which projects have processing work in progress or that
  need attention, and skip the empty ones. (Confirmed by the user, 2026-11-11.)
- **Current pain:** (Confirmed by the user, 2026-11-11.) Today the list shows only project name and a
  "N Tasks" toggle. The task states are only visible after expanding each row, and the list has
  no way to hide empty projects. The per-row task data is task IDs only (`tasks` field), so the
  client cannot tell running from queued without loading each project's tasks.
- **Definition of success (user-observable):**
  1. A user can toggle "Hide empty projects" (default on) and "Active work only" (default off) and
     the list updates with a correct total page count.
  2. Each row header shows correct Queued / Running / Failed counts without expanding it.
  3. A non-admin user never sees a project they could not see before, with or without filters.
  4. The list is noticeably easier to scan with 20 rows per page. (Confirmed by the user.)

## Current code/system summary

Verified by reading the code on 2026-11-11 (repo: `WebODM/`).

**Project list API** (`WebODM/app/api/projects.py`)

- `ProjectViewSet` (line ~100) sets `queryset = Project.objects.prefetch_related('task_set').filter(deleting=False).order_by('-created_at')`.
  It does **not** override `get_queryset`, `pagination_class`, or `filter_backends`.
- `ProjectFilter` (line ~52) provides `search` (name, task-name, `#tag`, `##task-tag`, `@owner`).
  The name search annotates with `StringAgg("task__name")`, which joins the task table, and
  returns `qs.distinct()`.
- `ProjectSerializer` (line ~24) exposes `tasks = TaskIDsSerializer(many=True)`, which returns
  **task IDs only** (`WebODM/app/api/tasks.py` line ~56-58). It also calls `get_perms()` per row
  (line ~36) and reads `obj.owner.id` per row (line ~44). Both are existing per-row queries.
- `ProjectViewSet.paginate_queryset` (line ~125) returns **no pagination** when the `page` query
  parameter is absent. This is how `MoveTaskDialog` gets a plain array.

**Visibility (how non-admin scoping is enforced today)**

- `WebODM/webodm/settings.py` (lines ~351-363) sets `DEFAULT_PERMISSION_CLASSES =
  [DjangoObjectPermissions]` and `DEFAULT_FILTER_BACKENDS = [ObjectPermissionsFilter (rest_framework_guardian), DjangoFilterBackend, OrderingFilter]`.
- Because `ObjectPermissionsFilter` is listed first, it narrows the queryset to projects the user
  may view **before** `ProjectFilter` runs. Scoping is therefore a queryset narrowing that every
  later filter only adds to.
- `DEFAULT_PERMISSION_CLASSES` is object-level only, so list scoping comes entirely from the filter
  backend. `ProjectViewSet` has no `get_queryset` override today (it sets `queryset` at line ~110).
- **[ASSUMPTION — confirm]:** the exact behavior of `rest_framework_guardian`'s
  `ObjectPermissionsFilter` (including superuser handling) is taken from its usual design. The
  installed djangorestframework-guardian 0.3.0 source is not in the repo and was not inspected. The
  test plan verifies it directly.

**Pagination**

- `REST_FRAMEWORK['PAGE_SIZE'] = 10` (settings.py line ~361) is the **global** default for every
  DRF list endpoint. `ProjectViewSet` does not set its own page size, and no `page_size_query_param`
  is configured.
- `WebODM/app/static/app/js/components/ProjectList.jsx` hard-codes `this.PROJECTS_PER_PAGE = 10`
  (line 28), requests the page via `this.props.source` (line 63), and uses `json.count` to size
  pagination (line 69). **Conflict with the approved "10 → 20" change:** changing only the client
  would make the client expect 20 rows per page while the server returns 10. Pages would skip rows.

**Task status and timestamps** (`WebODM/app/models/task.py`, `WebODM/nodeodm/status_codes.py`)

- `Task.status` is an `IntegerField(null=True)` with choices QUEUED, RUNNING, FAILED, COMPLETED,
  CANCELED (line ~222-226, 248). Codes come from `pyodm.types.TaskStatus`
  (`nodeodm/status_codes.py` line 1-6).
- **Null status:** code paths that set `status = None` are (a) a QUEUED task whose processing node
  went offline. It is detached, its `uuid` is cleared, and it is reassigned (lines ~718-723).
  (b) A task waiting to be dispatched: `uuid` unset, no pending action, status None (line ~736).
  Null therefore means "created or reset, not yet dispatched". Counting null as queued is
  consistent with the code. **Confirmed**, with one caveat in Open questions (partial uploads).
- `Task.partial` (line ~281) means "waiting for information or files to be uploaded before being
  considered for processing." A partial task can have null status and is not queued for processing.
- **The Task model has only `created_at` (line ~258) as a timestamp.** There is no `finished_at`,
  `updated_at`, or status-changed field. "Failed in the last 7 days" cannot be measured by failure
  time today. See Open questions Q1.

**Client row rendering** (`WebODM/app/static/app/js/components/ProjectListItem.jsx`)

- `numTasks = data.tasks.length` (line ~689), from the ID list.
- The header shows "N Tasks" with an expand toggle (lines ~777-784), only when `numTasks > 0`.
- Precedent: the expanded row has a client-side text/tag filter over loaded tasks (lines ~786-822)
  and a sort that is passed to the tasks endpoint as `?ordering=` (line ~882).

**Callers of `/api/projects/`**

- `Dashboard.jsx` line ~57 builds `source` from URL query state (`Utils.toSearchQuery(q)`). New
  params must go into that state.
- `MoveTaskDialog.jsx` line ~47 calls `/api/projects/?ordering=-created_at` with no page and
  expects an array (`json.filter` at line ~49). Its behavior must not change.

**Tests that exist**

- Backend: `WebODM/app/tests/test_api.py` (52 references to `/api/projects/`), and per-feature files
  such as `app/tests/test_api_tags.py`.
- Frontend (Jest/enzyme): `app/static/app/js/components/tests/ProjectList.test.jsx`,
  `ProjectListItem.test.jsx`.

**Customization inventory**

- `WebODM/docs/upgrade/2026-10-27-webodm-customization-inventory.md` has no entry for project-list
  pagination or filters. Its only `ProjectListItem.jsx` reference (line ~208) is for directory upload.
  This change adds a divergence from upstream that is not inventoried yet (follow-up, below).

**`.wolf/` cross-check**

- `.wolf/cerebrum.md` has no project-list entries. `.wolf/anatomy.md` describes
  `ProjectListItem.jsx` as containing a "fileMap", which does not match the component's current
  code. Code was trusted over the anatomy note. `.wolf/` was not edited.

## Proposed design

### 1. Server: filters and counts (`app/api/projects.py`)

- **`hide_empty`** (BooleanFilter): when true, excludes projects with `total == 0`. Implemented
  as `Exists(Task)` (or `~Exists`) so no join is added.
- **`has_active_work`** (BooleanFilter): when true, keeps projects with at least one active task,
  where active = queued (as defined below) OR running OR failed within the window. Implemented
  with `Exists` predicates for the same reason.
- **Per-row counts** (list action only): `ProjectListSerializer(ProjectSerializer)` adds
  `task_counts`. The `ProjectViewSet.get_queryset` annotates the queryset with scalar correlated
  subqueries (`Subquery` + `Count` over `Task` filtered by `OuterRef('pk')`) for each bucket, so
  counts come back in the same SQL statement as the list.
- **Pagination:** a `ProjectPagination(PageNumberPagination)` with `page_size = 10` (unchanged
  default) and `page_size_query_param = 'page_size'`, `max_page_size = 20`, attached only to
  `ProjectViewSet`. The UI sends `page_size=20`. The global `PAGE_SIZE` is not changed.
  (See Alternatives for why not a global change.)

### 2. Client: list and row (`ProjectList.jsx`, `ProjectListItem.jsx`)

- `PROJECTS_PER_PAGE = 20` and every list request sends `page_size=20` explicitly, so client and
  server cannot disagree.
- Two controls in the project-list header: "Hide empty projects" (default **on**) and "Active
  work only" (default **off**). The UI always sends both params explicitly (`hide_empty=true|false`,
  `has_active_work=true|false`) so the URL and the API response are deterministic.
- Changing either filter resets `page` to 1. Without this, a filter that shrinks the result can
  leave the user on a page that no longer exists (404).
- The row header shows a count summary whenever `task_counts.total > 0`, not only when the row is
  expanded: for example "2 running · 1 queued · 1 failed" (zero buckets omitted). Strings use `_()`.
- Expanded task list, its filter, and its sort are unchanged.

### 3. Definitions (exact)

| Term | Definition |
|---|---|
| `total` | Count of all `Task` rows for the project, any status, including null status and `partial = true`. |
| empty project | `total == 0`. A project with only CANCELED or partial tasks is **not** empty. |
| `queued` | `status = QUEUED`, **or** `status IS NULL AND partial = false`. **[ASSUMPTION — confirm]:** excluding `partial = true` (Q3). |
| `running` | `status = RUNNING`. |
| `failed` | `status = FAILED` **and** `created_at >= now() - WINDOW`. `created_at` is the only timestamp on `Task` (decided, Q1/D11). It means "created in the last 7 days and failed", not time of failure. A restart resets status to null without changing `created_at` (task.py ~851). |
| `WINDOW` | One server setting, default **7 days**, e.g. `PROJECT_LIST_FAILED_WINDOW_DAYS = 7` in `webodm/settings.py`. Not a per-request API parameter. |
| active work | `queued > 0 OR running > 0 OR failed > 0`. Used by `has_active_work`. |

COMPLETED and CANCELED count toward `total` only.

### 4. Visibility guarantee (why the new filters cannot widen access)

- The `ObjectPermissionsFilter` narrowing runs first (settings.py DEFAULT_FILTER_BACKENDS order).
- `hide_empty`, `has_active_work`, `search`, and the count annotations only add predicates or
  scalar subqueries. None adds an `OR` across projects, a union, an unscoped `Project.objects`
  query, or a `.all()`.
- The counts are per project the user already sees, and task IDs for the same projects are already
  in the response (`tasks`). **[ASSUMPTION — confirm]:** the same users who can view a project can
  already list its tasks, so the status counts add no new exposure.

### 5. Query strategy and N+1

- Counts are correlated subqueries in the single list statement. Count SQL does not grow with
  rows on the page. The existing `tasks` prefetch returns IDs only (`TaskIDsSerializer`), so status
  is not available from it.
- Why not `Count('task')`: the existing name-search join (`task__name`) plus `.distinct()` would
  multiply rows, and the counts would be inflated. Subqueries avoid the join entirely.
- **Is `prefetch_related('task_set')` still needed?** **Yes, in v1.** The `tasks` field
  (ID list) reads `obj.task_set`, and that field is part of the existing response contract. The
  counts do not use it. The prefetch loads full `Task` rows, not just IDs, which is heavier than
  needed. Narrowing it with `Prefetch('task_set', queryset=Task.objects.only('id', 'project_id'))` is
  a behavior-preserving option (Q5).
- **Existing N+1 not fixed by this change:** `get_perms()` (serializer line ~36) and `obj.owner`
  (line ~44) each cost a query per row. Going from 10 to 20 rows doubles that existing cost. Measured
  in the test plan. Fixing it (for example `select_related('owner')`) is optional (Q6).

### 6. Explicit non-goals

- No change to visibility rules, permissions, or `ProjectSerializer`'s existing fields.
- No new model field, no migration (see Q1 for the one option that needs one).
- No change to the expanded task list, its sort, or its filter.
- **Sort by last activity: NOT APPROVED.** Listed only as an optional idea. It has no defined
  timestamp today (see Q1), so it is deferred and not designed here.

## Files likely affected

| File | Expected change |
|---|---|
| `WebODM/app/api/projects.py` | `ProjectFilter`: add `hide_empty`, `has_active_work`. `ProjectViewSet`: `pagination_class`, `get_queryset` (list-only count subqueries), `get_serializer_class` (list uses `ProjectListSerializer`). New `ProjectPagination` and `ProjectListSerializer` in the same file. |
| `WebODM/webodm/settings.py` | `PROJECT_LIST_FAILED_WINDOW_DAYS` (default 7). `REST_FRAMEWORK` global unchanged. |
| `WebODM/app/static/app/js/components/ProjectList.jsx` | `PROJECTS_PER_PAGE = 20`, send `page_size`, `hide_empty`, `has_active_work`; reset `page` on filter change; filter controls. |
| `WebODM/app/static/app/js/components/ProjectListItem.jsx` | Always-visible count summary in the project-links row. |
| `WebODM/app/static/app/js/Dashboard.jsx` | Probably no change: `source` is built from URL query state. Confirm when implementing. |
| `WebODM/app/static/app/js/components/tests/ProjectList.test.jsx`, `ProjectListItem.test.jsx` | Extend. |
| `WebODM/app/tests/test_api_project_list_filters.py` (new) | Backend tests (see Test plan). Follows the `test_api_*.py` convention. |
| `WebODM/docs/src/content/docs/reference/project.md` | Document new params and `task_counts`. |
| `WebODM/app/models/task.py` | **Only** if Q1 option (2) is chosen (a timestamp field). Otherwise unchanged. |

## API/schema changes

### Query parameters on `GET /api/projects/` (all new, all optional)

| Param | Type / allowed values | Default (API) | Behavior |
|---|---|---|---|
| `page_size` | integer, 1–20 | 10 (unchanged) | Only used when `page` is present. Values above 20 are clamped to 20 (DRF `max_page_size`). |
| `hide_empty` | `true` / `false` | `false` | `true` excludes projects with `total == 0`. |
| `has_active_work` | `true` / `false` | `false` | `true` keeps projects with `queued`, `running`, or `failed` > 0. |

- Existing `search`, `ordering`, `id`, `name`, `description`, `created_at` are unchanged.
- The UI sends `page_size=20`, `hide_empty` (default `true`), and `has_active_work` (default `false`).
- **Open:** invalid boolean values. django-filter `BooleanFilter` ignores unrecognized values and
  returns the unfiltered list (Q7).
- **Default-on `hide_empty` is UI-only.** If it were the API default, existing API clients would
  silently lose empty projects. The API default stays `false`.

### Response (list only)

Each item in a list response gains one key, `task_counts`:

```json
"task_counts": { "total": 4, "queued": 1, "running": 2, "failed": 1 }
```

- `failed` counts failures inside the window (Q1 applies).
- Detail, create, update, and duplicate responses are **unchanged** (they use `ProjectSerializer`).
- Existing fields, including `tasks` (ID list), are unchanged.

### Backward compatibility

- All defaults reproduce today's behavior: `page_size` default 10, `hide_empty=false`,
  `has_active_work=false`.
- `MoveTaskDialog` (no `page`) still gets an unpaginated array.
- Old clients (no `page_size`) still get 10 rows per page, so the server change does not break the
  current UI or external consumers. Rolling back the UI alone is safe (see Rollout).
- **Schema:** no database migration under the recommended Q1 option.

## Data flow

1. User toggles a filter or changes page → `ProjectList` updates the URL query state (history).
2. `Dashboard.jsx` rebuilds `source` (`/api/projects/?page=1&page_size=20&hide_empty=true&has_active_work=false&search=…`).
3. `ProjectList.componentDidUpdate` sees a changed params hash (the new params are not in its
   "ignore" list) and calls `refresh()`.
4. Server: `ObjectPermissionsFilter` (visibility) → `ProjectFilter` (`search`, `hide_empty`,
   `has_active_work` as `Exists` predicates) → `OrderingFilter` → `ProjectPagination` →
   `ProjectListSerializer` (`task_counts` subqueries, `tasks` IDs from prefetch, existing
   `get_perms`/`owner`).
5. JSON → `ProjectList` sets `projects` and `updatePagination(20, count)` → `ProjectListItem` renders
   the count summary in the header; the expanded task list still loads `/api/projects/{id}/tasks/`.

## Risks and tradeoffs

1. **Page-size desync (verified in code).** A client-only change to 20 would skip rows. Mitigated by
   the `page_size` param (server default stays 10). **Residual:** clients must send the param; the UI
   always does.
2. **"Failed in last 7 days" cannot be measured by failure time.** Only `created_at` exists, so the
   window currently means "created in the last 7 days and FAILED". A task created 30 days ago that
   failed yesterday would be missed. This is a real difference from the approved wording. See Q1.
3. **Null status over-counts queued.** Partial uploads (waiting for files or commit) have null status.
   Counting them as queued would overstate work. Mitigation: exclude `partial = true` (Q3).
4. **Join fan-out.** Counting with a join would collide with the name-search join and `.distinct()`.
   Mitigated by subqueries (and a test that compares counts with the ORM).
5. **Existing N+1 remains.** `get_perms` and `owner` cost one query per row. Doubling the page size
   doubles that cost. Measured, not fixed here (Q6).
6. **Prefetch still loads full Task rows.** The user intent "do not load every task" is met for the
   counts, but not for the existing `tasks` field. Narrowing the prefetch is optional (Q5).
7. **Stale page after a filter change.** Without a page reset, the user can land on a 404 page. Mitigated
   by resetting `page` to 1.
8. **Silent invalid params.** A malformed boolean returns an unfiltered list rather than an error (Q7).
9. **Upstream divergence.** The change touches a fork-customized view and list component. It will
   conflict on upgrades and must be inventoried (follow-up). Tradeoff accepted by the user.
10. **Failed as "active" is a judgment call.** Failed tasks needing no action can keep a project in the
    "active" list. Mitigated by showing the failed count separately (Q2).

## Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| Count in Python from the prefetched `task_set` | Rejected | Counts would load every task row, and the `hide_empty` and `has_active_work` filters still need DB-side logic over all projects, so pagination counts would be wrong. Approved requirement is server-side aggregation. |
| `Count('task')` annotations | Rejected | Join fan-out with the search annotation and `.distinct()`. |
| Separate `/api/projects/activity/` endpoint keyed by project ID | Considered, not chosen | Keeps `ProjectSerializer` untouched, but adds a second round-trip and two sources of truth that can drift from the list page. |
| Change global `REST_FRAMEWORK['PAGE_SIZE']` to 20 | Rejected | Changes every DRF list endpoint and external consumers. The `page_size` param gets the same UI result without that risk. |
| Client-side filtering of the current page only | Rejected | Pagination would be wrong: filters must run over the full result set. |
| Failed window: "all failed tasks" (no window) | Accepted alternative (user-recorded) | Honest with the data we have. Downside: old failures stay in the active list forever. |
| Failed window: `created_at` proxy | **Chosen (user, 2026-11-11)** | No migration; meaning differs from "failed in last 7 days" and the UI label says so. |
| Failed window: add nullable `failed_at`, set in `set_failure` (task.py ~1346-1351) and the node-poll FAILED path (~910, 972-974); migration 0052 (latest is 0051_task_submitted_by) | Rejected for v1 (user) | Correct semantics, but schema change at several status sites. Revisit if "failed yesterday, created last month" misses become a problem, or for sort-by-activity. |
| Per-state params (`has_queued`, `has_running`, `has_failed`) instead of one `has_active_work` | Pending (Q2) | More control, more surface. v1 uses one boolean. |
| Sort by last activity | **Not approved** | No activity timestamp exists (Q1). Deferred. |

## Test plan

**Backend** (new file `WebODM/app/tests/test_api_project_list_filters.py`; run with
`./webodm.sh test backend app.tests.test_api_project_list_filters`):

- **Visibility matrix:** owner, member with `view_project`, non-member, admin, and anonymous. For each
  user and each filter combination: filtered IDs ⊆ unfiltered IDs for that user, and no project the
  user could not see before appears. Snapshot the unfiltered list before the change to confirm
  no default-path change.
- **Empty definition:** project with zero tasks → empty. Project with only CANCELED → not empty.
  Project with only partial null-status task → not empty.
- **Active definition:** QUEUED, null non-partial, RUNNING, FAILED in window → active. Null partial,
  COMPLETED, CANCELED, FAILED outside window → not active.
- **Failed window boundary:** tasks at `WINDOW - 1 h` and `WINDOW + 1 h` created_at, with the setting
  overridden in test.
- **Counts match the ORM:** for each project in a fixture, `task_counts` equals a direct ORM
  aggregation (no fan-out with a name search applied).
- **Search interaction:** `search` plus `hide_empty`/`has_active_work` returns the intersection, with
  correct counts and no duplicates.
- **Pagination:** no `page` → unpaginated array (MoveTaskDialog case). `page` with no `page_size` → 10.
  `page_size=20` → 20. `page_size=50` → clamped to 20. `count` reflects the filtered total.
- **Query count:** with `CaptureQueriesContext`, the number of SQL statements that touch `app_task` is
  the same for 2 and 20 projects (proves count subqueries add no per-row queries). Record the
  guardian/owner per-row query count as a baseline (not a pass/fail on the existing pattern).
- **Shape:** `task_counts` present on list items; absent on detail, create, update responses.
- **Invalid boolean:** behavior matches the chosen answer to Q7.

**Frontend** (extend `ProjectList.test.jsx` and `ProjectListItem.test.jsx`; run with
`./webodm.sh test frontend`):

- Request URL contains `page_size=20`, `hide_empty`, `has_active_work`.
- `PROJECTS_PER_PAGE` is 20 and `updatePagination` gets 20.
- Changing a filter resets `page` to 1.
- Header summary renders the non-zero buckets; hidden when `total == 0`; visible when collapsed.

**Manual QA** (dev stack, once implemented): one admin and one non-admin account, each with three
projects (empty, queued/running, failed-only). Confirm visibility matches the pre-change build and
that the summary matches the task pages.

**Regression:** `MoveTaskDialog` project picker still lists projects. Expanded task list and its
filter/sort still work.

## Documentation plan

- `WebODM/docs/src/content/docs/reference/project.md`: document `page_size`, `hide_empty`,
  `has_active_work`, `task_counts`, and the definitions table. Only after the behavior is verified.
- `WebODM/docs/src/content/docs/reference/task.md` (or the project page): short note on null-status
  and partial-task semantics as used by the counts. **[ASSUMPTION — confirm]:** this page is the right
  home; it was not reviewed in this pass.
- **Follow-up (not part of this change):** add a new entry to
  `WebODM/docs/upgrade/2026-10-27-webodm-customization-inventory.md` for project-list pagination,
  filters, and row counts (divergence from upstream). The inventory file is governed by the upgrade
  process and is not edited by this spec.
- **Conditional:** if the global rule to update DSO-Architecture service docs applies to WebODM's
  `/api/projects/` change, that page must also be updated. The DSO-Architecture root was not checked
  in this pass (Q8).

## Rollout/rollback plan

- **Migration:** none under the recommended Q1 option. If the timestamp option is chosen, the spec
  must be updated with a migration, backfill decision, and a Major-tier re-review first.
- **Order:** server and client can ship together. The server change is backward compatible (defaults
  preserve behavior), so an old UI keeps working against the new server (10 rows per page, no params).
- **Rollback:** revert the commit. Reverting only the UI is also safe, because the new server params
  are optional and ignored by old clients.
- **Frontend build:** the webpack production build and `collectstatic` are needed to ship the UI
  (per `WebODM/CLAUDE.md`). **[ASSUMPTION — confirm]:** normal WebODM image rebuild; no separate
  deploy target is involved.
- **Feature flag:** none proposed. **[ASSUMPTION — confirm]:** the user does not want a flag.
- **Monitoring:** check error logs for 404s on the project list after deploy (filter/page reset).

## Open questions

Each has a recommended answer. Items marked **blocking** must be answered before Approved.

- **Q1 (RESOLVED, user 2026-11-11): failed-window timestamp.** Use `created_at`, labeled honestly in
  the UI ("created in the last 7 days and failed"). No migration. A `failed_at` field is a possible
  later step and would also be needed for sort-by-activity.
- **Q2: is "failed" active work?** **Recommended:** yes. One `has_active_work` boolean covers queued,
  running, and failed. The row counts show each state, so a user can tell them apart. Per-state
  params are deferred.
- **Q3 (RESOLVED, user 2026-11-11): partial uploads and null status.** `queued` = QUEUED OR (null AND
  `partial = false`). Partial tasks count toward `total` (so the project is not empty) but not toward
  active work.
- **Q4: page size mechanism.** **Recommended:** `page_size` query param with server default 10,
  max 20; UI sends 20. Alternative: change the global `PAGE_SIZE` (rejected, affects all endpoints).
- **Q5: narrow the `task_set` prefetch to IDs?** **Recommended:** yes, if it is a small,
  behavior-preserving change in the same PR. Otherwise defer and record it.
- **Q6: fix the existing per-row N+1 (`get_perms`, `owner`)?** **Recommended:** defer. It is
  pre-existing and out of scope. Record the measured baseline. Add `select_related('owner')` only if
  the user wants it now.
- **Q7: invalid boolean values.** **Recommended:** return 400 with a clear message rather than silently
  ignoring. This needs a small validator. Confirm before implementation.
- **Q8: DSO-Architecture docs.** Does WebODM's `/api/projects/` change require an update to the DSO
  docs site, per the global rule? **[ASSUMPTION — confirm]:** not checked in this pass. Confirm the
  docs root and whether WebODM has a service page there.
- **Q9: failed window setting location.** **Recommended:** a Django setting with default 7 in
  `settings.py`, with an env override only if the user asks for one.
- **Q10: row summary for zero-task projects.** **Recommended:** hide the summary (not "0 tasks") for
  empty projects, matching the existing "N Tasks" behavior.
- **Q11 (new, from code review): newly created project vanishes.** `Dashboard.jsx` (~33-47) refreshes
  the list right after a project is created. A new project has zero tasks, so with `hide_empty` on by
  default it disappears immediately and looks like the create failed. **Recommended:** after a
  successful create, the client turns `hide_empty` off for that refresh (the toggle visibly flips
  off) so the new project shows; the user can turn it back on. Alternative: show a notice
  "Project created (hidden: empty projects)". Confirm before implementation.

## Decisions

Approved by the user on 2026-11-11 (from the approved requirements):

- **D1 (2026-11-11, approved):** Benefits any user with several projects. Visibility unchanged; admins
  see all.
- **D2 (2026-11-11, approved):** "Hide empty projects" toggle, zero tasks excluded. Default **on** for
  everyone.
- **D3 (2026-11-11, approved):** Active-work filter separating Queued, Running, and Failed, using
  WebODM `Task.status` as the source of truth (not live ClusterODX/Tapis state). Default **off**.
- **D4 (2026-11-11, approved):** Per-row counts (e.g. "2 running · 1 queued · 1 failed"), computed
  server-side with annotations or aggregation, not by loading every task. Must match DB statuses.
- **D5 (2026-11-11, approved):** Failed window is one configurable setting (7 days). "All failed" is
  recorded as an accepted alternative.
- **D6 (2026-11-11, approved):** Null status counts as queued. Confirmed against code (see Current code);
  partial-upload refinement confirmed by the user (Q3, see D12).
- **D7 (2026-11-11, approved):** Page size 10 → 20 (the UI page size; the server mechanism is Q4).
- **D8 (2026-11-11, approved):** Filters combine with existing text search and must not change
  permission scoping.
- **D9 (2026-11-11, approved):** Upstream divergence accepted. Customization-inventory follow-up
  recorded.
- **D10 (2026-11-11, approved as optional, NOT approved for design):** Sort by last activity. Marked
  **not approved**; deferred.

- **D11 (2026-11-11, approved):** Failed window uses `Task.created_at` (Q1). No `failed_at` field, no
  migration. Rejected: `failed_at` (deferred). Label states the limitation.
- **D12 (2026-11-11, approved):** `queued` = QUEUED OR (null status AND `partial = false`) (Q3).
- **D13 (2026-11-11, approved):** User need section (job-to-be-done, pain, scanning criterion)
  confirmed as written.

- **D14 (2026-11-11, approved):** User accepted the recommended answer to all remaining questions:
  Q2 failed counts as active work (one `has_active_work` boolean); Q4 `page_size` param, server
  default 10, max 20, UI sends 20; Q5 narrow the `task_set` prefetch to IDs if it stays a small,
  behavior-preserving change, else defer; Q6 defer the existing `get_perms`/`owner` N+1; Q7 return
  400 on malformed booleans; Q9 Django setting `PROJECT_LIST_FAILED_WINDOW_DAYS = 7`, no env
  override; Q10 hide the summary for empty projects; Q11 after a successful project create, the
  client turns `hide_empty` off for that refresh (toggle visibly flips off).
- **D15 (2026-11-11, resolved by check):** Q8: DSO-Architecture has `docs/services/webodm.md` with an
  API endpoints table listing `GET /api/projects/` as "List/create projects". Implementation must
  update that row (new params `page_size`, `hide_empty`, `has_active_work`, and `task_counts`),
  then commit and push from DSO-Architecture per the global rule (push needs explicit approval).
- **D16 (2026-11-11):** original implementation was on the 3.1.2 upgrade branch by mistake; re-applied by hand onto origin/master (3.3.1) in worktree WebODM-wt-project-filters.
- **D17 (2026-11-11, deviations forced by master 3.3.1 code):** master already ships a `ProjectsPagination` (`page_size` query param, `max_page_size = 100`, response includes `page_size`), a narrowed `task_set` prefetch (Q5 already done), a user-selectable page size in `Paginator.jsx` (10/25/50/100, stored in `project_page_size`) and `Dashboard.jsx` builds `source` including `page_size`. Therefore: (a) no new `ProjectPagination` and the server max stays 100, not 20 (clamping to 20 would break the existing 25/50/100 selector); (b) `ProjectList.jsx` has no `PROJECTS_PER_PAGE` constant: the UI default page size (D7) is now 20 in `Dashboard.jsx`, and 20 was added to the `Paginator` page-size menu; the server default stays 10; (c) `docs/src/content/docs/reference/project.md` does not exist on master, so the API reference was not updated there.
- **D18 (2026-11-11, QA fixes, user approved):** (A) Empty state: `ProjectList.jsx` shows "No projects match the current filters." plus a hint to untick "Hide empty projects" / "Active work only" (or change the search) when the page has zero projects and a filter or search is active (`isFiltering()`); the checkboxes live in `ProjectList`, outside `Paginator`, so they stay usable although `Paginator` hides its toolbar at 0 items. With no filters and no projects nothing is added. (B) Stale per-row `task_counts`: `ProjectListItem.refreshTaskCounts()` re-reads the counts via `GET /api/projects/?id=<id>` (unpaginated array, `[0].task_counts`), called from the success path of the existing `refresh()` (so newTaskAdded, taskDeleted, taskMoved, import, edit all covered), debounced 300 ms, superseding any in-flight request, failures ignored, timer/request cancelled on unmount; a project going from total 0 to 1 shows the summary. Status polling in `TaskListItem` did not notify the row, so the smallest hook was added: `TaskListItem` calls `onStatusChanged(task)` only when the status actually changes (not per poll tick), passed through `TaskList` (`onTaskStatusChanged`) to `refreshTaskCounts`. Tests added in `ProjectList.test.jsx`, `ProjectListItem.test.jsx`, `Paginator.test.jsx` (getQueryForPage preserves `hide_empty`/`has_active_work` across page, page size, sort, search).
- **D18 accepted, not fixed:** (C) a filtered-out empty page that is not the first looks empty: covered by the A message. (D) A bookmarked page number beyond the last page (after filters shrink the set) returns 404 from DRF pagination: pre-existing behaviour. (E) A slow earlier list request can overwrite a newer one (request race in `ProjectList.refresh`): pre-existing.

Proposed in this draft, now covered by D14 unless noted:

- **P1:** `hide_empty` and `has_active_work` API defaults are `false`; the UI default is `true` for
  `hide_empty`. Preserves current API behavior.
- **P2:** `task_counts` added only to list responses, via a list-only serializer subclass.
- **P3:** Count subqueries instead of `Count` annotations (avoids join fan-out).
- **P4:** Row count summary shown in the header at all times when `total > 0`.
- **P5:** Filter change resets `page` to 1.
- **Rejected (proposed):** global `PAGE_SIZE` change; Python-side counting; client-only page size change.

## User feedback / decisions

Received 2026-11-11: User need confirmed; Q1 = `created_at`; Q3 confirmed.

Received 2026-11-11: the user accepted all recommended answers (D14). No open items remain.
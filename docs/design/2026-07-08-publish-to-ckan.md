# Publish to CKAN — Design Spec

## Status

**Implementing**

## Objective

Add a "Publish to CKAN" button to the WebODM task detail panel that registers a completed ODM processing run as a CKAN dataset on ckan.tacc.utexas.edu. Publishing is mediated through the existing `dso-agent-api` service (FastAPI + LangGraph), which handles metadata inference, dry-run validation, resource creation, and returns the CKAN package URL. WebODM does not call CKAN directly.

## User Need

**Primary user** — Research or operational team using WebODM to process drone imagery who wishes to catalog and share results in a discoverable, persistent location (ckan.tacc.utexas.edu).

**Job-to-be-done** — After completing a photogrammetry task, the user clicks "Publish to CKAN", selects a target organization, and the full ODM output set appears as a CKAN dataset — without manually downloading files, creating packages, or linking resources.

**Current pain** — No integrated publishing workflow. Users must navigate CKAN manually, hit the 100 MB upload limit on large outputs, and repeat for every task.

**Definition of success** — Clicking "Publish to CKAN" on a completed task results in a CKAN dataset appearing at ckan.tacc.utexas.edu, with each output (orthophoto, DSM, DTM, point cloud, report, etc.) registered as a resource. The CKAN dataset URL is stored on the task and shown on the task panel.

**Assumptions** —
- Auth is Tapis OAuth2 JWT (6-hour TTL). WebODM holds a service-account Tapis username/password in env vars; it exchanges credentials for a JWT per publish job.
- Publishing is routed through `dso-agent-api` — WebODM never calls CKAN directly.
- Resources are registered as remote URL links (pointing to WebODM's asset download endpoints), not file uploads, to avoid CKAN's 100 MB limit.
- Feature is opt-in: hidden unless `WO_DSO_AGENT_URL` is configured.
- Only completed tasks may be published.

---

## Current Code/System Summary

### Plugin Architecture

WebODM uses an extensible plugin system:
- **Plugin base** (`app/plugins/__init__.py`): `PluginBase` lifecycle hooks — `include_js_files()`, `build_jsx_components()`, `api_mount_points()`, `app_mount_points()`
- **Data stores** (`app/plugins/data_store.py`): `GlobalDataStore` for plugin state (K-V, Postgres-backed)
- **Async tasks** (`app/plugins/worker.py`): `run_function_async(func, *args)` via Celery
- **API view base** (`app/plugins/views.py`): `TaskView` — DRF base class scoped to a project/task, enforces ownership
- **Button injection** (`PluginsAPI.Dashboard.addTaskActionButton`): JS hook to add buttons to task panel

### Task Model (`app/models/task.py`)

Key fields:
- `id` (UUID), `project` (FK), `name`, `status` (COMPLETED = 4), `created_at`
- `available_assets` (ArrayField): e.g. `["orthophoto.tif", "dsm.tif", "georeferenced_model.laz"]`
- `orthophoto_extent` (GeometryField, SRID=4326), `epsg`
- Asset download URL: `/api/projects/{project_pk}/tasks/{task_pk}/download/{asset}`

### Existing Plugin Precedents

- **OpenAerialMap** (`coreplugins/openaerialmap/`): async upload via Celery, `UserDataStore` for token, injects task action button
- **Cesium Ion** (`coreplugins/cesiumion/`): similar async + button pattern, global token

### DSO CKAN Publishing Stack

Two Tapis pods deployed on `portals.tapis.io`:

**dso-agent-api** (`https://dso-agent-api.pods.portals.tapis.io`)
- FastAPI + LangGraph service that orchestrates CKAN dataset registration end-to-end
- Accepts task metadata, infers CKAN fields, runs dry-run, creates package + resources
- Auth: `Authorization: Bearer <tapis_jwt>`
- Relevant endpoints:
  - `POST /v1/auth/login` — exchange Tapis credentials for JWT
  - `POST /v1/ckan-registration/runs` — start a registration run
  - `GET /v1/ckan-registration/runs/{thread_id}` — poll run state
  - `POST /v1/ckan-registration/tools/organization_list` — list orgs token can write to

**dso-mcp** — CKAN MCP server called internally by the agent; WebODM does not call it directly.

**Workflow states:** `analyze → metadata_report → dry_run → apply → applied`
Setting `action: "apply"` skips human review and goes straight to creating the dataset.

**Auth model:** No static CKAN tokens. Every request carries a Tapis JWT (6-hour TTL). The package is created under the authenticated user's identity in CKAN.

**Current blocker:** Both pods require GHCR image visibility set to Public before Tapis can pull them. Plugin must handle agent unavailability gracefully.

---

## Proposed Design

### Architecture Overview

A WebODM plugin (`coreplugins/ckan/`) that:
1. Injects a "Publish to CKAN" button on completed tasks (React)
2. Opens a **chat panel** where the user works with `dso-agent-api` to review and confirm metadata before anything is written to CKAN
3. Exposes plugin API endpoints that **proxy** agent calls server-side (so Tapis credentials never reach the browser)
4. On user confirmation, triggers the agent's `apply` step (async Celery), which creates the CKAN package and resources
5. Writes `task.ckan_url` on completion

### Interaction Model

The `dso-agent-api` run workflow maps directly to a chat with human review:

```
analyze  →  metadata_report  →  [USER REVIEWS / EDITS]  →  apply  →  applied
```

1. User clicks "Publish to CKAN" → chat panel slides open
2. WebODM backend starts an agent run (`action: "analyze"`) seeded with task metadata and asset URLs
3. Agent responds with proposed dataset title, description, tags, org list, and resource mapping
4. User reads the proposal, types corrections or additional context in the chat input
5. Agent updates its metadata plan accordingly
6. When the user is satisfied, they click **"Confirm & Publish"**
7. Backend sends `action: "apply"` to the agent via the resume endpoint
8. Apply runs asynchronously (Celery); chat panel shows progress
9. On completion: chat shows CKAN dataset URL as a clickable link; `task.ckan_url` is stored

### Plugin File Structure

```
coreplugins/ckan/
  __init__.py
  manifest.json
  plugin.py                 # PluginBase subclass
  api_views.py              # DRF proxy endpoints (start, message, confirm, status)
  publisher.py              # Celery apply step + Tapis JWT helper
  public/
    CKANPublishPanel.jsx    # Chat panel component (button + slide-out)
  templates/
    load_buttons.js         # JS button injection hook
```

### API Endpoints

All require authenticated WebODM user with task ownership. All proxy to `dso-agent-api`, adding the Tapis JWT server-side — credentials never leave Django.

---

**`POST /api/plugins/ckan/task/{task_pk}/chat/start`**

Opens a new agent run with `action: "analyze"` seeded with task metadata and asset URLs. Returns the thread ID and the agent's first message (proposed metadata as markdown).

Request: `{}` (no body; task context assembled server-side)

Response 201:
```json
{
  "thread_id": "abc-123",
  "message": "## Next Options\n...\n\nI've analyzed your ODM outputs. Here's the proposed CKAN dataset:\n\n**Title:** Site A Survey — July 2026\n...\n\nThread ID: `abc-123`\nStatus: `metadata_report`"
}
```

Response 503 if agent unreachable.

---

**`POST /api/plugins/ckan/task/{task_pk}/chat/message`**

Proxies a user message to the active agent run via the `resume` endpoint. Returns the agent's reply.

Request:
```json
{"thread_id": "abc-123", "message": "Change the title to 'Hurricane Maria Assessment — Sector 4'"}
```

Response 200:
```json
{
  "thread_id": "abc-123",
  "message": "Updated. Title is now 'Hurricane Maria Assessment — Sector 4'. Anything else to adjust?",
  "status": "metadata_report"
}
```

---

**`POST /api/plugins/ckan/task/{task_pk}/chat/confirm`**

Queues a Celery job (`apply_ckan_publish`) that will call the agent resume endpoint with `action: "apply"` and `approval: "REGISTER"`. Returns 202 immediately; the Celery task reads `result.dataset_url` from the synchronous apply response.

Request:
```json
{"thread_id": "abc-123"}
```

Response 202:
```json
{"status": "publishing", "message": "Publishing to CKAN…"}
```

Note: `approval: "REGISTER"` is required by the agent's apply gate (`APPLY_APPROVAL = "REGISTER"` in `nodes.py`). Without it the apply step is rejected.

---

**`GET /api/plugins/ckan/task/{task_pk}/publish-status`**

Returns current publish state (polled by frontend after confirm).

Response 200:
```json
{
  "status": "idle" | "publishing" | "success" | "error",
  "ckan_url": "https://ckan.tacc.utexas.edu/dataset/...",
  "thread_id": "abc-123",
  "timestamp": "2026-07-08T14:30:00Z",
  "error": ""
}
```

### Backend Proxy and Celery Logic (`api_views.py` + `publisher.py`)

**`api_views.py`** handles `start` and `message` synchronously — the agent responds in under 30 s:

```python
class ChatStartView(TaskView):
    def post(self, request, pk=None):
        task = self.get_object()
        jwt = publisher.get_tapis_jwt()

        r = requests.post(
            f"{settings.WO_DSO_AGENT_URL}/v1/ckan-registration/runs",
            headers={"Authorization": f"Bearer {jwt}"},
            json={
                "action": "analyze",
                "message": "Analyze these WebODM outputs and propose CKAN dataset metadata.",
                # CkanDatasetOverride — seed known fields; agent fills the rest
                "dataset": {
                    "title": task.name or f"ODM Task {task.id}",
                    "notes": publisher.build_notes(task),
                    "spatial": publisher.bbox_wkt(task.orthophoto_extent),
                },
                # RemoteResource list — one entry per available asset
                "remote_resources": publisher.build_remote_resources(task),
            },
            timeout=60
        )
        r.raise_for_status()
        data = r.json()  # AgentRunResponse
        text = (data.get("result") or {}).get("review_markdown") or str(data)
        return Response({"thread_id": data["thread_id"], "message": text, "status": data.get("status")}, status=201)


class ChatMessageView(TaskView):
    def post(self, request, pk=None):
        thread_id = request.data["thread_id"]
        message = request.data["message"]
        jwt = publisher.get_tapis_jwt()

        # CkanResumeRequest is identical to CkanRunRequest; just pass message
        r = requests.post(
            f"{settings.WO_DSO_AGENT_URL}/v1/ckan-registration/runs/{thread_id}/resume",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"message": message},
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("result") or {}).get("review_markdown") or str(data)
        return Response({"thread_id": thread_id, "message": text, "status": data.get("status")})
```

**`publisher.py`** — key helpers and the Celery apply step:

```python
def build_remote_resources(task) -> list[dict]:
    """Build RemoteResource list from task.available_assets."""
    return [
        {
            "url": f"{settings.WO_URL}/api/projects/{task.project_id}/tasks/{task.id}/download/{asset}",
            "name": _friendly_name(asset),
            "format": _infer_format(asset),
        }
        for asset in task.available_assets
    ]


def apply_ckan_publish(task_id, thread_id):
    """Celery task: send apply+REGISTER to agent, poll result, store dataset_url."""
    ds = GlobalDataStore('ckan')
    status_key = f"task_{task_id}_ckan_publish"
    try:
        jwt = get_tapis_jwt()

        # CkanApplyInput requires approval="REGISTER" to gate the write
        r = requests.post(
            f"{settings.WO_DSO_AGENT_URL}/v1/ckan-registration/runs/{thread_id}/resume",
            headers={"Authorization": f"Bearer {jwt}"},
            json={"action": "apply", "approval": "REGISTER"},
            timeout=60
        )
        r.raise_for_status()
        data = r.json()  # AgentRunResponse

        # Result field is "dataset_url" (confirmed from nodes.py line 514)
        dataset_url = (data.get("result") or {}).get("dataset_url") or ""
        if not dataset_url:
            raise RuntimeError(f"Apply succeeded but no dataset_url in response: {data}")

        Task.objects.filter(id=task_id).update(ckan_url=dataset_url)
        ds.set_json(status_key, {"status": "success", "ckan_url": dataset_url, "thread_id": thread_id})
    except Exception as e:
        logger.exception(f"CKAN apply failed for task {task_id}")
        ds.set_json(status_key, {"status": "error", "error": str(e), "thread_id": thread_id})
```

### React Chat Panel (`CKANPublishPanel.jsx`)

**Button state:**

| Condition | Button shows |
|---|---|
| `WO_DSO_AGENT_URL` not set | Hidden |
| task not COMPLETED | Hidden |
| `task.ckan_url` set | "Published to CKAN ↗" (link) + "Re-publish" |
| otherwise | "Publish to CKAN" |

**Chat panel behavior:**

1. On "Publish to CKAN" click: panel slides open; POST `/chat/start`; shows agent's metadata proposal as first message
2. Text input + send button for user messages; each send → POST `/chat/message`; appends agent reply
3. **"Confirm & Publish"** button is always visible at the bottom of the panel (not gated on any specific message)
4. On confirm: POST `/chat/confirm`; input locked; spinner shown
5. Poll `/publish-status` every 3 s; on `success`: show "Published ✓ — View on CKAN →"
6. On error: show message, "Retry" re-opens the confirm path (reuses same thread)
7. Conversation history rendered as a simple scrollable message list (user messages right-aligned, agent left-aligned)

---

## Files Likely Affected

### Create (7 files)

1. `coreplugins/ckan/__init__.py`
2. `coreplugins/ckan/manifest.json`
3. `coreplugins/ckan/plugin.py`
4. `coreplugins/ckan/api_views.py`
5. `coreplugins/ckan/publisher.py`
6. `coreplugins/ckan/public/CKANPublishPanel.jsx`
7. `coreplugins/ckan/templates/load_buttons.js`

### Modify (2 files + 1 migration)

1. **`app/models/task.py`** — add `ckan_url = models.URLField(null=True, blank=True)`
2. **`webodm/settings.py`** — add env vars (see below)
3. **Migration** (auto-generated via `makemigrations`)

---

## API/Schema Changes

### New Task field

```python
ckan_url = models.URLField(null=True, blank=True)
```

### New Django settings

```python
# webodm/settings.py
WO_DSO_AGENT_URL  = os.environ.get('WO_DSO_AGENT_URL', '')   # e.g. https://dso-agent-api.pods.portals.tapis.io
WO_TAPIS_USERNAME = os.environ.get('WO_TAPIS_USERNAME', '')   # service account
WO_TAPIS_PASSWORD = os.environ.get('WO_TAPIS_PASSWORD', '')   # service account
WO_URL            = os.environ.get('WO_URL', 'http://localhost:8000')  # externally reachable base URL for resource links
```

### Plugin API endpoints

- `POST /api/plugins/ckan/task/{task_pk}/chat/start`
- `POST /api/plugins/ckan/task/{task_pk}/chat/message`
- `POST /api/plugins/ckan/task/{task_pk}/chat/confirm`
- `GET  /api/plugins/ckan/task/{task_pk}/publish-status`

---

## Data Flow

```
User clicks "Publish to CKAN"
  ↓
CKANPublishPanel.jsx slides open
  → POST /api/plugins/ckan/task/{task_pk}/chat/start
  → api_views.py: GET Tapis JWT, build file list, POST /v1/ckan-registration/runs (action="analyze")
  → agent returns {thread_id, message: "Here's the proposed metadata…"}
  → panel renders agent message
  ↓
User reads proposal, types corrections
  → POST /api/plugins/ckan/task/{task_pk}/chat/message {thread_id, message}
  → api_views.py: POST /v1/ckan-registration/runs/{thread_id}/resume {message}
  → agent returns updated proposal
  → panel appends reply
  [repeat until satisfied]
  ↓
User clicks "Confirm & Publish"
  → POST /api/plugins/ckan/task/{task_pk}/chat/confirm {thread_id}
  → api_views.py: queues Celery apply_ckan_publish(task_id, thread_id) → 202
  ↓
Celery: apply_ckan_publish(task_id, thread_id)
  1. GET Tapis JWT
  2. POST /v1/ckan-registration/runs/{thread_id}/resume {action: "apply", approval: "REGISTER"}
     → agent returns {status: "applied", result: {dataset_url: "..."}} synchronously
  3. task.ckan_url = result.dataset_url from response
  4. GlobalDataStore → status="success"
  ↓
Frontend polls /publish-status every 3s
  → on success: shows "Published ✓ — View on CKAN →" in chat panel
```

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| **Agent pods not yet running** (GHCR whitelist blocker) | Plugin gracefully returns 503 if agent unreachable; UI shows "CKAN publishing unavailable" |
| **Tapis JWT expiry during long publish** | JWT is fetched fresh per publish job; 6h TTL is sufficient for a single run |
| **Unhandled agent states during apply** (`needs_dry_run`, `needs_input`, `needs_dataset_intent`) | The agent may return these states instead of `applied` if it requires a dry-run, needs more information, or detects a CKAN name collision. V1 decision: treat as error — Celery task raises `RuntimeError` if `dataset_url` is absent, stores `status="error"` in GlobalDataStore, and surfaces the agent's `status` field in the error message so the user has actionable context. Full handling of these states is deferred to v2. |
| **`requires_action` persona chat interrupts** | V1 assumes `CKAN_PERSONA_CHAT=false` on the deployed agent (the default). If enabled, the agent may return `requires_action` instead of `result.review_markdown`; the fallback `str(data)` would be shown in the chat panel as raw text. Surfacing `requires_action.message` gracefully is deferred to v2. |
| **Resource URLs unreachable from agent** | Requires `WO_URL` to be externally resolvable; documented requirement |
| **Duplicate publishes** | Button disabled while publishing; check `ckan_url` on load; re-publish creates new dataset (shown clearly in UI) |
| **Service account credentials in env vars** | Standard WebODM pattern (`WO_` env vars); excluded from version control via `.env` gitignore |
| **Celery worker crash** | Stale "publishing" state in GlobalDataStore; add signal-based or periodic cleanup in v2 |

---

## Alternatives Considered

### Direct CKAN API (no agent)

Call CKAN's `package_create` + `resource_create` directly with a static API token.

**Rejected**: The DSO stack already exists and is the authorized publishing path. Direct CKAN calls bypass the LangGraph metadata-inference and dry-run pipeline, bypass the Tapis auth model, and duplicate infrastructure already built and deployed.

### Per-user Tapis credentials

Each WebODM user enters their own Tapis username/password (stored in `UserDataStore`).

**Deferred to v2**: Simpler for MVP to use a single service account. Per-user attribution is valuable but requires a settings UI and exposes user credentials in the DB.

### Synchronous publish

Block the HTTP request until the agent returns.

**Rejected**: Agent runs can take 10–60 s; HTTP timeouts and UI freezes are unacceptable.

---

## Test Plan

### Unit tests (`tests/plugins/ckan/`)

1. `_get_tapis_jwt` — mock `/v1/auth/login`; verify Bearer token extracted
2. `apply_ckan_publish` — mock `/resume` endpoint; verify `dataset_url` extracted on `status="applied"`, error stored in GlobalDataStore when `dataset_url` absent (e.g. agent returns `needs_dry_run`)
3. `_build_resource_url` — verify URL format for all asset types
4. `_infer_format` — verify extension → CKAN format mapping

### Integration tests

1. POST /chat/start with non-completed task → 400
2. POST /chat/start with agent URL unset → 503
3. POST /chat/confirm with valid task → 202, GlobalDataStore status = "publishing"
4. GET /publish-status while publishing → `status="publishing"`
5. GET /publish-status after success → `status="success"`, `ckan_url` returned

### End-to-end (manual, once pods are live)

1. Complete task → Publish → select org → observe status → verify dataset on ckan.tacc.utexas.edu
2. Agent unreachable → graceful error message shown
3. Re-publish already-published task → new dataset created, existing URL shown alongside

---

## Documentation Plan

1. **`coreplugins/ckan/README.md`**: config, required env vars, token scope, network requirements
2. **Settings reference**: `WO_DSO_AGENT_URL`, `WO_TAPIS_USERNAME`, `WO_TAPIS_PASSWORD`, `WO_URL`
3. **Pre-requisite note**: dso-agent-api pod must be running (GHCR visibility unblocked + GitHub Secrets set)

---

## Rollout / Rollback

**Rollout gate**: Plugin is inactive unless `WO_DSO_AGENT_URL` is set in the environment.

**Rollback**: Remove `coreplugins/ckan/` or unset `WO_DSO_AGENT_URL`; restart WebODM. Existing `task.ckan_url` values are retained but unused.

**Dependency**: `dso-agent-api` pod must be live before end-to-end testing is possible. Track via [GHCR whitelist blocker noted in docs/webodm-ckan-context.md].

---

## Open Questions

1. **Republish behavior**: Create new dataset, or call `schema_upsert_package` on the existing one? Proposed: new dataset for MVP (simpler); show existing URL to prevent accidental re-publish.
2. **Dataset title format**: `task.name` alone, or `project.name — task.name`? Proposed: `project.name — task.name`.
3. **Dataset visibility**: Public or org-private by default? Proposed: inherit from org defaults; expose toggle in v2.
4. **`WO_URL` value in production**: Expected `https://webodm.tacc.utexas.edu` — confirm before deployment so resource links are externally reachable from the agent pod.
5. **Service account Tapis identity**: Which Tapis user should the service account be? Needs a dedicated service account with `create_dataset` permission in the target orgs.

---

## Decisions

### Decision 1: Route through dso-agent-api, not direct CKAN (Approved)
The agent is the authorized publishing path for this stack. Direct CKAN calls bypass the Tapis auth model and duplicate existing infrastructure.

### Decision 2: Tapis JWT auth via logged-in user's OAuth2 token (Approved — revised 2026-07-15)
The plugin uses the requesting user's stored `TapisOAuth2Token` (retrieved via `TapisOAuth2Client` / `TapisOAuth2Token` models). `token.get_or_refresh_access_token()` handles expiry and refresh automatically. No service-account credentials (`WO_TAPIS_USERNAME` / `WO_TAPIS_PASSWORD`) are needed or stored. If the user has no Tapis token the API returns HTTP 403 with an actionable message. The Celery apply task receives `user_id` and performs the same lookup.

### Decision 3: Remote URLs for resources (Approved)
Assets registered as URL links to WebODM download endpoints; no file upload. Avoids 100 MB CKAN limit.

### Decision 4: Async Celery publish; no agent-side polling (Approved)
Agent runs take 10–60 s; async + frontend polling of `/publish-status` is the right model. The apply `POST /resume` call returns `status: "applied"` and `result.dataset_url` synchronously in the same response — no separate GET poll of the agent is needed.

### Decision 5: Add `task.ckan_url` field (Approved)
Single nullable URLField; enables Task API to surface the link and prevents re-discovery on reload.

### Decision 6: Chat panel with human-in-the-loop (Approved — 2026-07-08)
User requested a chat interface so they can review and confirm metadata before anything is written to CKAN. Button opens a slide-out chat panel driven by the agent's `analyze → resume → apply` workflow. The original auto-apply design was rejected.

---

## User Feedback / Decisions

- 2026-07-08: Auth pattern confirmed as Tapis JWT via dso-agent-api (not static CKAN token).
- 2026-07-08: Org selection: user-selected at publish time.
- 2026-07-08: All available assets registered as resources.
- 2026-07-08: Context doc (`docs/webodm-ckan-context.md`) provided; spec updated to use agent stack.
- 2026-07-08: UX changed from one-click auto-apply to chat panel with human review. Button opens a slide-out chat where user works with the agent to confirm metadata before "Confirm & Publish" triggers the apply step.
- 2026-07-08: Agent source inspected (`routes_agent.py`, `schemas.py`, `graph.py`, `nodes.py`). Key findings: `CkanResumeRequest` is identical to `CkanRunRequest`; asset URLs go in `remote_resources` (not `files`); metadata seed goes in `dataset` (`CkanDatasetOverride`); apply requires `approval: "REGISTER"`; result field for the CKAN URL is `result.dataset_url`.
- 2026-07-15: Spec reconciled against `dso-agent-api-reference.md`. Fixed: (1) API/Schema Changes endpoint list updated to match chat-based design; (2) data flow diagram corrected — apply POST returns `dataset_url` synchronously, no agent-side polling loop needed; (3) `approval: "REGISTER"` added to data flow step 2; (4) stale `_poll_until_applied` references removed from Risks and Test Plan; (5) unhandled agent states (`needs_dry_run`, `needs_input`, `needs_dataset_intent`) documented in Risks with explicit v1 decision; (6) `requires_action` persona chat interrupt assumption documented.

---

**Spec Version**: 1.4
**Date**: 2026-07-15
**Status**: Implemented

# CKAN Publish Plugin

Adds a **Publish to CKAN** button to completed WebODM task pages. Clicking it opens a chat panel where the DSO agent proposes dataset metadata; after review the user confirms and the plugin registers the task outputs as a CKAN dataset on `ckan.tacc.utexas.edu`.

Publishing is mediated entirely through `dso-agent-api` — WebODM never calls CKAN directly.

## Requirements

- The logged-in user must have authenticated with Tapis (via the WebODM Tapis OAuth2 login flow). A valid `TapisOAuth2Token` must exist for their account.
- The `dso-agent-api` pod must be reachable from the Django container at `WO_DSO_AGENT_URL`.

## Configuration

All configuration is via environment variables in `.env` or your Docker Compose override.

| Variable | Required | Description |
|---|---|---|
| `WO_DSO_AGENT_URL` | **Yes** | Base URL of the DSO agent API (e.g. `https://dso-agent-api.pods.portals.tapis.io`). Plugin is hidden when unset. |
| `WO_URL` | **Yes** | Externally reachable base URL of this WebODM instance (e.g. `https://webodm.tacc.utexas.edu`). Used to construct CKAN resource download URLs when no HTTP request context is available (e.g. inside the Celery worker). |
| `TAPIS_BASE_URL` | Yes (for auth) | Tapis tenant base URL (e.g. `https://portals.tapis.io`). Set by the Tapis OAuth2 integration. |
| `TAS_URL` | No | TACC TAS API base URL. Used to look up user email from TACC username when the Django user record has no email. Falls back gracefully if unset. |
| `TAS_SERVICE_USERNAME` | No | TAS service account username for email lookups. |
| `TAS_SERVICE_PASSWORD` | No | TAS service account password for email lookups. |

## How it works

1. User clicks **Publish to CKAN** on a completed task page.
2. Django proxies a `POST /v1/ckan-registration/runs` call to `dso-agent-api` carrying task metadata (title, notes, tags, spatial bbox, temporal coverage, output file URLs).
3. The agent proposes a CKAN dataset record and streams back a markdown summary in the chat panel.
4. The user reviews and edits the proposal via chat, then clicks **Confirm & Publish**.
5. A Celery task (`apply_ckan_publish`) sends an apply+REGISTER instruction to the agent, which creates the CKAN package and registers all output files as remote URL resources.
6. The resulting CKAN dataset URL is stored on `Task.ckan_url` and shown in the UI.

On re-publish, the previously used CKAN `owner_org` is remembered in the plugin data store so the agent skips the org-selection step.

## Assets registered in CKAN

Output files are registered as **remote URL resources** pointing back to WebODM's download endpoints — no files are uploaded to CKAN. This avoids the 100 MB CKAN upload limit. The task is automatically set to `public=True` before publishing so the download URLs are accessible without authentication.

Publishable asset types: orthophoto, DSM, DTM, point cloud (LAZ/LAS/PLY), textured model (ZIP), processing report (PDF), and all-outputs archive. Intermediate files (cameras.json, shots.geojson, etc.) are excluded. Two HTML viewer links (Web Map Viewer, 3D Model Viewer) are also registered.

## Running the tests

```bash
./webodm.sh test backend app.tests.test_ckan_plugin
```

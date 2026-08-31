# Tapis JWT Expiry Logout - Design Spec

## Status

Implemented

## Objective

Remove Tapis OAuth2 refresh-token use from WebODM's runtime flow for the Portals tenant and make JWT access-token expiry a reauthentication boundary. When the browser observes the stored Tapis JWT has expired, WebODM should log the user out of the UI instead of trying to refresh the token.

## User need

**Primary user** - WebODM users authenticating through the Tapis Portals tenant.

**Job-to-be-done** - Use WebODM with Tapis-backed features until the current Tapis JWT expires, then be sent through login again cleanly.

**Current pain** - The code tries to refresh Tapis JWTs, but the current Portals tenant does not provide a working refresh flow. This creates misleading backend behavior and can pass expired tokens downstream to Tapis-dependent services.

**Definition of success** - WebODM no longer exposes or calls a Tapis refresh-token endpoint, does not try a refresh grant from backend helpers or plugins, does not store newly returned refresh tokens from the OAuth callback, and logs the user out of the browser session when the JWT expiry time is reached.

## Current code/system summary

WebODM is configured for Tapis OAuth2-only authentication. The canonical DSO auth docs identify the active tenant as `portals` with base URL `https://portals.tapis.io`.

Current token handling is split across these paths:

- `app/api/tapis_oauth2.py` exchanges authorization codes for tokens, stores `access_token`, stores `refresh_token` when present, and exposes `TapisOAuth2TokenRefreshView`.
- `app/api/urls.py` exposes `POST /api/oauth2/tapis/refresh/{client_id}/`.
- `app/models/oauth2.py` has `TapisOAuth2Token.refresh()` and `get_or_refresh_access_token()`. The helper currently returns an expired access token when no refresh token exists.
- `app/static/app/js/main.jsx` imports `app/static/app/js/classes/TapisTokenManager.js`, so token-expiry behavior is part of the main WebODM UI bundle.
- `app/static/app/js/classes/TapisTokenManager.js` monitors `window.tapisTokenInfo.expires_at`, warns 10 minutes before expiry, and currently shows a modal before redirecting to `/logout/` after expiry.
- `app/templates/app/base.html` injects `window.tapisTokenInfo` only when `app/templatetags/tapis_tags.py` returns a non-expired token.
- `app/views/app.py`, `app/services/tapis_storage.py`, `app/models/task.py`, `coreplugins/ckan/publisher.py`, and `coreplugins/embeddings/embeddings_client.py` call `get_or_refresh_access_token()`.
- `coreplugins/upstream/api.py` has its own manual refresh-token grant path.
- ClusterODM requires a valid user JWT for Tapis job submission and related Tapis API calls; it already rejects missing or expired JWTs.

Known existing risk: `app/auth/tapis_oauth2.py` decodes JWT claims locally and checks expiration/user claims, but does not verify the JWT signature. That is not introduced by this change and is not part of this implementation unless separately approved.

## Proposed design

Keep the existing database schema and remove refresh from behavior.

Scope and non-goals:

- No database migration.
- No JWT signature-verification fix.
- No service-account, delegation, or token-extension design.
- No tenant-generic OAuth redesign.
- No external docs commit, push, deployment, or database mutation without explicit approval.

Validity-helper contract:

- Add `TapisOAuth2Token.get_valid_access_token()`.
- It extracts the raw JWT, requires JWT-shaped input, requires a known effective expiration time from `expires_at` or the JWT `exp` claim, applies a small server-side expiry skew of 30 seconds, and returns the token only when it is still valid beyond that skew.
- Expired, malformed, missing, or unparsable tokens return `None`.
- The helper never sends HTTP requests and never attempts a refresh-token grant.

Implementation plan:

1. Add the non-refreshing `get_valid_access_token()` helper described above.
2. Keep `refresh_token` on the model for migration/backward compatibility, but stop writing new refresh-token values in the OAuth callback. On the next successful OAuth callback for a user/client, clear that row's `refresh_token` to an empty string.
3. Remove `TapisOAuth2Token.refresh()`. Replace `get_or_refresh_access_token()` call sites with `get_valid_access_token()`. Do not leave a runtime helper whose name implies refresh.
4. Remove `TapisOAuth2TokenRefreshView` and the `/api/oauth2/tapis/refresh/{client_id}/` route from WebODM's API. The route should return `404` after removal.
5. Update callers to use the non-refreshing helper and return clear reauthentication-required errors when the token is expired or missing.
6. Remove the manual refresh-token grant in `coreplugins/upstream/api.py`.
7. Update `app/views/tapis_auth.py` so logout clears any stored `refresh_token` values for the authenticated user before ending the Django session. This is opportunistic cleanup, not a DB migration.
8. Update the UI page behavior in `TapisTokenManager` so every loaded WebODM UI page redirects to `/logout/` immediately when the expiration time is reached. Remove the expired-session modal and 10-second delay. Keep the pre-expiry warning because it gives the user a chance to save work before logout.
9. Update the token template tag or `base.html` so an already-expired stored token still emits enough expiry metadata for the JavaScript to log the user out immediately on page load. This covers the reload-after-expiry case where the user still has a Django session cookie but no valid Tapis JWT.
10. Update WebODM and DSO docs to describe the Portals behavior: access JWTs are not refreshed; users must reauthenticate after expiry.

Caller behavior:

- HTTP/API views should return `401` or redirect to login/dashboard with a reauthentication message, depending on the existing pattern for that endpoint.
- Non-HTTP service, task, CKAN, embeddings, storage, and Upstream code should not call logout. They should return `None` or raise existing domain errors with clear reauthentication-required text.
- ClusterODM should not receive expired JWTs from WebODM. If WebODM cannot obtain a valid token, task submission/status paths should fail before or at the WebODM boundary instead of forwarding stale credentials.

## Files likely affected

- `WebODM/app/models/oauth2.py`
- `WebODM/app/api/tapis_oauth2.py`
- `WebODM/app/api/urls.py`
- `WebODM/app/static/app/js/classes/TapisTokenManager.js`
- `WebODM/app/templates/app/base.html`
- `WebODM/app/templatetags/tapis_tags.py`
- `WebODM/app/views/tapis_auth.py`
- `WebODM/app/views/app.py`
- `WebODM/app/services/tapis_storage.py`
- `WebODM/app/models/task.py`
- `WebODM/coreplugins/upstream/api.py`
- `WebODM/coreplugins/ckan/publisher.py`
- `WebODM/coreplugins/embeddings/embeddings_client.py`
- `WebODM/app/tests/test_clusterodm_admin.py`
- `WebODM/app/tests/test_tapis_oauth2_tokens.py`
- `WebODM/coreplugins/upstream/tests.py` or the existing upstream test location if present
- `WebODM/coreplugins/embeddings/tests.py`
- `WebODM/TAPIS_OAUTH2_INTEGRATION.md`
- `WebODM/DEPLOYMENT_INSTRUCTIONS.md`
- `WebODM/DOCKER_DEPLOYMENT.md`
- `/Users/wmobley/Documents/Github/DSO-Architecture/docs/auth/tapis-oauth2.md`
- `/Users/wmobley/Documents/Github/DSO-Architecture/docs/services/webodm.md`

## API/schema changes

API change:

- Remove `POST /api/oauth2/tapis/refresh/{client_id}/` from the WebODM API.

Schema change:

- No database migration is planned. `TapisOAuth2Token.refresh_token` remains in the schema for backward compatibility and rollback simplicity, but it becomes unused by runtime code.

## Data flow

1. User authenticates through Tapis OAuth2 authorization-code flow.
2. WebODM exchanges the code for an access token and stores the JWT plus `expires_at`.
3. WebODM does not persist or later use a refresh token.
4. WebODM clears any old stored refresh-token value for that user/client during callback persistence.
5. Pages inject the stored token expiry into `window.tapisTokenInfo` without exposing the JWT itself.
6. Browser JavaScript on every loaded WebODM UI page warns before expiry and redirects to `/logout/` when expiry is reached or already past.
7. Logout clears any still-populated refresh-token values for the authenticated user and ends the Django session.
8. Backend features that need Tapis, ClusterODM, CKAN, Upstream, embeddings, or storage APIs request a valid stored access JWT through `get_valid_access_token()`.
9. If the stored JWT is expired, malformed, missing, or within the expiry skew, the backend returns or raises a clear reauthentication-required error instead of calling the Tapis refresh-token grant.

## Risks and tradeoffs

- Long-running background work that starts after the user's JWT expires will fail until the user logs in again. This is an explicit tradeoff of removing refresh in a tenant where refresh is unavailable.
- Existing rows may contain `refresh_token` values until the next successful login or logout clears them. Leaving the column avoids a migration but means code review must ensure no remaining runtime path uses it.
- Removing a public API route can break any client that calls `/api/oauth2/tapis/refresh/{client_id}/`. The route appears internal/documented rather than used by current frontend code.
- Logging out on client-observed expiry depends on the page having usable `expires_at` metadata. The template/tag change must cover both valid and already-expired tokens.
- The existing JWT signature-verification gap remains. This change should not make that gap worse, but it does not fix it.
- The 30-second server skew can reject a nearly expired token before the browser's exact expiry timer fires. That is intentional to avoid handing tokens to Tapis or ClusterODM that are likely to expire during request setup.

## Alternatives considered

- Keep refresh opportunistic and fall back to logout when refresh fails. Rejected because the user confirmed refresh is not available in the current Portals tenant, and retaining refresh calls creates noisy failures and misleading behavior.
- Add a service-account or delegated credential for background tasks. Rejected for this change because the request is about removing refresh from the user-token flow, and a service credential would increase auth scope and review burden.
- Drop the `refresh_token` database column. Rejected for now because it creates migration and rollback work without changing runtime behavior.
- Disable Tapis-backed background features near expiry. Deferred. The smaller change is to require a valid token at call time and fail with a reauthentication message when expired.

## Test plan

- Add `WebODM/app/tests/test_tapis_oauth2_tokens.py` for `TapisOAuth2Token` helper behavior:
  - valid unexpired JWT returns the JWT.
  - expired JWT returns `None`, even if `refresh_token` is populated.
  - no HTTP request is made for refresh-token grant.
- Update ClusterODM admin tests so an expired token with a stored `refresh_token` redirects to dashboard instead of attempting refresh.
- Add or update tests for the OAuth2 callback storing no new refresh token.
- Add or update an Upstream plugin test so expired tokens return `None` without a refresh POST.
- Add or update CKAN and embeddings tests if their helper assertions or error messages reference token refresh.
- Verify the removed refresh route returns `404`.
- Add or update logout tests so `tapis_logout_view` clears stored `refresh_token` values before ending the session.
- Assert expired-token paths do not call external network boundaries:
  - no Tapis refresh-token `requests.post`;
  - no CKAN agent publish request when user token is expired;
  - no Upstream API request when user token is expired;
  - no Tapis storage `requests.request` or file `requests.get` when user token is expired;
  - no embeddings `Tapis(...)` construction or `submitJob` when user token is expired.
- Add `WebODM/app/static/app/js/tests/TapisTokenManager.test.js`:
  - expired or exactly-current `expires_at` redirects immediately to `/logout/`;
  - token expiring within 10 minutes warns but does not logout early;
  - missing token metadata is tolerated without redirect loops.
- Run focused backend tests, likely:
  - `./webodm.sh test backend app.tests.test_clusterodm_admin`
  - `./webodm.sh test backend app.tests.test_tapis_oauth2_tokens`
  - focused plugin tests for Upstream, CKAN, and embeddings where available
- Run a JavaScript syntax/build check for `TapisTokenManager.js` if the repo tooling supports a focused command; otherwise run the existing frontend build or parser check and document any unavailable dependency.

## Documentation plan

Update WebODM docs and canonical DSO architecture docs to remove refresh as an expected WebODM behavior:

- WebODM OAuth2 integration docs: remove refresh endpoint usage, refresh API table entry, and refresh examples.
- WebODM deployment docs: remove token refresh monitoring language and describe reauthentication on expiry.
- DSO auth docs: qualify or remove the generic refresh-token section for Portals/WebODM.
- DSO WebODM service page: remove `/api/oauth2/tapis/refresh/{client_id}/` from API endpoint list.

Editing `/Users/wmobley/Documents/Github/DSO-Architecture` requires filesystem approval in this environment. Committing or pushing DSO docs remains a separate explicit approval gate.

## Rollout/rollback plan

Rollout:

- Deploy WebODM with refresh-token usage removed.
- Users with active browser sessions continue until their current JWT expiry time.
- On expiry, the UI logs the user out and they reauthenticate through Tapis.

Rollback:

- Revert the WebODM code and docs changes.
- No database rollback is needed because the schema remains unchanged.
- Any retained `refresh_token` values in old rows are still present if a future tenant supports refresh and the refresh behavior is intentionally restored.

## Open questions

- Should this task also fix JWT signature verification in `app/auth/tapis_oauth2.py`, or should that stay as a separate security task? Recommendation: keep it separate.

## Decisions

### 2026-08-28 - Treat Tapis JWT expiry as terminal

- **Decision:** Remove refresh-token grant behavior from WebODM's Tapis flow and require reauthentication after the access JWT expires.
- **Reason:** The current Portals tenant does not provide a working refresh flow, so refresh attempts create noisy failures and can leave expired-token behavior ambiguous.
- **Alternatives rejected:** Keep opportunistic refresh and fall back to logout when refresh fails; rejected because refresh is known unavailable for this tenant.
- **User feedback:** User said refresh is unavailable in Portals and asked to remove refresh from the flow.
- **Impact on implementation:** Remove refresh view/route, stop storing new refresh tokens, replace refresh-capable helpers with validity-only helpers, and update plugin callers.

### 2026-08-28 - Keep schema compatibility

- **Decision:** Keep the `refresh_token` database column but stop runtime code from using it for Tapis refresh. Clear the field on the next successful OAuth callback and on logout for the authenticated user.
- **Reason:** Runtime behavior can be corrected without a migration, retaining the column keeps rollback simple, and opportunistic clearing reduces legacy secret exposure without a bulk database mutation.
- **Alternatives rejected:** Drop the column now; rejected because it adds migration risk without improving the user-visible behavior. Bulk-clear all existing database rows now; rejected because database mutation is outside the current approval.
- **User feedback:** None beyond the request to remove refresh from the flow.
- **Impact on implementation:** No Django migration is planned; code review must verify the column is unused by runtime refresh paths and cleared only through normal callback/logout code paths.

### 2026-08-28 - Logout immediately at JWT timeout

- **Decision:** When any loaded WebODM UI page sees that the JWT expiry time has arrived or is already past, redirect immediately to `/logout/`.
- **Reason:** This matches the user's requested behavior and avoids keeping a Django UI session that no longer has usable Tapis credentials.
- **Alternatives rejected:** Keep the current expired-session modal and delayed redirect; rejected because the requested behavior is logout on timeout.
- **User feedback:** User said "on timeout of the jwt token lets log the user out of the UI" and then clarified that the UI page changes must be included.
- **Impact on implementation:** Update `TapisTokenManager` and expiry metadata injection so active sessions and reload-after-expiry sessions both logout.

### 2026-08-28 - Server-side token access fails closed

- **Decision:** `get_valid_access_token()` returns no token for expired, malformed, missing, unparsable, or nearly expired JWTs and never makes network calls.
- **Reason:** Browser logout is user experience, not the security boundary. WebODM must avoid forwarding expired or questionable credentials to ClusterODM, Tapis storage, CKAN, Upstream, or embeddings.
- **Alternatives rejected:** Use client-side logout as the main boundary; rejected because background tasks and API calls can happen without a currently active browser timer.
- **User feedback:** None.
- **Impact on implementation:** All Tapis-backed callers move to the non-refreshing helper and tests assert expired-token paths do not call external services.

## User feedback / decisions

- 2026-08-28: User clarified that UI page changes are required: when Tapis auth times out, users should be logged out of the WebODM UI.
- 2026-08-28: User approved the design and asked to implement it: "great do it".

## Implementation deviations

### 2026-08-31 - Fixed `_decode_jwt_payload` broken by refactor

- **Issue:** During implementation, `_decode_jwt_payload` lost its body (only the guard clause remained). The JWT base64 decode logic ended up as dead code inside `_looks_like_jwt` after its `return` statement. This meant `_expires_at_from_token` always returned `None`, so `compute_expires_at` never used the JWT `exp` claim.
- **Fix:** Restored `_decode_jwt_payload` with its full implementation (base64 decode + JSON parse). Removed dead code from `_looks_like_jwt`.
- **Impact:** Without this fix, `get_valid_access_token()` would only check the `expires_at` DB field, never the JWT's own `exp` claim. This is a correctness issue but not a security regression since the 30-second skew and `expires_at` check still prevent expired tokens from being used.

### Files changed (20 modified, 2 new)

**Modified:**
- `app/models/oauth2.py` — Added `get_valid_access_token()`, removed `refresh()` and `get_or_refresh_access_token()`, added `_looks_like_jwt()`, fixed `_decode_jwt_payload()`
- `app/api/tapis_oauth2.py` — Removed `TapisOAuth2TokenRefreshView`, callback no longer stores refresh tokens
- `app/api/urls.py` — Removed `/api/oauth2/tapis/refresh/` route
- `app/views/app.py` — ClusterODM admin uses `get_valid_access_token()`
- `app/views/tapis_auth.py` — Logout clears stored refresh tokens
- `app/templatetags/tapis_tags.py` — Returns expired token metadata for JS logout
- `app/services/tapis_storage.py` — All token calls use `get_valid_access_token()`
- `app/models/task.py` — Uses `get_valid_access_token()`
- `coreplugins/upstream/api.py` — Removed manual refresh grant, uses `get_valid_access_token()`
- `coreplugins/ckan/publisher.py` — Uses `get_valid_access_token()`
- `coreplugins/embeddings/embeddings_client.py` — Uses `get_valid_access_token()`
- `coreplugins/embeddings/tests.py` — Updated mock method names
- `app/tests/test_clusterodm_admin.py` — Added expired JWT rejection test
- `app/static/app/js/classes/TapisTokenManager.js` — Immediate redirect, NaN handling, dedup flag
- `TAPIS_OAUTH2_INTEGRATION.md` — Removed refresh documentation
- `DEPLOYMENT_INSTRUCTIONS.md` — Updated token expiry behavior
- `nodeodm/external/NodeODM` — Submodule update (unrelated)

**New:**
- `app/tests/test_tapis_oauth2_tokens.py` — Unit tests for token validity helpers
- `app/static/app/js/tests/TapisTokenManager.test.js` — JS tests for expiry redirect behavior

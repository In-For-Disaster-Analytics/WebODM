# Tapis OAuth2 Integration for WebODM

This document describes the Tapis OAuth2 integration that has been added to WebODM. **This WebODM instance is configured for Tapis-only authentication** - all other login methods have been disabled.

## Overview

The Tapis OAuth2 integration provides:
- **Tapis-only authentication** - Standard Django login forms are disabled
- OAuth2 authentication flow using Tapis authorization servers
- User management and account creation from Tapis user information
- Token expiry handling that logs users out when their Tapis JWT expires
- Django admin interface for OAuth2 client management
- REST API endpoints for OAuth2 operations

## ⚠️ Important: Tapis-Only Configuration

This WebODM instance has been configured to **only allow Tapis OAuth2 authentication**. The following have been disabled/removed:
- Standard Django username/password login
- External authentication endpoints
- Django's built-in authentication forms

Users **must** authenticate through Tapis to access this WebODM instance.

## Architecture

### Components

1. **Authentication Backend** (`app/auth/tapis_oauth2.py`)
   - Custom Django authentication backend
   - Validates Tapis OAuth2 tokens
   - Creates/updates user accounts from Tapis user data

2. **Models** (`app/models/oauth2.py`)
   - `TapisOAuth2Client`: OAuth2 client configuration
   - `TapisOAuth2Token`: User OAuth2 tokens storage
   - `TapisOAuth2State`: CSRF protection for OAuth2 flow

3. **API Views** (`app/api/tapis_oauth2.py`)
   - Authorization initiation
   - OAuth2 callback handling
   - Token status and revocation management
   - Status and revocation endpoints

4. **Admin Interface** (`app/admin/oauth2.py`)
   - Django admin integration for managing OAuth2 clients
   - Token monitoring and management
   - State cleanup utilities

## Setup Instructions

### 1. Install Dependencies

```bash
pip install requests-oauthlib==1.3.1 oauthlib==3.2.0
```

### 2. Database Migration

Create and run database migrations for the new OAuth2 models:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Environment Configuration

Add the following environment variables or configure in `webodm/settings.py`:

```bash
# Required: Base URL for Tapis API
export WO_TAPIS_BASE_URL="https://tacc.tapis.io"

# Required: Tapis tenant ID
export WO_TAPIS_TENANT_ID="your-tenant-id"
```

### 4. Create OAuth2 Client

1. Access the Django admin interface: `/admin/`
2. Navigate to "Tapis OAuth2 Clients"
3. Add a new client with:
   - **Name**: Descriptive name (e.g., "WebODM Production")
   - **Client ID**: Your Tapis OAuth2 client ID
   - **Client Secret**: Your Tapis OAuth2 client secret (or leave blank to auto-generate)
   - **Tenant ID**: Your Tapis tenant ID
   - **Base URL**: Your Tapis base URL (e.g., `https://tacc.tapis.io`)
   - **Callback URL**: `https://your-webodm-domain.com/api/oauth2/tapis/callback/`

### 5. Register OAuth2 Client with Tapis

Register your WebODM instance as an OAuth2 client with Tapis:

```bash
curl -X POST https://tacc.tapis.io/v3/oauth2/clients \
  -H "Content-Type: application/json" \
  -H "X-Tapis-Tenant: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "client_id": "webodm-client-id",
    "callback_url": "https://your-webodm-domain.com/api/oauth2/tapis/callback/",
    "display_name": "WebODM Instance"
  }'
```

## Usage

### User Authentication Flow

1. **Initiate OAuth2 Flow**
   ```
   GET /api/oauth2/tapis/authorize/{client_id}/
   ```
   - Redirects user to Tapis authorization server
   - Optional `redirect_after` parameter for post-auth redirect

2. **OAuth2 Callback**
   ```
   GET /api/oauth2/tapis/callback/
   ```
   - Handles authorization code from Tapis
   - Exchanges code for access token data
   - Authenticates user and creates session

3. **Check Authentication Status**
   ```
   GET /api/oauth2/tapis/status/
   ```
   - Returns user's OAuth2 token status
   - Shows token validity and expiration

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/oauth2/tapis/authorize/{client_id}/` | GET | Initiate OAuth2 flow |
| `/api/oauth2/tapis/callback/` | GET | Handle OAuth2 callback |
| `/api/oauth2/tapis/status/` | GET | Get token status |
| `/api/oauth2/tapis/revoke/{client_id}/` | POST | Revoke tokens |

### Frontend Integration

The login page has been modified to only show Tapis authentication. Users visiting `/login/` will see:

- **Automatic Tapis OAuth2 login button** using the default configured client
- **No username/password fields** - these have been removed
- **Error handling** for OAuth2 authentication issues

The login template automatically uses the first active Tapis OAuth2 client for authentication.

### JavaScript Integration

```javascript
// Check OAuth2 status
fetch('/api/oauth2/tapis/status/')
  .then(response => response.json())
  .then(data => {
    console.log('OAuth2 Status:', data);
  });

// Tapis JWT expiry is terminal in the current Portals tenant.
// Loaded UI pages redirect to /logout/ when the token expires.
```

## HPC access (Tapis system credentials)

Signing in proves identity, but running a job needs more: ClusterODX submits Tapis jobs
with the user's own JWT, and Tapis must hold a credential for that user on the execution
system (`ls6`, TMS-managed SSH keys). A user without one gets
`SYSTEMS_MISSING_CREDENTIALS` on their first job.

WebODM therefore checks the credential and can create it on request:

- The dashboard mounts `HpcAccessBanner`. It calls `GET /api/tapis/hpc-access/` and, when
  the credential is missing and the user holds an active allocation, shows a
  **Set up HPC access** button. The button calls `POST /api/tapis/hpc-access/`, which asks
  Tapis to generate TMS keys (`createTmsKeys=true`). WebODM never sees key material.
- The same banner appears above the task form and inside a failed task whose error
  contains `SYSTEMS_MISSING_CREDENTIALS`.
- The check is advisory. `unknown` results (Tapis unreachable, expired token, unexpected
  response) are shown as a dismissible note and never block task submission.

### Endpoint

`GET /api/tapis/hpc-access/?system_id=<optional>&refresh=1` returns HTTP 200 with the
payload below whatever Tapis answered (`400` only for a malformed `system_id`, `429` when
throttled):

```json
{"system_id": "ls6", "status": "ready|missing|unknown",
 "code": "ok|credential_missing|token_expired|not_authorized|tapis_unreachable|unexpected_response|no_tapis_token|misconfigured",
 "detail": "<Tapis message, at most 300 characters>", "checked_at": "2026-11-03T15:04:05Z"}
```

`POST /api/tapis/hpc-access/` runs a fresh probe first and only creates when it reports
`missing`. Responses: `200` with the refreshed status; `409` with `already_ready` or
`cannot_verify`; `429` while another request for the same user is in flight; `502` with
`create_failed`, `not_authorized`, `token_expired` or `tapis_unreachable`.

Probe rules: `missing` requires an explicit Tapis signal (`SYSAPI_CRED_NOT_FOUND` from the
credential record, or `SYSTEMS_MISSING_CREDENTIALS` from a Files listing of the system
root). A bare 404 or 403 is `unknown`. Positive results are cached per user for
`WO_TAPIS_CREDENTIAL_CACHE_SECONDS`; the cache is cleared on logout and after a create.
Both methods are throttled per user (`hpc_access_get` 10/min, `hpc_access_post` 3/min).
The banner stays silent for `no_tapis_token` and `misconfigured`, so stock (non-Tapis)
accounts and unconfigured dev instances see nothing.

Note for development: with `WO_DEBUG=YES` the cache backend is `DummyCache`, so the
positive-result cache, the refresh limiter and the create lock are inert there; production
uses Redis.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `WO_TAPIS_EXEC_SYSTEM_ID` | `ls6` | Execution system to check. Must equal ClusterODX `system.executionSystemId`. |
| `WO_TAPIS_CREDENTIAL_CACHE_SECONDS` | `600` | How long a `ready` result is cached per user. |

The user's JWT is only sent to the OAuth client's `base_url`, which must equal
`WO_TAPIS_BASE_URL`; a mismatch yields `misconfigured` and no outbound call.

## Configuration Options

### Settings

The following settings have been configured for Tapis-only authentication in `webodm/settings.py`:

```python
# Tapis OAuth2 Configuration
TAPIS_BASE_URL = os.environ.get('WO_TAPIS_BASE_URL', 'https://tacc.tapis.io')
TAPIS_TENANT_ID = os.environ.get('WO_TAPIS_TENANT_ID', '')

# Authentication backends - Tapis OAuth2 only
AUTHENTICATION_BACKENDS = (
    'guardian.backends.ObjectPermissionBackend',
    'app.auth.tapis_oauth2.TapisOAuth2Backend',  # Only Tapis OAuth2
)

# External auth disabled
EXTERNAL_AUTH_ENDPOINT = ''

# Template context processor for Tapis
TEMPLATES[0]['OPTIONS']['context_processors'].append('app.contexts.tapis.tapis_oauth2_context')
```

**Note**: The standard Django `ModelBackend` and `ExternalBackend` have been removed to enforce Tapis-only authentication.

### Multiple Tenants

The integration supports multiple Tapis tenants by creating separate OAuth2 clients for each tenant.

## Security Considerations

1. **Client Secrets**: Store client secrets securely and rotate them regularly
2. **HTTPS**: Always use HTTPS in production for OAuth2 flows
3. **Token Storage**: Tokens are stored encrypted in the database
4. **State Validation**: CSRF protection through OAuth2 state parameter
5. **Token Expiration**: Tapis JWT expiry is terminal; users must re-authenticate after logout

## Troubleshooting

### Common Issues

1. **Invalid Client Error**
   - Verify client ID and secret in Django admin
   - Ensure client is registered with Tapis

2. **Callback URL Mismatch**
   - Verify callback URL matches exactly in both Tapis and WebODM
   - Check for trailing slashes

3. **Token Validation Failed**
   - Check Tapis tenant ID configuration
   - Verify Tapis base URL is correct
   - Check network connectivity to Tapis servers

4. **User Creation Failed**
   - Check Django logs for specific errors
   - Verify user data returned from Tapis

### Debugging

Enable debug logging in Django settings:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'app.auth.tapis_oauth2': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'app.api.tapis_oauth2': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Testing OAuth2 Flow

1. Access `/api/oauth2/tapis/authorize/your-client-id/`
2. Complete Tapis authentication
3. Verify redirect to WebODM with successful login
4. Check `/api/oauth2/tapis/status/` for token information

#### Simulating Short Token Expiration (Local Testing)

When you need to test the warning banner or automatic logout without waiting hours, force a shorter expiry while running WebODM locally:

```bash
export WO_TAPIS_FORCE_TOKEN_EXPIRATION_SECONDS=30
./webodm.sh start
```

Any tokens created while this variable is set will be treated as expiring in 30 seconds, so the UI should warn and log out accordingly. Remove the variable (or restart without it) to return to normal Tapis-provided expirations.

## Maintenance

### Token Cleanup

Periodically clean up expired OAuth2 states:

```python
# In Django shell or management command
from app.models import TapisOAuth2State
TapisOAuth2State.cleanup_expired()
```

### Monitoring

Monitor OAuth2 integration through:
- Django admin interface for client and token status
- Application logs for authentication errors
- Database queries for token usage patterns

## Migration from External Auth

If migrating from the existing external authentication system:

1. Install and configure Tapis OAuth2 integration
2. Create OAuth2 clients for existing authentication endpoints
3. Update frontend to use OAuth2 flow
4. Gradually migrate users to OAuth2 authentication
5. Disable old external authentication once migration is complete

## Support

For issues specific to this integration, check:
1. Django application logs
2. Tapis API documentation: https://tapis.readthedocs.io/
3. OAuth2 specification: https://tools.ietf.org/html/rfc6749

## Files Modified/Added

### New Files
- `app/auth/tapis_oauth2.py` - Tapis OAuth2 authentication backend
- `app/models/oauth2.py` - OAuth2 database models
- `app/api/tapis_oauth2.py` - OAuth2 API views
- `app/admin/oauth2.py` - Django admin interface for OAuth2
- `app/contexts/tapis.py` - Template context processor for Tapis
- `app/views/tapis_auth.py` - Custom login/logout views for Tapis-only auth
- `app/templates/app/registration/tapis_login.html` - Tapis-only login template

### Modified Files
- `requirements.txt` - Added OAuth2 dependencies (`requests-oauthlib`, `oauthlib`)
- `webodm/settings.py` - **Tapis-only authentication backends**, disabled external auth
- `webodm/urls.py` - **Removed Django auth URLs**, admin-only access
- `app/api/urls.py` - Added OAuth2 endpoints, **disabled external auth API**
- `app/urls.py` - Added Tapis authentication URLs
- `app/models/__init__.py` - Import OAuth2 models
- `app/admin.py` - Import OAuth2 admin
- `app/templates/app/registration/login.html` - **Replaced with Tapis-only login**

### Key Changes for Tapis-Only Authentication

1. **Authentication Backends**: Only `TapisOAuth2Backend` and `ObjectPermissionBackend` are enabled
2. **Login Templates**: Standard login forms replaced with Tapis OAuth2 redirect
3. **URL Configuration**: Django's built-in auth URLs removed
4. **API Endpoints**: External authentication API disabled
5. **Admin Access**: Django admin still accessible but requires Tapis authentication

⚠️ **Warning**: Once these changes are applied, **only users with valid Tapis accounts** can access this WebODM instance.

This integration provides a robust, secure, and scalable OAuth2 authentication solution for WebODM using Tapis services.

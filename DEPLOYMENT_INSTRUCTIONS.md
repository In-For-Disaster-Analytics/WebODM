# WebODM Tapis OAuth2 Deployment Instructions

This guide provides step-by-step instructions for deploying the Tapis OAuth2 integration in your WebODM environment.

## ⚠️ Important Notice

**This configuration disables all authentication methods except Tapis OAuth2.** Ensure you have valid Tapis credentials and have registered your OAuth2 client with Tapis before proceeding.

## Prerequisites

1. **WebODM Installation**: Either Docker-based or native installation
2. **Tapis Account**: Valid account with the target Tapis tenant
3. **Tapis OAuth2 Client**: Registered OAuth2 application in Tapis
4. **Network Access**: WebODM server can reach Tapis API endpoints
5. **Admin Access**: Ability to modify WebODM configuration and database

## Deployment Steps

### Step 1: Apply Code Changes

All necessary files have been created/modified in your WebODM installation:

**New Files:**
- `app/auth/tapis_oauth2.py`
- `app/models/oauth2.py`
- `app/api/tapis_oauth2.py`
- `app/admin/oauth2.py`
- `app/contexts/tapis.py`
- `app/views/tapis_auth.py`
- `app/migrations/0002_tapis_oauth2_models.py`
- `setup_tapis_oauth2.py`

**Modified Files:**
- `requirements.txt`
- `webodm/settings.py`
- `webodm/urls.py`
- `app/api/urls.py`
- `app/urls.py`
- `app/models/__init__.py`
- `app/admin.py`
- `app/templates/app/registration/login.html`

### Step 2: Environment Configuration

Set the following environment variables:

#### For Docker Deployment:
```bash
# Add to docker-compose.yml or .env file
WO_TAPIS_BASE_URL=https://tacc.tapis.io
WO_TAPIS_TENANT_ID=your-tenant-id
```

#### For Native Deployment:
```bash
export WO_TAPIS_BASE_URL="https://tacc.tapis.io"
export WO_TAPIS_TENANT_ID="your-tenant-id"
```

### Step 3: Install Dependencies

#### For Docker Deployment:
The dependencies will be installed automatically when the container rebuilds.

#### For Native Deployment:
```bash
pip install requests-oauthlib==1.3.1 oauthlib==3.2.0
```

### Step 4: Database Migration

#### Option A: Using the Setup Script (Recommended)
```bash
python setup_tapis_oauth2.py
```

#### Option B: Manual Migration
```bash
python manage.py migrate
```

### Step 5: Create Tapis OAuth2 Client

#### Via Setup Script:
The setup script will prompt you to create a client during setup.

#### Via Django Admin:
1. Start WebODM
2. Access Django admin: `http://your-webodm-domain.com/admin/`
3. Navigate to "Tapis OAuth2 Clients"
4. Add new client:
   - **Name**: Descriptive name (e.g., "Production WebODM")
   - **Client ID**: Your Tapis OAuth2 client ID
   - **Client Secret**: Your Tapis OAuth2 client secret
   - **Tenant ID**: Your Tapis tenant ID
   - **Base URL**: Tapis API base URL (e.g., `https://tacc.tapis.io`)
   - **Callback URL**: `https://your-webodm-domain.com/api/oauth2/tapis/callback/`

### Step 6: Register Callback URL with Tapis

Register your WebODM callback URL with your Tapis OAuth2 client:

#### Using Tapis API:
```bash
curl -X POST https://tacc.tapis.io/v3/oauth2/clients \
  -H "Content-Type: application/json" \
  -H "X-Tapis-Tenant: your-tenant-id" \
  -H "Authorization: Bearer your-admin-token" \
  -d '{
    "client_id": "your-webodm-client-id",
    "callback_url": "https://your-webodm-domain.com/api/oauth2/tapis/callback/",
    "display_name": "WebODM Instance"
  }'
```

#### Using Tapis Dashboard:
Navigate to your Tapis tenant dashboard and configure the OAuth2 client with the callback URL.

### Step 7: Test Authentication

1. Access your WebODM instance: `https://your-webodm-domain.com`
2. You should be redirected to the login page showing "Login with Tapis"
3. Click the login button
4. Complete OAuth2 flow with Tapis
5. Verify successful login to WebODM dashboard

## Docker-Specific Instructions

### Using webodm.sh Script

1. **Stop WebODM**:
   ```bash
   ./webodm.sh stop
   ```

2. **Set Environment Variables**:
   Create or modify `.env` file in WebODM directory:
   ```bash
   WO_TAPIS_BASE_URL=https://tacc.tapis.io
   WO_TAPIS_TENANT_ID=your-tenant-id
   ```

3. **Rebuild and Start**:
   ```bash
   ./webodm.sh rebuild
   ./webodm.sh start
   ```

4. **Run Setup**:
   ```bash
   ./webodm.sh run webapp python setup_tapis_oauth2.py
   ```

### Using Docker Compose Directly

1. **Modify docker-compose.yml**:
   ```yaml
   services:
     webapp:
       environment:
         - WO_TAPIS_BASE_URL=https://tacc.tapis.io
         - WO_TAPIS_TENANT_ID=your-tenant-id
   ```

2. **Rebuild and Start**:
   ```bash
   docker-compose build webapp
   docker-compose up -d
   ```

3. **Run Migrations**:
   ```bash
   docker-compose exec webapp python manage.py migrate
   ```

## Configuration Verification

### Check Authentication Backend:
```bash
# In Django shell
python manage.py shell
```

```python
from django.conf import settings
print(settings.AUTHENTICATION_BACKENDS)
# Should show only Tapis and Guardian backends
```

### Check OAuth2 Client:
```bash
# In Django shell
from app.models import TapisOAuth2Client
clients = TapisOAuth2Client.objects.all()
for client in clients:
    print(f"Client: {client.name} (Active: {client.is_active})")
```

### Test OAuth2 Endpoints:
```bash
curl -s https://your-webodm-domain.com/api/oauth2/tapis/status/ | jq
```

## Troubleshooting

### Common Issues:

1. **Migration Errors**:
   ```bash
   # Reset migrations if necessary
   python manage.py migrate app zero
   python manage.py migrate
   ```

2. **Template Errors**:
   - Verify `default_tapis_client_id` is available in template context
   - Check Django admin for active OAuth2 clients

3. **OAuth2 Flow Errors**:
   - Verify callback URL matches exactly in both Tapis and WebODM
   - Check Tapis tenant ID configuration
   - Verify network connectivity to Tapis endpoints

4. **Authentication Loop**:
   - Clear browser cookies
   - Check Django session configuration
   - Verify OAuth2 client is active

### Debug Logging:

Add to `webodm/settings.py`:
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

## Rollback Instructions

If you need to revert to standard authentication:

1. **Restore Authentication Backends**:
   ```python
   # In webodm/settings.py
   AUTHENTICATION_BACKENDS = (
       'django.contrib.auth.backends.ModelBackend',
       'guardian.backends.ObjectPermissionBackend',
   )
   ```

2. **Restore Django Auth URLs**:
   ```python
   # In webodm/urls.py
   urlpatterns = [
       url(r'^', include('app.urls')),
       url(r'^', include('django.contrib.auth.urls')),  # Add this back
       url(r'^admin/', admin.site.urls),
       # ... rest of URLs
   ]
   ```

3. **Restore Login Template**:
   - Restore original `app/templates/app/registration/login.html`

4. **Restart WebODM**

## Security Considerations

1. **Client Secrets**: Store securely and rotate regularly
2. **HTTPS**: Always use HTTPS in production
3. **Callback URLs**: Use exact matching, avoid wildcards
4. **Token Storage**: Tokens are encrypted in database
5. **Session Management**: Configure appropriate session timeouts

## Monitoring

Monitor the following for production deployments:

- OAuth2 authentication success/failure rates
- Token refresh frequency
- Database growth (OAuth2 state cleanup)
- Tapis API response times
- WebODM authentication errors

## Support

For issues with this integration:

1. Check Django application logs
2. Review Tapis API documentation
3. Verify OAuth2 client configuration
4. Test network connectivity to Tapis endpoints

---

**🚨 Final Warning**: Once deployed, only users with valid Tapis accounts can access WebODM. Ensure you have tested the complete OAuth2 flow before deploying to production.
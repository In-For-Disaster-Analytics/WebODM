# Tapis OAuth2 Docker Deployment for WebODM

This guide shows how to deploy the Tapis OAuth2 integration using WebODM's `webodm.sh` Docker management script.

## Prerequisites

1. **Tapis Account**: Valid credentials for your target tenant
2. **Tapis OAuth2 Client**: Registered with callback URL
3. **Domain/Hostname**: Where WebODM will be accessible
4. **SSL Certificate** (recommended): For production HTTPS

## Step-by-Step Deployment

### 1. Configure Environment Variables

Create or edit the `.env` file in your WebODM directory:

```bash
# Create .env file for Tapis configuration
cat > .env << EOF
WO_TAPIS_BASE_URL=https://tacc.tapis.io
WO_TAPIS_TENANT_ID=your-tenant-id-here
EOF
```

Or set them directly:
```bash
export WO_TAPIS_BASE_URL="https://tacc.tapis.io"
export WO_TAPIS_TENANT_ID="your-tenant-id"
```

### 2. Stop Current WebODM Instance

```bash
./webodm.sh stop
```

### 3. Rebuild Docker Containers

This rebuilds the containers with your new Tapis OAuth2 code:

```bash
./webodm.sh rebuild
```

### 4. Start WebODM with Your Configuration

#### For Development/Testing:
```bash
./webodm.sh start --hostname localhost --port 8000 --detached
```

#### For Production with SSL:
```bash
./webodm.sh start \
  --hostname your-domain.com \
  --port 443 \
  --ssl \
  --detached
```

#### For Production with Custom SSL:
```bash
./webodm.sh start \
  --hostname your-domain.com \
  --ssl-cert /path/to/cert.pem \
  --ssl-key /path/to/key.pem \
  --detached
```

### 5. Run Database Migration and Setup

```bash
# Run the interactive setup script
./webodm.sh run webapp python setup_tapis_oauth2.py
```

This will:
- Run database migrations for OAuth2 models
- Verify environment configuration  
- Optionally create a Tapis OAuth2 client
- Provide setup completion status

### 6. Configure OAuth2 Client (if not done in setup)

Access Django admin to create OAuth2 client:

```bash
# Get the admin URL
echo "Admin URL: http://$(./webodm.sh start --hostname localhost --port 8000 | grep -o 'localhost:[0-9]*')/admin/"
```

Or if running with custom hostname:
```
https://your-domain.com/admin/
```

**OAuth2 Client Configuration:**
- **Name**: `WebODM-Production` (or similar)
- **Client ID**: Your Tapis OAuth2 client ID
- **Client Secret**: Your Tapis OAuth2 client secret  
- **Tenant ID**: Your Tapis tenant ID
- **Base URL**: `https://tacc.tapis.io` (or your Tapis URL)
- **Callback URL**: `https://your-domain.com/api/oauth2/tapis/callback/`

### 7. Register Callback URL with Tapis

Register your WebODM callback URL with Tapis:

```bash
curl -X POST https://tacc.tapis.io/v3/oauth2/clients \
  -H "Content-Type: application/json" \
  -H "X-Tapis-Tenant: your-tenant-id" \
  -H "Authorization: Bearer your-tapis-token" \
  -d '{
    "client_id": "your-webodm-client-id",
    "callback_url": "https://your-domain.com/api/oauth2/tapis/callback/",
    "display_name": "WebODM Instance"
  }'
```

### 8. Test Authentication

1. Visit your WebODM instance: `https://your-domain.com`
2. You should see "Login with Tapis" button
3. Complete OAuth2 flow
4. Verify successful login to dashboard

## Configuration Examples

### Example 1: Development Setup
```bash
# Environment
export WO_TAPIS_BASE_URL="https://tacc.tapis.io"
export WO_TAPIS_TENANT_ID="dev"

# Start WebODM
./webodm.sh start --hostname localhost --port 8000 --debug --dev

# Setup
./webodm.sh run webapp python setup_tapis_oauth2.py
```

### Example 2: Production Setup with SSL
```bash
# Environment  
cat > .env << EOF
WO_TAPIS_BASE_URL=https://tacc.tapis.io
WO_TAPIS_TENANT_ID=tacc
EOF

# Start WebODM
./webodm.sh start \
  --hostname webodm.yourdomain.com \
  --ssl \
  --detached \
  --media-dir /data/webodm/media \
  --db-dir /data/webodm/db

# Setup
./webodm.sh run webapp python setup_tapis_oauth2.py
```

### Example 3: Multi-Node Production
```bash
# Start with multiple processing nodes
./webodm.sh start \
  --hostname webodm.yourdomain.com \
  --ssl \
  --detached \
  --default-nodes 3 \
  --gpu \
  --worker-memory 8GB \
  --worker-cpus 4
```

## Management Commands

### Check Status
```bash
docker ps | grep webodm
```

### View Logs
```bash
# All services
./webodm.sh run webapp docker-compose logs

# Specific service  
./webodm.sh run webapp docker-compose logs webapp
```

### Access Shell
```bash
# Django shell
./webodm.sh run webapp python manage.py shell

# Bash shell
./webodm.sh run webapp bash
```

### Database Operations
```bash
# Run migrations manually
./webodm.sh run webapp python manage.py migrate

# Create superuser (after Tapis auth is working)
./webodm.sh run webapp python manage.py createsuperuser
```

## Troubleshooting

### Check Environment Variables
```bash
./webodm.sh run webapp python -c "
import os
print('TAPIS_BASE_URL:', os.environ.get('WO_TAPIS_BASE_URL'))
print('TAPIS_TENANT_ID:', os.environ.get('WO_TAPIS_TENANT_ID'))
"
```

### Check OAuth2 Clients
```bash
./webodm.sh run webapp python manage.py shell -c "
from app.models import TapisOAuth2Client
for c in TapisOAuth2Client.objects.all():
    print(f'Client: {c.name} (Active: {c.is_active})')
"
```

### Test OAuth2 Endpoints
```bash
# Test status endpoint
curl -s https://your-domain.com/api/oauth2/tapis/status/ | jq

# Test authorize redirect
curl -I https://your-domain.com/api/oauth2/tapis/authorize/your-client-id/
```

### View Authentication Logs
```bash
./webodm.sh run webapp docker-compose logs webapp | grep -i tapis
```

## Updates and Maintenance

### Update WebODM (preserving Tapis integration)
```bash
# Stop WebODM
./webodm.sh stop

# Update WebODM
./webodm.sh update

# Rebuild with your changes (Tapis code should persist)
./webodm.sh rebuild

# Start again
./webodm.sh start --detached [your-options]
```

### Backup Configuration
```bash
# Backup OAuth2 client data
./webodm.sh run webapp python manage.py dumpdata app.TapisOAuth2Client > tapis_clients_backup.json

# Restore OAuth2 client data
./webodm.sh run webapp python manage.py loaddata tapis_clients_backup.json
```

## Performance Tuning

For production deployments with heavy usage:

```bash
./webodm.sh start \
  --hostname webodm.yourdomain.com \
  --ssl \
  --detached \
  --default-nodes 4 \
  --worker-memory 16GB \
  --worker-cpus 8 \
  --broker redis://redis-cluster:6379
```

## Security Checklist

- [ ] HTTPS enabled (SSL)
- [ ] Strong OAuth2 client secret
- [ ] Callback URL uses HTTPS
- [ ] Firewall configured (only 80/443 exposed)
- [ ] Regular security updates
- [ ] Database backups configured
- [ ] Log monitoring enabled

---

**🎉 Your WebODM instance will now use Tapis OAuth2 exclusively for authentication!**

Users visiting your WebODM instance will be automatically redirected through Tapis for authentication - no other login methods will be available.
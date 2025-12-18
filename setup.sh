#!/bin/bash

# WebODM + ClusterODM Automated Setup Script for webodm.tacc.utexas.edu
# This script automates the deployment process described in DEPLOYMENT_GUIDE.md

set -e  # Exit on any error

# Configuration
HOSTNAME="webodm.tacc.utexas.edu"
WEBODM_PORT="8000"
CLUSTERODM_PORT="3000"
NODEODM_PORT="3001"
CORRAL_BASE="/corral"
CORRAL_GROUP="PT2050-DataX"
CORRAL_GROUP_ID=""
REPO_BASE="$HOME/ODM-SUITE"
LOCAL_DB_DIR="$REPO_BASE/postgres-data"
LOG_FILE="$REPO_BASE/setup.sh.log"

# Ensure log file directory exists, initialize the log and always mirror output to stdout
mkdir -p "$(dirname "$LOG_FILE")"
if [[ -z "${APPEND_SETUP_LOG:-}" ]]; then
    : > "$LOG_FILE"
fi

exec > >(tee -a "$LOG_FILE")
exec 2>&1

timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

log_write() {
    local level="$1"
    local message="$2"

    printf '%s [%s] %s\n' "$(timestamp)" "$level" "$message"
}

# Logging functions
log_info() { log_write "INFO" "$1"; }
log_success() { log_write "SUCCESS" "$1"; }
log_warning() { log_write "WARNING" "$1"; }
log_error() { log_write "ERROR" "$1"; }

# Cross-platform stat helpers
stat_owner() {
    local path="$1"
    if stat --format %U "$path" &>/dev/null; then
        stat --format %U "$path"
    else
        stat -f %Su "$path"
    fi
}

stat_group() {
    local path="$1"
    if stat --format %G "$path" &>/dev/null; then
        stat --format %G "$path"
    else
        stat -f %Sg "$path"
    fi
}

resolve_corral_group() {
    if getent group "$CORRAL_GROUP" &>/dev/null; then
        CORRAL_GROUP_ID=$(getent group "$CORRAL_GROUP" | cut -d: -f3)
    else
        CORRAL_GROUP_ID=""
    fi
}

require_corral_group_membership() {
    resolve_corral_group

    if [[ -z "$CORRAL_GROUP_ID" ]]; then
        log_error "Required group $CORRAL_GROUP is not defined on this system. Please create it or mount the shared storage before continuing."
        exit 1
    fi

    if ! id -nG "$USER" | tr ' ' '\n' | grep -Fxq "$CORRAL_GROUP"; then
        log_error "User $USER is not a member of $CORRAL_GROUP. Please run 'sudo usermod -a -G $CORRAL_GROUP $USER' (or equivalent) and re-login."
        exit 1
    fi
}

# Ensure ownership of corral directories when possible
ensure_dir_ownership() {
    local path="$1"
    local desired_user="$USER"
    local desired_group

    resolve_corral_group
    if [[ -n "$CORRAL_GROUP_ID" ]]; then
        desired_group="$CORRAL_GROUP"
    else
        desired_group=$(id -gn)
    fi

    [[ -e "$path" ]] || return 0

    local current_owner current_group
    current_owner=$(stat_owner "$path" 2>/dev/null || echo "")
    current_group=$(stat_group "$path" 2>/dev/null || echo "")

    if [[ "$current_owner" == "$desired_user" && "$current_group" == "$desired_group" ]]; then
        return 0
    fi

    if sudo chown -R "$desired_user:$desired_group" "$path"; then
        log_info "Adjusted ownership for $path"
        if [[ "$desired_group" == "$CORRAL_GROUP" ]]; then
            sudo chmod g+rwXs "$path" 2>/dev/null || true
        fi
    else
        log_warning "Could not change ownership of $path; continuing (root-squash?)"
    fi
}

# Handle signals properly
cleanup() {
    log_error "Script interrupted"
    exit 1
}
trap cleanup SIGINT SIGTERM

# JWT helper for ClusterODM probes
clusterodm_probe_token() {
    local candidate
    for candidate in \
        "$CLUSTERODM_HEALTHCHECK_TOKEN" \
        "$TAPIS_HEALTHCHECK_TOKEN" \
        "$TAPIS_ACCESS_TOKEN" \
        "$TAPIS_TOKEN"
    do
        if [[ -n "$candidate" ]]; then
            printf '%s' "$candidate"
            return 0
        fi
    done

    if [[ -n "$CLUSTERODM_HEALTHCHECK_TOKEN_FILE" && -f "$CLUSTERODM_HEALTHCHECK_TOKEN_FILE" ]]; then
        tr -d '\r\n' < "$CLUSTERODM_HEALTHCHECK_TOKEN_FILE"
        return 0
    fi

    return 1
}

clusterodm_probe_curl() {
    local url="$1"
    shift || true

    local token
    token=$(clusterodm_probe_token 2>/dev/null || true)

    if [[ -n "$token" ]]; then
        curl -s -H "Authorization: Bearer $token" "$url" "$@"
    else
        curl -s "$url" "$@"
    fi
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Ensure Docker Compose plugin is available
    if ! docker compose version &> /dev/null; then
        log_warning "Docker Compose plugin not found, attempting installation..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y docker-compose-plugin
        else
            log_warning "apt-get not available, please install the Docker Compose plugin manually"
        fi

        if ! docker compose version &> /dev/null; then
            log_error "Docker Compose plugin is not installed. Please install docker-compose-plugin and rerun this script."
            exit 1
        fi

        log_success "Docker Compose plugin installed"
    fi
    
    # Check if Node.js is installed, install if not
    if ! command -v node &> /dev/null; then
        log_info "Node.js not found, installing..."
        # Install Node.js via NodeSource repository
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt-get install -y nodejs
        
        # Verify installation
        if ! command -v node &> /dev/null; then
            log_error "Failed to install Node.js"
            exit 1
        else
            log_success "Node.js $(node --version) installed successfully"
        fi
    fi
    
    # Check if user is in docker group
    if ! groups | grep -q docker; then
        log_error "User is not in docker group. Please add user to docker group and re-login."
        exit 1
    fi

    require_corral_group_membership
    
    # Create corral base directory if it doesn't exist
    if [[ ! -d "$CORRAL_BASE" ]]; then
        log_info "Creating /corral base directory..."
        sudo mkdir -p "$CORRAL_BASE"
        log_success "/corral directory created"
    fi
    
    log_success "Prerequisites check passed"
}

# Create storage directories
setup_storage() {
    log_info "Setting up storage directories..."
    
    # Create WebODM build directory (needed for Docker build context)
    mkdir -p "$REPO_BASE/WebODM/db"
    
    # Copy db build files if they don't exist
    if [[ ! -f "$REPO_BASE/WebODM/db/Dockerfile" ]]; then
        log_info "Database build files missing - this suggests the WebODM repository was not fully cloned"
        log_error "Please ensure the WebODM repository is completely cloned with all files"
        exit 1
    fi
    
    # Create WebODM storage
    mkdir -p "$CORRAL_BASE/webodm/media"
    mkdir -p "$CORRAL_BASE/webodm/backups"
    mkdir -p "$LOCAL_DB_DIR"
    
    # Create ClusterODM storage
    sudo mkdir -p "$CORRAL_BASE/clusterodm/data"
    
    # Set permissions (best effort; may be skipped on root-squashed exports)
    ensure_dir_ownership "$CORRAL_BASE/webodm"
    ensure_dir_ownership "$CORRAL_BASE/clusterodm"
    if sudo chown -R 999:999 "$LOCAL_DB_DIR"; then
        log_info "Database directory owner set to postgres (999:999)"
    else
        log_warning "Could not set ownership on $LOCAL_DB_DIR (postgres container may fail)"
    fi
    
    log_success "Storage directories created (existing contents preserved)"
}

# Update repositories
update_repos() {
    log_info "Updating repositories..."
    
    # Update WebODM
    if [[ -d "$REPO_BASE/WebODM" ]]; then
        cd "$REPO_BASE/WebODM"
        if [[ -d ".git" ]]; then
            log_info "Pulling latest WebODM..."
            git pull origin master || git pull origin main || log_warning "Failed to pull WebODM"
        fi
    fi
    
    # Update ClusterODM-Tapis
    if [[ -d "/home/wmobley/ODM-SUITE/ClusterODM" ]]; then
        cd "/home/wmobley/ODM-SUITE/ClusterODM"
        if [[ -d ".git" ]]; then
            log_info "Pulling latest ClusterODM-Tapis..."
            git pull origin master || git pull origin main || log_warning "Failed to pull ClusterODM-Tapis"
        fi
    fi
    
    log_success "Repository updates completed"
}

# Install Docker Buildx if needed
install_buildx() {
    if ! docker buildx version &> /dev/null; then
        log_info "Installing Docker Buildx..."
        
        # Get latest buildx release
        BUILDX_VERSION=$(curl -s https://api.github.com/repos/docker/buildx/releases/latest | grep 'tag_name' | cut -d '"' -f 4)
        
        # Create plugin directory
        mkdir -p ~/.docker/cli-plugins
        
        # Download and install buildx
        curl -L "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-amd64" -o ~/.docker/cli-plugins/docker-buildx
        chmod +x ~/.docker/cli-plugins/docker-buildx
        
        log_success "Docker Buildx installed"
    else
        log_info "Docker Buildx is already available"
    fi
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    # Try to install buildx if missing
    install_buildx
    
    # Check if buildx is working
    if docker buildx version &> /dev/null; then
        # Enable Docker BuildKit
        export DOCKER_BUILDKIT=1
        export COMPOSE_DOCKER_CLI_BUILD=1
        log_info "Docker BuildKit enabled with Buildx"
    else
        # Fallback to legacy build
        log_warning "BuildKit/Buildx not available, using legacy Docker build"
        unset DOCKER_BUILDKIT
        unset COMPOSE_DOCKER_CLI_BUILD
    fi
    
    # Install ClusterODM-Tapis dependencies
    if [[ -d "/home/wmobley/ODM-SUITE/ClusterODM" ]]; then
        cd "/home/wmobley/ODM-SUITE/ClusterODM"
        log_info "Installing ClusterODM-Tapis npm dependencies..."
        npm install
    fi
    
    # Build WebODM
    if [[ -d "$REPO_BASE/WebODM" ]]; then
        cd "$REPO_BASE/WebODM"
        log_info "Installing WebODM npm dependencies..."
        npm install || log_error "WebODM npm install failed"

        log_info "Building WebODM frontend bundle..."
        npx webpack --mode production || log_error "WebODM frontend bundle build failed"

        log_info "Building WebODM Docker images (webapp, worker)..."
        docker compose build --no-cache webapp worker || log_error "WebODM docker compose build failed"

        log_info "Recreating WebODM containers..."
        docker compose up -d --force-recreate webapp worker || log_error "WebODM docker compose up failed"
    fi
    
    log_success "Docker image builds completed"
}

# Setup ClusterODM
setup_clusterodm() {
    log_info "Setting up ClusterODM..."
    
    cd "/home/wmobley/ODM-SUITE/ClusterODM" || {
        log_error "ClusterODM-Tapis directory not found"
        exit 1
    }

    # Update repo
    if [[ -d ".git" ]]; then
        log_info "Pulling latest ClusterODM-Tapis..."
        git pull origin master || git pull origin main || log_warning "Failed to pull ClusterODM-Tapis"
    fi

    # Restart via helper script with desired ports
    if [[ ! -x "./restart.sh" ]]; then
        chmod +x ./restart.sh
    fi

    PORT=$CLUSTERODM_PORT ADMIN_WEB_PORT=10000 ./restart.sh
    
    log_success "ClusterODM setup completed"
}

# Setup WebODM
setup_webodm() {
    log_info "Setting up WebODM..."
    
    cd "$REPO_BASE/WebODM" || {
        log_error "WebODM directory not found"
        exit 1
    }

    resolve_corral_group
    
    # Verify .env file has correct storage paths
    if [[ -f .env ]]; then
        log_info "Ensuring WebODM .env paths and settings are up to date..."

        # Only override media/db paths if missing; avoid silently switching to empty locations
        current_media_dir=$(grep '^WO_MEDIA_DIR=' .env | cut -d'=' -f2- || true)
        if [[ -z "$current_media_dir" ]]; then
            echo "WO_MEDIA_DIR=$CORRAL_BASE/webodm/media" >> .env
        else
            log_info "Keeping existing WO_MEDIA_DIR=$current_media_dir"
        fi

        current_db_dir=$(grep '^WO_DB_DIR=' .env | cut -d'=' -f2- || true)
        if [[ -z "$current_db_dir" ]]; then
            echo "WO_DB_DIR=$LOCAL_DB_DIR" >> .env
        else
            log_info "Keeping existing WO_DB_DIR=$current_db_dir"
        fi

        if grep -q '^WO_CORRAL_GROUP=' .env; then
            sed -i "s|^WO_CORRAL_GROUP=.*|WO_CORRAL_GROUP=$CORRAL_GROUP|" .env
        else
            echo "WO_CORRAL_GROUP=$CORRAL_GROUP" >> .env
        fi
        if [[ -n "$CORRAL_GROUP_ID" ]]; then
            if grep -q '^WO_CORRAL_GROUP_ID=' .env; then
                sed -i "s|^WO_CORRAL_GROUP_ID=.*|WO_CORRAL_GROUP_ID=$CORRAL_GROUP_ID|" .env
            else
                echo "WO_CORRAL_GROUP_ID=$CORRAL_GROUP_ID" >> .env
            fi
        fi
        if grep -q '^WO_HOST=' .env; then
            sed -i "s|^WO_HOST=.*|WO_HOST=$HOSTNAME|" .env
        else
            echo "WO_HOST=$HOSTNAME" >> .env
        fi
        if grep -q '^WO_PORT=' .env; then
            sed -i "s|^WO_PORT=.*|WO_PORT=$WEBODM_PORT|" .env
        else
            echo "WO_PORT=$WEBODM_PORT" >> .env
        fi
        if grep -q '^WO_DEBUG=' .env; then
            sed -i "s|^WO_DEBUG=.*|WO_DEBUG=NO|" .env
        else
            echo "WO_DEBUG=NO" >> .env
        fi
    else
        log_error ".env file not found in WebODM directory"
        exit 1
    fi
    
    # Make webodm.sh executable
    chmod +x webodm.sh
    
    # Start WebODM without default NodeODM nodes
    log_info "Starting WebODM..."
    ./webodm.sh start --hostname "$HOSTNAME" --port "$WEBODM_PORT" --default-nodes 0
    
    # Wait for WebODM to be ready
    log_info "Waiting for WebODM to be ready..."
    webodm_ready=false
    for i in {1..60}; do
        if curl -s "http://localhost:$WEBODM_PORT/api/" > /dev/null; then
            log_success "WebODM is ready"
            webodm_ready=true
            break
        fi
        sleep 5
    done
    
    if [ "$webodm_ready" = false ]; then
        log_error "WebODM failed to start within timeout"
        return 1
    fi
    
    # Setup Tapis OAuth2 integration (id/secret/callback preconfigured)
    log_info "Setting up Tapis OAuth2 integration..."
    ./webodm.sh exec webapp python manage.py shell << 'PYCODE' || log_warning "Tapis OAuth2 setup failed"
from app.models import TapisOAuth2Client

client_id = "webodm.tacc.utexas.edu"
client_secret = "wOwGPBAd9Prn"
callback_url = "https://webodm.tacc.utexas.edu/api/oauth2/tapis/callback"
name = "WEBodm.tacc.utexas.edu"
description = ""
base_url = "https://portals.tapis.io"
tenant_id = "portals"

obj, created = TapisOAuth2Client.objects.update_or_create(
    client_id=client_id,
    defaults={
        "client_secret": client_secret,
        "callback_url": callback_url,
        "name": name,
        "description": description,
        "base_url": base_url,
        "tenant_id": tenant_id,
    },
)
print(f"{'Created' if created else 'Updated'} TapisOAuth2Client: {obj}")
PYCODE
    
    log_success "WebODM setup completed"
}

# Connect ClusterODM to WebODM
connect_clusterodm() {
    log_info "Connecting ClusterODM to WebODM..."
    
    clusterodm_hostname="clusterodm.tacc.utexas.edu"
    clusterodm_port=443
    clusterodm_scheme="https"

    # Best effort reachability check (non-fatal)
    if clusterodm_probe_curl "${clusterodm_scheme}://${clusterodm_hostname}:${clusterodm_port}/info" > /dev/null; then
        log_success "ClusterODM endpoint is reachable"
    else
        log_warning "ClusterODM endpoint not reachable now; will still register processing node"
    fi
    
    # Add ClusterODM as a processing node in WebODM
    log_info "Registering ClusterODM as a processing node..."
    docker exec webapp python manage.py shell -c "
from app.models import ProcessingNode
import requests

# ClusterODM connection details
clusterodm_hostname = 'clusterodm.tacc.utexas.edu'
clusterodm_port = 443
node_name = 'ClusterODM (TACC)'

# Check if ClusterODM node already exists
existing_node = ProcessingNode.objects.filter(hostname=clusterodm_hostname, port=clusterodm_port).first()

if existing_node:
    print(f'ClusterODM node already exists: {existing_node.hostname}:{existing_node.port}')
else:
    # Create new ClusterODM processing node
    try:
        node = ProcessingNode.objects.create(
            hostname=clusterodm_hostname,
            port=clusterodm_port,
            token='',
            label=node_name,
            engine='odm',
            engine_version='',
            max_images=0,
            available=True
        )
        print(f'Created ClusterODM processing node: {node.hostname}:{node.port}')
        try:
            node.update_node_info()
            if node.online:
                print(f'✓ ClusterODM node is online and ready')
            else:
                print(f'⚠ ClusterODM node created but appears offline')
        except Exception as e:
            print(f'⚠ ClusterODM node created but update_node_info failed: {e}')

    except Exception as e:
        print(f'Error creating ClusterODM node: {e}')
" || log_warning "Failed to register ClusterODM with WebODM"
    
    log_success "ClusterODM connection setup completed"
}

# Setup nginx reverse proxy
setup_nginx() {
    log_info "Setting up nginx reverse proxy..."
    
    # Install nginx if not present
    if ! command -v nginx &> /dev/null; then
        log_info "Installing nginx..."
        sudo apt update
        sudo apt install -y nginx
    fi
    
    # Create nginx configuration for WebODM
    sudo tee /etc/nginx/sites-available/webodm << 'EOF'
server {
    listen 80;
    server_name webodm.tacc.utexas.edu;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name webodm.tacc.utexas.edu;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/wedodm.tacc.utexas.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wedodm.tacc.utexas.edu/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    
    # Increase client max body size for large uploads
    client_max_body_size 10G;
    
    # WebODM main application (root path)
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for long uploads/processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    # ClusterODM API (accessible at /cluster/)
    location /cluster/ {
        proxy_pass http://localhost:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for ClusterODM
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # ClusterODM info endpoint (for health checks)
    location /cluster-info {
        proxy_pass http://localhost:3000/info;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
    
    # Create nginx configuration for ClusterODM
    sudo tee /etc/nginx/sites-available/clusterodm << 'EOF'
server {
    listen 80;
    server_name clusterodm.tacc.utexas.edu;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name clusterodm.tacc.utexas.edu;

    # SSL Configuration (using webodm certificate for both domains)
    ssl_certificate /etc/letsencrypt/live/webodm.tacc.utexas.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/webodm.tacc.utexas.edu/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    
    # Increase client max body size for large uploads
    client_max_body_size 10G;
    
    # ClusterODM main application (root path)
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long uploads/processing
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Admin web interface for webhook endpoints
    location /admin {
        proxy_pass http://localhost:10000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Webhook endpoints for node registration/de-registration
    location /webhook {
        proxy_pass http://localhost:10000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Shorter timeouts for webhook calls
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF
    
    # Enable both sites
    sudo ln -sf /etc/nginx/sites-available/webodm /etc/nginx/sites-enabled/
    sudo ln -sf /etc/nginx/sites-available/clusterodm /etc/nginx/sites-enabled/
    
    # Remove default nginx site if it exists
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx configuration
    if sudo nginx -t; then
        log_success "Nginx configuration is valid"
        
        # Restart nginx
        sudo systemctl restart nginx
        sudo systemctl enable nginx
        
        log_success "Nginx reverse proxy configured and started"
    else
        log_error "Nginx configuration is invalid"
        exit 1
    fi
}

# Configure firewall
setup_firewall() {
    log_info "Configuring firewall..."
    
    # Check if ufw is available
    if command -v ufw &> /dev/null; then
        # Allow HTTP and HTTPS
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # Allow SSH (important!)
        sudo ufw allow 22/tcp
        
        # Optional: Allow direct access to services (for debugging)
        # sudo ufw allow "$WEBODM_PORT/tcp"
        # sudo ufw allow "$CLUSTERODM_PORT/tcp"
        # sudo ufw allow "$NODEODM_PORT/tcp"
        
        # Enable firewall if not already enabled
        if ! sudo ufw status | grep -q "Status: active"; then
            sudo ufw --force enable
        fi
        
        log_success "Firewall configured for HTTP/HTTPS"
    else
        log_warning "ufw not available, skipping firewall configuration"
    fi
}

# Setup backup script
setup_backup() {
    log_info "Setting up backup script..."
    
    # Create backup script
    sudo tee /usr/local/bin/webodm-backup.sh > /dev/null << 'EOF'
#!/bin/bash
BACKUP_DIR="/corral/webodm/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
if docker ps | grep -q db; then
    docker exec db pg_dump -U postgres webodm > $BACKUP_DIR/webodm_$DATE.sql
    echo "Database backed up to $BACKUP_DIR/webodm_$DATE.sql"
fi

# Media backup
if [[ -d "/corral/webodm/media" ]]; then
    tar -czf $BACKUP_DIR/media_$DATE.tar.gz -C /corral/webodm media/
    echo "Media files backed up to $BACKUP_DIR/media_$DATE.tar.gz"
fi

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete
echo "Old backups cleaned up"
EOF
    
    sudo chmod +x /usr/local/bin/webodm-backup.sh
    
    # Add to crontab if not already present
    if ! crontab -l 2>/dev/null | grep -q "webodm-backup"; then
        (crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/webodm-backup.sh") | crontab -
        log_success "Daily backup scheduled at 2 AM"
    fi
    
    log_success "Backup script installed"
}

# Health check
health_check() {
    log_info "Running health checks..."
    
    local all_good=true
    
    # Check WebODM
    if curl -s "http://localhost:$WEBODM_PORT/api/" > /dev/null; then
        log_success "WebODM is responding"
    else
        log_error "WebODM is not responding"
        all_good=false
    fi
    
    # Check ClusterODM (remote)
    if clusterodm_probe_curl "https://clusterodm.tacc.utexas.edu:443/info" > /dev/null; then
        log_success "ClusterODM is responding"
    else
        log_error "ClusterODM is not responding"
        all_good=false
    fi
    
    # Check Docker containers
    local containers_down=$(docker ps -a --filter "status=exited" --format "table {{.Names}}" | grep -E "(webapp|db|broker|worker)" | wc -l)
    if [[ $containers_down -eq 0 ]]; then
        log_success "All Docker containers are running"
    else
        log_warning "$containers_down containers are not running"
        docker ps -a --filter "status=exited"
    fi
    
    # Check storage
    local storage_usage=$(df -h "$CORRAL_BASE" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [[ $storage_usage -lt 90 ]]; then
        log_success "Storage usage is healthy ($storage_usage%)"
    else
        log_warning "Storage usage is high ($storage_usage%)"
    fi
    
    if $all_good; then
        log_success "All health checks passed"
        return 0
    else
        log_error "Some health checks failed"
        return 1
    fi
}

# Print summary
print_summary() {
    log_info "Deployment Summary:"
    echo "==========================================="
    echo "WebODM URL: http://$HOSTNAME:$WEBODM_PORT"
    echo "ClusterODM URL: http://$HOSTNAME:$CLUSTERODM_PORT"
    echo "Media Storage: $CORRAL_BASE/webodm/media"
    echo "Database Storage: $LOCAL_DB_DIR"
    echo "Backups: $CORRAL_BASE/webodm/backups"
    echo "==========================================="
    echo ""
    echo "Management Commands:"
    echo "  Start:   cd $REPO_BASE/WebODM && ./webodm.sh start"
    echo "  Stop:    cd $REPO_BASE/WebODM && ./webodm.sh stop"
    echo "  Status:  cd $REPO_BASE/WebODM && ./webodm.sh status"
    echo "  Backup:  sudo /usr/local/bin/webodm-backup.sh"
    echo "  Logs:    docker compose logs"
    echo ""
}

# Full update process
full_update() {
    log_info "Starting full update process..."
    
    # Stop services first
    log_info "Stopping services for update..."
    cd "$REPO_BASE/WebODM" && ./webodm.sh stop || log_warning "WebODM stop failed"
    # Stop ClusterODM-Tapis Node.js process
    if [[ -f "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid" ]]; then
        pid=$(cat "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid")
        kill $pid 2>/dev/null || log_warning "ClusterODM process already stopped"
        rm -f "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid"
    else
        log_warning "ClusterODM PID file not found, trying to kill by name"
        pkill -f "node index.js.*tapis-config.json" || log_warning "No ClusterODM process found"
    fi
    # Update repositories and rebuild images
    update_repos
    build_images
    
    # Restart services
    log_info "Restarting services after update..."
    # Start ClusterODM-Tapis with Node.js
    cd "/home/wmobley/ODM-SUITE/ClusterODM" && nohup node index.js --asr tapis-config.json --port $CLUSTERODM_PORT --admin-web-port 10000 > clusterodm-tapis.log 2>&1 &
    echo $! > "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid"
    cd "$REPO_BASE/WebODM" && ./webodm.sh start --hostname "$HOSTNAME" --port "$WEBODM_PORT" --default-nodes 0
    if health_check; then
        log_success "Update completed successfully!"
    else
        log_error "Update completed with issues. Please check the logs."
        exit 1
    fi
}

# Main execution
main() {
    log_info "Starting WebODM + ClusterODM automated setup..."
    log_info "Repository base: $REPO_BASE"
    log_info "Hostname: $HOSTNAME"

    check_root
    check_prerequisites
    setup_storage

    # Stop any existing services before building to avoid conflicts
    log_info "Stopping any existing services before setup..."
    cd "$REPO_BASE/WebODM" && ./webodm.sh stop 2>/dev/null || log_warning "No WebODM services to stop"
    pkill -f "node index.js.*tapis-config.json" 2>/dev/null || log_warning "No ClusterODM process to stop"

    build_images  # Build images during initial setup
    setup_clusterodm
    setup_webodm
    connect_clusterodm
    setup_nginx
    setup_firewall
    setup_backup

    if health_check; then
        log_success "Deployment completed successfully!"
        print_summary
    else
        log_error "Deployment completed with issues. Please check the logs."
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    "health")
        health_check
        ;;
    "backup")
        /usr/local/bin/webodm-backup.sh
        ;;
    "stop")
        log_info "Stopping all services..."
        cd "$REPO_BASE/WebODM" && ./webodm.sh stop || log_warning "WebODM stop failed"
        # Stop ClusterODM-Tapis Node.js process
    if [[ -f "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid" ]]; then
        pid=$(cat "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid")
        kill $pid 2>/dev/null || log_warning "ClusterODM process already stopped"
        rm -f "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid"
    else
        log_warning "ClusterODM PID file not found"
    fi
    log_success "All services stopped"
    ;;
"start")
    log_info "Starting all services..."
    # Start ClusterODM-Tapis with Node.js
    cd "/home/wmobley/ODM-SUITE/ClusterODM" && nohup node index.js --asr tapis-config.json --port $CLUSTERODM_PORT --admin-web-port 10000 > clusterodm-tapis.log 2>&1 &
    echo $! > "/home/wmobley/ODM-SUITE/ClusterODM/clusterodm-tapis.pid"
    cd "$REPO_BASE/WebODM" && ./webodm.sh start --hostname "$HOSTNAME" --port "$WEBODM_PORT" --default-nodes 0
    log_success "All services started"
    ;;
    "restart")
        $0 stop
        sleep 5
        $0 start
        ;;
    "update")
        full_update
        ;;
    "build")
        build_images
        ;;
    "pull")
        update_repos
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [health|backup|start|stop|restart|update|build|pull]"
        echo ""
        echo "Commands:"
        echo "  (no args)  - Run full automated setup with Docker builds"
        echo "  health     - Run health checks only"
        echo "  backup     - Run backup script"
        echo "  start      - Start all services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  update     - Pull repos, rebuild Docker images, and restart services"
        echo "  build      - Rebuild all Docker images only"
        echo "  pull       - Pull latest code from all repositories"
        exit 1
        ;;
esac

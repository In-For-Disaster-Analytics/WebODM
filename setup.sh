#!/bin/bash

# WebODM + ClusterODM Automated Setup Script for webodm.tacc.utexas.edu
# This script automates the deployment process described in DEPLOYMENT_GUIDE.md

set -e  # Exit on any error

# Handle signals properly
cleanup() {
    log_error "Script interrupted"
    exit 1
}
trap cleanup SIGINT SIGTERM

# Configuration
HOSTNAME="webodm.tacc.utexas.edu"
WEBODM_PORT="8000"
CLUSTERODM_PORT="4000"
NODEODM_PORT="3001"
CORRAL_BASE="/corral"
REPO_BASE="$HOME/ODM-SUITE"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

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
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if user is in docker group
    if ! groups | grep -q docker; then
        log_error "User is not in docker group. Please add user to docker group and re-login."
        exit 1
    fi
    
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
    mkdir -p "$CORRAL_BASE/webodm/db"
    mkdir -p "$CORRAL_BASE/webodm/backups"
    
    # Create ClusterODM storage
    sudo mkdir -p "$CORRAL_BASE/clusterodm/data"
    
    # Set permissions
    sudo chown -R "$USER:$(id -gn)" "$CORRAL_BASE/webodm"
    sudo chown -R "$USER:$(id -gn)" "$CORRAL_BASE/clusterodm"
    
    log_success "Storage directories created"
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
    
    # Update ClusterODM
    if [[ -d "$REPO_BASE/ClusterODM" ]]; then
        cd "$REPO_BASE/ClusterODM"
        if [[ -d ".git" ]]; then
            log_info "Pulling latest ClusterODM..."
            git pull origin master || git pull origin main || log_warning "Failed to pull ClusterODM"
        fi
    fi
    
    # Update NodeODM-LS6
    if [[ -d "$REPO_BASE/nodeodm-ls6" ]]; then
        cd "$REPO_BASE/nodeodm-ls6"
        if [[ -d ".git" ]]; then
            log_info "Pulling latest NodeODM-LS6..."
            git pull origin master || git pull origin main || log_warning "Failed to pull NodeODM-LS6"
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
    
    # Build ClusterODM
    if [[ -d "$REPO_BASE/ClusterODM" ]]; then
        cd "$REPO_BASE/ClusterODM"
        log_info "Building ClusterODM Docker image..."
        docker-compose build --no-cache
    fi
    
    # Build WebODM
    if [[ -d "$REPO_BASE/WebODM" ]]; then
        cd "$REPO_BASE/WebODM"
        log_info "Building WebODM Docker images..."
        ./webodm.sh rebuild
    fi
    
    # Build NodeODM-LS6
    if [[ -d "$REPO_BASE/nodeodm-ls6" ]]; then
        cd "$REPO_BASE/nodeodm-ls6"
        if [[ -f docker-compose.yml ]]; then
            log_info "Building NodeODM-LS6 Docker image..."
            docker-compose build --no-cache
        fi
    fi
    
    log_success "Docker image builds completed"
}

# Setup ClusterODM
setup_clusterodm() {
    log_info "Setting up ClusterODM..."
    
    cd "$REPO_BASE/ClusterODM" || {
        log_error "ClusterODM directory not found"
        exit 1
    }
    
    # Create .env if it doesn't exist
    if [[ ! -f .env ]]; then
        log_info "Creating ClusterODM .env file..."
        cat > .env << EOF
NODE_ENV=production
PORT=$CLUSTERODM_PORT
CLUSTER_HOST=$HOSTNAME
CLUSTER_PORT=$CLUSTERODM_PORT
DATA_DIR=$CORRAL_BASE/clusterodm/data
TAPIS_BASE_URL=https://portals.tapis.io
TAPIS_TENANT_ID=portals
SECRET_KEY=$(openssl rand -hex 32)
EOF
    fi
    
    log_info "Starting ClusterODM..."
    docker-compose up -d
    
    # Wait for ClusterODM to be ready
    log_info "Waiting for ClusterODM to be ready..."
    clusterodm_ready=false
    for i in {1..30}; do
        if curl -s "http://localhost:$CLUSTERODM_PORT/info" > /dev/null; then
            log_success "ClusterODM is ready"
            clusterodm_ready=true
            break
        fi
        sleep 2
    done
    
    if [ "$clusterodm_ready" = false ]; then
        log_error "ClusterODM failed to start within timeout"
        return 1
    fi
    
    log_success "ClusterODM setup completed"
}

# Setup WebODM
setup_webodm() {
    log_info "Setting up WebODM..."
    
    cd "$REPO_BASE/WebODM" || {
        log_error "WebODM directory not found"
        exit 1
    }
    
    # Verify .env file has correct corral paths
    if [[ -f .env ]]; then
        # Update .env with corral paths if not already set
        if ! grep -q "$CORRAL_BASE/webodm" .env; then
            log_info "Updating WebODM .env for corral storage..."
            sed -i "s|WO_MEDIA_DIR=.*|WO_MEDIA_DIR=$CORRAL_BASE/webodm/media|" .env
            sed -i "s|WO_DB_DIR=.*|WO_DB_DIR=$CORRAL_BASE/webodm/db|" .env
            sed -i "s|WO_HOST=.*|WO_HOST=$HOSTNAME|" .env
            sed -i "s|WO_PORT=.*|WO_PORT=$WEBODM_PORT|" .env
            sed -i "s|WO_DEBUG=.*|WO_DEBUG=NO|" .env
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
    
    # Setup Tapis OAuth2 integration
    log_info "Setting up Tapis OAuth2 integration..."
    ./webodm.sh exec webapp python setup_tapis_oauth2.py || log_warning "Tapis OAuth2 setup failed"
    
    log_success "WebODM setup completed"
}

# Connect ClusterODM to WebODM
connect_clusterodm() {
    log_info "Connecting ClusterODM to WebODM..."
    
    # Wait a bit for both services to be fully ready
    sleep 10
    
    # Check if ClusterODM is responding
    if ! curl -s "http://localhost:$CLUSTERODM_PORT/info" > /dev/null; then
        log_error "ClusterODM is not responding, cannot connect to WebODM"
        return 1
    fi
    
    # Add ClusterODM as a processing node in WebODM
    log_info "Registering ClusterODM as a processing node..."
    docker exec webapp python manage.py shell -c "
from app.models import ProcessingNode
import requests

# ClusterODM connection details
clusterodm_hostname = 'host.docker.internal'
clusterodm_port = $CLUSTERODM_PORT
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
        
        # Test the connection
        node.update_node_info()
        if node.online:
            print(f'✓ ClusterODM node is online and ready')
        else:
            print(f'⚠ ClusterODM node created but appears offline')
            
    except Exception as e:
        print(f'Error creating ClusterODM node: {e}')
" || log_warning "Failed to register ClusterODM with WebODM"
    
    log_success "ClusterODM connection setup completed"
}

# Setup NodeODM-LS6 (optional)
setup_nodeodm() {
    log_info "Setting up NodeODM-LS6..."
    
    if [[ -d "$REPO_BASE/nodeodm-ls6" ]]; then
        cd "$REPO_BASE/nodeodm-ls6"
        
        # Create config if it doesn't exist
        if [[ ! -f config.json && -f config.example.json ]]; then
            cp config.example.json config.json
        fi
        
        # Start NodeODM
        if [[ -f docker-compose.yml ]]; then
            docker-compose up -d
            log_success "NodeODM-LS6 started"
        else
            log_warning "NodeODM-LS6 docker-compose.yml not found"
        fi
    else
        log_warning "NodeODM-LS6 directory not found, skipping"
    fi
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
        proxy_pass http://localhost:$CLUSTERODM_PORT;
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
    
    # Check ClusterODM
    if curl -s "http://localhost:$CLUSTERODM_PORT/info" > /dev/null; then
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
    echo "Database Storage: $CORRAL_BASE/webodm/db"
    echo "Backups: $CORRAL_BASE/webodm/backups"
    echo "==========================================="
    echo ""
    echo "Management Commands:"
    echo "  Start:   cd $REPO_BASE/WebODM && ./webodm.sh start"
    echo "  Stop:    cd $REPO_BASE/WebODM && ./webodm.sh stop"
    echo "  Status:  cd $REPO_BASE/WebODM && ./webodm.sh status"
    echo "  Backup:  sudo /usr/local/bin/webodm-backup.sh"
    echo "  Logs:    docker-compose logs"
    echo ""
}

# Full update process
full_update() {
    log_info "Starting full update process..."
    
    # Stop services first
    log_info "Stopping services for update..."
    cd "$REPO_BASE/WebODM" && ./webodm.sh stop || log_warning "WebODM stop failed"
    cd "$REPO_BASE/ClusterODM" && docker-compose down || log_warning "ClusterODM stop failed"
    [[ -d "$REPO_BASE/nodeodm-ls6" ]] && cd "$REPO_BASE/nodeodm-ls6" && docker-compose down || log_warning "NodeODM stop failed"
    
    # Update repositories and rebuild images
    update_repos
    build_images
    
    # Restart services
    log_info "Restarting services after update..."
    cd "$REPO_BASE/ClusterODM" && docker-compose up -d
    cd "$REPO_BASE/WebODM" && ./webodm.sh start --hostname "$HOSTNAME" --port "$WEBODM_PORT" --default-nodes 0
    [[ -d "$REPO_BASE/nodeodm-ls6" ]] && cd "$REPO_BASE/nodeodm-ls6" && docker-compose up -d
    
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
    build_images  # Build images during initial setup
    setup_clusterodm
    setup_webodm
    connect_clusterodm
    setup_nodeodm
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
        cd "$REPO_BASE/ClusterODM" && docker-compose down || log_warning "ClusterODM stop failed"
        [[ -d "$REPO_BASE/nodeodm-ls6" ]] && cd "$REPO_BASE/nodeodm-ls6" && docker-compose down || log_warning "NodeODM stop failed"
        log_success "All services stopped"
        ;;
    "start")
        log_info "Starting all services..."
        cd "$REPO_BASE/ClusterODM" && docker-compose up -d
        cd "$REPO_BASE/WebODM" && ./webodm.sh start --hostname "$HOSTNAME" --port "$WEBODM_PORT" --default-nodes 0
        [[ -d "$REPO_BASE/nodeodm-ls6" ]] && cd "$REPO_BASE/nodeodm-ls6" && docker-compose up -d
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
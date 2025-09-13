#!/bin/bash

# Configuration
CLUSTERODM_PORT="4000"

# Logging functions
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Connect ClusterODM to WebODM
log_info "Connecting ClusterODM to WebODM..."

# Check if ClusterODM is responding
if ! curl -s "http://localhost:$CLUSTERODM_PORT/info" > /dev/null; then
    log_error "ClusterODM is not responding on port $CLUSTERODM_PORT"
    exit 1
fi

log_info "ClusterODM is responding, registering as processing node..."

# Add ClusterODM as a processing node in WebODM
docker exec webapp python manage.py shell -c "
from nodeodm.models import ProcessingNode

# ClusterODM connection details (use container name on Docker network)
clusterodm_hostname = 'clusterodm'  # Docker container name
clusterodm_port = 3000  # Internal port, not the mapped port
node_name = 'ClusterODM (TACC)'

print(f'Connecting to ClusterODM at {clusterodm_hostname}:{clusterodm_port}')

# Check if ClusterODM node already exists
existing_node = ProcessingNode.objects.filter(hostname=clusterodm_hostname, port=clusterodm_port).first()

if existing_node:
    print(f'ClusterODM node already exists: {existing_node.hostname}:{existing_node.port}')
    print(f'Status: {\"Online\" if existing_node.is_online() else \"Offline\"}')
else:
    # Create new ClusterODM processing node
    try:
        node = ProcessingNode.objects.create(
            hostname=clusterodm_hostname,
            port=clusterodm_port,
            token='',
            label=node_name,
            engine='odm',
            max_images=0
        )
        print(f'✓ Created ClusterODM processing node: {node.hostname}:{node.port}')
        
        # Test the connection
        if node.update_node_info():
            print(f'✓ ClusterODM node is online and ready')
        else:
            print(f'⚠ ClusterODM node created but appears offline')
            
    except Exception as e:
        print(f'✗ Error creating ClusterODM node: {e}')
"

log_success "ClusterODM connection completed"
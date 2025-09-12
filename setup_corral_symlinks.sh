#!/bin/bash

# Corral Symlink-Based Project Discovery Setup
# This script sets up the directory structure and discovery system for large datasets

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

CORRAL_BASE="/corral"

# Create directory structure
setup_corral_structure() {
    log_info "Setting up corral directory structure..."
    
    # Create user data directories
    sudo mkdir -p "$CORRAL_BASE/user-data"
    sudo mkdir -p "$CORRAL_BASE/webodm/projects/active"
    sudo mkdir -p "$CORRAL_BASE/webodm/projects/archived"
    sudo mkdir -p "$CORRAL_BASE/webodm/scripts"
    sudo mkdir -p "$CORRAL_BASE/webodm/logs"
    
    # Set permissions
    sudo chown -R $USER:$(id -gn) "$CORRAL_BASE/user-data"
    sudo chown -R $USER:$(id -gn) "$CORRAL_BASE/webodm/projects"
    sudo chown -R $USER:$(id -gn) "$CORRAL_BASE/webodm/scripts"
    sudo chown -R $USER:$(id -gn) "$CORRAL_BASE/webodm/logs"
    
    # Make user-data world-writable for SFTP users (with sticky bit)
    sudo chmod 1777 "$CORRAL_BASE/user-data"
    
    log_success "Directory structure created"
}

# Create discovery script
create_discovery_script() {
    log_info "Creating project discovery script..."
    
    cat > "$CORRAL_BASE/webodm/scripts/discover_projects.sh" << 'EOF'
#!/bin/bash

# Corral Project Discovery Script
# Scans for new projects uploaded via SFTP and registers them with WebODM

CORRAL_BASE="/corral"
USER_DATA_DIR="$CORRAL_BASE/user-data"
ACTIVE_PROJECTS_DIR="$CORRAL_BASE/webodm/projects/active"
LOG_FILE="$CORRAL_BASE/webodm/logs/discovery.log"
LOCK_FILE="/tmp/corral_discovery.lock"

log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Prevent multiple instances
if [ -f "$LOCK_FILE" ]; then
    log_msg "Discovery already running (lock file exists)"
    exit 1
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log_msg "Starting project discovery scan..."

# Find projects with .ready flag
find "$USER_DATA_DIR" -name ".ready" -type f | while read ready_file; do
    project_dir=$(dirname "$ready_file")
    username=$(basename "$(dirname "$project_dir")")
    project_name=$(basename "$project_dir")
    symlink_path="$ACTIVE_PROJECTS_DIR/${username}_${project_name}"
    
    log_msg "Found ready project: $project_dir"
    
    # Check if already processed
    if [ -L "$symlink_path" ]; then
        log_msg "Project already registered: $symlink_path"
        continue
    fi
    
    # Validate project structure
    if [ ! -d "$project_dir/images" ]; then
        log_msg "ERROR: No images directory found in $project_dir"
        continue
    fi
    
    # Count images
    image_count=$(find "$project_dir/images" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.tiff" -o -iname "*.tif" \) | wc -l)
    
    if [ "$image_count" -eq 0 ]; then
        log_msg "ERROR: No images found in $project_dir/images"
        continue
    fi
    
    log_msg "Found $image_count images in project"
    
    # Create symlink
    ln -sf "$project_dir" "$symlink_path"
    log_msg "Created symlink: $symlink_path -> $project_dir"
    
    # Read metadata if exists
    metadata_file="$project_dir/metadata.json"
    if [ -f "$metadata_file" ]; then
        log_msg "Found metadata file: $metadata_file"
    else
        log_msg "No metadata file found, using defaults"
        # Create default metadata
        cat > "$metadata_file" << METADATA_EOF
{
    "project_name": "${username}_${project_name}",
    "description": "Project imported from corral for user ${username}",
    "processing_options": {
        "resize-to": 2048,
        "quality": "medium",
        "build-overviews": true
    },
    "imported_at": "$(date -Iseconds)",
    "image_count": $image_count
}
METADATA_EOF
    fi
    
    # Register with WebODM
    log_msg "Registering project with WebODM..."
    docker exec webapp python manage.py import_corral_project \
        --path "$project_dir" \
        --symlink "$symlink_path" \
        --username "$username" \
        --name "${username}_${project_name}" 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        log_msg "Successfully registered project: ${username}_${project_name}"
        # Mark as processed
        touch "$project_dir/.processed"
    else
        log_msg "ERROR: Failed to register project with WebODM"
        # Remove symlink on failure
        rm -f "$symlink_path"
    fi
done

log_msg "Discovery scan completed"
EOF

    chmod +x "$CORRAL_BASE/webodm/scripts/discover_projects.sh"
    log_success "Discovery script created"
}

# Create example user directory
create_example_structure() {
    log_info "Creating example directory structure..."
    
    # Create example user directory
    mkdir -p "$CORRAL_BASE/user-data/example_user/my_drone_project"
    
    cat > "$CORRAL_BASE/user-data/example_user/my_drone_project/README.txt" << 'EOF'
# Corral Project Structure

To upload a project via SFTP:

1. Create your project directory:
   /corral/user-data/your_username/your_project_name/

2. Upload your images:
   /corral/user-data/your_username/your_project_name/images/
   - Place all drone images (.jpg, .png, .tiff) here

3. (Optional) Create metadata.json:
   {
     "project_name": "My Drone Survey",
     "description": "Description of the project",
     "processing_options": {
       "resize-to": 2048,
       "quality": "high",
       "build-overviews": true
     }
   }

4. Signal completion:
   touch /corral/user-data/your_username/your_project_name/.ready

The discovery script will automatically find and import your project into WebODM.

Your files stay in the original location - no copying or moving!
EOF
    
    log_success "Example structure created"
}

# Create WebODM management command
create_management_command() {
    log_info "Creating WebODM management command..."
    
    # Create the management command directory structure
    docker exec webapp mkdir -p /webodm/app/management/commands
    
    # Create the corral import command
    docker exec webapp tee /webodm/app/management/commands/import_corral_project.py > /dev/null << 'EOF'
import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from app.models import Project, Task
from django.utils import timezone

class Command(BaseCommand):
    help = 'Import a project from corral path'

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True, help='Path to corral project directory')
        parser.add_argument('--symlink', required=True, help='Symlink path in active projects')
        parser.add_argument('--username', required=True, help='Username for project owner')
        parser.add_argument('--name', required=True, help='Project name')

    def handle(self, *args, **options):
        project_path = options['path']
        symlink_path = options['symlink']
        username = options['username']
        project_name = options['name']
        
        self.stdout.write(f"Importing project: {project_name}")
        self.stdout.write(f"Source path: {project_path}")
        
        # Get or create user
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.email = f"{username}@tacc.utexas.edu"  # Default email
            user.save()
            self.stdout.write(f"Created user: {username}")
        
        # Read metadata
        metadata_file = os.path.join(project_path, 'metadata.json')
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except json.JSONDecodeError:
                self.stdout.write(self.style.WARNING(f"Invalid metadata file: {metadata_file}"))
        
        # Create project
        project = Project.objects.create(
            name=project_name,
            description=metadata.get('description', f'Corral import from {project_path}'),
            owner=user,
            created_at=timezone.now()
        )
        
        self.stdout.write(f"Created WebODM project: {project.id}")
        
        # Create task with corral path reference
        images_path = os.path.join(project_path, 'images')
        if not os.path.exists(images_path):
            raise CommandError(f"Images directory not found: {images_path}")
        
        # Count images
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.tiff', '*.tif']:
            image_files.extend(
                [f for f in os.listdir(images_path) 
                 if f.lower().endswith(ext.replace('*', ''))]
            )
        
        if not image_files:
            raise CommandError(f"No images found in: {images_path}")
        
        # Get processing options
        processing_options = metadata.get('processing_options', {})
        
        task = Task.objects.create(
            project=project,
            name=f"Corral Task - {project_name}",
            processing_node=None,  # Will be assigned automatically
            options=processing_options,
            created_at=timezone.now()
        )
        
        # Store corral reference in task
        task.corral_path = project_path
        task.symlink_path = symlink_path
        task.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully imported project "{project_name}" '
                f'with {len(image_files)} images'
            )
        )
        
        return f"Project {project.id}, Task {task.id}"
EOF
    
    log_success "Management command created"
}

# Setup cron job for discovery
setup_cron() {
    log_info "Setting up discovery cron job..."
    
    # Add cron job to run every 5 minutes
    (crontab -l 2>/dev/null; echo "*/5 * * * * $CORRAL_BASE/webodm/scripts/discover_projects.sh") | crontab -
    
    log_success "Cron job configured to run every 5 minutes"
}

# Print usage instructions
print_usage() {
    echo ""
    log_info "Corral Symlink Integration Setup Complete!"
    echo "==========================================="
    echo ""
    echo "📁 Directory Structure:"
    echo "   User uploads:     $CORRAL_BASE/user-data/username/project-name/"
    echo "   Active projects:  $CORRAL_BASE/webodm/projects/active/"
    echo "   Discovery logs:   $CORRAL_BASE/webodm/logs/discovery.log"
    echo ""
    echo "📋 User Workflow:"
    echo "   1. SFTP upload to: $CORRAL_BASE/user-data/[username]/[project-name]/images/"
    echo "   2. Create .ready flag: touch $CORRAL_BASE/user-data/[username]/[project-name]/.ready"
    echo "   3. Discovery script runs automatically every 5 minutes"
    echo "   4. Project appears in WebODM interface"
    echo ""
    echo "🔧 Management:"
    echo "   Manual discovery:  $CORRAL_BASE/webodm/scripts/discover_projects.sh"
    echo "   View logs:         tail -f $CORRAL_BASE/webodm/logs/discovery.log"
    echo "   List projects:     ls -la $CORRAL_BASE/webodm/projects/active/"
    echo ""
    echo "📖 Example:"
    echo "   See: $CORRAL_BASE/user-data/example_user/my_drone_project/README.txt"
    echo ""
}

# Main execution
main() {
    log_info "Setting up Corral Symlink-Based Project Discovery..."
    
    setup_corral_structure
    create_discovery_script  
    create_example_structure
    create_management_command
    setup_cron
    
    print_usage
}

main
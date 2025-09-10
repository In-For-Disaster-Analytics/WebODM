# Tapis Storage Integration for WebODM

This document describes the Tapis storage integration that automatically discovers flight directories from `ptdatax.project.*` systems and creates WebODM projects for drone image processing.

## Overview

The integration provides:
- Automatic discovery of Tapis storage systems matching the `ptdatax.project.*` pattern
- Scanning for flight directories with the structure `<Flight>/code/images/*.jpg`
- Automatic creation of WebODM projects from discovered flight data
- Background image downloading from Tapis systems to WebODM
- REST API endpoints for manual control
- Django management commands for batch operations

## Prerequisites

1. **Tapis OAuth2 Setup**: The WebODM instance must be configured with Tapis OAuth2 authentication (see `TAPIS_OAUTH2_INTEGRATION.md`)
2. **User Authentication**: Users must have authenticated with Tapis and have valid OAuth2 tokens
3. **System Access**: Users must have access to `ptdatax.project.*` systems in Tapis
4. **Flight Structure**: Flight directories must follow the pattern `<FlightName>/code/images/*.jpg`

## Components

### Services (`app/services/tapis_storage.py`)

#### TapisStorageService
Core service class for interacting with Tapis storage systems:
- `discover_project_systems()`: Find all accessible `ptdatax.project.*` systems
- `scan_system_for_flights()`: Scan a system for flight directories
- `create_project_from_flight()`: Create WebODM project from flight data
- `download_flight_images()`: Download images from Tapis to WebODM

#### TapisFlightDiscoveryService
High-level service for automated flight discovery:
- `discover_and_create_projects()`: Complete workflow from discovery to project creation

### REST API Endpoints (`app/api/tapis_storage.py`)

Base URL: `/api/tapis-storage/`

#### GET `/systems/`
List all accessible `ptdatax.project.*` systems for the authenticated user.

**Response:**
```json
{
  "success": true,
  "systems": [
    {
      "id": "ptdatax.project.example",
      "host": "data.tacc.utexas.edu",
      "systemType": "LINUX",
      "description": "Project data system",
      "created": "2024-01-01T00:00:00Z"
    }
  ],
  "count": 1
}
```

#### POST `/discover-flights/`
Discover flight directories across systems.

**Request Body (optional):**
```json
{
  "systems": ["ptdatax.project.system1", "ptdatax.project.system2"]
}
```

**Response:**
```json
{
  "success": true,
  "flights": [
    {
      "flight_name": "Flight001",
      "system_id": "ptdatax.project.example",
      "images_path": "Flight001/code/images",
      "image_count": 150,
      "discovered_at": "2024-01-01T12:00:00"
    }
  ],
  "count": 1
}
```

#### POST `/create-projects/`
Create WebODM projects from flight data.

**Auto-discovery mode:**
```json
{
  "auto_discover": true
}
```

**Manual mode:**
```json
{
  "flights": [
    {
      "flight_name": "Flight001",
      "system_id": "ptdatax.project.example",
      "images_path": "Flight001/code/images",
      "image_count": 150
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "results": {
    "systems_scanned": 2,
    "flights_discovered": 3,
    "projects_created": 2,
    "errors": [],
    "created_projects": [
      {
        "project_id": 123,
        "project_name": "Flight001 (ptdatax.project.example)",
        "flight_name": "Flight001",
        "system_id": "ptdatax.project.example",
        "image_count": 150
      }
    ]
  }
}
```

#### GET `/flight-projects/`
List all projects created from Tapis flight data for the authenticated user.

#### POST `/sync-project-images/`
Download images for a specific flight project.

**Request Body:**
```json
{
  "project_id": 123
}
```

## Django Management Commands

### `discover_tapis_flights`

Discover flight directories and create WebODM projects via command line.

```bash
# Basic usage
python manage.py discover_tapis_flights --user username

# Dry run (show what would be created without creating)
python manage.py discover_tapis_flights --user username --dry-run

# Use specific Tapis client
python manage.py discover_tapis_flights --user username --client-id my-client-id

# Scan specific systems only
python manage.py discover_tapis_flights --user username --systems ptdatax.project.system1 ptdatax.project.system2
```

**Options:**
- `--user`: Username of the user to create projects for (required)
- `--client-id`: Tapis OAuth2 client ID (optional, uses first active client if not specified)  
- `--dry-run`: Show what would be created without actually creating projects
- `--systems`: Specific system IDs to scan (optional, scans all `ptdatax.project.*` if not specified)

## Celery Tasks (`app/tasks/tapis_storage.py`)

For background processing and automation:

### `discover_and_create_flight_projects`
```python
from app.tasks.tapis_storage import discover_and_create_flight_projects
result = discover_and_create_flight_projects.delay(user_id=1, client_id='my-client')
```

### `download_flight_images` 
```python
from app.tasks.tapis_storage import download_flight_images
flight_info = {...}
result = download_flight_images.delay(task_id=123, flight_info=flight_info)
```

### `periodic_flight_discovery`
```python
from app.tasks.tapis_storage import periodic_flight_discovery
# Run for all users
result = periodic_flight_discovery.delay()
# Run for specific user
result = periodic_flight_discovery.delay(user_id=1)
```

## Usage Examples

### 1. API-based Discovery and Project Creation

```bash
# 1. Authenticate with Tapis (get token)
curl -X POST "https://webodm.example.com/api/oauth2/tapis/authorize/my-client-id/"

# 2. Discover available systems
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     "https://webodm.example.com/api/tapis-storage/systems/"

# 3. Discover flights
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     "https://webodm.example.com/api/tapis-storage/discover-flights/"

# 4. Create projects automatically
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"auto_discover": true}' \
     "https://webodm.example.com/api/tapis-storage/create-projects/"
```

### 2. Command-line Discovery

```bash
# Navigate to WebODM directory
cd /path/to/webodm

# Discover and create projects for a user
./webodm.sh manage discover_tapis_flights --user john_doe

# Dry run to see what would be created
./webodm.sh manage discover_tapis_flights --user john_doe --dry-run

# Scan specific systems only
./webodm.sh manage discover_tapis_flights --user john_doe --systems ptdatax.project.system1
```

### 3. Programmatic Usage

```python
from django.contrib.auth.models import User
from app.models.oauth2 import TapisOAuth2Client
from app.services.tapis_storage import TapisFlightDiscoveryService

# Get user and client
user = User.objects.get(username='john_doe')
client = TapisOAuth2Client.objects.filter(is_active=True).first()

# Discover and create projects
results = TapisFlightDiscoveryService.discover_and_create_projects(user, client)

print(f"Created {results['projects_created']} projects from {results['flights_discovered']} flights")
```

## Configuration

### Environment Variables

The integration uses the existing Tapis OAuth2 environment variables:
- `WO_TAPIS_BASE_URL`: Tapis API base URL
- `WO_TAPIS_TENANT_ID`: Tapis tenant ID

### Django Settings

No additional Django settings are required beyond the existing Tapis OAuth2 configuration.

## Project Structure and Tagging

Created projects include:
- **Name**: `<FlightName> (<SystemID>)`
- **Description**: Auto-generated with flight details and discovery timestamp
- **Tags**: `tapis,flight,<SystemID>,<FlightName>` (comma-separated)
- **Owner**: The authenticated user
- **Tasks**: One task per project with import URL pointing to Tapis system

## Error Handling

The integration includes comprehensive error handling:
- Invalid or expired Tapis tokens
- Inaccessible storage systems
- Missing flight directory structure
- Network failures during file operations
- Duplicate project prevention

Errors are logged and returned in API responses with appropriate HTTP status codes.

## Limitations and Considerations

1. **Authentication**: Users must maintain valid Tapis OAuth2 tokens
2. **Directory Structure**: Flight directories must exactly match `<Flight>/code/images/*.jpg`
3. **File Types**: Only `.jpg` and `.jpeg` files are considered
4. **Large Datasets**: Image downloading may take significant time for large flight datasets
5. **Storage**: Downloaded images consume local disk space in WebODM
6. **Permissions**: Users can only access systems they have permissions for in Tapis

## Troubleshooting

### Common Issues

1. **"No Tapis token found"**
   - Solution: User needs to authenticate with Tapis OAuth2 first

2. **"No flight directories found"**
   - Check that flight directories follow the exact pattern `<Flight>/code/images/*.jpg`
   - Verify user has access to the storage systems

3. **"Token expired"**
   - Solution: User needs to refresh their Tapis OAuth2 token

4. **"System not accessible"**
   - Verify the system ID exists and user has proper permissions
   - Check network connectivity to Tapis API

### Debug Commands

```bash
# Check Tapis OAuth2 setup
python manage.py shell
>>> from app.models.oauth2 import TapisOAuth2Client, TapisOAuth2Token
>>> TapisOAuth2Client.objects.filter(is_active=True)
>>> TapisOAuth2Token.objects.filter(user__username='john_doe')

# Test system discovery
python manage.py shell
>>> from app.services.tapis_storage import TapisStorageService
>>> from django.contrib.auth.models import User
>>> from app.models.oauth2 import TapisOAuth2Client
>>> user = User.objects.get(username='john_doe')
>>> client = TapisOAuth2Client.objects.filter(is_active=True).first()
>>> service = TapisStorageService(user, client)
>>> systems = service.discover_project_systems()
>>> print(systems)
```

## Future Enhancements

Potential improvements:
1. **Batch Processing**: Parallel processing of multiple systems/flights
2. **Progress Tracking**: Real-time progress updates for large downloads
3. **Incremental Sync**: Only download new/changed images
4. **Storage Optimization**: Compression and deduplication
5. **Notification System**: Email alerts for successful/failed discoveries
6. **Web UI**: Frontend interface for flight discovery and management
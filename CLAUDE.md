# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

WebODM is a user-friendly, commercial-grade software for drone image processing. It's built as a Django web application with React frontend components and uses Docker for deployment. The system processes aerial images to generate georeferenced maps, point clouds, elevation models and textured 3D models.

## Architecture

WebODM follows a microservices architecture using Docker:

- **webapp**: Django application serving the web interface and API
- **db**: PostgreSQL with PostGIS extensions for spatial data
- **broker**: Redis for task queuing and caching
- **worker**: Celery workers for background task processing
- **node-odm**: Processing nodes running NodeODM for photogrammetry tasks

The system communicates with processing nodes (NodeODM, NodeMICMAC, ClusterODM) via REST APIs to distribute computational work.

## Common Commands

### Development Setup
```bash
# Start WebODM in development mode
./webodm.sh start --dev

# Start with specific configuration
./webodm.sh start --port 8080 --hostname mydomain.com

# Stop WebODM
./webodm.sh stop

# Complete teardown
./webodm.sh down

# Update to latest version
./webodm.sh update
```

### Testing
```bash
# Run all tests
./webodm.sh test

# Run frontend tests only
./webodm.sh test frontend

# Run backend tests only  
./webodm.sh test backend

# Run specific test
./webodm.sh test backend app.tests.test_specific_module
```

### Native Development (when not using Docker)
```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Build frontend assets
webpack --mode production
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver --no-gunicorn

# Start Celery worker
./worker.sh start

# Build translations
python manage.py translate build --safe
```

### Production Deployment
```bash
# Start with SSL
./webodm.sh start --ssl --hostname webodm.example.com

# Start with GPU support (Linux only)
./webodm.sh start --gpu

# Start with custom media/DB directories
./webodm.sh start --media-dir /path/to/media --db-dir /path/to/db

# Reset admin password
./webodm.sh resetadminpassword newpassword
```

## Key Components

### Django Apps
- **app**: Main WebODM application containing models, views, API endpoints
- **nodeodm**: Integration with NodeODM processing nodes
- **coreplugins**: Built-in plugins for extended functionality

### Core Models (app/models/)
- **Project**: Groups related tasks and manages permissions
- **Task**: Represents photogrammetry processing jobs
- **Plugin**: Plugin management and configuration
- **Preset**: Processing presets with predefined options
- **Theme**: UI customization settings

### Frontend Structure
- Built with React and bundled via Webpack
- Entry points: main.jsx, Dashboard.jsx, MapView.jsx, ModelView.jsx
- Static assets in app/static/
- Templates in app/templates/

### Plugin System
WebODM features an extensive plugin architecture:
- Server-side signals for event handling
- Client-side API for UI modifications
- ES6/React build system for plugins
- Built-in data store and async task runner

## Environment Configuration

Key environment variables (set in `.env` or via command line):
- `WO_PORT`: Port to bind (default: 8000)
- `WO_HOST`: Hostname (default: localhost)
- `WO_DEBUG`: Enable debug mode (YES/NO)
- `WO_DEV`: Enable development mode (YES/NO)
- `WO_SSL`: Enable SSL (YES/NO)
- `WO_BROKER`: Celery broker URL (default: redis://localhost)
- `WO_DEFAULT_NODES`: Number of default processing nodes

## File Storage

- **Media files**: `/webodm/app/media` (or custom via `--media-dir`)
- **Database**: PostgreSQL data (or custom via `--db-dir`)
- **Processing results**: Stored in project/task subdirectories
- **Plugins**: `coreplugins/` directory

## Development Notes

### Code Style
- Django follows standard Django conventions
- React components use ES6+ syntax with Babel transpilation
- SCSS for styling with CSS extraction via webpack

### Database
- Uses PostgreSQL with PostGIS extensions for spatial operations
- Migrations handled via standard Django migration system
- Settings support multiple database engines via environment variables

### Background Processing
- Celery for background tasks (image processing, cleanup, etc.)
- Redis as message broker and cache backend
- Tasks include image resizing, task result processing, file cleanup

### API
- Django REST Framework for API endpoints
- JWT authentication supported
- Object-level permissions via django-guardian
- API documentation available at `/api/docs/`

## Processing Pipeline

1. **Image Upload**: Users upload drone images via web interface
2. **Task Creation**: System creates processing task with selected options
3. **Node Assignment**: Task dispatched to available processing node
4. **Processing**: NodeODM/MicMac performs photogrammetry processing
5. **Result Storage**: Outputs (orthomosaic, 3D model, etc.) stored and indexed
6. **Visualization**: Results displayed via web interface with map/3D viewers

## Customization

- **Themes**: Admin panel allows custom CSS, logos, colors
- **Plugins**: Extensive plugin system for adding functionality
- **Settings**: Many aspects configurable via admin interface
- **External Auth**: Supports external authentication endpoints

## Common File Locations

- Main settings: `webodm/settings.py`
- URL configuration: `webodm/urls.py`, `app/urls.py`
- Static files: `app/static/app/`
- Templates: `app/templates/`
- Frontend entry: `app/static/app/js/main.jsx`
- Docker configs: `docker-compose*.yml`
- Webpack config: `webpack.config.js`
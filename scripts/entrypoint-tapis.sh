#!/bin/bash
set -e

echo "Starting WebODM with Tapis OAuth2 integration..."

restore_tapis_oauth_imports() {
    # The Docker build comments these imports out so build-time Django commands can run.
    # Runtime always needs the model exports because URL and context modules import them.
    if [ -f /webodm/app/models/__init__.py ]; then
        sed -i 's/#TAPIS_TEMP_DISABLE#from \.oauth2 import/from \.oauth2 import/' /webodm/app/models/__init__.py
    fi

    if [ -f /webodm/app/admin.py ]; then
        sed -i 's/#TAPIS_TEMP_DISABLE#from \.admin\.oauth2 import/from \.admin\.oauth2 import/' /webodm/app/admin.py
    fi
}

restore_tapis_oauth_imports

# Check if Tapis OAuth2 is configured
if [ -n "$WO_TAPIS_BASE_URL" ] && [ -n "$WO_TAPIS_TENANT_ID" ]; then
    echo "Tapis OAuth2 configuration detected:"
    echo "  Base URL: $WO_TAPIS_BASE_URL" 
    echo "  Tenant ID: $WO_TAPIS_TENANT_ID"
    
    # Wait for database to be ready
    echo "Waiting for database..."
    timeout=60
    start_time=$(date +%s)
    
    while ! python manage.py shell -c "from django.db import connection; connection.cursor()" > /dev/null 2>&1; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        if [ $elapsed -gt $timeout ]; then
            echo "Database timeout after ${timeout}s"
            exit 1
        fi
        echo "Database not ready, waiting..."
        sleep 2
    done
    
    # Run Tapis OAuth2 setup
    echo "Setting up Tapis OAuth2 integration..."
    python /webodm/scripts/setup_tapis_oauth2.py
    
    echo "✓ Tapis OAuth2 integration ready"
else
    echo "No Tapis OAuth2 configuration found, skipping setup"
fi

# Continue with original entrypoint
exec "$@"

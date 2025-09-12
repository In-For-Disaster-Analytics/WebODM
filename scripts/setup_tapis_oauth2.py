#!/usr/bin/env python3
"""
Tapis OAuth2 setup script for WebODM
Runs database migrations and creates default OAuth2 client
"""

import os
import sys
import django
import logging

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Step 0: Re-enable OAuth2 models (disabled during Docker build) and fix compatibility BEFORE Django setup
logger.info("Re-enabling OAuth2 models and admin...")
try:
    # Re-enable models
    models_init_path = '/webodm/app/models/__init__.py'
    if os.path.exists(models_init_path):
        with open(models_init_path, 'r') as f:
            content = f.read()
        if '#TAPIS_TEMP_DISABLE#from .oauth2 import' in content:
            content = content.replace('#TAPIS_TEMP_DISABLE#from .oauth2 import', 'from .oauth2 import')
            with open(models_init_path, 'w') as f:
                f.write(content)
            logger.info("✓ Re-enabled OAuth2 models")
    
    # Fix JSONField compatibility BEFORE Django setup
    oauth2_model_path = '/webodm/app/models/oauth2.py'
    if os.path.exists(oauth2_model_path):
        with open(oauth2_model_path, 'r') as f:
            content = f.read()
        if 'models.JSONField(default=dict, blank=True' in content:
            content = content.replace('models.JSONField(default=dict, blank=True', 'models.TextField(blank=True, default="{}"')
            with open(oauth2_model_path, 'w') as f:
                f.write(content)
            logger.info("✓ Fixed OAuth2 model Django compatibility")
    
    # Fix JSONField in migration files
    migration_path = '/webodm/app/migrations/0002_tapis_oauth2_models.py'
    if os.path.exists(migration_path):
        with open(migration_path, 'r') as f:
            content = f.read()
        if 'models.JSONField(blank=True, default=dict' in content:
            content = content.replace('models.JSONField(blank=True, default=dict', 'models.TextField(blank=True, default="{}"')
            with open(migration_path, 'w') as f:
                f.write(content)
            logger.info("✓ Fixed OAuth2 migration Django compatibility")
    
    # Re-enable admin
    admin_path = '/webodm/app/admin.py'
    if os.path.exists(admin_path):
        with open(admin_path, 'r') as f:
            content = f.read()
        if '#TAPIS_TEMP_DISABLE#from .admin.oauth2 import' in content:
            content = content.replace('#TAPIS_TEMP_DISABLE#from .admin.oauth2 import', 'from .admin.oauth2 import')
            with open(admin_path, 'w') as f:
                f.write(content)
            logger.info("✓ Re-enabled OAuth2 admin")
            
except Exception as e:
    logger.warning(f"Could not re-enable OAuth2 components: {e}")

# Setup Django AFTER re-enabling models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')
sys.path.insert(0, '/webodm')
django.setup()

from django.core.management import call_command
from app.models import TapisOAuth2Client
from django.db import connection, transaction

def main():
    """Setup Tapis OAuth2 integration"""
    
    # Step 1: Apply compatibility fixes
    logger.info("Applying Tapis OAuth2 compatibility fixes...")
    try:
        # Fix Django compatibility issue with JSONField
        oauth2_model_path = '/webodm/app/models/oauth2.py'
        if os.path.exists(oauth2_model_path):
            with open(oauth2_model_path, 'r') as f:
                content = f.read()
            if 'models.JSONField(default=dict, blank=True' in content:
                content = content.replace('models.JSONField(default=dict, blank=True', 'models.TextField(blank=True, default="{}"')
                with open(oauth2_model_path, 'w') as f:
                    f.write(content)
                logger.info("✓ Fixed OAuth2 model Django compatibility")
        
        # Fix URL naming conflict
        urls_path = '/webodm/app/urls.py'
        if os.path.exists(urls_path):
            with open(urls_path, 'r') as f:
                content = f.read()
            if "name='login'" in content:
                content = content.replace("name='login'", "name='tapis_login'")
                with open(urls_path, 'w') as f:
                    f.write(content)
                logger.info("✓ Fixed URL naming conflict")
        
        # Fix template URL references
        template_path = '/webodm/app/templates/app/registration/login.html'
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()
            if "{% url 'login' %}" in content:
                content = content.replace("{% url 'login' %}", "/login/")
                with open(template_path, 'w') as f:
                    f.write(content)
                logger.info("✓ Fixed template URL references")
                
    except Exception as e:
        logger.warning(f"Could not apply all fixes: {e}")
    
    # Step 2: Create and run migrations
    logger.info("Creating Tapis OAuth2 migrations...")
    try:
        call_command('makemigrations', 'app', verbosity=0)
        logger.info("✓ Migrations created")
    except Exception as e:
        if "Conflicting migrations" in str(e):
            logger.info("Migration conflict detected, attempting to merge...")
            try:
                call_command('makemigrations', '--merge', '--noinput', 'app', verbosity=0)
                logger.info("✓ Migration conflict resolved with merge")
            except Exception as merge_e:
                logger.warning(f"Could not merge migrations: {merge_e}")
        else:
            logger.info(f"No new migrations needed: {e}")
    
    logger.info("Running database migrations...")
    try:
        call_command('migrate', verbosity=0)
        logger.info("✓ Database migrations completed")
    except Exception as e:
        logger.error(f"DETAILED MIGRATION ERROR: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        
        if "Conflicting migrations" in str(e):
            logger.info("Migration conflict during migrate, attempting to merge...")
            try:
                call_command('makemigrations', '--merge', '--noinput', 'app', verbosity=0)
                call_command('migrate', verbosity=0)
                logger.info("✓ Migration conflict resolved and migrations completed")
            except Exception as merge_e:
                logger.error(f"DETAILED MERGE ERROR: {merge_e}")
                return False
        else:
            logger.warning(f"Migration issue detected, attempting to continue...")
            # Check connection status
            logger.info(f"Connection status: {connection.connection}")
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                logger.info("✓ Database connection is working")
            except Exception as conn_e:
                logger.error(f"Database connection error: {conn_e}")
                connection.close()
                logger.info("Reset database connection")
    
    # Step 3: Get environment variables first
    tapis_base_url = os.environ.get('WO_TAPIS_BASE_URL', 'https://portals.tapis.io')
    tapis_tenant_id = os.environ.get('WO_TAPIS_TENANT_ID', 'portals')
    tapis_client_id = os.environ.get('WO_TAPIS_CLIENT_ID', 'webodm.tacc.utexas.edu')
    tapis_client_secret = os.environ.get('WO_TAPIS_CLIENT_SECRET')
    callback_url = os.environ.get('WO_TAPIS_CALLBACK_URL', 'https://webodm.tacc.utexas.edu/api/oauth2/tapis/callback/')
    
    # Step 4: Check if OAuth2 client already exists
    try:
        existing_client = TapisOAuth2Client.objects.filter(client_id=tapis_client_id).first()
        if existing_client:
            logger.info(f"✓ OAuth2 client already exists: {existing_client.name}")
            return True
    except Exception as e:
        # Table might not exist yet, or we have transaction issues
        logger.info(f"Could not check existing client (table may not exist): {e}")
        # Reset connection before continuing
        connection.close()
    
    if not tapis_client_secret:
        logger.error("WO_TAPIS_CLIENT_SECRET environment variable is required for production")
        return False
    
    # Step 5: Create OAuth2 client
    try:
        # Ensure clean transaction state
        try:
            transaction.rollback()
        except:
            pass
        connection.close()
        
        # Use atomic transaction for client creation
        with transaction.atomic():
            client = TapisOAuth2Client.objects.create(
                client_id=tapis_client_id,
                client_secret=tapis_client_secret,
                tenant_id=tapis_tenant_id,
                base_url=tapis_base_url,
                callback_url=callback_url,
                name="WEBodm.tacc.utexas.edu",
                description="OAuth2 client for WebODM at TACC"
            )
        
        logger.info(f"✓ Created OAuth2 client: {client.name}")
        logger.info(f"  Client ID: {client.client_id}")
        logger.info(f"  Callback URL: {client.callback_url}")
        logger.info(f"  Tenant: {client.tenant_id}")
        return True
        
    except Exception as e:
        logger.error(f"DETAILED CLIENT CREATION ERROR: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
        
        # Check if it's a database connection issue
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            logger.info("Database connection is working during client creation")
        except Exception as conn_e:
            logger.error(f"Database connection error during client creation: {conn_e}")
            
        # Check if table exists
        try:
            from django.db import models
            TapisOAuth2Client._meta.get_field('client_id')
            logger.info("OAuth2 model seems to be properly defined")
        except Exception as model_e:
            logger.error(f"OAuth2 model issue: {model_e}")
            
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
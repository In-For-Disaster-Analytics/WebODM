#!/usr/bin/env python
"""
Setup script for Tapis OAuth2 integration with WebODM

This script should be run in a properly configured WebODM environment 
(e.g., within the Docker container or with all dependencies installed)

Usage:
    python setup_tapis_oauth2.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')
django.setup()

from django.core.management import execute_from_command_line
from django.contrib.auth.models import User
from app.models import TapisOAuth2Client
from django.db import transaction


def setup_tapis_oauth2():
    """
    Setup Tapis OAuth2 integration for WebODM
    """
    print("Setting up Tapis OAuth2 integration for WebODM...")
    
    # Step 1: Run migrations
    print("\n1. Running database migrations...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("✓ Database migrations completed successfully")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False
    
    # Step 2: Check environment variables
    print("\n2. Checking environment configuration...")
    
    tapis_base_url = os.environ.get('WO_TAPIS_BASE_URL', '')
    tapis_tenant_id = os.environ.get('WO_TAPIS_TENANT_ID', '')
    
    if not tapis_base_url:
        print("⚠ Warning: WO_TAPIS_BASE_URL environment variable not set")
        tapis_base_url = input("Enter Tapis base URL (e.g., https://tacc.tapis.io): ").strip()
    
    if not tapis_tenant_id:
        print("⚠ Warning: WO_TAPIS_TENANT_ID environment variable not set")  
        tapis_tenant_id = input("Enter Tapis tenant ID: ").strip()
    
    if tapis_base_url and tapis_tenant_id:
        print(f"✓ Tapis configuration: {tapis_base_url} (tenant: {tapis_tenant_id})")
    else:
        print("✗ Tapis configuration incomplete")
        return False
    
    # Step 3: Create OAuth2 client (optional)
    print("\n3. Setting up Tapis OAuth2 client...")
    
    create_client = input("Create a Tapis OAuth2 client now? (y/n): ").strip().lower()
    
    if create_client == 'y':
        try:
            with transaction.atomic():
                client_id = input("Enter Tapis OAuth2 client ID: ").strip()
                client_secret = input("Enter Tapis OAuth2 client secret (leave blank to generate): ").strip()
                
                if not client_secret:
                    client_secret = TapisOAuth2Client.generate_client_secret()
                    print(f"Generated client secret: {client_secret}")
                
                callback_url = input("Enter callback URL (e.g., https://your-webodm.com/api/oauth2/tapis/callback/): ").strip()
                client_name = input("Enter descriptive name for this client: ").strip() or f"WebODM-{tapis_tenant_id}"
                
                # Create the client
                client = TapisOAuth2Client.objects.create(
                    client_id=client_id,
                    client_secret=client_secret,
                    tenant_id=tapis_tenant_id,
                    base_url=tapis_base_url,
                    callback_url=callback_url,
                    name=client_name,
                    description=f"OAuth2 client for WebODM integration with {tapis_tenant_id}"
                )
                
                print(f"✓ Created OAuth2 client: {client.name} (ID: {client.client_id})")
                
        except Exception as e:
            print(f"✗ Failed to create OAuth2 client: {e}")
            return False
    else:
        print("⚠ OAuth2 client not created. You can create one later in Django admin.")
    
    # Step 4: Final instructions
    print("\n" + "="*60)
    print("🎉 Tapis OAuth2 integration setup completed!")
    print("="*60)
    
    print(f"""
Next steps:
1. If you haven't created an OAuth2 client, go to Django admin:
   - Visit /admin/ 
   - Navigate to 'Tapis OAuth2 Clients'
   - Add a new client with your Tapis credentials

2. Register your WebODM callback URL with Tapis:
   - Use the Tapis API or dashboard
   - Callback URL format: https://your-webodm-domain.com/api/oauth2/tapis/callback/

3. Test the authentication flow:
   - Visit /login/ 
   - Click "Login with Tapis"
   - Complete the OAuth2 flow

4. Environment variables used:
   - WO_TAPIS_BASE_URL={tapis_base_url}
   - WO_TAPIS_TENANT_ID={tapis_tenant_id}

5. Available endpoints:
   - Login: /login/
   - OAuth2 authorize: /api/oauth2/tapis/authorize/<client_id>/
   - OAuth2 callback: /api/oauth2/tapis/callback/
   - Token status: /api/oauth2/tapis/status/
   - Token refresh: /api/oauth2/tapis/refresh/<client_id>/
   - Token revoke: /api/oauth2/tapis/revoke/<client_id>/
    """)
    
    return True


if __name__ == '__main__':
    try:
        success = setup_tapis_oauth2()
        if not success:
            print("\n❌ Setup failed. Please check the errors above.")
            sys.exit(1)
        else:
            print("✅ Setup completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during setup: {e}")
        sys.exit(1)
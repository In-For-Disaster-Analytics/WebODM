#!/usr/bin/env python
"""
Fix ClusterODM connection by manually updating node info
"""

import os
import django
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')
django.setup()

from nodeodm.models import ProcessingNode

def fix_clusterodm_connection():
    print("=== Fixing ClusterODM Connection ===")
    
    node = ProcessingNode.objects.filter(hostname='clusterodm.tacc.utexas.edu').first()
    if not node:
        print("❌ ClusterODM node not found!")
        return
    
    print(f"Found node: {node.hostname}:{node.port}")
    
    # Get the info manually
    try:
        api_client = node.api_client(timeout=30)
        info = api_client.info()
        
        print("✅ Got API info successfully:")
        print(f"  Version: {info.version}")
        print(f"  Task queue: {info.task_queue_count}")
        print(f"  Engine: {info.engine}")
        print(f"  Engine version: {info.engine_version}")
        
        # Manually update the node fields
        node.api_version = info.version
        node.queue_count = info.task_queue_count
        node.engine_version = info.engine_version if info.engine_version != '?' else 'ClusterODM'
        node.engine = 'odm'  # Keep as odm for compatibility
        node.available_options = []  # ClusterODM doesn't expose options the same way
        node.last_refreshed = timezone.now()
        
        # Handle max_images
        if hasattr(info, 'max_images') and info.max_images is not None:
            node.max_images = info.max_images
        else:
            node.max_images = 0  # Unlimited for ClusterODM
        
        node.save()
        
        print("✅ Manually updated node info")
        print(f"  API Version: {node.api_version}")
        print(f"  Engine Version: {node.engine_version}")
        print(f"  Last refreshed: {node.last_refreshed}")
        print(f"  Node is online: {node.is_online()}")
        
    except Exception as e:
        print(f"❌ Failed to fix connection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_clusterodm_connection()
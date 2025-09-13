#!/usr/bin/env python
"""
Debug script for ClusterODM connection to WebODM
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webodm.settings')
django.setup()

from nodeodm.models import ProcessingNode

def debug_clusterodm_connection():
    print("=== ClusterODM Connection Debug ===")
    
    # Find all nodes
    all_nodes = ProcessingNode.objects.all()
    print(f"Total processing nodes: {len(all_nodes)}")
    for node in all_nodes:
        print(f"  - {node.hostname}:{node.port} ({node.label})")
    
    print("\n=== Looking for ClusterODM node ===")
    
    # Try different ways to find the node
    node_by_hostname = ProcessingNode.objects.filter(hostname='clusterodm.tacc.utexas.edu').first()
    node_by_label = ProcessingNode.objects.filter(label='ClusterODM (TACC)').first()
    node_by_port = ProcessingNode.objects.filter(port=443).first()
    
    print(f"By hostname 'clusterodm.tacc.utexas.edu': {node_by_hostname}")
    print(f"By label 'ClusterODM (TACC)': {node_by_label}")
    print(f"By port 443: {node_by_port}")
    
    # Use whichever node we found
    node = node_by_hostname or node_by_label or node_by_port
    
    if not node:
        print("❌ No ClusterODM node found!")
        return
    
    print(f"\n=== Testing node: {node} ===")
    print(f"Hostname: {node.hostname}")
    print(f"Port: {node.port}")
    print(f"Label: {node.label}")
    print(f"API Version: {node.api_version}")
    print(f"Last refreshed: {node.last_refreshed}")
    print(f"Engine: {node.engine}")
    print(f"Token: {'***' if node.token else '(empty)'}")
    
    print("\n=== Testing API client ===")
    try:
        api_client = node.api_client(timeout=30)
        print(f"✅ API client created: {api_client}")
        
        print("Testing info() call...")
        info = api_client.info()
        print(f"✅ API info call successful:")
        print(f"  Version: {info.version}")
        print(f"  Task queue: {info.task_queue_count}")
        print(f"  Engine: {info.engine}")
        print(f"  Engine version: {info.engine_version}")
        
    except Exception as e:
        print(f"❌ API client failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Testing node update ===")
    try:
        print("Calling update_node_info()...")
        success = node.update_node_info()
        
        # Refresh from database
        node.refresh_from_db()
        
        print(f"Update result: {success}")
        print(f"New API version: {node.api_version}")
        print(f"New last refreshed: {node.last_refreshed}")
        print(f"Node is online: {node.is_online()}")
        
    except Exception as e:
        print(f"❌ Update failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_clusterodm_connection()
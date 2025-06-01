#!/usr/bin/env python3
"""
Test script for Zoom MCP Server
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config.settings import initialize_config
from src.server import test_zoom_connection, get_zoom_sites, get_zoom_rooms

async def main():
    """Test the Zoom MCP server functionality."""
    try:
        # Initialize configuration
        initialize_config()
        print("✓ Configuration initialized")
        
        # Test connection
        print("\n1. Testing Zoom connection...")
        connection_result = await test_zoom_connection()
        print(f"✓ Connection test: {connection_result}")
        
        # Test getting sites
        print("\n2. Getting Zoom sites...")
        sites_result = await get_zoom_sites()
        print(f"✓ Found {sites_result['total_count']} sites:")
        for site in sites_result['sites'][:5]:  # Show first 5
            print(f"  - {site['name']} (ID: {site['id']})")
        
        # Test getting rooms
        print("\n3. Getting Zoom rooms...")
        rooms_result = await get_zoom_rooms()
        print(f"✓ Found {rooms_result['total_count']} rooms:")
        for room in rooms_result['rooms'][:5]:  # Show first 5
            print(f"  - {room['name']} (Status: {room['status']}, Health: {room.get('health', 'N/A')})")
        
        # Test getting rooms for first site if available
        if sites_result['sites']:
            first_site_id = sites_result['sites'][0]['id']
            first_site_name = sites_result['sites'][0]['name']
            print(f"\n4. Getting rooms for site '{first_site_name}'...")
            site_rooms_result = await get_zoom_rooms(first_site_id)
            print(f"✓ Found {site_rooms_result['total_count']} rooms in {first_site_name}:")
            for room in site_rooms_result['rooms'][:3]:  # Show first 3
                print(f"  - {room['name']} (Status: {room['status']})")
        
        print("\n🎉 All tests passed! The Zoom MCP server is working correctly.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
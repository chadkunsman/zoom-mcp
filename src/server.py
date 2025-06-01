#!/usr/bin/env python3
"""
Zoom MCP Server

A FastMCP server that provides tools for monitoring Zoom room status across sites.
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

mcp = FastMCP("Zoom MCP Server")

@mcp.tool()
async def get_zoom_sites() -> Dict[str, Any]:
    """Get all Zoom sites/locations with hierarchy and aliases.
    
    USE THIS to understand available locations before using location-specific queries.
    Shows campus → building → floor relationships and common aliases like 'SF1', 'DEN1', etc.
    
    Perfect for: "What locations do we have?", "Show me all sites", "What are the building names?"
    """
    try:
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth
        from src.config.zoom_hierarchy import ZoomHierarchy
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        hierarchy = ZoomHierarchy(zoom_auth)
        
        # Get hierarchy with all relationships
        hierarchy_data = await hierarchy.discover_and_build_hierarchy()
        
        # Format for display
        sites_list = []
        for location in hierarchy.locations.values():
            site_data = {
                'id': location.id,
                'name': location.name,
                'type': location.type,
                'address': location.address,
                'timezone': location.timezone,
                'aliases': [alias for alias, loc_id in hierarchy.aliases.items() if loc_id == location.id],
                'children_count': len(location.children),
                'parent_id': location.parent_id
            }
            sites_list.append(site_data)
        
        return {
            'sites': sites_list,
            'total_count': len(sites_list),
            'hierarchy_summary': {
                'campuses': len(hierarchy_data['campuses']),
                'buildings': len(hierarchy_data['buildings']),
                'floors': len(hierarchy_data['floors'])
            },
            'common_aliases': {
                'sf1': 'USSFO (San Francisco)',
                'den1': 'USDEN (Denver)', 
                'nyc': 'USNYC (New York)',
                'cantor': 'CANTOR'
            }
        }
        
    except Exception as e:
        raise ToolError(f"Failed to get Zoom sites: {str(e)}")

@mcp.tool()
async def get_zoom_rooms(location_query: Optional[str] = None) -> Dict[str, Any]:
    """Get Zoom rooms with optional location filtering.
    
    IMPORTANT: For maximum efficiency when checking ALL rooms company-wide (e.g., "find offline rooms anywhere", "all rooms", "company-wide status"), 
    DO NOT provide location_query - this makes a single API call to get all rooms.
    
    USE location_query ONLY for specific location filtering (e.g., 'SF1', 'DEN1', 'Floor 1', 'Denver Building 2').
    This uses smart location resolution but makes multiple API calls per location.
    
    Examples:
    - Company-wide queries: omit location_query for single efficient API call
    - Location-specific: use location_query='SF1' for San Francisco only
    """
    try:
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth, zoom_api_get
        from src.config.zoom_hierarchy import ZoomHierarchy
        from src.config.zoom_fuzzy import ZoomFuzzyMatcher
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        hierarchy = ZoomHierarchy(zoom_auth)
        
        if location_query:
            # Resolve location query to specific location IDs using fuzzy matching
            fuzzy_matcher = ZoomFuzzyMatcher(hierarchy)
            resolution = await fuzzy_matcher.fuzzy_resolve_location(location_query)
            location_ids = await hierarchy.get_all_location_ids_for_resolution(resolution)
            
            # Get rooms for all resolved locations
            all_rooms = []
            location_summary = {}
            
            for location_id in location_ids:
                try:
                    response = await zoom_api_get(zoom_auth, 'rooms', {
                        'page_size': '100',
                        'location_id': location_id
                    })
                    
                    location_obj = hierarchy.locations.get(location_id)
                    location_name = location_obj.name if location_obj else location_id
                    room_count = len(response.get('rooms', []))
                    
                    if room_count > 0:
                        location_summary[location_name] = {
                            'room_count': room_count,
                            'location_id': location_id
                        }
                    
                    for room in response.get('rooms', []):
                        room_data = {
                            'id': room['id'],
                            'name': room['name'],
                            'room_type': room.get('room_type', ''),
                            'status': room.get('status', ''),
                            'location_id': room.get('location_id', ''),
                            'capacity': room.get('capacity', 0),
                            'device_ip': room.get('device_ip', ''),
                            'health': room.get('health', ''),
                            'issues': room.get('issues', []),
                            'location_context': {
                                'location_name': location_name,
                                'query_resolved_to': resolution.resolution_type
                            }
                        }
                        all_rooms.append(room_data)
                        
                except Exception as loc_error:
                    # Continue with other locations if one fails
                    continue
            
            # Group rooms by status for summary
            status_summary = {}
            for room in all_rooms:
                status = room['status']
                if status not in status_summary:
                    status_summary[status] = 0
                status_summary[status] += 1
            
            # Generate user-friendly confirmation message
            confirmation_msg = _generate_confirmation_message(location_query, resolution, location_summary)
            
            return {
                'confirmation': confirmation_msg,
                'rooms': all_rooms,
                'total_count': len(all_rooms),
                'query': location_query,
                'resolution': {
                    'type': resolution.resolution_type,
                    'locations_found': len(resolution.resolved_locations),
                    'aliases_used': resolution.aliases_used,
                    'includes_hierarchy': resolution.includes_hierarchy
                },
                'location_summary': location_summary,
                'status_summary': status_summary
            }
        else:
            # No location filter - get all rooms
            response = await zoom_api_get(zoom_auth, 'rooms', {'page_size': '100'})
            
            rooms = []
            for room in response.get('rooms', []):
                rooms.append({
                    'id': room['id'],
                    'name': room['name'],
                    'room_type': room.get('room_type', ''),
                    'status': room.get('status', ''),
                    'location_id': room.get('location_id', ''),
                    'capacity': room.get('capacity', 0),
                    'device_ip': room.get('device_ip', ''),
                    'health': room.get('health', ''),
                    'issues': room.get('issues', [])
                })
                
            return {
                'rooms': rooms,
                'total_count': response.get('total_records', len(rooms)),
                'query': None,
                'resolution': None
            }
        
    except Exception as e:
        raise ToolError(f"Failed to get Zoom rooms: {str(e)}")

def _generate_confirmation_message(location_query: str, resolution, location_summary: dict) -> str:
    """Generate a user-friendly confirmation message explaining what was resolved."""
    
    if resolution.resolution_type == 'campus':
        # Whole campus
        resolved_location = resolution.resolved_locations[0]
        campus_name = resolved_location.name
        
        # Count total floors/buildings included
        location_details = []
        floor_count = 0
        building_count = 0
        
        for loc_name, info in location_summary.items():
            if loc_name != campus_name:  # Don't count the campus itself
                if 'Floor' in loc_name:
                    floor_count += 1
                    location_details.append(loc_name)
                elif 'Building' in loc_name:
                    building_count += 1
                    location_details.append(loc_name)
        
        if floor_count > 0:
            floors_text = f"{floor_count} floors ({', '.join(location_details)})"
            return f"✅ Showing all '{location_query}' rooms from {campus_name} campus in Zoom across {floors_text}"
        elif building_count > 0:
            buildings_text = f"{building_count} buildings ({', '.join(location_details)})"
            return f"✅ Showing all '{location_query}' rooms from {campus_name} campus in Zoom across {buildings_text}"
        else:
            return f"✅ Showing all '{location_query}' rooms from {campus_name} campus in Zoom"
    
    elif resolution.resolution_type == 'floor':
        # Specific floor
        resolved_location = resolution.resolved_locations[0]
        floor_name = resolved_location.name
        
        # Get parent campus from aliases or naming patterns
        parent_campus = _get_parent_campus_name(resolution.aliases_used)
        
        return f"✅ Showing '{location_query}' rooms from {floor_name} in {parent_campus} site in Zoom"
    
    elif resolution.resolution_type == 'denver_building':
        # Denver-specific building (DEN1/DEN2)
        building_name = "Denver Building 1" if 'den1' in resolution.aliases_used[0] else "Denver Building 2"
        floor_names = [loc.name for loc in resolution.resolved_locations]
        
        if len(floor_names) == 1:
            return f"✅ Showing '{location_query}' rooms from {building_name} ({floor_names[0]}) in USDEN site in Zoom"
        else:
            floors_text = f"{len(floor_names)} floors ({', '.join(floor_names)})"
            return f"✅ Showing '{location_query}' rooms from {building_name} across {floors_text} in USDEN site in Zoom"
    
    elif resolution.resolution_type == 'building':
        # Specific building  
        resolved_location = resolution.resolved_locations[0]
        building_name = resolved_location.name
        
        # Get parent campus from aliases or naming patterns
        parent_campus = _get_parent_campus_name(resolution.aliases_used)
        
        return f"✅ Showing '{location_query}' rooms from {building_name} in {parent_campus} site in Zoom"
    
    elif resolution.resolution_type == 'multiple':
        # Multiple matches
        location_names = [loc.name for loc in resolution.resolved_locations]
        return f"🔍 Found multiple matches for '{location_query}': {', '.join(location_names)} in Zoom"
    
    else:
        # Fallback
        return f"✅ Showing '{location_query}' rooms from Zoom"

def _get_parent_campus_name(aliases_used: List[str]) -> str:
    """Extract parent campus name from resolution aliases."""
    if not aliases_used:
        return "Unknown Campus"
    
    for alias in aliases_used:
        if 'ussfo' in alias.lower():
            return "USSFO"
        elif 'usden' in alias.lower():
            return "USDEN"  
        elif 'usnyc' in alias.lower():
            return "USNYC"
        elif 'cantor' in alias.lower():
            return "CANTOR"
    
    return "Unknown Campus"

@mcp.tool()
async def get_room_details(room_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific Zoom room.
    
    USE THIS when you have a specific room ID and need complete details about that single room.
    Returns full room configuration, settings, and recent events.
    
    Perfect for: "Tell me about room ABC123", "What are the details of this specific room?"
    """
    try:
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth, zoom_api_get
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        
        # Get room details
        room_response = await zoom_api_get(zoom_auth, f'rooms/{room_id}')
        
        # Get room events if available
        try:
            events_response = await zoom_api_get(zoom_auth, f'rooms/{room_id}/events', 
                                               {'page_size': '10', 'type': 'past'})
            events = events_response.get('events', [])
        except:
            events = []
            
        return {
            'room': room_response,
            'recent_events': events
        }
        
    except Exception as e:
        raise ToolError(f"Failed to get room details: {str(e)}")

@mcp.tool()
async def resolve_location(location_query: str) -> Dict[str, Any]:
    """DEBUG TOOL: Test how location queries get resolved without fetching rooms.
    
    USE THIS to understand what locations will be searched before running expensive room queries.
    Shows which aliases match, what locations are found, and how many API calls would be made.
    
    Perfect for: "How would 'DEN1' be resolved?", "What locations match 'Floor 1'?", debugging location queries.
    """
    try:
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth
        from src.config.zoom_hierarchy import ZoomHierarchy
        from src.config.zoom_fuzzy import ZoomFuzzyMatcher
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        hierarchy = ZoomHierarchy(zoom_auth)
        fuzzy_matcher = ZoomFuzzyMatcher(hierarchy)
        
        resolution = await fuzzy_matcher.fuzzy_resolve_location(location_query)
        location_ids = await hierarchy.get_all_location_ids_for_resolution(resolution)
        
        # Get details about resolved locations
        resolved_details = []
        for loc in resolution.resolved_locations:
            details = {
                'id': loc.id,
                'name': loc.name,
                'type': loc.type,
                'children_count': len(loc.children),
                'parent_id': loc.parent_id
            }
            resolved_details.append(details)
        
        # Generate confirmation message
        confirmation_msg = _generate_confirmation_message(location_query, resolution, {})
        
        return {
            'confirmation': confirmation_msg,
            'query': location_query,
            'resolution_type': resolution.resolution_type,
            'includes_hierarchy': resolution.includes_hierarchy,
            'aliases_used': resolution.aliases_used,
            'resolved_locations': resolved_details,
            'location_ids_to_query': location_ids,
            'total_locations_to_search': len(location_ids)
        }
        
    except Exception as e:
        raise ToolError(f"Failed to resolve location: {str(e)}")

@mcp.tool()
async def test_zoom_connection() -> Dict[str, Any]:
    """Test Zoom API connection and validate authentication credentials.
    
    USE THIS FIRST to verify your Zoom credentials are working before using other tools.
    Returns authentication status, account info, and token cache status.
    
    Perfect for: "Is my connection working?", "Test Zoom authentication", troubleshooting setup.
    """
    try:
        from src.config.settings import ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth
        
        if not ZOOM_ACCOUNT_ID or not ZOOM_CLIENT_ID:
            raise ToolError("Zoom credentials not configured")
            
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        token = await zoom_auth.get_valid_token()
        
        return {
            'status': 'success',
            'account_id': ZOOM_ACCOUNT_ID,
            'client_id': ZOOM_CLIENT_ID,
            'token_cached': token is not None,
            'message': 'Successfully authenticated with Zoom API'
        }
        
    except Exception as e:
        raise ToolError(f"Zoom connection test failed: {str(e)}")

def parse_arguments():
    """Parse command-line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Zoom MCP Server')
    parser.add_argument('--zoom-account-id', help='Zoom Account ID')
    parser.add_argument('--zoom-client-id', help='Zoom Client ID')
    parser.add_argument('--zoom-client-secret', help='Zoom Client Secret')
    
    return parser.parse_args()

def main():
    """Main entry point for the MCP server."""
    args = parse_arguments()
    
    from src.config.settings import initialize_config
    initialize_config(
        zoom_account_id=args.zoom_account_id,
        zoom_client_id=args.zoom_client_id,
        zoom_client_secret=args.zoom_client_secret
    )
    mcp.run()

if __name__ == "__main__":
    main()
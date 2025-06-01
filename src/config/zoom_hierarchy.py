import re
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .zoom_auth import ZoomAuth, zoom_api_get

@dataclass
class LocationInfo:
    id: str
    name: str
    type: str
    address: str = ""
    timezone: str = ""
    parent_id: Optional[str] = None
    children: List[str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []

@dataclass 
class LocationResolution:
    query: str
    resolved_locations: List[LocationInfo]
    resolution_type: str  # 'campus', 'building', 'floor', 'specific'
    includes_hierarchy: bool
    aliases_used: List[str] = None
    
    def __post_init__(self):
        if self.aliases_used is None:
            self.aliases_used = []

class ZoomHierarchy:
    def __init__(self, zoom_auth: ZoomAuth):
        self.zoom_auth = zoom_auth
        self.locations: Dict[str, LocationInfo] = {}
        self.aliases: Dict[str, str] = {}  # alias -> location_id
        self.hierarchy_cache = None
        self.cache_timestamp = 0
        
    async def discover_and_build_hierarchy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Dynamically discover all locations and build hierarchy."""
        import time
        
        # Use cache if recent (5 minutes)
        if not force_refresh and self.hierarchy_cache and (time.time() - self.cache_timestamp < 300):
            return self.hierarchy_cache
            
        # Get all locations from Zoom API
        response = await zoom_api_get(self.zoom_auth, 'rooms/locations', {'page_size': '300'})
        
        # Clear existing data
        self.locations.clear()
        self.aliases.clear()
        
        # Process all locations
        for location_data in response.get('locations', []):
            loc = LocationInfo(
                id=location_data['id'],
                name=location_data['name'],
                type=location_data.get('type', ''),
                address=location_data.get('address', ''),
                timezone=location_data.get('timezone', '')
            )
            self.locations[loc.id] = loc
            
        # Build parent-child relationships by analyzing room associations
        await self._build_relationships()
        
        # Generate dynamic aliases
        self._generate_aliases()
        
        # Build hierarchy summary
        hierarchy = self._build_hierarchy_summary()
        
        self.hierarchy_cache = hierarchy
        self.cache_timestamp = time.time()
        
        return hierarchy
    
    async def _build_relationships(self):
        """Infer parent-child relationships from room data and naming patterns."""
        # Get sample rooms to understand location relationships
        rooms_response = await zoom_api_get(self.zoom_auth, 'rooms', {'page_size': '300'})
        
        # Group rooms by location to understand usage patterns
        location_usage = {}
        for room in rooms_response.get('rooms', []):
            location_id = room.get('location_id')
            if location_id and location_id in self.locations:
                if location_id not in location_usage:
                    location_usage[location_id] = []
                location_usage[location_id].append(room)
        
        # Analyze naming patterns to infer hierarchy
        campuses = [loc for loc in self.locations.values() if loc.type == 'campus']
        buildings = [loc for loc in self.locations.values() if loc.type == 'building']  
        floors = [loc for loc in self.locations.values() if loc.type == 'floor']
        
        # For each floor/building, try to find its parent campus
        for location in buildings + floors:
            parent_campus = self._find_parent_campus(location, campuses, location_usage)
            if parent_campus:
                location.parent_id = parent_campus.id
                parent_campus.children.append(location.id)
        
        # For floors, try to find parent buildings
        for floor in floors:
            parent_building = self._find_parent_building(floor, buildings, location_usage)
            if parent_building and not floor.parent_id:
                floor.parent_id = parent_building.id
                parent_building.children.append(floor.id)
    
    def _find_parent_campus(self, location: LocationInfo, campuses: List[LocationInfo], 
                           location_usage: Dict) -> Optional[LocationInfo]:
        """Find the parent campus for a building/floor based on naming patterns."""
        
        # Look for naming patterns like SFO-1-1 → USSFO
        for campus in campuses:
            # Extract potential code from campus name (USSFO → SFO)
            if campus.name.startswith('US') and len(campus.name) == 5:
                campus_code = campus.name[2:]  # SFO, NYC, DEN
                
                # Check if location name contains this code
                if campus_code.lower() in location.name.lower():
                    return campus
                    
        # Check room naming patterns - rooms often contain location codes
        if location.id in location_usage:
            for room in location_usage[location.id][:5]:  # Check first few rooms
                room_name = room.get('name', '').upper()
                for campus in campuses:
                    if campus.name.startswith('US') and len(campus.name) == 5:
                        campus_code = campus.name[2:]
                        if campus_code in room_name:
                            return campus
        
        return None
    
    def _find_parent_building(self, floor: LocationInfo, buildings: List[LocationInfo],
                             location_usage: Dict) -> Optional[LocationInfo]:
        """Find the parent building for a floor."""
        # Simple name-based matching for now
        for building in buildings:
            # Check if they're in the same campus context
            if (building.name in floor.name or 
                any(word in building.name.lower() for word in floor.name.lower().split())):
                return building
        return None
    
    def _generate_aliases(self):
        """Dynamically generate aliases for all locations."""
        for loc in self.locations.values():
            aliases = self._generate_location_aliases(loc)
            for alias in aliases:
                self.aliases[alias.lower()] = loc.id
    
    def _generate_location_aliases(self, location: LocationInfo) -> List[str]:
        """Generate aliases for a specific location."""
        aliases = [location.name.lower()]
        
        if location.type == 'campus':
            # Pattern: US + 3-letter code → multiple aliases
            if location.name.startswith('US') and len(location.name) == 5:
                city_code = location.name[2:]  # SFO, NYC, DEN
                aliases.extend([
                    city_code.lower(),
                    city_code.lower() + '1',  # Common pattern
                    city_code.lower() + ' 1',
                ])
                
                # Add full city names based on common patterns
                city_names = {
                    'SFO': ['san francisco', 'sf'],
                    'NYC': ['new york', 'ny'], 
                    'DEN': ['denver'],
                    'LAX': ['los angeles', 'la'],
                    'CHI': ['chicago'],
                    'ATL': ['atlanta']
                }
                
                if city_code in city_names:
                    aliases.extend(city_names[city_code])
                    
        elif location.type == 'building':
            # Generate building-specific aliases
            # "Building 1" → "bldg 1", "b1", etc.
            name_lower = location.name.lower()
            if 'building' in name_lower:
                building_num = re.search(r'building\s+(\d+)', name_lower)
                if building_num:
                    num = building_num.group(1)
                    aliases.extend([
                        f'bldg {num}',
                        f'building{num}',
                        f'b{num}'
                    ])
        
        elif location.type == 'floor':
            # Generate floor aliases
            name_lower = location.name.lower()
            if 'floor' in name_lower:
                floor_num = re.search(r'floor\s+(\d+)', name_lower)
                if floor_num:
                    num = floor_num.group(1)
                    aliases.extend([
                        f'floor{num}',
                        f'f{num}',
                        f'{num}f',
                        f'level {num}'
                    ])
        
        return aliases
    
    def _build_hierarchy_summary(self) -> Dict[str, Any]:
        """Build a summary of the location hierarchy."""
        campuses = {}
        buildings = {}
        floors = {}
        
        for loc in self.locations.values():
            if loc.type == 'campus':
                campuses[loc.id] = {
                    'id': loc.id,
                    'name': loc.name,
                    'children': loc.children,
                    'aliases': [alias for alias, loc_id in self.aliases.items() if loc_id == loc.id]
                }
            elif loc.type == 'building':
                buildings[loc.id] = {
                    'id': loc.id,
                    'name': loc.name,
                    'parent': loc.parent_id,
                    'children': loc.children,
                    'aliases': [alias for alias, loc_id in self.aliases.items() if loc_id == loc.id]
                }
            elif loc.type == 'floor':
                floors[loc.id] = {
                    'id': loc.id,
                    'name': loc.name,
                    'parent': loc.parent_id,
                    'aliases': [alias for alias, loc_id in self.aliases.items() if loc_id == loc.id]
                }
        
        return {
            'campuses': campuses,
            'buildings': buildings,
            'floors': floors,
            'total_locations': len(self.locations)
        }
    
    async def resolve_location_query(self, query: str) -> LocationResolution:
        """Resolve a natural language query to specific location(s)."""
        await self.discover_and_build_hierarchy()
        
        query_lower = query.lower().strip()
        
        # Direct alias match
        if query_lower in self.aliases:
            location_id = self.aliases[query_lower]
            location = self.locations[location_id]
            
            return LocationResolution(
                query=query,
                resolved_locations=[location],
                resolution_type=location.type,
                includes_hierarchy=location.type in ['campus', 'building'],
                aliases_used=[query_lower]
            )
        
        # Pattern matching for complex queries
        patterns = [
            # "SF1 Floor 1" → specific floor in campus
            (r'^([a-z]+\d*)\s+floor\s+(\d+)$', self._resolve_campus_floor),
            
            # "SF1 Building 1" → specific building in campus  
            (r'^([a-z]+\d*)\s+building\s+(\d+)$', self._resolve_campus_building),
            
            # "Floor 1" → all Floor 1s across campuses
            (r'^floor\s+(\d+)$', self._resolve_floor_across_campuses),
            
            # Fuzzy name matching
            (r'^(.+)$', self._resolve_fuzzy_match)
        ]
        
        for pattern, resolver in patterns:
            match = re.match(pattern, query_lower)
            if match:
                result = await resolver(match.groups(), query)
                if result:
                    return result
        
        raise ValueError(f"Could not resolve location query: {query}")
    
    async def _resolve_campus_floor(self, groups: tuple, original_query: str) -> Optional[LocationResolution]:
        """Resolve queries like 'SF1 Floor 1'."""
        campus_alias, floor_num = groups
        
        # Find campus
        if campus_alias in self.aliases:
            campus_id = self.aliases[campus_alias]
            campus = self.locations[campus_id]
            
            # Find specific floor in this campus
            for child_id in campus.children:
                child = self.locations.get(child_id)
                if child and child.type == 'floor' and floor_num in child.name.lower():
                    return LocationResolution(
                        query=original_query,
                        resolved_locations=[child],
                        resolution_type='floor',
                        includes_hierarchy=False,
                        aliases_used=[campus_alias]
                    )
        
        return None
    
    async def _resolve_campus_building(self, groups: tuple, original_query: str) -> Optional[LocationResolution]:
        """Resolve queries like 'SF1 Building 1'."""
        campus_alias, building_num = groups
        
        if campus_alias in self.aliases:
            campus_id = self.aliases[campus_alias]
            campus = self.locations[campus_id]
            
            # Find specific building in this campus
            for child_id in campus.children:
                child = self.locations.get(child_id)
                if child and child.type == 'building' and building_num in child.name.lower():
                    return LocationResolution(
                        query=original_query,
                        resolved_locations=[child],
                        resolution_type='building',
                        includes_hierarchy=True,
                        aliases_used=[campus_alias]
                    )
        
        return None
    
    async def _resolve_floor_across_campuses(self, groups: tuple, original_query: str) -> Optional[LocationResolution]:
        """Resolve queries like 'Floor 1' across all campuses."""
        floor_num = groups[0]
        
        matching_floors = []
        for loc in self.locations.values():
            if loc.type == 'floor' and floor_num in loc.name.lower():
                matching_floors.append(loc)
        
        if matching_floors:
            return LocationResolution(
                query=original_query,
                resolved_locations=matching_floors,
                resolution_type='floor_multi',
                includes_hierarchy=False,
                aliases_used=[]
            )
        
        return None
    
    async def _resolve_fuzzy_match(self, groups: tuple, original_query: str) -> Optional[LocationResolution]:
        """Fuzzy matching for location names."""
        search_term = groups[0]
        
        # Try partial name matches
        for loc in self.locations.values():
            if search_term in loc.name.lower():
                return LocationResolution(
                    query=original_query,
                    resolved_locations=[loc],
                    resolution_type=loc.type,
                    includes_hierarchy=loc.type in ['campus', 'building'],
                    aliases_used=[]
                )
        
        return None
    
    async def get_all_location_ids_for_resolution(self, resolution: LocationResolution) -> List[str]:
        """Get all location IDs that should be queried for rooms based on resolution."""
        location_ids = []
        
        for location in resolution.resolved_locations:
            if resolution.includes_hierarchy:
                # Include all children (floors/buildings)
                location_ids.extend(self._get_all_descendants(location.id))
            else:
                # Just this specific location
                location_ids.append(location.id)
        
        return location_ids
    
    def _get_all_descendants(self, location_id: str) -> List[str]:
        """Get all descendant location IDs (children, grandchildren, etc.)."""
        descendants = [location_id]
        location = self.locations.get(location_id)
        
        if location:
            for child_id in location.children:
                descendants.extend(self._get_all_descendants(child_id))
        
        return descendants
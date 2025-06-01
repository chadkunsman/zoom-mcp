import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from .zoom_hierarchy import LocationInfo, LocationResolution

@dataclass
class CampusStructure:
    """Represents the structure of locations within a campus."""
    campus: LocationInfo
    buildings: List[LocationInfo]
    floors: List[LocationInfo]
    
    def has_buildings(self) -> bool:
        return len(self.buildings) > 0
    
    def has_floors(self) -> bool:
        return len(self.floors) > 0
    
    def has_numbered_buildings(self) -> bool:
        """Check if campus has buildings with numbers (Building 1, Building 2, etc.)"""
        building_numbers = []
        for building in self.buildings:
            match = re.search(r'building\s+(\d+)', building.name.lower())
            if match:
                building_numbers.append(int(match.group(1)))
        return len(building_numbers) > 1
    
    def has_numbered_floors(self) -> bool:
        """Check if campus has floors with numbers (Floor 1, Floor 2, etc.)"""
        floor_numbers = []
        for floor in self.floors:
            match = re.search(r'floor\s+(\d+)', floor.name.lower())
            if match:
                floor_numbers.append(int(match.group(1)))
        return len(floor_numbers) > 1

class ZoomFuzzyMatcher:
    def __init__(self, hierarchy):
        self.hierarchy = hierarchy
        self.campus_structures = {}
    
    async def analyze_campus_structures(self):
        """Analyze the structure of each campus to understand numbering patterns."""
        await self.hierarchy.discover_and_build_hierarchy()
        
        self.campus_structures.clear()
        
        # Group locations by campus
        for campus in [loc for loc in self.hierarchy.locations.values() if loc.type == 'campus']:
            buildings = []
            floors = []
            
            # Find all children of this campus
            for child_id in campus.children:
                child = self.hierarchy.locations.get(child_id)
                if child:
                    if child.type == 'building':
                        buildings.append(child)
                    elif child.type == 'floor':
                        floors.append(child)
                    
                    # Also check grandchildren (floors under buildings)
                    for grandchild_id in child.children:
                        grandchild = self.hierarchy.locations.get(grandchild_id)
                        if grandchild and grandchild.type == 'floor':
                            floors.append(grandchild)
            
            self.campus_structures[campus.id] = CampusStructure(
                campus=campus,
                buildings=buildings,
                floors=floors
            )
    
    async def fuzzy_resolve_location(self, query: str) -> LocationResolution:
        """Resolve location using contextually-aware fuzzy matching."""
        await self.analyze_campus_structures()
        
        query_lower = query.lower().strip()
        
        # Check Denver hardcoded aliases first (special case)
        denver_match = self._try_denver_aliases(query_lower)
        if denver_match:
            return denver_match
        
        # Try numbered pattern matching first (DEN1, SF1, NYC2, etc.)
        numbered_match = self._try_numbered_pattern(query_lower)
        if numbered_match:
            return numbered_match
        
        # Try direct fuzzy matching
        fuzzy_matches = self._fuzzy_match_all_locations(query_lower)
        
        if len(fuzzy_matches) == 1:
            location = fuzzy_matches[0][0]
            return LocationResolution(
                query=query,
                resolved_locations=[location],
                resolution_type=location.type,
                includes_hierarchy=location.type in ['campus', 'building'],
                aliases_used=[query_lower]
            )
        elif len(fuzzy_matches) > 1:
            # Multiple matches - return best scoring ones
            best_score = fuzzy_matches[0][1]
            best_matches = [match[0] for match in fuzzy_matches if match[1] >= best_score - 10]
            
            return LocationResolution(
                query=query,
                resolved_locations=best_matches,
                resolution_type='multiple',
                includes_hierarchy=True,
                aliases_used=[query_lower]
            )
        
        raise ValueError(f"No location matches found for: {query}")
    
    def _try_denver_aliases(self, query_lower: str) -> Optional[LocationResolution]:
        """Handle Denver-specific building aliases (DEN1 = Building 1, DEN2 = Building 2)."""
        
        # Define Denver building mappings based on room naming analysis
        denver_building_mappings = {
            'den1': {
                'description': 'Denver Building 1',
                'floor_ids': ['xx14SBuZSuCRHd7jZBsmzw'],  # Floor 3 where DEN-1-* rooms are
                'room_prefix': 'DEN-1-'
            },
            'den2': {
                'description': 'Denver Building 2', 
                'floor_ids': ['zh10l_aJT6CkImBHJn4skQ', '7EZDyz67TxC0Y-XMASub7g', 'bAwBNuv7SAii8pdGRX2a3w'],  # T3F3, T3F5, T3F6
                'room_prefix': 'DEN-2-'
            }
        }
        
        if query_lower in denver_building_mappings:
            mapping = denver_building_mappings[query_lower]
            
            # Get the floor locations for this building
            building_floors = []
            for floor_id in mapping['floor_ids']:
                if floor_id in self.hierarchy.locations:
                    building_floors.append(self.hierarchy.locations[floor_id])
            
            if building_floors:
                return LocationResolution(
                    query=query_lower,
                    resolved_locations=building_floors,
                    resolution_type='denver_building',
                    includes_hierarchy=True,
                    aliases_used=[f"denver_{query_lower}_hardcoded"]
                )
        
        return None
    
    def _try_numbered_pattern(self, query_lower: str) -> Optional[LocationResolution]:
        """Handle patterns like DEN1, SF1, NYC2, etc."""
        # Pattern: 2-4 letters + optional number
        match = re.match(r'^([a-z]{2,4})(\d*)$', query_lower)
        if not match:
            return None
        
        location_code, number = match.groups()
        
        # Find matching campus
        matching_campus = None
        for structure in self.campus_structures.values():
            campus_name = structure.campus.name.lower()
            
            # Check if location_code matches campus (USSFO → SF, SFO)
            if campus_name.startswith('us') and len(campus_name) == 5:
                campus_code = campus_name[2:]  # SFO from USSFO
                if (location_code == campus_code or 
                    location_code == campus_code[:2] or  # SF from SFO
                    campus_code.startswith(location_code)):
                    matching_campus = structure
                    break
            elif location_code in campus_name:
                matching_campus = structure
                break
        
        if not matching_campus:
            return None
        
        # Interpret the number based on campus structure
        if number:
            return self._interpret_numbered_location(matching_campus, int(number), query_lower)
        else:
            # No number - return whole campus
            return LocationResolution(
                query=query_lower,
                resolved_locations=[matching_campus.campus],
                resolution_type='campus',
                includes_hierarchy=True,
                aliases_used=[location_code]
            )
    
    def _interpret_numbered_location(self, campus_structure: CampusStructure, 
                                   number: int, original_query: str) -> LocationResolution:
        """Interpret numbered queries based on what actually exists in the campus."""
        
        # Priority 1: If campus has numbered buildings, number refers to building
        if campus_structure.has_numbered_buildings():
            for building in campus_structure.buildings:
                building_match = re.search(r'building\s+(\d+)', building.name.lower())
                if building_match and int(building_match.group(1)) == number:
                    return LocationResolution(
                        query=original_query,
                        resolved_locations=[building],
                        resolution_type='building',
                        includes_hierarchy=True,
                        aliases_used=[f"{campus_structure.campus.name.lower()}_building_{number}"]
                    )
        
        # Priority 2: If campus has numbered floors, number refers to floor
        if campus_structure.has_numbered_floors():
            for floor in campus_structure.floors:
                floor_match = re.search(r'floor\s+(\d+)', floor.name.lower())
                if floor_match and int(floor_match.group(1)) == number:
                    return LocationResolution(
                        query=original_query,
                        resolved_locations=[floor],
                        resolution_type='floor',
                        includes_hierarchy=False,
                        aliases_used=[f"{campus_structure.campus.name.lower()}_floor_{number}"]
                    )
        
        # Priority 3: Default to campus with clarification
        return LocationResolution(
            query=original_query,
            resolved_locations=[campus_structure.campus],
            resolution_type='campus_with_clarification',
            includes_hierarchy=True,
            aliases_used=[f"{campus_structure.campus.name.lower()}_unclear_{number}"]
        )
    
    def _fuzzy_match_all_locations(self, query_lower: str) -> List[Tuple[LocationInfo, float]]:
        """Fuzzy match against all locations with scoring."""
        matches = []
        
        for location in self.hierarchy.locations.values():
            score = self._calculate_fuzzy_score(query_lower, location)
            if score > 30:  # Minimum threshold
                matches.append((location, score))
        
        # Sort by score (highest first)
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _calculate_fuzzy_score(self, query_lower: str, location: LocationInfo) -> float:
        """Calculate fuzzy matching score for a location."""
        name_lower = location.name.lower()
        
        # Exact match
        if query_lower == name_lower:
            return 100
        
        # Campus code matching (USSFO → SF, SFO)
        if location.type == 'campus' and location.name.startswith('US') and len(location.name) == 5:
            campus_code = location.name[2:].lower()  # SFO from USSFO
            
            if query_lower == campus_code:
                return 95
            elif query_lower == campus_code[:2]:  # SF from SFO
                return 90
            elif query_lower in campus_code or campus_code.startswith(query_lower):
                return 85
        
        # Substring matching
        if query_lower in name_lower:
            return 80 - (len(name_lower) - len(query_lower)) * 2  # Prefer shorter matches
        
        if name_lower in query_lower:
            return 75
        
        # Word boundary matching
        words = name_lower.split()
        for word in words:
            if word.startswith(query_lower):
                return 70
            elif query_lower in word:
                return 60
        
        # Character overlap (very fuzzy)
        overlap = len(set(query_lower) & set(name_lower))
        if overlap >= 2:
            return min(50, overlap * 8)
        
        return 0
    
    def get_location_context(self, location: LocationInfo) -> Dict:
        """Get contextual information about a location."""
        if location.type == 'campus':
            structure = self.campus_structures.get(location.id)
            if structure:
                return {
                    'type': 'campus',
                    'buildings_count': len(structure.buildings),
                    'floors_count': len(structure.floors),
                    'has_numbered_buildings': structure.has_numbered_buildings(),
                    'has_numbered_floors': structure.has_numbered_floors(),
                    'structure_type': self._describe_structure(structure)
                }
        
        return {'type': location.type}
    
    def _describe_structure(self, structure: CampusStructure) -> str:
        """Describe the structure of a campus for user clarity."""
        if structure.has_numbered_buildings():
            return f"Has {len(structure.buildings)} buildings"
        elif structure.has_numbered_floors():
            return f"Has {len(structure.floors)} floors"
        elif structure.buildings and structure.floors:
            return f"Mixed: {len(structure.buildings)} buildings, {len(structure.floors)} floors"
        elif structure.buildings:
            return f"Building-based: {len(structure.buildings)} buildings"
        elif structure.floors:
            return f"Floor-based: {len(structure.floors)} floors"
        else:
            return "Simple campus"
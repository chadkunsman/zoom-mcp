# Zoom MCP Server Features

This document details the advanced features of the Zoom MCP server, including smart location resolution, fuzzy matching, and Denver-specific building aliases.

## Core Features Overview

### 1. Smart Location Resolution
- **Dynamic Discovery**: Automatically discovers all Zoom locations and builds hierarchical relationships
- **Fuzzy Matching**: Contextually-aware matching that understands location hierarchies  
- **Hybrid Approach**: Combines hardcoded mappings with dynamic fuzzy matching
- **User-Friendly Confirmations**: Clear messages explaining what was resolved

### 2. Bearer Token Management
- **Automatic Refresh**: 1-hour token expiration with 5-minute buffer
- **Multi-Level Caching**: Memory cache + file persistence
- **Retry Logic**: Automatic retry on 401 authentication failures

### 3. Hierarchical Location Discovery
- **Campus → Building → Floor**: Understands 3-level location hierarchy
- **Room Association Analysis**: Infers parent-child relationships from room data
- **Dynamic Alias Generation**: Creates aliases based on naming patterns

## Location Resolution Details

### Fuzzy Matching Algorithm

The `ZoomFuzzyMatcher` class provides contextually-aware location resolution:

```python
# Resolution priority order:
1. Denver hardcoded aliases (DEN1, DEN2) 
2. Numbered pattern matching (SF1, NYC2, etc.)
3. Direct fuzzy name matching
4. Campus code matching (USSFO → SF, SFO)
5. Substring matching with scoring
```

### Supported Query Patterns

| Query Pattern | Example | Resolution |
|---------------|---------|------------|
| Campus codes | `SF1`, `NYC`, `DEN` | Resolves to campus with buildings/floors |
| Building numbers | `Building 1`, `DEN1` | Specific building or hardcoded alias |
| Floor numbers | `Floor 1`, `3F` | All floors with that number |
| Fuzzy names | `Denver`, `Francisco` | Best matching location |

### Denver Building Aliases

Special hardcoded mappings for Denver due to room naming incompatibility:

```python
denver_building_mappings = {
    'den1': {
        'description': 'Denver Building 1',
        'floor_ids': ['xx14SBuZSuCRHd7jZBsmzw'],  # Floor 3
        'room_prefix': 'DEN-1-'  # Rooms: DEN-1-101, DEN-1-102, etc.
    },
    'den2': {
        'description': 'Denver Building 2', 
        'floor_ids': ['zh10l_aJT6CkImBHJn4skQ', '7EZDyz67TxC0Y-XMASub7g', 'bAwBNuv7SAii8pdGRX2a3w'],
        'room_prefix': 'DEN-2-'  # Rooms: DEN-2-201, DEN-2-202, etc.
    }
}
```

**Why Denver is Special:**
- Room names follow `DEN-1-*` and `DEN-2-*` patterns
- Zoom location hierarchy doesn't have "Building 1" and "Building 2" 
- Instead, DEN-1 rooms are on "Floor 3", DEN-2 rooms are on T3F3/T3F5/T3F6
- Hardcoded mappings bridge this gap for user-friendly queries

## API Integration Features

### Authenticated API Calls

All Zoom API interactions use the `zoom_api_get` helper:

```python
async def zoom_api_get(zoom_auth: ZoomAuth, endpoint: str, params: dict = None) -> dict:
    """Make authenticated GET request with automatic token refresh."""
    # Features:
    # - Automatic bearer token injection
    # - 401 retry with token refresh  
    # - Proper error handling
    # - aiohttp context management
```

### Location Hierarchy Discovery

The server dynamically builds location relationships:

```python
# Discovery process:
1. Fetch all locations from /rooms/locations API
2. Fetch sample rooms to understand usage patterns  
3. Analyze naming patterns to infer parent-child relationships
4. Build campus → building → floor hierarchy
5. Generate dynamic aliases based on patterns
6. Cache for 5 minutes to avoid repeated API calls
```

### Room Data Aggregation

When querying rooms by location, the server:

1. **Resolves Location**: Uses fuzzy matching to find target locations
2. **Expands Hierarchy**: Includes all child locations if hierarchical
3. **Fetches Rooms**: Makes parallel API calls for each location
4. **Aggregates Results**: Combines and enriches room data
5. **Generates Summary**: Provides confirmation and statistics

## User Experience Features

### Confirmation Messages

The server provides contextual confirmation messages:

```json
{
  "confirmation": "✅ Showing 'DEN1' rooms from Denver Building 1 (Floor 3) in USDEN site in Zoom",
  "rooms": [...],
  "total_count": 20,
  "query": "DEN1",
  "resolution": {
    "type": "denver_building",
    "aliases_used": ["denver_den1_hardcoded"]
  }
}
```

### Resolution Types

Different resolution types provide different confirmation messages:

- **`campus`**: Whole campus with all buildings/floors
- **`building`**: Specific building with all floors  
- **`floor`**: Specific floor only
- **`denver_building`**: Denver-specific hardcoded building
- **`multiple`**: Multiple matches found

### Location Context

Each room includes location context:

```json
{
  "id": "room123",
  "name": "DEN-1-101", 
  "status": "Available",
  "location_context": {
    "location_name": "Floor 3",
    "query_resolved_to": "denver_building"
  }
}
```

## Advanced Query Examples

### Campus-Level Queries
```bash
# Get all rooms in San Francisco
mcp call get_zoom_rooms --params '{"location_query":"SF1"}' python src/server.py

# Expected: All rooms across all SF buildings/floors
# Confirmation: "✅ Showing all 'SF1' rooms from USSFO campus in Zoom across 3 floors"
```

### Building-Level Queries
```bash  
# Get Denver Building 1 rooms
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' python src/server.py

# Expected: Only DEN-1-* rooms from Floor 3
# Confirmation: "✅ Showing 'DEN1' rooms from Denver Building 1 (Floor 3) in USDEN site in Zoom"
```

### Floor-Level Queries
```bash
# Get all Floor 1 rooms across all campuses
mcp call get_zoom_rooms --params '{"location_query":"Floor 1"}' python src/server.py

# Expected: All rooms from any location named "Floor 1"
# Confirmation: "✅ Showing 'Floor 1' rooms from Floor 1 in USSFO site in Zoom"
```

### Fuzzy Matching Examples
```bash
# Partial matches
mcp call get_zoom_rooms --params '{"location_query":"Denver"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"Francisco"}' python src/server.py

# Expected: Best matching location based on scoring algorithm
```

## Testing the Features

### Test Location Resolution
```bash
# Test all resolution types
mcp call resolve_location --params '{"location_query":"SF1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"DEN1"}' python src/server.py  
mcp call resolve_location --params '{"location_query":"Floor 1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"Building 2"}' python src/server.py
```

### Test Denver Aliases
```bash
# Verify Denver hardcoded mappings work
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' python src/server.py
# Should return ~20 rooms with DEN-1-* names

mcp call get_zoom_rooms --params '{"location_query":"DEN2"}' python src/server.py  
# Should return ~108 rooms with DEN-2-* names
```

### Test Fuzzy Matching
```bash
# Test various fuzzy patterns
mcp call resolve_location --params '{"location_query":"SF"}' python src/server.py
mcp call resolve_location --params '{"location_query":"NYC2"}' python src/server.py
mcp call resolve_location --params '{"location_query":"york"}' python src/server.py
```

## Implementation Architecture

### Module Responsibilities

- **`server.py`**: MCP tools and user interface
- **`zoom_auth.py`**: OAuth token lifecycle management
- **`zoom_hierarchy.py`**: Location discovery and relationship building  
- **`zoom_fuzzy.py`**: Smart resolution and Denver aliases
- **`settings.py`**: Environment configuration and basic auth

### Data Flow

```
User Query → Fuzzy Matcher → Location IDs → Room API Calls → Aggregated Results → Confirmation Message
     ↓              ↓              ↓              ↓                   ↓                ↓
   "DEN1"     Denver Alias    Floor IDs      Room Data         Enhanced Data    User Message
```

### Caching Strategy

- **Token Cache**: Memory + file, 1-hour expiration, 5-minute buffer
- **Hierarchy Cache**: Memory only, 5-minute expiration
- **Location Cache**: Built dynamically, expires with hierarchy

## Performance Characteristics

### API Call Optimization
- **Parallel Requests**: Multiple location queries run concurrently
- **Smart Caching**: Avoids repeated hierarchy discovery calls
- **Minimal Requests**: Only fetches rooms for resolved locations

### Response Times
- **First Call**: ~2-3 seconds (includes hierarchy discovery)
- **Cached Calls**: ~1-2 seconds (hierarchy cached)
- **Token Refresh**: Adds ~500ms when needed

### Memory Usage
- **Token Files**: ~1KB per account
- **Memory Cache**: ~50KB for typical hierarchy data
- **No Database**: Stateless design, no persistent storage

## Troubleshooting Features

### Debug Tools
```bash
# Test connection and auth
mcp call test_zoom_connection --params '{}' python src/server.py

# View all sites and hierarchy
mcp call get_zoom_sites --params '{}' python src/server.py

# Debug location resolution
mcp call resolve_location --params '{"location_query":"your_query"}' python src/server.py
```

### Common Issues
1. **"No location matches found"**: Query doesn't match any location names or aliases
2. **"Zoom configuration not initialized"**: Missing environment variables
3. **"Token request failed"**: Invalid Zoom credentials or insufficient scopes
4. **Empty results**: Query resolved but no rooms found in those locations

### Error Recovery
- **Token Expiration**: Automatic refresh and retry
- **API Failures**: Continue with other locations, partial results
- **Cache Corruption**: Graceful fallback, rebuild cache
- **Network Issues**: Clear error messages, retry suggestions

## Future Enhancement Ideas

### Potential Improvements
1. **Natural Language**: "Conference rooms in San Francisco"
2. **Capacity Filtering**: "Large rooms in Denver Building 1"  
3. **Availability Filtering**: "Available rooms right now"
4. **Room Booking**: Integration with Zoom scheduling
5. **Health Monitoring**: Alert on room issues
6. **Usage Analytics**: Track room utilization patterns

### Extensibility
The modular design allows easy addition of:
- New location resolution patterns
- Additional API endpoints
- Custom confirmation message formats
- Site-specific hardcoded mappings
- Performance monitoring and metrics
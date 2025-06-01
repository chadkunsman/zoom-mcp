# Zoom MCP Server Best Practices

This guide covers best practices specific to the Zoom MCP server implementation, including patterns for authentication, location resolution, and API integration.

## Zoom MCP Server Architecture

### Actual Project Structure

```
zoom_mcp/
├── src/
│   ├── server.py              # Main MCP tools (5 tools)
│   └── config/                # Configuration modules
│       ├── settings.py        # Environment & basic auth
│       ├── zoom_auth.py       # OAuth token management
│       ├── zoom_hierarchy.py  # Location discovery
│       └── zoom_fuzzy.py      # Smart location resolution
├── docs/                      # Comprehensive documentation
├── test_server.py             # Direct testing script
├── .env                       # Zoom credentials (not in git)
└── CLAUDE.md                  # AI assistant instructions
```

### Key Design Patterns

1. **Specialized Modules**: Each config module has a single responsibility
2. **Import Timing**: Configuration imported inside tool functions
3. **Caching Strategy**: File-based token persistence + memory cache
4. **Hybrid Resolution**: Hardcoded Denver aliases + dynamic fuzzy matching
5. **User-Friendly Output**: Confirmation messages explaining resolutions

## Configuration Best Practices

### Environment Configuration Pattern

```python
# src/config/settings.py - Simple approach for Zoom MCP
import os
import base64
from dotenv import load_dotenv

load_dotenv()

# Global variables (set by initialize_config)
ZOOM_ACCOUNT_ID = None
ZOOM_CLIENT_ID = None  
ZOOM_CLIENT_SECRET = None

def initialize_config():
    """Initialize configuration from environment variables."""
    global ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
    
    ZOOM_ACCOUNT_ID = os.getenv('ZOOM_ACCOUNT_ID')
    ZOOM_CLIENT_ID = os.getenv('ZOOM_CLIENT_ID')
    ZOOM_CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')
    
    if not all([ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET]):
        raise ValueError("Zoom credentials must be configured")

def get_auth_header():
    """Generate Basic Auth header for OAuth requests."""
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"
```

### **Critical Pattern**: Import Inside Functions

```python
# WRONG - imports at module level
from src.config.settings import ZOOM_ACCOUNT_ID  # Will be None!

@mcp.tool()
async def my_tool():
    # ZOOM_ACCOUNT_ID will be None here
    pass

# CORRECT - import inside function
@mcp.tool()
async def my_tool():
    from src.config.settings import ZOOM_ACCOUNT_ID  # Gets actual value
    # ZOOM_ACCOUNT_ID has correct value here
```

## Error Handling Best Practices

### Zoom-Specific Error Patterns

```python
@mcp.tool()
async def get_zoom_rooms(location_query: Optional[str] = None) -> Dict[str, Any]:
    """Get Zoom rooms with proper error handling."""
    try:
        # Import inside function to avoid timing issues
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        # Tool logic here...
        
    except ValueError as e:
        # Client-friendly error for validation issues
        raise ValueError(str(e))
    except Exception as e:
        # Generic error with context
        raise ToolError(f"Failed to get Zoom rooms: {str(e)}")
```

### Authentication Error Handling

```python
# src/config/zoom_auth.py
async def zoom_api_get(zoom_auth: ZoomAuth, endpoint: str, params: dict = None) -> dict:
    """API call with retry on auth failure."""
    token = await zoom_auth.get_valid_token()
    
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {token}'}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 401:
                # Clear cache and retry once
                zoom_auth.token_cache = None
                token = await zoom_auth.get_valid_token()
                headers['Authorization'] = f'Bearer {token}'
                # Retry logic...
            elif response.status != 200:
                error_text = await response.text()
                raise Exception(f"API call failed: {response.status} - {error_text}")
            
            return await response.json()
```

## Token Management Best Practices

### Caching Strategy

```python
# Multi-level caching approach
class ZoomAuth:
    def __init__(self, account_id: str, auth_header: str):
        self.token_cache = None      # Memory cache
        self.token_file = f"zoom_token_{account_id}.json"  # File cache
        
    async def get_valid_token(self) -> str:
        # 1. Check memory cache first (fastest)
        if self.token_cache and not self._is_token_expired(self.token_cache):
            return self.token_cache['access_token']
            
        # 2. Check file cache (persistent across restarts)
        cached_token = self._load_cached_token()
        if cached_token and not self._is_token_expired(cached_token):
            self.token_cache = cached_token
            return cached_token['access_token']
        
        # 3. Request new token (slowest)
        new_token = await self._request_new_token()
        self._save_token_to_file(new_token)
        self.token_cache = new_token
        return new_token['access_token']
    
    def _is_token_expired(self, token_data: dict) -> bool:
        """5-minute buffer before expiration."""
        if not token_data or 'expires_at' not in token_data:
            return True
        return time.time() >= (token_data['expires_at'] - 300)
```

### File Safety Pattern

```python
def _save_token_to_file(self, token_data: dict):
    """Save token with error handling."""
    try:
        with open(self.token_file, 'w') as f:
            json.dump(token_data, f)
    except Exception:
        # Continue without file caching if write fails
        # Don't break the application for cache issues
        pass

def _load_cached_token(self) -> Optional[dict]:
    """Load token with error handling."""
    try:
        with open(self.token_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # File doesn't exist or is corrupted - not an error
        return None
```

## Location Resolution Best Practices

### Hybrid Approach Pattern

```python
# Combine hardcoded mappings with dynamic fuzzy matching
class ZoomFuzzyMatcher:
    def _try_denver_aliases(self, query_lower: str) -> Optional[LocationResolution]:
        """Handle Denver-specific hardcoded aliases."""
        denver_building_mappings = {
            'den1': {
                'description': 'Denver Building 1',
                'floor_ids': ['xx14SBuZSuCRHd7jZBsmzw'],  # Floor 3
                'room_prefix': 'DEN-1-'
            },
            'den2': {
                'description': 'Denver Building 2', 
                'floor_ids': ['zh10l_aJT6CkImBHJn4skQ', '7EZDyz67TxC0Y-XMASub7g', 'bAwBNuv7SAii8pdGRX2a3w'],
                'room_prefix': 'DEN-2-'
            }
        }
        
        if query_lower in denver_building_mappings:
            # Return hardcoded mapping
            return self._build_denver_resolution(query_lower, denver_building_mappings[query_lower])
        
        return None
    
    async def fuzzy_resolve_location(self, query: str) -> LocationResolution:
        """Try Denver aliases first, then fall back to fuzzy matching."""
        query_lower = query.lower().strip()
        
        # Check Denver hardcoded aliases first
        denver_match = self._try_denver_aliases(query_lower)
        if denver_match:
            return denver_match
        
        # Fall back to dynamic fuzzy matching for other sites
        return self._dynamic_fuzzy_match(query_lower)
```

### User-Friendly Confirmation Messages

```python
def _generate_confirmation_message(location_query: str, resolution, location_summary: dict) -> str:
    """Generate contextual confirmation messages."""
    
    if resolution.resolution_type == 'denver_building':
        building_name = "Denver Building 1" if 'den1' in resolution.aliases_used[0] else "Denver Building 2"
        floor_names = [loc.name for loc in resolution.resolved_locations]
        
        if len(floor_names) == 1:
            return f"✅ Showing '{location_query}' rooms from {building_name} ({floor_names[0]}) in USDEN site in Zoom"
        else:
            floors_text = f"{len(floor_names)} floors ({', '.join(floor_names)})"
            return f"✅ Showing '{location_query}' rooms from {building_name} across {floors_text} in USDEN site in Zoom"
    
    elif resolution.resolution_type == 'campus':
        resolved_location = resolution.resolved_locations[0]
        campus_name = resolved_location.name
        return f"✅ Showing all '{location_query}' rooms from {campus_name} campus in Zoom"
    
    # ... other resolution types
```

## API Integration Best Practices

### Async HTTP Patterns

```python
# Use context managers for proper resource cleanup
async def zoom_api_get(zoom_auth: ZoomAuth, endpoint: str, params: dict = None) -> dict:
    """Make authenticated API call with proper resource management."""
    token = await zoom_auth.get_valid_token()
    url = f"https://api.zoom.us/v2/{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            else:
                # Handle errors appropriately
                error_text = await response.text()
                raise Exception(f"API call failed: {response.status} - {error_text}")
```

### Rate Limiting Consideration

```python
# Add delays between requests if needed
async def get_all_rooms_for_locations(location_ids: List[str]) -> List[dict]:
    """Get rooms for multiple locations with rate limiting."""
    all_rooms = []
    
    for i, location_id in enumerate(location_ids):
        try:
            response = await zoom_api_get(zoom_auth, 'rooms', {
                'page_size': '100',
                'location_id': location_id
            })
            all_rooms.extend(response.get('rooms', []))
            
            # Add small delay between requests to be API-friendly
            if i < len(location_ids) - 1:
                await asyncio.sleep(0.1)
                
        except Exception:
            # Continue with other locations if one fails
            continue
    
    return all_rooms
```

## Security Best Practices

### Credential Management

```python
# .env file (never commit to git)
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here

# .gitignore
.env
zoom_token_*.json
*.log
```

### Error Message Security

```python
# Don't expose sensitive information in error messages
try:
    result = await some_api_call()
except Exception as e:
    # Log detailed error for debugging
    logger.error(f"API call failed: {str(e)}", exc_info=True)
    
    # Return generic error to client
    raise ToolError("Service temporarily unavailable")
```

## Testing Best Practices

### Use MCPTools for Development Testing

```bash
# Test all tools work
mcp tools python src/server.py

# Test specific functionality
mcp call test_zoom_connection --params '{}' python src/server.py
mcp call resolve_location --params '{"location_query":"DEN1"}' python src/server.py

# Interactive testing
mcp shell python src/server.py
```

### Direct Script Testing

```python
# test_server.py - For automated testing
async def main():
    """Test key functionality."""
    try:
        initialize_config()
        
        # Test auth
        result = await test_zoom_connection()
        assert result['status'] == 'success'
        
        # Test core functionality
        sites = await get_zoom_sites()
        assert sites['total_count'] > 0
        
        rooms = await get_zoom_rooms("DEN1")
        assert rooms['total_count'] > 0
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0
```

## Performance Best Practices

### Caching Strategy

- **Hierarchy Cache**: 5-minute cache for location discovery
- **Token Cache**: Memory + file persistence with 5-minute expiration buffer
- **Avoid Repeated API Calls**: Cache responses when appropriate

### Concurrent Operations

```python
# Process multiple locations concurrently when safe
async def get_rooms_for_multiple_locations(location_ids: List[str]) -> List[dict]:
    """Get rooms for multiple locations concurrently."""
    tasks = []
    for location_id in location_ids:
        task = zoom_api_get(zoom_auth, 'rooms', {
            'page_size': '100',
            'location_id': location_id
        })
        tasks.append(task)
    
    # Execute concurrently
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    all_rooms = []
    for response in responses:
        if isinstance(response, Exception):
            continue  # Skip failed requests
        all_rooms.extend(response.get('rooms', []))
    
    return all_rooms
```

## Common Pitfalls to Avoid

### 1. Import Timing Issues
- ❌ Never import config modules at module level
- ✅ Always import inside tool functions

### 2. Token Management
- ❌ Don't ignore token expiration
- ✅ Use 5-minute buffer and automatic refresh

### 3. Error Handling
- ❌ Don't expose sensitive information in errors
- ✅ Use generic client errors, detailed server logs

### 4. Location Resolution
- ❌ Don't assume all sites follow same patterns
- ✅ Use hybrid approach (hardcoded + fuzzy)

### 5. API Integration
- ❌ Don't ignore rate limits
- ✅ Add appropriate delays and error handling

## Next Steps

- **Testing**: See [testing.md](testing.md) for comprehensive testing strategies
- **Authentication**: Review [authentication.md](authentication.md) for OAuth implementation details
- **Deployment**: Check [deployment.md](deployment.md) for production considerations
# Zoom MCP Server Quick Start Guide

This guide will get you up and running with the Zoom MCP server that monitors room status across sites.

## Prerequisites

- Python 3.11+
- UV package manager
- Zoom Pro/Business account with API access
- Zoom Server-to-Server OAuth app credentials

## Installation

```bash
# Clone or navigate to the zoom_mcp directory
cd zoom_mcp

# Install dependencies
uv pip install -e .

# Install MCPTools for testing
brew tap f/mcptools && brew install mcp
```

## Zoom API Configuration

1. Create a Server-to-Server OAuth app in the [Zoom Marketplace](https://marketplace.zoom.us/)
2. Get your credentials: Account ID, Client ID, Client Secret
3. Add the following scopes: `room:read:admin`

Create `.env` file:

```bash
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here
```

## Basic Server Overview

The server provides these tools:

```python
# Main MCP server with 5 tools
mcp = FastMCP("Zoom MCP Server")

@mcp.tool()
async def test_zoom_connection() -> Dict[str, Any]:
    """Test connection to Zoom API and validate authentication."""

@mcp.tool()
async def get_zoom_sites() -> Dict[str, Any]:
    """Get all Zoom sites/locations with hierarchy and aliases."""

@mcp.tool()
async def get_zoom_rooms(location_query: Optional[str] = None) -> Dict[str, Any]:
    """Get Zoom rooms with smart location resolution (e.g., 'SF1', 'DEN1', 'Floor 1')."""

@mcp.tool()
async def get_room_details(room_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific Zoom room."""

@mcp.tool()
async def resolve_location(location_query: str) -> Dict[str, Any]:
    """Test location resolution - see how queries get resolved."""
```

## Test Your Server

```bash
# List all available tools
mcp tools python src/server.py

# Test Zoom connection
mcp call test_zoom_connection --params '{}' python src/server.py

# Get all sites with hierarchy
mcp call get_zoom_sites --params '{}' python src/server.py

# Get all rooms
mcp call get_zoom_rooms --params '{}' python src/server.py

# Get rooms for a specific location (smart resolution)
mcp call get_zoom_rooms --params '{"location_query":"SF1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"Floor 1"}' python src/server.py

# Test location resolution
mcp call resolve_location --params '{"location_query":"SF1"}' python src/server.py

# Interactive testing
mcp shell python src/server.py
```

## Smart Location Resolution

The server includes sophisticated fuzzy matching for location queries:

```python
# Examples of supported location queries:
"SF1"        # San Francisco campus (USSFO)
"DEN1"       # Denver Building 1 (hardcoded for room naming compatibility)
"DEN2"       # Denver Building 2 (hardcoded for room naming compatibility)
"Floor 1"    # All Floor 1s across campuses
"NYC"        # New York campus
"Building 2" # All Building 2s
```

### Denver Special Case

Denver has hardcoded building aliases due to room naming patterns:
- **DEN1**: Maps to Floor 3 (where DEN-1-* rooms are located)
- **DEN2**: Maps to T3F3, T3F5, T3F6 floors (where DEN-2-* rooms are located)
- Other sites use purely dynamic fuzzy matching

## Zoom API Integration

The server handles OAuth 2.0 bearer token authentication automatically:

```python
# Token caching with 1-hour expiration and 5-minute buffer
class ZoomAuth:
    async def get_valid_token(self) -> str:
        """Get valid bearer token, refreshing if needed."""
        # Cached token with automatic refresh
        
# All API calls use authenticated requests
async def zoom_api_get(zoom_auth: ZoomAuth, endpoint: str, 
                      params: dict = None) -> dict:
    """Make authenticated GET request to Zoom API."""
    # Handles token refresh, rate limiting, error handling
```

## Error Handling

```python
from fastmcp.exceptions import ToolError

@mcp.tool()
async def get_zoom_rooms(location_query: Optional[str] = None) -> Dict[str, Any]:
    """Get Zoom rooms with error handling."""
    try:
        # Import inside function to avoid timing issues
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        # Tool logic with proper error handling
        
    except Exception as e:
        raise ToolError(f"Failed to get Zoom rooms: {str(e)}")
```

## Architecture Components

The server is organized into specialized modules:

```python
# Core components:
src/config/settings.py      # Environment configuration
src/config/zoom_auth.py     # OAuth token management
src/config/zoom_hierarchy.py # Location discovery & relationships
src/config/zoom_fuzzy.py    # Smart location resolution
src/server.py              # Main MCP server with tools

# Key patterns:
- Configuration imported inside tool functions (timing)
- Bearer token caching with automatic refresh
- Hierarchical location discovery from API
- Contextually-aware fuzzy matching
- User-friendly confirmation messages
```

## Next Steps

- **Authentication**: See [authentication.md](authentication.md) for Zoom OAuth implementation
- **Testing**: Review [testing.md](testing.md) for MCPTools usage and examples
- **Best Practices**: Read [best-practices.md](best-practices.md) for Zoom-specific patterns
- **Deployment**: Check [deployment.md](deployment.md) for production deployment
- **MCPTools**: See [mcptools.md](mcptools.md) for detailed testing guide

## Project Structure

```
zoom_mcp/
├── src/
│   ├── server.py          # Main MCP server with 5 tools
│   └── config/            # Configuration modules
│       ├── settings.py    # Environment & basic auth
│       ├── zoom_auth.py   # OAuth token management
│       ├── zoom_hierarchy.py # Location discovery
│       └── zoom_fuzzy.py  # Smart location resolution
├── docs/                  # Comprehensive documentation
│   ├── quickstart.md
│   ├── authentication.md
│   ├── testing.md
│   ├── mcptools.md
│   └── ...
├── test_server.py         # Direct testing script
├── pyproject.toml         # UV dependencies
├── .env                   # Zoom credentials
└── CLAUDE.md             # AI assistant instructions
```

## Configuration Pattern

**Important**: Import configuration modules inside tool functions to avoid timing issues:

```python
# WRONG - imports at module level before config is initialized
from src.config.settings import ZOOM_ACCOUNT_ID

@mcp.tool()
async def my_tool():
    # ZOOM_ACCOUNT_ID will be None here
    pass

# CORRECT - import inside function after config is set
@mcp.tool()
async def my_tool():
    from src.config.settings import ZOOM_ACCOUNT_ID  # Gets current value
    # ZOOM_ACCOUNT_ID has correct value here
```

## Example Tool Responses

```json
// get_zoom_rooms with location query
{
  "confirmation": "✅ Showing 'DEN1' rooms from Denver Building 1 (Floor 3) in USDEN site in Zoom",
  "rooms": [...],
  "total_count": 20,
  "query": "DEN1",
  "resolution": {
    "type": "denver_building",
    "locations_found": 1,
    "aliases_used": ["denver_den1_hardcoded"]
  }
}
```
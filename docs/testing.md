# Zoom MCP Server Testing Guide

This guide covers testing strategies for the Zoom MCP server, focusing on MCPTools usage and practical testing approaches.

## Testing Overview

### Test Types for Zoom MCP Server

1. **MCPTools Testing**: Primary method for testing tools interactively
2. **Direct Script Testing**: Using test_server.py for automated testing
3. **Authentication Testing**: Zoom OAuth token validation
4. **Location Resolution Testing**: Fuzzy matching and Denver aliases
5. **API Integration Testing**: Real Zoom API calls

## MCPTools Testing (Primary Method)

### Installation

```bash
# macOS (Homebrew)
brew tap f/mcptools
brew install mcp
```

### Basic Testing Commands

```bash
# List all Zoom MCP tools
mcp tools python src/server.py

# Test Zoom connection
mcp call test_zoom_connection --params '{}' python src/server.py

# Get all sites with hierarchy
mcp call get_zoom_sites --params '{}' python src/server.py

# Get all rooms
mcp call get_zoom_rooms --params '{}' python src/server.py

# Test location resolution
mcp call get_zoom_rooms --params '{"location_query":"SF1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"Floor 1"}' python src/server.py

# Test location resolution details
mcp call resolve_location --params '{"location_query":"DEN2"}' python src/server.py

# Get room details
mcp call get_room_details --params '{"room_id":"your_room_id_here"}' python src/server.py

# Interactive testing shell
mcp shell python src/server.py

# View server logs during testing
mcp tools --server-logs python src/server.py
```

### Advanced Testing

```bash
# Test Denver building aliases specifically
mcp call resolve_location --params '{"location_query":"DEN1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"DEN2"}' python src/server.py

# Test fuzzy matching for other sites
mcp call resolve_location --params '{"location_query":"SF1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"NYC"}' python src/server.py

# Save test results
mcp tools python src/server.py > zoom_tools_output.json
```

### Interactive Shell Testing

```bash
# Start interactive shell
mcp shell python src/server.py

# Inside the shell:
mcp > tools                                    # List available tools
mcp > call test_zoom_connection                # Test connection
mcp > call get_zoom_sites                      # Get sites
mcp > call get_zoom_rooms {"location_query":"SF1"}  # Get SF1 rooms
mcp > call resolve_location {"location_query":"DEN1"}  # Test resolution
mcp > help                                     # Show help
mcp > exit                                     # Exit shell
```

## Direct Script Testing

The project includes `test_server.py` for automated testing:

```python
# test_server.py - Direct testing script
import asyncio
from src.config.settings import initialize_config
from src.server import test_zoom_connection, get_zoom_sites, get_zoom_rooms

async def main():
    """Test the Zoom MCP server functionality."""
    try:
        # Initialize configuration
        initialize_config()
        
        # Test connection
        connection_result = await test_zoom_connection()
        print(f"✓ Connection test: {connection_result}")
        
        # Test getting sites
        sites_result = await get_zoom_sites()
        print(f"✓ Found {sites_result['total_count']} sites")
        
        # Test getting rooms
        rooms_result = await get_zoom_rooms()
        print(f"✓ Found {rooms_result['total_count']} rooms")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
```

Run with: `python test_server.py`

## Authentication Testing

### Test Zoom Connection

```bash
# Test authentication works
mcp call test_zoom_connection --params '{}' python src/server.py

# Expected successful response:
{
  "status": "success",
  "account_id": "your_account_id",
  "client_id": "your_client_id",
  "token_cached": true,
  "message": "Successfully authenticated with Zoom API"
}
```

### Debug Authentication Issues

```python
# Check environment variables
from src.config.settings import ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
print(f"Account ID: {'✓' if ZOOM_ACCOUNT_ID else '✗'}")
print(f"Client ID: {'✓' if ZOOM_CLIENT_ID else '✗'}")
print(f"Client Secret: {'✓' if ZOOM_CLIENT_SECRET else '✗'}")

# Check token file
import json, time
try:
    with open('zoom_token_your_account_id.json', 'r') as f:
        token_data = json.load(f)
        print(f"Token expires at: {token_data.get('expires_at')}")
        print(f"Token expired: {time.time() >= token_data.get('expires_at', 0)}")
except FileNotFoundError:
    print("No cached token file found")
```

## Location Resolution Testing

### Test Fuzzy Matching

```bash
# Test various location queries
mcp call resolve_location --params '{"location_query":"SF1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"Floor 1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"Denver"}' python src/server.py

# Test Denver hardcoded aliases
mcp call resolve_location --params '{"location_query":"DEN1"}' python src/server.py
mcp call resolve_location --params '{"location_query":"DEN2"}' python src/server.py
```

### Expected Denver Resolution Response

```json
{
  "confirmation": "✅ Showing 'DEN1' rooms from Denver Building 1 (Floor 3) in USDEN site in Zoom",
  "query": "DEN1",
  "resolution_type": "denver_building",
  "resolved_locations": [
    {
      "id": "xx14SBuZSuCRHd7jZBsmzw",
      "name": "Floor 3",
      "type": "floor"
    }
  ],
  "aliases_used": ["denver_den1_hardcoded"]
}
```

## Room Data Testing

### Test Room Queries

```bash
# Get all rooms
mcp call get_zoom_rooms --params '{}' python src/server.py

# Get rooms by location
mcp call get_zoom_rooms --params '{"location_query":"SF1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' python src/server.py
mcp call get_zoom_rooms --params '{"location_query":"DEN2"}' python src/server.py

# Test room details (replace with actual room ID)
mcp call get_room_details --params '{"room_id":"actual_room_id_here"}' python src/server.py
```

### Expected Room Response Format

```json
{
  "confirmation": "✅ Showing 'DEN1' rooms from Denver Building 1 (Floor 3) in USDEN site in Zoom",
  "rooms": [
    {
      "id": "room_id",
      "name": "DEN-1-101",
      "room_type": "ZoomRoom",
      "status": "Available",
      "capacity": 8,
      "health": "Good"
    }
  ],
  "total_count": 20,
  "query": "DEN1",
  "resolution": {
    "type": "denver_building",
    "aliases_used": ["denver_den1_hardcoded"]
  }
}
```

## Troubleshooting Testing Issues

### Common Problems

1. **"Zoom credentials not configured"**
   - Check `.env` file exists with correct variables
   - Verify `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`

2. **"Token request failed: 401"**
   - Verify Zoom app credentials are correct
   - Check app has `room:read:admin` scope
   - Ensure Server-to-Server OAuth app type

3. **"No location matches found"**
   - Check location query spelling
   - Try `get_zoom_sites` to see available locations
   - Test with `resolve_location` to debug fuzzy matching

4. **Import timing issues**
   - Configuration modules imported inside tool functions
   - Never import config at module level before `initialize_config()`

### Debug Commands

```bash
# Test all tools work
mcp tools python src/server.py

# Test connection specifically
mcp call test_zoom_connection --params '{}' python src/server.py

# List all sites to see hierarchy
mcp call get_zoom_sites --params '{}' python src/server.py

# Test location resolution
mcp call resolve_location --params '{"location_query":"your_query"}' python src/server.py
```

## Test Environment Setup

### Environment Variables

```bash
# Required for testing
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here
```

### Dependencies

```bash
# Install testing dependencies
uv add pytest pytest-asyncio

# Install MCPTools
brew tap f/mcptools && brew install mcp
```

## Testing Checklist

### Before Testing

- [ ] `.env` file configured with Zoom credentials
- [ ] MCPTools installed (`brew install mcp`)
- [ ] Dependencies installed (`uv pip install -e .`)
- [ ] Network access to Zoom API

### Core Functionality Tests

- [ ] `mcp tools python src/server.py` - Lists 5 tools
- [ ] `test_zoom_connection` - Returns success with token_cached: true
- [ ] `get_zoom_sites` - Returns sites with hierarchy
- [ ] `get_zoom_rooms` - Returns rooms list
- [ ] `get_zoom_rooms` with location query - Returns filtered rooms
- [ ] `resolve_location` - Returns proper resolution details

### Location Resolution Tests

- [ ] `SF1` resolves to San Francisco campus
- [ ] `DEN1` resolves to Denver Building 1 (Floor 3)
- [ ] `DEN2` resolves to Denver Building 2 (T3F3, T3F5, T3F6)
- [ ] `Floor 1` resolves to all Floor 1 locations
- [ ] Invalid queries return proper error messages

### Authentication Tests

- [ ] Valid credentials return success
- [ ] Invalid credentials return proper error
- [ ] Token caching works (check token file created)
- [ ] Token refresh works on expiration

## Next Steps

- **Best Practices**: See [best-practices.md](best-practices.md) for Zoom-specific testing patterns
- **Authentication**: Review [authentication.md](authentication.md) for auth testing details
- **MCPTools**: Check [mcptools.md](mcptools.md) for comprehensive MCPTools usage







# Zoom Authentication Guide

This guide covers the Zoom OAuth 2.0 Server-to-Server authentication implementation used in the Zoom MCP server.

## Zoom OAuth 2.0 Server-to-Server Authentication

The Zoom MCP server uses OAuth 2.0 Server-to-Server authentication for secure API access.

### 1. Zoom App Setup

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Create a "Server-to-Server OAuth" application
3. Get your credentials:
   - **Account ID**: Your Zoom account identifier
   - **Client ID**: OAuth client identifier
   - **Client Secret**: OAuth client secret
4. Add required scopes: `room:read:admin`

### 2. Environment Configuration

Create `.env` file with your Zoom credentials:

```bash
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here
```

### 3. Authentication Implementation

The authentication is handled by dedicated modules:

```python
# src/config/settings.py - Basic Auth header generation
import base64
import os
from dotenv import load_dotenv

load_dotenv()

ZOOM_ACCOUNT_ID = os.getenv('ZOOM_ACCOUNT_ID')
ZOOM_CLIENT_ID = os.getenv('ZOOM_CLIENT_ID')
ZOOM_CLIENT_SECRET = os.getenv('ZOOM_CLIENT_SECRET')

def get_auth_header():
    """Generate Basic Auth header for OAuth token requests."""
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"
```

### 4. Token Management with Caching

The `ZoomAuth` class handles token lifecycle with file-based caching:

```python
# src/config/zoom_auth.py - Token management
import json
import time
import aiohttp
from typing import Optional

class ZoomAuth:
    def __init__(self, account_id: str, auth_header: str):
        self.account_id = account_id
        self.auth_header = auth_header
        self.token_file = f"zoom_token_{account_id}.json"
        self.token_cache = None
        
    async def get_valid_token(self) -> str:
        """Get valid bearer token, refreshing if needed."""
        # Check cache first
        if self.token_cache and not self._is_token_expired(self.token_cache):
            return self.token_cache['access_token']
            
        # Try loading from file
        cached_token = self._load_cached_token()
        if cached_token and not self._is_token_expired(cached_token):
            self.token_cache = cached_token
            return cached_token['access_token']
        
        # Request new token
        new_token = await self._request_new_token()
        self._save_token_to_file(new_token)
        self.token_cache = new_token
        return new_token['access_token']
    
    def _is_token_expired(self, token_data: dict) -> bool:
        """Check if token is expired (with 5-minute buffer)."""
        if not token_data or 'expires_at' not in token_data:
            return True
        return time.time() >= (token_data['expires_at'] - 300)  # 5 min buffer
    
    async def _request_new_token(self) -> dict:
        """Request new access token from Zoom."""
        url = "https://zoom.us/oauth/token"
        data = {
            'grant_type': 'account_credentials',
            'account_id': self.account_id
        }
        headers = {
            'Authorization': self.auth_header,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    token_data = await response.json()
                    # Add expiration timestamp
                    token_data['expires_at'] = time.time() + token_data.get('expires_in', 3600)
                    return token_data
                else:
                    error_text = await response.text()
                    raise Exception(f"Token request failed: {response.status} - {error_text}")
```

### 5. Authenticated API Calls

All Zoom API calls use the cached bearer token:

```python
# src/config/zoom_auth.py - API helper function
async def zoom_api_get(zoom_auth: ZoomAuth, endpoint: str, params: dict = None) -> dict:
    """Make authenticated GET request to Zoom API."""
    token = await zoom_auth.get_valid_token()
    
    url = f"https://api.zoom.us/v2/{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 401:
                # Token might be expired, force refresh and retry once
                zoom_auth.token_cache = None
                token = await zoom_auth.get_valid_token()
                headers['Authorization'] = f'Bearer {token}'
                
                async with session.get(url, headers=headers, params=params) as retry_response:
                    if retry_response.status == 200:
                        return await retry_response.json()
                    else:
                        error_text = await retry_response.text()
                        raise Exception(f"API call failed after retry: {retry_response.status} - {error_text}")
            else:
                error_text = await response.text()
                raise Exception(f"API call failed: {response.status} - {error_text}")
```

### 6. Usage in MCP Tools

Tools import authentication modules inside functions to avoid timing issues:

```python
# src/server.py - MCP tool implementation
@mcp.tool()
async def get_zoom_rooms(location_query: Optional[str] = None) -> Dict[str, Any]:
    """Get Zoom rooms with smart location resolution."""
    try:
        # Import inside function to avoid timing issues
        from src.config.settings import ZOOM_ACCOUNT_ID, get_auth_header
        from src.config.zoom_auth import ZoomAuth, zoom_api_get
        
        if not ZOOM_ACCOUNT_ID:
            raise ToolError("Zoom configuration not initialized")
            
        # Create auth instance
        zoom_auth = ZoomAuth(ZOOM_ACCOUNT_ID, get_auth_header())
        
        # Make authenticated API call
        response = await zoom_api_get(zoom_auth, 'rooms', {'page_size': '100'})
        
        # Process response
        rooms = []
        for room in response.get('rooms', []):
            rooms.append({
                'id': room['id'],
                'name': room['name'],
                'status': room.get('status', ''),
                'health': room.get('health', ''),
                # ... other room data
            })
            
        return {
            'rooms': rooms,
            'total_count': len(rooms)
        }
        
    except Exception as e:
        raise ToolError(f"Failed to get Zoom rooms: {str(e)}")
```

## Token Lifecycle Management

### Token Caching Strategy

1. **Memory Cache**: Fast access for current session
2. **File Cache**: Persistent storage across server restarts
3. **Automatic Refresh**: 5-minute buffer before expiration
4. **Retry Logic**: Automatic retry on 401 responses

```python
# Token lifecycle flow:
1. Check memory cache → valid? return token
2. Check file cache → valid? load to memory, return token  
3. Request new token → save to file, cache in memory, return token
4. On API 401 → clear cache, refresh token, retry request
```

### File-Based Token Storage

```python
def _save_token_to_file(self, token_data: dict):
    """Save token to file for persistence."""
    try:
        with open(self.token_file, 'w') as f:
            json.dump(token_data, f)
    except Exception:
        # Continue without file caching if write fails
        pass

def _load_cached_token(self) -> Optional[dict]:
    """Load token from file if available."""
    try:
        with open(self.token_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
```

## Error Handling and Security

### Authentication Error Handling

```python
@mcp.tool()
async def test_zoom_connection() -> Dict[str, Any]:
    """Test Zoom API connection and authentication."""
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
```

### Security Considerations

1. **Credentials**: Never commit secrets to git - use `.env` files
2. **Token Storage**: File permissions should restrict access to tokens
3. **Error Messages**: Don't expose sensitive information in error messages
4. **Scopes**: Request minimal required scopes (`room:read:admin`)
5. **HTTPS**: Always use HTTPS in production

## Testing Authentication

### Manual Testing

```bash
# Test connection to Zoom API
mcp call test_zoom_connection --params '{}' python src/server.py

# Expected successful response:
{
  "status": "success",
  "account_id": "your_account_id",
  "client_id": "your_client_id", 
  "token_cached": true,
  "message": "Successfully authenticated with Zoom API"
}

# Test API calls
mcp call get_zoom_sites --params '{}' python src/server.py
```

### Direct Testing Script

```python
# test_server.py - Direct authentication testing
import asyncio
from src.config.settings import initialize_config
from src.server import test_zoom_connection

async def main():
    initialize_config()
    result = await test_zoom_connection()
    print(f"Auth test result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Troubleshooting Authentication Issues

### Common Problems

1. **"Zoom credentials not configured"**
   - Check `.env` file exists and has correct variable names
   - Verify environment variables are loaded properly

2. **"Token request failed: 401"**
   - Verify Client ID and Client Secret are correct
   - Check Account ID matches your Zoom account
   - Ensure app has `room:read:admin` scope

3. **"API call failed: 401"** 
   - Token may have expired - automatic retry should handle this
   - Check if token file is corrupted (delete to force refresh)

4. **Import timing issues**
   - Always import config modules inside tool functions
   - Never import at module level before `initialize_config()`

### Debug Token Issues

```python
# Check token file contents
import json
try:
    with open('zoom_token_your_account_id.json', 'r') as f:
        token_data = json.load(f)
        print(f"Token expires at: {token_data.get('expires_at')}")
        print(f"Current time: {time.time()}")
        print(f"Token expired: {time.time() >= token_data.get('expires_at', 0)}")
except FileNotFoundError:
    print("No cached token file found")
```

### Configuration Verification

```python
# Verify environment setup
from src.config.settings import ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET

print(f"Account ID: {'✓' if ZOOM_ACCOUNT_ID else '✗'}")
print(f"Client ID: {'✓' if ZOOM_CLIENT_ID else '✗'}")
print(f"Client Secret: {'✓' if ZOOM_CLIENT_SECRET else '✗'}")
```

## Environment Variables Reference

```bash
# Required Zoom OAuth credentials
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here  
ZOOM_CLIENT_SECRET=your_client_secret_here

# Optional: Custom token cache location
# TOKEN_CACHE_DIR=/custom/path/to/tokens
```

## Key Implementation Files

- **`src/config/settings.py`**: Environment variable loading and basic auth header generation
- **`src/config/zoom_auth.py`**: Token management, caching, and API call wrapper
- **`src/server.py`**: MCP tools using authentication (import config inside functions)
- **`.env`**: Zoom OAuth credentials (never commit to git)
- **`zoom_token_*.json`**: Cached token files (auto-generated, can be deleted to force refresh)

## Next Steps

- **Testing**: Check [testing.md](testing.md) for comprehensive testing with MCPTools
- **Best Practices**: Review [best-practices.md](best-practices.md) for Zoom-specific patterns
- **Deployment**: See [deployment.md](deployment.md) for production deployment considerations
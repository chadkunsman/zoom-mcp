# Zoom MCP Server

A FastMCP Model Context Protocol server that provides intelligent monitoring and management of Zoom rooms across multiple sites with smart location resolution.

## 🚀 Features

- **5 Powerful Tools** for comprehensive Zoom room management
- **Smart Location Resolution** with fuzzy matching (e.g., "SF1", "DEN1", "Floor 3")
- **Denver Building Aliases** - Special hardcoded mappings for room naming compatibility
- **Efficient API Usage** - Single call for company-wide queries vs. multiple location-specific calls
- **OAuth 2.0 Authentication** with automatic token refresh and file-based caching
- **Hierarchical Location Discovery** - Understands campus → building → floor relationships
- **User-Friendly Confirmations** - Clear messages explaining what was resolved

## 🛠️ Tools Available

### `test_zoom_connection`
Test Zoom API authentication and connection status.
```bash
# Usage: Verify credentials are working
mcp call test_zoom_connection --params '{}' uv run src/server.py
```

### `get_zoom_sites` 
Get all Zoom locations with hierarchy and aliases.
```bash
# Usage: Understand available locations and relationships
mcp call get_zoom_sites --params '{}' uv run src/server.py
```

### `get_zoom_rooms`
Get Zoom rooms with optional smart location filtering.

**⚡ IMPORTANT**: For maximum efficiency with company-wide queries (e.g., "find offline rooms anywhere"), omit `location_query` to make a single API call.

```bash
# Company-wide (EFFICIENT - single API call)
mcp call get_zoom_rooms --params '{}' uv run src/server.py

# Location-specific (multiple API calls)
mcp call get_zoom_rooms --params '{"location_query":"SF1"}' uv run src/server.py
mcp call get_zoom_rooms --params '{"location_query":"DEN1"}' uv run src/server.py
mcp call get_zoom_rooms --params '{"location_query":"Floor 3"}' uv run src/server.py
```

### `get_room_details`
Get detailed information about a specific room.
```bash
# Usage: Deep dive into specific room configuration
mcp call get_room_details --params '{"room_id":"ROOM_ID_HERE"}' uv run src/server.py
```

### `resolve_location`
Debug tool to test location resolution without fetching rooms.
```bash
# Usage: Debug how location queries get resolved
mcp call resolve_location --params '{"location_query":"DEN2"}' uv run src/server.py
```

## 📍 Smart Location Resolution

The server understands various location query patterns:

| Query Pattern | Example | What It Resolves |
|---------------|---------|------------------|
| Campus codes | `SF1`, `NYC`, `DEN` | Entire campus with all buildings/floors |
| Building numbers | `Building 1`, `DEN1` | Specific building or hardcoded alias |
| Floor numbers | `Floor 1`, `3F` | All floors with that number across sites |
| Partial names | `Denver`, `Francisco` | Best fuzzy match |

### Special Denver Building Aliases

Due to Zoom's location hierarchy vs. room naming patterns, Denver has special hardcoded mappings:

- **`DEN1`** → Denver Building 1 (Floor 3) → Rooms: `DEN-1-101`, `DEN-1-102`, etc.
- **`DEN2`** → Denver Building 2 (T3F3, T3F5, T3F6) → Rooms: `DEN-2-201`, `DEN-2-202`, etc.

## 🔧 Installation & Setup

### Prerequisites
- Python 3.10+
- UV package manager
- Zoom Pro/Business account with API access

### 1. Clone Repository
```bash
git clone https://github.com/chadkunsman/zoom-mcp.git
cd zoom-mcp
```

### 2. Install Dependencies
```bash
uv pip install -e .
```

### 3. Zoom API Configuration

1. Create a **Server-to-Server OAuth** app in [Zoom Marketplace](https://marketplace.zoom.us/)
2. Add required scope: `room:read:admin`
3. Get your credentials: Account ID, Client ID, Client Secret

### 4. Configure Credentials

Create `.env` file:
```bash
ZOOM_ACCOUNT_ID=your_account_id_here
ZOOM_CLIENT_ID=your_client_id_here
ZOOM_CLIENT_SECRET=your_client_secret_here
```

### 5. Test Installation
```bash
# Install MCPTools for testing
brew tap f/mcptools && brew install mcp

# Test the server
mcp tools uv run src/server.py
mcp call test_zoom_connection --params '{}' uv run src/server.py
```

## 🔌 MCP Client Configuration

### For Claude Desktop and Similar MCP Clients

Add to your MCP client configuration:

#### Using Environment Variables (Recommended)
```json
{
  "mcpServers": {
    "zoom-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/zoom-mcp",
        "src/server.py"
      ],
      "env": {
        "ZOOM_ACCOUNT_ID": "your_account_id_here",
        "ZOOM_CLIENT_ID": "your_client_id_here",
        "ZOOM_CLIENT_SECRET": "your_client_secret_here"
      }
    }
  }
}
```

#### Using Command-Line Arguments
```json
{
  "mcpServers": {
    "zoom-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/zoom-mcp",
        "src/server.py",
        "--zoom-account-id",
        "your_account_id_here",
        "--zoom-client-id", 
        "your_client_id_here",
        "--zoom-client-secret",
        "your_client_secret_here"
      ]
    }
  }
}
```

## 💡 Usage Examples

### Find All Offline Rooms (Efficient)
"Are any Zoom rooms offline anywhere in the company?"
→ Uses `get_zoom_rooms` without location_query (single API call)

### Check Specific Location
"Show me all rooms in San Francisco"
→ Uses `get_zoom_rooms` with `location_query: "SF1"`

### Debug Location Resolution
"How would 'DEN2' be resolved?"
→ Uses `resolve_location` to see what locations match

### Room Status by Building
"What's the status of Denver Building 1 rooms?"
→ Uses `get_zoom_rooms` with `location_query: "DEN1"`

## 🏗️ Architecture

```
zoom-mcp/
├── src/
│   ├── server.py              # Main MCP server with 5 tools
│   └── config/                # Configuration modules
│       ├── settings.py        # Environment & auth configuration
│       ├── zoom_auth.py       # OAuth token management
│       ├── zoom_hierarchy.py  # Location discovery & relationships
│       └── zoom_fuzzy.py      # Smart location resolution
├── docs/                      # Comprehensive documentation
└── test_server.py            # Direct testing script
```

### Key Design Patterns

- **Import Inside Functions**: Configuration modules imported inside tool functions to avoid timing issues
- **Multi-Level Token Caching**: Memory cache + file persistence with 1-hour expiration and 5-minute buffer
- **Hierarchical Discovery**: Automatic campus → building → floor relationship building
- **Hybrid Resolution**: Hardcoded Denver aliases + dynamic fuzzy matching for other sites

## 🧪 Testing

### MCPTools Testing
```bash
# List all tools
mcp tools uv run src/server.py

# Test authentication
mcp call test_zoom_connection --params '{}' uv run src/server.py

# Interactive testing
mcp shell uv run src/server.py
```

### Direct Script Testing
```bash
python test_server.py
```

## 📚 Documentation

Comprehensive documentation available in `docs/`:

- [Quick Start Guide](docs/quickstart.md) - Setup and basic usage
- [Authentication Guide](docs/authentication.md) - OAuth implementation details
- [Testing Guide](docs/testing.md) - MCPTools usage and examples
- [Best Practices](docs/best-practices.md) - Zoom-specific patterns
- [Advanced Features](docs/zoom-features.md) - Deep dive into capabilities

## 🔒 Security

- Credentials stored in `.env` files (not committed to git)
- Token caching with secure file permissions
- Bearer token automatic refresh
- Error messages don't expose sensitive information

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with MCPTools
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Troubleshooting

### Common Issues

1. **"Zoom credentials not configured"**
   - Verify `.env` file exists with correct variables
   - Check environment variable names match exactly

2. **"Token request failed: 401"**
   - Verify Zoom app credentials are correct
   - Ensure app has `room:read:admin` scope
   - Confirm app is Server-to-Server OAuth type

3. **"No location matches found"**
   - Check spelling of location query
   - Use `get_zoom_sites` to see available locations
   - Test with `resolve_location` to debug fuzzy matching

4. **Import timing issues**
   - Configuration modules imported inside tool functions
   - Never import config at module level before `initialize_config()`

### Debug Commands
```bash
# Test connection
mcp call test_zoom_connection --params '{}' uv run src/server.py

# List all sites
mcp call get_zoom_sites --params '{}' uv run src/server.py

# Debug location resolution
mcp call resolve_location --params '{"location_query":"your_query"}' uv run src/server.py
```

---

Built with [FastMCP](https://github.com/jlowin/fastmcp) and the [Model Context Protocol](https://modelcontextprotocol.io/).
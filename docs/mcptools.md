# MCPTools Documentation

## Overview

MCPTools is a command-line interface for interacting with MCP (Model Context Protocol) servers. It provides utilities for testing, validating, and working with MCP servers using both stdio and HTTP transport methods.

## Installation

### macOS (Homebrew)

```bash
brew tap f/mcptools
brew install mcp
```

### From Source (Go)

```bash
go install github.com/f/mcptools/cmd/mcptools@latest
```

## Basic Commands

**Important**: In all MCPTools commands, everything after the command (like `tools`, `call`, `shell`) is the **command to launch your MCP server**. MCPTools will start the server and communicate with it via stdio.

### List Available Tools

```bash
# List all available tools from your MCP server
# Syntax: mcp tools [SERVER_LAUNCH_COMMAND]
mcp tools npx -y @modelcontextprotocol/server-filesystem ~

# For Python servers:
mcp tools python src/server.py
mcp tools .venv/bin/python src/server.py

# Format output as pretty JSON
mcp tools --format pretty npx -y @modelcontextprotocol/server-filesystem ~
```

### Call a Tool

```bash
# Call a specific tool with parameters
# Syntax: mcp call [TOOL_NAME] --params '[JSON_PARAMS]' [SERVER_LAUNCH_COMMAND]
mcp call read_file --params '{"path":"README.md"}' --format pretty npx -y @modelcontextprotocol/server-filesystem ~

# For Python servers:
mcp call get_zoom_sites --params '{}' python src/server.py
mcp call get_zoom_rooms --params '{"site_id":"87iUChR1SniA6ebkDv119Q"}' .venv/bin/python src/server.py
```

### Interactive Shell

```bash
# Start an interactive shell for MCP commands
# Syntax: mcp shell [SERVER_LAUNCH_COMMAND]
mcp shell npx -y @modelcontextprotocol/server-filesystem ~

# For Python servers:
mcp shell python src/server.py
mcp shell .venv/bin/python src/server.py

# Use commands within the shell
mcp > tools
mcp > read_file {"path":"README.md"}
```

## Testing Your MCP Server

### Basic Testing

```bash
# Test your server after building (JavaScript/Node.js)
mcp tools node build/index.js

# Test Python MCP server
mcp tools python src/server.py
mcp tools .venv/bin/python src/server.py

# View server logs while testing
mcp tools --server-logs npx -y @modelcontextprotocol/server-filesystem ~
mcp tools --server-logs python src/server.py
```

### Web Interface for Testing

```bash
# Start a web interface for testing your MCP server
mcp web npx -y @modelcontextprotocol/server-filesystem ~

# Specify a custom port
mcp web --port 8080 npx -y @modelcontextprotocol/server-filesystem ~
```

## MCP Guard for Security Testing

Guard mode allows you to test security constraints by filtering available tools and prompts:

```bash
# Allow only read operations
mcp guard --allow 'tools:read_*' npx -y @modelcontextprotocol/server-filesystem ~

# Deny modification operations
mcp guard --deny tools:write_*,delete_*,create_*,move_* npx -y @modelcontextprotocol/server-filesystem ~
```

## Server Configurations

Define, manage, and test different server configurations:

```bash
# Add a server configuration
mcp configs set vscode my-server npm run mcp-server

# View configurations
mcp configs view vscode

# List all configurations
mcp configs ls
```

## Alias Management

Create aliases for frequently used server commands:

```bash
# Add a server alias
mcp alias add myfs npx -y @modelcontextprotocol/server-filesystem ~/

# Use the alias
mcp tools myfs
mcp call read_file --params '{"path":"README.md"}' myfs
```

## Logging

Monitor MCP operations for debugging:

```bash
# View guard logs
tail -f ~/.mcpt/logs/guard.log

# View proxy logs
tail -f ~/.mcpt/logs/proxy.log
```

## Mock Server Creation

For testing without a full implementation:

```bash
# Create a mock tool
mcp mock tool hello_world "A simple greeting tool"

# Create a mock tool with prompt and resource
mcp mock tool hello_world "A greeting tool" \
      prompt welcome "A welcome prompt" "Hello {{name}}, welcome to {{location}}!" \
      resource docs://readme "Documentation" "Mock MCP Server\nThis is a mock server"
```

## Integration with JSON Configurations

Sample configuration for use in MCP host applications:

```json
"my-mcp-server": {
  "command": "mcp",
  "args": [
    "guard", "--allow", "tools:read_*,list_*,search_*",
    "npx", "-y", "@modelcontextprotocol/server-filesystem",
    "/path/to/files"
  ]
}
```

For more information, refer to the [MCPTools GitHub repository](https://github.com/f/mcptools).
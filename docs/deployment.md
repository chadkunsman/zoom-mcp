# Deployment Guide

This guide covers deploying FastMCP servers to production environments, from simple cloud platforms to enterprise setups.

## Deployment Options Overview

| Platform | Best For | Transport Support | Auto-scaling | Cost |
|----------|----------|-------------------|--------------|------|
| Google Cloud Run | Serverless, auto-scaling | Streamable HTTP only* | Yes | Pay-per-use |
| Vercel | Node.js/Python, edge network | Streamable HTTP only* | Yes | Generous free tier |
| Railway | Simple deployment | Both transports | Yes | Simple pricing |
| Digital Ocean | Traditional hosting | Both transports | Manual | Predictable costs |
| AWS ECS/Fargate | Enterprise, containers | Both transports | Yes | Complex pricing |

*Legacy HTTP+SSE transport prevents scaling to zero due to persistent connections.

## Local Development Setup

### Development Server

```python
# src/server.py
import os
from fastmcp import FastMCP

mcp = FastMCP("Development Server")

@mcp.tool()
def example_tool() -> str:
    """Example development tool."""
    return "Hello from development!"

if __name__ == "__main__":
    # Development configuration
    transport = os.getenv("TRANSPORT", "stdio")
    port = int(os.getenv("PORT", "8000"))
    
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run()  # Default STDIO for local testing
```

### Environment Configuration

```bash
# .env.development
DEBUG=true
LOG_LEVEL=debug
TRANSPORT=stdio

# .env.production  
DEBUG=false
LOG_LEVEL=info
TRANSPORT=http
PORT=8000
```

## Cloud Run Deployment (Recommended)

Best for: Serverless applications with automatic scaling

### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv pip install --system --no-cache-dir -e .

# Copy source code
COPY src/ ./src/
COPY docs/ ./docs/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["python", "src/server.py"]
```

### 2. Production Server Configuration

```python
# src/server.py
import os
import logging
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG") != "true" else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

mcp = FastMCP(
    name="Production MCP Server",
    version="1.0.0"
)

# Add health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "healthy", "version": "1.0.0"})

# Your tools here
@mcp.tool()
def production_tool() -> dict:
    """Production-ready tool."""
    return {"message": "Production server running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port
    )
```

### 3. Deploy to Cloud Run

```bash
# Build and deploy
gcloud run deploy mcp-server \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --port 8000 \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --set-env-vars DEBUG=false,LOG_LEVEL=info

# Custom domain (optional)
gcloud run domain-mappings create \
    --service mcp-server \
    --domain your-domain.com \
    --region us-central1
```

## Vercel Deployment

Best for: Simple deployment with global edge network

### 1. Create `vercel.json`

```json
{
  "builds": [
    {
      "src": "src/server.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "src/server.py"
    }
  ],
  "env": {
    "DEBUG": "false",
    "LOG_LEVEL": "info"
  }
}
```

### 2. Adapt Server for Vercel

```python
# src/server.py - Vercel compatible
from fastmcp import FastMCP

mcp = FastMCP("Vercel MCP Server")

@mcp.tool()
def vercel_tool() -> str:
    """Tool running on Vercel."""
    return "Hello from Vercel!"

# Create ASGI app for Vercel
app = mcp.http_app()

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. Deploy

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

## Railway Deployment

Best for: Simple deployment with database support

### 1. Create `railway.toml`

```toml
[build]
builder = "NIXPACKS"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[env]
PORT = { default = "8000" }
DEBUG = { default = "false" }
```

### 2. Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy  
railway login
railway link
railway up
```

## Traditional VPS Deployment

Best for: Full control and predictable costs

### 1. Server Setup (Ubuntu)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip nginx

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create application directory
sudo mkdir -p /opt/mcp-server
sudo chown $USER:$USER /opt/mcp-server
cd /opt/mcp-server

# Clone your repository
git clone https://github.com/your-username/your-mcp-server.git .

# Install dependencies
uv pip install --system -e .
```

### 2. Systemd Service

```ini
# /etc/systemd/system/mcp-server.service
[Unit]
Description=FastMCP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mcp-server
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PORT=8000
Environment=DEBUG=false
ExecStart=/usr/bin/python3 src/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable mcp-server
sudo systemctl start mcp-server
sudo systemctl status mcp-server
```

### 3. Nginx Configuration

```nginx
# /etc/nginx/sites-available/mcp-server
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for SSE
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Enable site and SSL
sudo ln -s /etc/nginx/sites-available/mcp-server /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Install SSL certificate (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Docker Deployment

### 1. Multi-stage Dockerfile

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install UV
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache-dir -e .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app
COPY --chown=app:app src/ ./src/
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/server.py"]
```

### 2. Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - LOG_LEVEL=info
      - DATABASE_URL=postgresql://user:pass@db:5432/mcpdb
    depends_on:
      - db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=mcpdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - mcp-server
    restart: unless-stopped

volumes:
  postgres_data:
```

## Environment Variables

### Required Configuration

```bash
# Server Configuration
PORT=8000
HOST=0.0.0.0
DEBUG=false
LOG_LEVEL=info

# Authentication (if using OAuth)
OAUTH_CLIENT_ID=your_client_id
OAUTH_CLIENT_SECRET=your_client_secret
JWT_SECRET_KEY=your_very_secure_secret_here

# Database (if needed)
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# External APIs
OPENAI_API_KEY=your_openai_key
EXTERNAL_API_KEY=your_api_key

# Monitoring
SENTRY_DSN=your_sentry_dsn
```

### Environment-Specific Files

```bash
# .env.development
DEBUG=true
LOG_LEVEL=debug
DATABASE_URL=sqlite:///dev.db

# .env.staging
DEBUG=false
LOG_LEVEL=info
DATABASE_URL=postgresql://user:pass@staging-db:5432/staging

# .env.production
DEBUG=false
LOG_LEVEL=warning
DATABASE_URL=postgresql://user:pass@prod-db:5432/production
```

## Production Considerations

### 1. Monitoring and Logging

```python
import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configure Sentry
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[LoggingIntegration()],
        traces_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "production")
    )

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
```

### 2. Database Connections

```python
import asyncpg
from contextlib import asynccontextmanager

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url)
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def get_connection(self):
        async with self.pool.acquire() as connection:
            yield connection

# Use in your tools
db = DatabaseManager(os.getenv("DATABASE_URL"))

@mcp.tool()
async def get_user_data(user_id: str) -> dict:
    """Get user data from database."""
    async with db.get_connection() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1", user_id
        )
        return dict(result) if result else {"error": "User not found"}
```

### 3. Caching

```python
import redis.asyncio as redis
import json
from typing import Optional

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    async def get(self, key: str) -> Optional[dict]:
        value = await self.redis.get(key)
        return json.loads(value) if value else None
    
    async def set(self, key: str, value: dict, ttl: int = 3600):
        await self.redis.setex(key, ttl, json.dumps(value))

cache = CacheManager(os.getenv("REDIS_URL", "redis://localhost:6379"))

@mcp.tool()
async def cached_api_call(endpoint: str) -> dict:
    """API call with caching."""
    cache_key = f"api:{endpoint}"
    
    # Check cache first
    cached_result = await cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Make API call
    result = await make_api_call(endpoint)
    
    # Cache result
    await cache.set(cache_key, result, ttl=1800)
    
    return result
```

## Security in Production

### 1. HTTPS/TLS

```python
# For uvicorn deployment
if __name__ == "__main__":
    import uvicorn
    
    # Production with SSL
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="/path/to/private.key",
        ssl_certfile="/path/to/certificate.crt"
    )
```

### 2. Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/mcp")
@limiter.limit("100/hour")
async def mcp_endpoint(request: Request):
    # Your MCP handling logic
    pass
```

### 3. CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-allowed-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "MCP-Session-ID"],
)
```

## CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install UV
        run: pip install uv
      
      - name: Install dependencies
        run: uv pip install --system -e .[dev]
      
      - name: Run tests
        run: pytest
      
      - name: Run linting
        run: ruff check .

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v1
        with:
          service: mcp-server
          image: gcr.io/project-id/mcp-server
          region: us-central1
          env_vars: |
            DEBUG=false
            LOG_LEVEL=info
```

## Monitoring and Health Checks

### Health Check Endpoint

```python
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    from starlette.responses import JSONResponse
    
    # Check database connection
    try:
        async with db.get_connection() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check external APIs
    try:
        # Test your external dependencies
        api_status = "healthy"
    except Exception:
        api_status = "unhealthy"
    
    status = "healthy" if db_status == "healthy" and api_status == "healthy" else "unhealthy"
    
    return JSONResponse({
        "status": status,
        "checks": {
            "database": db_status,
            "external_api": api_status
        },
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })
```

## Troubleshooting Deployment Issues

### Common Problems

1. **Port Binding Issues**: Ensure your app binds to `0.0.0.0`, not `127.0.0.1`
2. **Environment Variables**: Use proper environment variable loading
3. **Health Check Failures**: Implement proper health check endpoints
4. **Memory Limits**: Monitor memory usage and adjust container limits
5. **Database Connections**: Use connection pooling for better performance

### Debug Commands

```bash
# Check logs
docker logs container-name
kubectl logs pod-name
gcloud run logs read --service=mcp-server

# Test endpoints
curl -f http://localhost:8000/health
curl -H "Authorization: Bearer token" http://localhost:8000/mcp

# Monitor resources
docker stats
kubectl top pods
```

## Next Steps

- **Testing**: See [testing.md](testing.md) for production testing strategies
- **Best Practices**: Review [best-practices.md](best-practices.md) for production optimization
- **Authentication**: Check [authentication.md](authentication.md) for secure production auth
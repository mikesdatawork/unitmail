# Skill: Gateway Service Core

## What This Skill Does
Creates the Flask-based API gateway service that handles HTTP requests and WebSocket connections.

## Components

### app.py - Application Factory
- `create_app()` factory pattern
- Blueprint registration
- CORS configuration
- Error handlers (400, 401, 403, 404, 429, 500)
- Request/response logging middleware
- Health check endpoints

### server.py - WebSocket Server
- `GatewayServer` class with Flask-SocketIO
- Real-time event broadcasting
- Graceful shutdown with signal handlers
- Auto-detects async mode (eventlet/gevent/threading)

### middleware.py - Request Processing
- Rate limiting (InMemoryRateLimiter, RedisRateLimiter)
- Request validation decorators
- Request ID tracking (X-Request-ID)
- Metrics collection

### routes/__init__.py - API Blueprints
- `/api/v1/auth` - Authentication
- `/api/v1/messages` - Email operations
- `/api/v1/mailboxes` - Folder management
- `/api/v1/users` - User management
- `/api/v1/domains` - Domain configuration

## Usage
```bash
# Start gateway
python scripts/run_gateway.py --port 5000

# With debug mode
python scripts/run_gateway.py --debug

# Without WebSocket
python scripts/run_gateway.py --no-websocket
```

## Endpoints
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

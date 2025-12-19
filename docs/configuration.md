# Configuration Reference

Environment variables for PyPSA App.

## Application

| Variable | Description | Default |
|----------|-------------|---------|
| `BASE_URL` | Publicly accessible URL of the application | `http://localhost:5173` |
| `DATA_DIR` | File storage directory to store application data and network files | `./data` |

## Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database URL (SQLite and PostgreSQL is supported) | `sqlite:///./data/pypsa-app.db` |

## Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_AUTH` | Enable GitHub OAuth authentication | `false` |
| `GITHUB_CLIENT_ID` | GitHub OAuth app client ID (create at https://github.com/settings/developers) | - |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret | - |
| `SESSION_SECRET_KEY` | Secret key for session cookies (generate with: openssl rand -base64 32) | `dev-secret-key-change-in-production` |
| `SESSION_TTL` | Session time-to-live in seconds (default: 7 days) | `604800` |
| `ADMIN_GITHUB_USERNAME` | GitHub username that becomes admin on first login | - |

## Map

| Variable | Description | Default |
|----------|-------------|---------|
| `MAPBOX_TOKEN` | Mapbox access token for interactive network map via kepler.gl | - |

## Redis

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL for caching (optional) | - |
| `PLOT_CACHE_TTL` | Time-to-live in seconds for plot cache entries | `86400` |
| `MAP_CACHE_TTL` | Time-to-live in seconds for map cache entries | `3600` |
| `NETWORK_CACHE_TTL` | Time-to-live in seconds for network cache entries | `7200` |
| `MAX_CACHE_SIZE_MB` | Maximum cache size in megabytes | `50` |

## Development

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_ONLY` | Run backend only without serving the frontend | `false` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins (only used in backend-only mode) | `http://localhost:5173,http://localhost:5174` |

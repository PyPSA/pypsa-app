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

## LLM Chat

Feature-flagged AI chat assistant for network analysis (disabled by default).

| Variable | Description | Default |
|----------|-------------|---------|
| `CHAT_ENABLED` | Feature flag to enable AI chat endpoints | `false` |
| `LLM_PROVIDER` | LLM provider name (e.g., `openai`, `anthropic`) | `openai` |
| `LLM_MODEL` | LLM model identifier | `qwen3.5:9b` |
| `LLM_API_KEY` | API key or bearer token for the LLM provider | - |
| `LLM_API_BASE` | Custom API base URL for the LLM provider (omit to use provider default) | - |
| `LLM_MAX_TOKENS` | Maximum tokens per completion | `2048` |
| `LLM_TEMPERATURE` | Sampling temperature (0.0–2.0) | `0.2` |
| `LLM_REQUEST_TIMEOUT_SECONDS` | Request timeout in seconds for provider calls | `120` |
| `LLM_MAX_TOOL_ITERATIONS` | Maximum tool-calling loop iterations per chat request | `8` |
| `LLM_INTERNAL_API_BASE` | Base URL for internal HTTP calls from chat tools to the app's own REST API | auto-derived from `LLM_INTERNAL_PORT` |
| `LLM_INTERNAL_PORT` | Port used to derive `LLM_INTERNAL_API_BASE` when not set explicitly | `8000` |

### Quick Start (Ollama)

```bash
export CHAT_ENABLED=true
export LLM_PROVIDER=openai
export LLM_MODEL=qwen3.5:9b
export LLM_API_KEY=your-bearer-token
export LLM_API_BASE=http://localhost:11434/v1
```

> [!NOTE]
> For Ollama models, use `openai/` as the provider prefix — **not** `ollama/` — to avoid a LiteLLM
> bug that drops `tool_calls` for reasoning models.

## Development

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_ONLY` | Run backend only without serving the frontend | `false` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins (only used in backend-only mode) | `http://localhost:5173,http://localhost:5174` |

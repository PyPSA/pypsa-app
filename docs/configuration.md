# Configuration Reference

Environment variables for PyPSA App.

## Application

| Variable | Description | Default |
|----------|-------------|---------|
| `BASE_URL` | Publicly accessible URL of the application | `http://localhost:5173` |
| `LOCAL_MODE` | Single-user local-dashboard deployment (the bare `pypsa-app` CLI). Enables zero-copy in-place network registration. Incompatible with any authentication. | `false` |
| `DEMO_MODE` | Public read-only demo deployment. Disables all write endpoints, uses a shared 'demo' user. | `false` |
| `DATA_DIR` | File storage directory to store application data and network files | `PydanticUndefined` |

## Database

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database URL (SQLite and PostgreSQL are supported). Defaults to a SQLite file inside data_dir. | `__derive_from_data_dir__` |

## Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTH_GITHUB_CLIENT_ID` | GitHub OAuth app client ID (create at https://github.com/settings/developers) | - |
| `AUTH_GITHUB_CLIENT_SECRET` | GitHub OAuth app client secret | - |
| `AUTH_PASSWORD_ENABLED` | Enable password based login | `false` |
| `SESSION_SECRET_KEY` | Secret key for session cookies (generate with: openssl rand -base64 32) | `dev-secret-key-change-in-production` |
| `SESSION_TTL` | Session time-to-live in seconds (default: 7 days) | `604800` |

## Networks

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_UPLOAD_SIZE_MB` | Maximum network file upload size in megabytes | `2000` |

## Runs

| Variable | Description | Default |
|----------|-------------|---------|
| `SNAKEDISPATCH_SYNC_INTERVAL` | Interval in seconds between background Snakedispatch sync cycles | `10.0` |
| `CALLBACK_URL_ALLOWED_DOMAINS` | Comma-separated list of allowed domains for run callback URLs (e.g. hooks.myorg.dev,example.com). Callbacks are rejected unless the host matches. Empty disables callbacks entirely. | `` |
| `SNAKEDISPATCH_BACKENDS` | Comma-separated list of Snakedispatch backends in name=url format (e.g. cluster-a=http://sd-a:8000,cluster-b=http://sd-b:8000) | - |

## Redis

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL for caching (optional) | - |
| `PLOT_CACHE_TTL` | Time-to-live in seconds for plot cache entries | `86400` |
| `NETWORK_CACHE_TTL` | Time-to-live in seconds for network cache entries | `7200` |
| `RUN_OUTPUTS_CACHE_TTL` | Time-to-live in seconds for run output file list cache entries | `10800` |
| `MAX_CACHE_SIZE_MB` | Maximum cache size in megabytes | `50` |

## Rate limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RATELIMIT_ENABLED` | Enable per route rate limiting. Auto on when LOCAL_MODE is off. | - |
| `RATELIMIT_DEFAULT` | Default per key rate limit applied to all routes | `120/minute` |
| `RATELIMIT_LOGIN` | Rate limit for POST /auth/login/password | `5/minute;20/hour` |
| `RATELIMIT_EXPENSIVE` | Rate limit for task queueing routes (plots, statistics). | `60/minute;600/hour` |
| `TRUST_CLOUDFLARE_IP` | Trust the CF-Connecting-IP header as the client IP for rate limiting. Only enable when the app sits behind a Cloudflare tunnel. | `false` |

## Email

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_HOST` | SMTP server hostname (enables email notifications when set) | - |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP authentication username | - |
| `SMTP_PASSWORD` | SMTP authentication password | - |
| `SMTP_USE_TLS` | Use TLS/STARTTLS for SMTP connection | `true` |
| `SMTP_FROM_ADDRESS` | Sender email address for notifications | `noreply@pypsa-app.local` |

## Development

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_ONLY` | Run backend only without serving the frontend | `false` |
| `CORS_ORIGINS` | Comma-separated list of allowed CORS origins (only used in backend-only mode) | `http://localhost:5173,http://localhost:5174` |

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from pypsa_app.backend.__version__ import __description__, __version__
from pypsa_app.backend.api.routes import (
    admin,
    api_keys,
    auth,
    cache,
    networks,
    plots,
    runs,
    statistics,
    tasks,
    version,
)
from pypsa_app.backend.api.deps import set_auth_disabled_user
from pypsa_app.backend.cache import cache_service
from pypsa_app.backend.database import Base, SessionLocal, engine
from pypsa_app.backend.models import User, UserRole
from pypsa_app.backend.settings import API_V1_PREFIX, settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def _ensure_system_user() -> None:
    """Create a system admin user for auth-disabled mode."""
    if settings.enable_auth:
        msg = "Cannot create system user when authentication is enabled"
        raise RuntimeError(msg)
    db = SessionLocal()
    try:
        system_user = db.query(User).filter(User.username == "system").first()
        if not system_user:
            system_user = User(username="system", role=UserRole.ADMIN)
            db.add(system_user)
            db.commit()
            db.refresh(system_user)
        set_auth_disabled_user(system_user)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info(
        "Starting PyPSA Web App API",
        extra={
            "version": __version__,
            "api_prefix": API_V1_PREFIX,
            "backend_only": settings.backend_only,
            "networks_path": str(settings.networks_path),
            "database_url": settings.database_url,
        },
    )

    # Ensure networks directory exists
    settings.networks_path.mkdir(parents=True, exist_ok=True)

    # Auto-create database tables and verify connection
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database ready")
    finally:
        db.close()

    # Create system user for auth-disabled mode
    if not settings.enable_auth:
        _ensure_system_user()

    # Initialize authentication if enabled
    if settings.enable_auth:
        logger.info(
            "Authentication enabled - initializing session store",
            extra={
                "github_client_id": settings.github_client_id,
                "session_ttl": settings.session_ttl,
            },
        )

        # Verify required auth settings
        if not settings.github_client_id or not settings.github_client_secret:
            msg = (
                "Authentication is enabled but GitHub OAuth"
                " credentials are not configured. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET"
                " environment variables."
            )
            raise RuntimeError(msg)

        # Verify Redis is available (required for session storage)
        if not cache_service.ping():
            msg = (
                "Authentication is enabled but Redis is not available. "
                "Redis is required for session storage when authentication is enabled. "
                "Set REDIS_URL environment variable and ensure Redis is running."
            )
            raise RuntimeError(msg)

        # Initialize session store
        from pypsa_app.backend.auth import session  # noqa: PLC0415

        session.session_store = session.SessionStore()
        logger.info(
            "Session store initialized",
            extra={
                "redis_url": settings.redis_url,
            },
        )
    else:
        logger.info("Authentication disabled")

    # Check smk-executor connectivity
    if settings.smk_executor_url:
        try:
            from pypsa_app.backend.services.run import (  # noqa: PLC0415
                SmkExecutorClient,
            )

            client = SmkExecutorClient(settings.smk_executor_url)
            health = client.health_check()
            logger.info(
                "smk-executor connected",
                extra={
                    "url": settings.smk_executor_url,
                    "status": health.get("status"),
                },
            )
        except Exception as e:
            logger.warning(
                "smk-executor unreachable at startup (non-fatal)",
                extra={"url": settings.smk_executor_url, "error": str(e)},
            )
    else:
        logger.info("smk-executor not configured (SMK_EXECUTOR_URL not set)")

    yield

    # Shutdown
    logger.info("Shutting down PyPSA Web App API")
    engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="PyPSA App",
    version=__version__,
    description=__description__,
    openapi_url=f"{API_V1_PREFIX}/openapi.json",
    docs_url="/docs" if settings.backend_only else "/api/docs",
    redoc_url="/redoc" if settings.backend_only else "/api/redoc",
    lifespan=lifespan,
)

# Add session middleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="oauth_session",
    max_age=600,  # OAuth state only needs to last 10 minutes
    same_site="lax",
    https_only=not settings.base_url.startswith("http://localhost"),
)

# Configure CORS (only needed in dev mode with separate frontend server)
if settings.backend_only:
    # Parse comma-separated CORS origins from environment variable
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        raise exc

    logger.error(  # noqa: TRY400
        "Unexpected error",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error": str(exc),
            "error_type": exc.__class__.__name__,
            "client_host": request.client.host if request.client else None,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred"},
    )


# Include routers
if settings.enable_auth:
    app.include_router(auth.router, prefix=f"{API_V1_PREFIX}/auth", tags=["auth"])
    app.include_router(
        api_keys.router, prefix=f"{API_V1_PREFIX}/auth/api-keys", tags=["auth"]
    )
app.include_router(admin.router, prefix=f"{API_V1_PREFIX}/admin", tags=["admin"])
app.include_router(
    networks.router, prefix=f"{API_V1_PREFIX}/networks", tags=["networks"]
)
app.include_router(plots.router, prefix=f"{API_V1_PREFIX}/plots", tags=["plots"])
app.include_router(
    statistics.router,
    prefix=f"{API_V1_PREFIX}/statistics",
    tags=["statistics"],
)
app.include_router(cache.router, prefix=f"{API_V1_PREFIX}/cache", tags=["cache"])
app.include_router(version.router, prefix=f"{API_V1_PREFIX}/version", tags=["version"])
app.include_router(tasks.router, prefix=f"{API_V1_PREFIX}/tasks", tags=["tasks"])
app.include_router(runs.router, prefix=f"{API_V1_PREFIX}/runs", tags=["runs"])


# Health check endpoint
@app.get("/health")
def health_check() -> dict:
    health_status = {
        "status": "healthy",
        "version": __version__,
        "cache": {"status": "unknown", "type": "redis"},
        "smk_executor": {"status": "not_configured"},
    }

    # Check cache health
    try:
        if cache_service.ping():
            health_status["cache"]["status"] = "healthy"
        else:
            health_status["cache"]["status"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception as e:
        logger.exception(
            "Cache health check failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "cache_type": "redis",
            },
        )
        health_status["cache"]["status"] = "unhealthy"
        health_status["cache"]["error"] = str(e)
        health_status["status"] = "degraded"

    # Check smk-executor health
    if settings.smk_executor_url:
        try:
            from pypsa_app.backend.services.run import (  # noqa: PLC0415
                SmkExecutorClient,
            )

            client = SmkExecutorClient(settings.smk_executor_url)
            result = client.health_check()
            health_status["smk_executor"]["status"] = result.get("status", "unknown")
            health_status["smk_executor"]["ssh"] = result.get("ssh", False)
        except Exception as e:
            health_status["smk_executor"]["status"] = "unhealthy"
            health_status["smk_executor"]["error"] = str(e)
            health_status["status"] = "degraded"

    return health_status


# Serve frontend static files (production mode)
if not settings.backend_only:
    from pypsa_app.backend.spa_static_files import SPAStaticFiles

    static_dir = Path(__file__).parent / "static"

    # Mount main app (catch-all for SPA routing)
    app_dir = static_dir / "app"
    if app_dir.exists():
        app.mount("/", SPAStaticFiles(directory=app_dir, html=True), name="app")
        logger.info(
            "Serving main app",
            extra={
                "app_type": "main",
                "directory": str(app_dir),
                "mount_path": "/",
            },
        )
    else:
        logger.warning(
            "Main app not found",
            extra={
                "app_type": "main",
                "expected_directory": str(app_dir),
                "build_command": "cd frontend/app && npm run build",
            },
        )

else:
    # Development mode - API only
    @app.get("/")
    def root() -> dict:
        return {
            "message": "PyPSA Web App API (dev mode)",
            "version": __version__,
            "docs": "/docs",
            "frontend": "Run: cd frontend && npm run dev",
        }

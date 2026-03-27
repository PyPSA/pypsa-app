import asyncio
import contextlib
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
    public,
    runs,
    statistics,
    tasks,
    version,
)
from pypsa_app.backend.auth.authenticate import set_auth_disabled_user
from pypsa_app.backend.cache import cache_service
from pypsa_app.backend.database import SessionLocal, engine
from pypsa_app.backend.models import SnakedispatchBackend, User, UserRole
from pypsa_app.backend.services.backend_registry import backend_registry
from pypsa_app.backend.services.run import SnakedispatchError
from pypsa_app.backend.services.sync import run_sync_loop
from pypsa_app.backend.settings import API_V1_PREFIX, settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def _sync_backends() -> None:
    """Upsert backends from settings into the DB and populate the registry."""
    configured = {b["name"]: b["url"] for b in settings.resolved_backends}
    db = SessionLocal()
    try:
        for backend in db.query(SnakedispatchBackend).all():
            if backend.name in configured:
                backend.url = configured.pop(backend.name)
                backend.is_active = True
            else:
                backend.is_active = False

        for name, url in configured.items():
            db.add(SnakedispatchBackend(name=name, url=url, is_active=True))

        db.commit()

        # Populate registry (needs DB ids for new backends)
        backend_registry.clear()
        for backend in (
            db.query(SnakedispatchBackend)
            .filter(SnakedispatchBackend.is_active.is_(True))
            .all()
        ):
            backend_registry.register(backend.id, backend.name, backend.url)

        # Startup health check (non-fatal)
        for bid, client in backend_registry.all_clients().items():
            name = backend_registry.get_name(bid)
            try:
                health = client.health_check()
                logger.info(
                    "Snakedispatch backend connected",
                    extra={
                        "backend_name": name,
                        "status": health.get("status"),
                    },
                )
            except Exception as e:
                logger.warning(
                    "Snakedispatch backend unreachable at startup",
                    extra={"backend_name": name, "error": str(e)},
                )
    finally:
        db.close()


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

    # Run database migrations
    from alembic import command  # noqa: PLC0415
    from alembic.config import Config  # noqa: PLC0415

    alembic_ini = str(Path(__file__).resolve().parents[3] / "alembic.ini")  # noqa: ASYNC240
    alembic_cfg = Config(alembic_ini)
    command.upgrade(alembic_cfg, "head")

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

    # Backends must exist in DB before registry can map IDs to clients
    if settings.resolved_backends:
        _sync_backends()
    else:
        logger.info(
            "No Snakedispatch backends configured (SNAKEDISPATCH_BACKENDS not set)"
        )

    sync_task = None
    if settings.resolved_backends:
        sync_task = asyncio.create_task(
            run_sync_loop(interval=settings.snakedispatch_sync_interval)
        )
        logger.info(
            "Background run sync started",
            extra={"interval": settings.snakedispatch_sync_interval},
        )

    yield

    # Shutdown
    logger.info("Shutting down PyPSA Web App API")
    if sync_task is not None:
        sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sync_task
        logger.info("Background run sync stopped")
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


if settings.resolved_backends:

    @app.exception_handler(SnakedispatchError)
    async def snakedispatch_exception_handler(
        request: Request, exc: SnakedispatchError
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
    app.include_router(public.router, prefix=f"{API_V1_PREFIX}/public", tags=["public"])
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
if settings.resolved_backends:
    app.include_router(runs.router, prefix=f"{API_V1_PREFIX}/runs", tags=["runs"])


# Health check endpoint
@app.get("/health")
def health_check() -> dict:
    health_status: dict = {
        "status": "healthy",
        "version": __version__,
        "cache": {"status": "unknown", "type": "redis"},
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

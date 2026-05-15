"""Custom StaticFiles handler for SPA (Single Page Application) routing.
Falls back to index.html for client-side routing and allows to serve static files
(from build frontend).
"""

from http import HTTPStatus

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.types import Scope

from pypsa_app.backend.settings import API_V1_PREFIX


class SPAStaticFiles(StaticFiles):
    """Static files for Single Page Application."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as ex:
            if ex.status_code == HTTPStatus.NOT_FOUND:
                # Unmatched /api/v1/* paths must return JSON 404, not the SPA shell —
                # otherwise SPA fetch callers crash parsing HTML as JSON.
                request_path = scope.get("path", "") or f"/{path}"
                if request_path == API_V1_PREFIX or request_path.startswith(
                    f"{API_V1_PREFIX}/"
                ):
                    return JSONResponse(
                        status_code=HTTPStatus.NOT_FOUND,
                        content={"detail": "Not Found"},
                    )
                # Return index.html for non-API routes so SvelteKit's client-side
                # router can handle them.
                return await super().get_response("index.html", scope)
            raise

"""Public (unauthenticated) API endpoints"""

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from pypsa_app.backend.api.deps import require_public_run
from pypsa_app.backend.models import Run, RunStatus
from pypsa_app.backend.schemas.public import PublicRunResponse

router = APIRouter()

RUN_TERMINAL_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.ERROR,
    RunStatus.CANCELLED,
}


@router.get("/runs/{run_id}", response_model=PublicRunResponse)
async def get_public_run(run: Run = Depends(require_public_run)) -> JSONResponse:
    data = PublicRunResponse(
        job_id=run.job_id,
        status=run.status,
        workflow=run.workflow,
        configfile=run.configfile,
        git_ref=run.git_ref,
        git_sha=run.git_sha,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_job_count=run.total_job_count,
        jobs_finished=run.jobs_finished,
        visibility=run.visibility,
        owner=run.owner,
        backend=run.backend,
        networks=run.networks,
    )

    is_terminal = run.status in RUN_TERMINAL_STATUSES
    cache_control = "public, max-age=300" if is_terminal else "no-cache"

    return JSONResponse(
        content=data.model_dump(mode="json"),
        headers={"Cache-Control": cache_control},
    )

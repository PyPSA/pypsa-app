"""Version response schemas"""

from pydantic import BaseModel


class VersionResponse(BaseModel):
    version: str
    pypsa_version: str
    local_mode: bool
    runs_enabled: bool

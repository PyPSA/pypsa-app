"""Version response schemas"""

from pydantic import BaseModel


class VersionResponse(BaseModel):
    version: str
    pypsa_version: str
    demo_mode: bool
    runs_enabled: bool

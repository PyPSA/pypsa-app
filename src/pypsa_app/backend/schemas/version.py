"""Version response schemas"""

from pydantic import BaseModel


class VersionResponse(BaseModel):
    version: str
    pypsa_version: str
    snakedispatch_backends: list[str]

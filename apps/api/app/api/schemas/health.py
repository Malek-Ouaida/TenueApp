from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["api"]


class HealthDependencySnapshot(BaseModel):
    name: str
    status: str
    critical: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["api"]
    dependencies: list[HealthDependencySnapshot]

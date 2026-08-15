from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "citypulse-api"
    version: str


class CheckResult(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: dict[str, CheckResult]


class VersionResponse(BaseModel):
    service: str = "citypulse-api"
    version: str

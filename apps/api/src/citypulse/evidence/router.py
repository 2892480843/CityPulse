from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.evidence.service import city_evidence_summary
from citypulse.identity.rbac import Identity, resolve_identity
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/cities", tags=["evidence"])


class CityEvidenceSummary(BaseModel):
    city_code: str
    total_observations: int
    sourced_share: float
    metric_coverage: float
    covered_metrics: list[str]
    missing_metrics: list[str]
    date_min: str | None
    date_max: str | None
    latest_available_at: str | None
    sources: list[str]


@router.get("/{city_code}/evidence", response_model=CityEvidenceSummary)
async def evidence_summary(
    city_code: str,
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return await city_evidence_summary(db, city_code=city_code)  # type: ignore[return-value]

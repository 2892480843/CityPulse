from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.city_catalog.schemas import CityListResponse
from citypulse.city_catalog.service import search_cities
from citypulse.identity.rbac import Identity, resolve_identity
from citypulse.shared.db import get_session

router = APIRouter(prefix="/api/v1/cities", tags=["city-catalog"])


@router.get("", response_model=CityListResponse)
async def list_cities(
    _identity: Annotated[Identity, Depends(resolve_identity)],
    db: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CityListResponse:
    return await search_cities(db, query=q, limit=limit)

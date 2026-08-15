import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from citypulse.city_catalog.models import City
from citypulse.city_catalog.schemas import CityListResponse, CityView


async def search_cities(
    db: AsyncSession, *, query: str | None = None, limit: int = 20
) -> CityListResponse:
    statement = select(City).options(selectinload(City.aliases)).order_by(City.code)
    if query:
        term = query.strip()
        pattern = f"%{term}%"
        statement = statement.where(
            sa.or_(
                City.name.ilike(pattern),
                City.province.ilike(pattern),
                City.code.like(pattern),
                City.aliases.any(alias=term),
            )
        )
    statement = statement.limit(limit)
    result = await db.execute(statement)
    cities = list(result.scalars())
    items = [
        CityView(
            id=city.id,
            code=city.code,
            name=city.name,
            province=city.province,
            valid_from=city.valid_from,
            valid_to=city.valid_to,
            aliases=[alias.alias for alias in city.aliases],
        )
        for city in cities
    ]
    return CityListResponse(items=items, total=len(items))


async def known_city_codes(db: AsyncSession) -> set[str]:
    result = await db.execute(select(City.code))
    return set(result.scalars())

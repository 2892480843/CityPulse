"""Sync adapters: administrative divisions import and Open-Meteo weather.

Both adapters only touch official or keyless open endpoints. The weather
adapter converts daily temperatures into the contract's weather_fit metric
and flows through the full ingestion pipeline (validate + immutable commit),
never bypassing the data contract.
"""

import csv
import hashlib
import json
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citypulse.city_catalog.models import City
from citypulse.data_source.models import DataSource
from citypulse.ingestion import service as ingestion
from citypulse.ingestion.models import Dataset
from citypulse.shared.errors import AppError

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_DAYS = 14

OFFICIAL_SYSTEM_ACTOR = uuid.UUID("00000000-0000-4000-8000-0000000000a1")


def read_divisions(path: Path) -> list[tuple[str, str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            (row["code"].strip(), row["name"].strip(), row["province"].strip())
            for row in csv.DictReader(handle)
        ]


async def sync_admin_divisions(db: AsyncSession, *, snapshot_path: Path) -> dict[str, Any]:
    rows = read_divisions(snapshot_path)
    existing = {city.code: city for city in (await db.execute(select(City))).scalars()}
    created = 0
    updated = 0
    for code, name, province in rows:
        city = existing.get(code)
        if city is None:
            db.add(City(code=code, name=name, province=province))
            created += 1
        elif city.name != name or city.province != province:
            city.name = name
            city.province = province
            updated += 1
    await db.flush()
    return {"created": created, "updated": updated, "total_units": len(rows)}


def comfort_fit(day_max_c: float, day_min_c: float, precipitation_mm: float) -> float:
    """Map daily weather onto the 0-100 weather_fit contract metric.

    Comfort peaks when the daily midpoint sits in 16-26C; rain pushes the
    score down. Deliberately simple and versioned with the sync source.
    """
    mid = (day_max_c + day_min_c) / 2
    if 16 <= mid <= 26:
        base = 100.0
    elif mid < 16:
        base = max(20.0, 100.0 - (16 - mid) * 6)
    else:
        base = max(20.0, 100.0 - (mid - 26) * 6)
    penalty = min(40.0, precipitation_mm * 4)
    return round(max(0.0, min(100.0, base - penalty)), 1)


def fetch_weather_rows(
    city_name: str,
    *,
    end_date: date,
    days: int = WEATHER_DAYS,
    getter: Callable[[str], Any] | None = None,
) -> list[tuple[date, float]]:
    """Return [(metric_date, weather_fit)] for one city via Open-Meteo."""
    if getter is None:
        getter = _http_get_json
    geo = getter(
        f"{OPEN_METEO_GEOCODE}?name={urllib.parse.quote(city_name)}&count=1"
        "&language=zh&format=json"
    )
    results = geo.get("results") or []
    if not results:
        return []
    url = (
        f"{OPEN_METEO_ARCHIVE}?latitude={results[0]['latitude']}"
        f"&longitude={results[0]['longitude']}"
        f"&start_date={(end_date - timedelta(days=days)).isoformat()}"
        f"&end_date={end_date.isoformat()}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&timezone=Asia%2FShanghai"
    )
    daily = getter(url).get("daily") or {}
    out: list[tuple[date, float]] = []
    for index, day in enumerate(daily.get("time") or []):
        fit = comfort_fit(
            float(daily["temperature_2m_max"][index]),
            float(daily["temperature_2m_min"][index]),
            float(daily["precipitation_sum"][index] or 0),
        )
        out.append((date.fromisoformat(day), fit))
    return out


def _http_get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


async def sync_open_meteo_weather(
    db: AsyncSession,
    *,
    upload_dir: Path,
    max_cities: int = 8,
    fetcher: Callable[[str], list[tuple[date, float]]] | None = None,
) -> dict[str, Any]:
    """Pull recent weather for cities that already carry observations."""
    codes = (
        (
            await db.execute(
                select(sa.distinct(sa.text("city_code")))
                .select_from(sa.text("signal_observations"))
                .limit(max_cities)
            )
        ).scalars().all()
        or []
    )
    city_rows = (
        await db.execute(select(City).where(City.code.in_(codes)))
    ).scalars() if codes else []
    cities = {city.code: city for city in city_rows}
    if not cities:
        raise AppError(
            code="NO_OBSERVED_CITIES",
            message="Commit observation data before syncing weather.",
            status_code=409,
        )

    end_date = date.today() - timedelta(days=1)
    lines = [
        "city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at"
    ]
    synced: list[str] = []
    for code in codes:
        city = cities.get(code)
        if city is None:
            continue
        try:
            rows = fetcher(city.name, end_date=end_date) if fetcher else fetch_weather_rows(
                city.name, end_date=end_date
            )
        except Exception:
            continue
        if not rows:
            continue
        synced.append(city.name)
        for metric_date, fit in rows:
            available = f"{(metric_date + timedelta(days=1)).isoformat()}T08:00:00+08:00"
            lines.append(
                f"{code},{metric_date.isoformat()},weather_fit,{fit},{available},"
                f"https://open-meteo.com/en/docs,{available},{available}"
            )

    if len(lines) == 1:
        return {"synced_cities": [], "observation_count": 0, "dataset_id": None}

    content = ("\n".join(lines) + "\n").encode("utf-8")
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"official-weather-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.csv"
    (upload_dir / stored_name).write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    existing = await db.execute(select(Dataset).where(Dataset.sha256 == digest))
    if existing.scalar_one_or_none() is not None:
        return {
            "synced_cities": synced,
            "observation_count": 0,
            "dataset_id": None,
            "note": "weather snapshot unchanged since last sync",
        }

    dataset, _already = await ingestion.create_dataset(
        db,
        source_type="official_sync",
        source_name="Open-Meteo 官方开放气象同步",
        legal_basis="Open-Meteo 免费开放接口（CC-BY 4.0），城市级聚合",
        original_filename=stored_name,
        stored_filename=stored_name,
        sha256=digest,
        byte_size=len(content),
        uploaded_by=None,
    )
    await ingestion.validate_dataset(db, dataset, upload_dir=upload_dir, max_rows=200_000)
    if dataset.status != "valid":
        raise AppError(
            code="WEATHER_SYNC_INVALID",
            message="Weather sync failed the data contract; nothing was committed.",
            status_code=502,
        )
    version, _committed = await ingestion.commit_dataset(
        db,
        dataset,
        upload_dir=upload_dir,
        max_rows=200_000,
        committed_by=OFFICIAL_SYSTEM_ACTOR,
    )
    return {
        "synced_cities": synced,
        "observation_count": version.observation_count,
        "dataset_id": str(dataset.id),
    }


async def run_sync(
    db: AsyncSession, source: DataSource, *, snapshot_dir: Path, upload_dir: Path
) -> dict[str, Any]:
    if source.kind == "open_meteo_weather":
        result = await sync_open_meteo_weather(db, upload_dir=upload_dir)
    elif source.kind == "admin_divisions":
        snapshot = snapshot_dir / "admin_divisions_cn.csv"
        result = await sync_admin_divisions(db, snapshot_path=snapshot)
    else:
        raise AppError(
            code="UNKNOWN_SOURCE_KIND",
            message=f"No sync adapter for {source.kind}.",
            status_code=400,
        )
    source.last_synced_at = datetime.now(UTC)
    source.last_status = "succeeded"
    source.last_summary = json.dumps(result, ensure_ascii=False, default=str)[:300]
    await db.flush()
    return result


async def ensure_sources_seeded(db: AsyncSession) -> list[DataSource]:
    result = await db.execute(select(DataSource))
    existing = {source.kind: source for source in result.scalars()}
    seeds = [
        DataSource(
            kind="admin_divisions",
            label="行政区划（地级）· 民政部公开代码派生快照",
            source_url="https://github.com/modood/Administrative-divisions-of-China",
        ),
        DataSource(
            kind="open_meteo_weather",
            label="Open-Meteo 历史气象（免费开放接口）",
            source_url="https://open-meteo.com/en/docs",
        ),
    ]
    added = [seed for seed in seeds if seed.kind not in existing]
    if added:
        db.add_all(added)
        await db.flush()
    result = await db.execute(select(DataSource).order_by(DataSource.kind))
    return list(result.scalars())

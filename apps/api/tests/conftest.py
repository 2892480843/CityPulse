import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from citypulse.identity.service import create_user, ensure_roles_seeded
from citypulse.main import create_app
from citypulse.shared.orm import Base

ADMIN_PASSWORD = "guard-root-9173"
ANALYST_PASSWORD = "signal-keeper-88"
OPERATOR_PASSWORD = "market-ops-3345"


def _build_database(tmp_path: Path) -> str:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'citypulse-test.db'}"
    sync_engine = sa.create_engine(f"sqlite:///{tmp_path / 'citypulse-test.db'}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    return database_url


def _seed_reference_data(database_url: str) -> None:
    sync_engine = sa.create_engine(database_url.replace("+aiosqlite", ""))
    with sync_engine.begin() as connection:
        for code, name, province in (
            ("222401", "延吉", "吉林"),
            ("370300", "淄博", "山东"),
            ("620500", "天水", "甘肃"),
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO cities (id, code, name, province) "
                    "VALUES (lower(hex(randomblob(16))), :code, :name, :province)"
                ),
                {"code": code, "name": name, "province": province},
            )
    sync_engine.dispose()


async def _seed_users(database_url: str) -> None:
    engine = create_async_engine(database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        await ensure_roles_seeded(db)
        await create_user(
            db,
            username="admin",
            password=ADMIN_PASSWORD,
            display_name="管理员",
            roles=["admin"],
        )
        await create_user(
            db,
            username="analyst",
            password=ANALYST_PASSWORD,
            display_name="分析师",
            roles=["analyst"],
        )
        await create_user(
            db,
            username="operator",
            password=OPERATOR_PASSWORD,
            display_name="运营人员",
            roles=["operator"],
        )
        await db.commit()
    await engine.dispose()


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = _build_database(tmp_path)
    _seed_reference_data(database_url)
    asyncio.run(_seed_users(database_url))

    app = create_app()
    engine = create_async_engine(database_url)
    with TestClient(app) as client:
        app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        yield client
    asyncio.run(engine.dispose())


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    csrf = client.cookies.get("citypulse_csrf")
    assert csrf is not None
    return {"X-CSRF-Token": csrf}


@pytest.fixture
def admin_client(app_client: TestClient) -> TestClient:
    login(app_client, "admin", ADMIN_PASSWORD)
    return app_client


@pytest.fixture
def analyst_client(app_client: TestClient) -> TestClient:
    login(app_client, "analyst", ANALYST_PASSWORD)
    return app_client


@pytest.fixture
def operator_client(app_client: TestClient) -> TestClient:
    login(app_client, "operator", OPERATOR_PASSWORD)
    return app_client


VALID_CSV = "\n".join(
    [
        "city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at",
        "222401,2026-07-01,content_growth,40.5,2026-07-02T08:00:00+08:00,https://example.gov.cn/a,2026-07-01T18:00:00+08:00,2026-07-02T08:00:00+08:00",
        "222401,2026-07-02,content_growth,42.5,2026-07-03T08:00:00+08:00,https://example.gov.cn/a,2026-07-02T18:00:00+08:00,2026-07-03T08:00:00+08:00",
        "370300,2026-07-01,content_growth,30.0,2026-07-02T08:00:00+08:00,https://example.gov.cn/b,2026-07-01T18:00:00+08:00,2026-07-02T08:00:00+08:00",
    ]
) + "\n"


def commit_dataset(client: TestClient, csv_text: str, name: str = "seed.csv") -> str:
    import io

    headers = login(client, "analyst", ANALYST_PASSWORD)
    created = client.post(
        "/api/v1/datasets",
        files={"file": (name, io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
        data={"source_name": "测试种子", "legal_basis": "公开统计"},
        headers=headers,
    )
    assert created.status_code in (200, 201), created.text
    dataset_id = created.json()["dataset"]["id"]
    validated = client.post(f"/api/v1/datasets/{dataset_id}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    assert validated.json()["dataset"]["status"] == "valid", validated.json()
    committed = client.post(f"/api/v1/datasets/{dataset_id}/commit", headers=headers)
    assert committed.status_code == 200, committed.text
    return dataset_id


T0 = "2026-07-15"


def fresh_csv() -> str:
    """Recent observations for a high-signal target and a quiet control."""
    from datetime import date, timedelta

    base = date.today() - timedelta(days=2)
    lines = [
        "city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at"
    ]
    target_levels = {
        "content_growth": 84,
        "search_growth": 79,
        "event_trigger": 76,
        "accessibility": 66,
        "supply_capacity": 61,
        "weather_fit": 72,
        "novelty": 86,
        "cross_region_spread": 82,
    }
    control_levels = {
        "content_growth": 26,
        "search_growth": 22,
        "event_trigger": 30,
        "accessibility": 64,
        "supply_capacity": 66,
        "weather_fit": 70,
        "novelty": 56,
        "cross_region_spread": 28,
    }
    for day_offset in (2, 1):
        day = base + timedelta(days=2 - day_offset)
        available = f"{(day + timedelta(days=1)).isoformat()}T08:00:00+08:00"
        published = f"{day.isoformat()}T18:00:00+08:00"
        for city, levels in (("222401", target_levels), ("370300", control_levels)):
            for metric, value in levels.items():
                lines.append(
                    f"{city},{day.isoformat()},{metric},{value},{available},"
                    f"https://example.gov.cn/{city[4:]},{published},{available}"
                )
            lines.append(
                f"{city},{day.isoformat()},risk_pressure,28,{available},"
                f"https://example.gov.cn/{city[4:]},{published},{available}"
            )
    return "\n".join(lines) + "\n"


def backtest_csv(t0: str = T0) -> str:
    """Target 222401 ramps across cutoffs; control 370300 stays low.

    available_at is the morning after each metric_date, so a cutoff only sees
    rows that were actually obtainable before it. The target crosses the
    action threshold between the T0-14 and T0-7 cutoffs; the control never
    crosses it.
    """
    from datetime import date, timedelta

    start = date.fromisoformat(t0) - timedelta(days=45)
    end = date.fromisoformat(t0) - timedelta(days=1)
    lines = [
        "city_code,metric_date,metric_name,value,available_at,source_url,published_at,observed_at"
    ]
    day = start
    while day <= end:
        offset = (date.fromisoformat(t0) - day).days
        ramp = max(0.0, min(1.0, (30 - offset) / 22))
        target_levels = {
            "content_growth": 16 + 68 * ramp,
            "search_growth": 15 + 64 * ramp,
            "event_trigger": 30 + 46 * ramp,
            "accessibility": 66,
            "supply_capacity": 61,
            "weather_fit": 72,
            "novelty": 86,
            "cross_region_spread": 20 + 62 * ramp,
        }
        control_levels = {
            "content_growth": 26,
            "search_growth": 22,
            "event_trigger": 30,
            "accessibility": 64,
            "supply_capacity": 66,
            "weather_fit": 70,
            "novelty": 56,
            "cross_region_spread": 28,
        }
        available = f"{(day + timedelta(days=1)).isoformat()}T08:00:00+08:00"
        published = f"{day.isoformat()}T18:00:00+08:00"
        for city, levels in (("222401", target_levels), ("370300", control_levels)):
            for metric, value in levels.items():
                lines.append(
                    f"{city},{day.isoformat()},{metric},{round(value, 1)},{available},"
                    f"https://example.gov.cn/{city[4:]},{published},{available}"
                )
            lines.append(
                f"{city},{day.isoformat()},risk_pressure,28,{available},"
                f"https://example.gov.cn/{city[4:]},{published},{available}"
            )
        day += timedelta(days=1)
    return "\n".join(lines) + "\n"

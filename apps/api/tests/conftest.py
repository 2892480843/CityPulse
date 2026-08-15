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

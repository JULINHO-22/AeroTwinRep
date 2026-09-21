import asyncio

from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings
from app.db.session import is_database_available
from app.main import app


async def get_health() -> tuple[int, dict[str, str]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        return response.status_code, response.json()


def test_health_in_demo_mode_exposes_demo_details() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(demo_mode=True)
    app.dependency_overrides[is_database_available] = lambda: True

    status_code, body = asyncio.run(get_health())

    assert status_code == 200
    assert body == {
        "status": "ok",
        "environment": "DEMO",
        "database": "connected",
    }
    app.dependency_overrides.clear()


def test_health_outside_demo_mode_is_neutral() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(demo_mode=False)
    app.dependency_overrides[is_database_available] = lambda: True

    status_code, body = asyncio.run(get_health())

    assert status_code == 200
    assert body == {"status": "ok"}
    app.dependency_overrides.clear()


def test_health_is_degraded_when_database_is_unavailable() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(demo_mode=True)
    app.dependency_overrides[is_database_available] = lambda: False

    status_code, body = asyncio.run(get_health())

    assert status_code == 503
    assert body == {
        "status": "degraded",
        "environment": "DEMO",
        "database": "unavailable",
    }
    app.dependency_overrides.clear()

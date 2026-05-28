"""Integration tests for /health and root endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_root_returns_metadata() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "E.L.O"
    assert "version" in body


@pytest.mark.asyncio
async def test_health_returns_ok_with_db_and_postgis() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"] == "ok"
    assert "USE_GEOS" in body["checks"]["postgis"]

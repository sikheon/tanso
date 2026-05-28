"""Integration tests for /api/v1/vehicles CRUD (no external APIs)."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_vehicles_returns_seeded_data() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/vehicles")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 7  # 7 seeded vehicles
    # Every item has the required keys
    for v in items:
        assert v["fuel_type"] in {"gasoline", "diesel", "lpg", "hybrid", "electric"}
        assert v["emission_factor_g_per_km"] is not None


@pytest.mark.asyncio
async def test_get_vehicle_by_id() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/vehicles/1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert body["model"]


@pytest.mark.asyncio
async def test_get_missing_vehicle_returns_404() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/vehicles/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_vehicle_create_update_delete_roundtrip() -> None:
    async with _client() as ac:
        # Create
        r = await ac.post(
            "/api/v1/vehicles",
            json={
                "plate": "TEST-API-CRUD",
                "model": "테스트 차량",
                "fuel_type": "hybrid",
                "vehicle_class": "suv",
                "year_produced": 2025,
            },
        )
        assert r.status_code == 201
        body = r.json()
        vid = body["id"]
        assert body["emission_factor_g_per_km"] == 99.0  # auto-mapped hybrid/suv

        # Update
        r = await ac.patch(f"/api/v1/vehicles/{vid}", json={"model": "수정됨"})
        assert r.status_code == 200
        assert r.json()["model"] == "수정됨"

        # Delete (hard)
        r = await ac.delete(f"/api/v1/vehicles/{vid}")
        assert r.status_code == 204

        # Verify gone
        r = await ac.get(f"/api/v1/vehicles/{vid}")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_vehicle_create_with_unknown_fuel_returns_400() -> None:
    async with _client() as ac:
        r = await ac.post(
            "/api/v1/vehicles",
            json={"fuel_type": "unobtainium", "vehicle_class": "sedan"},
        )
    assert r.status_code == 400
    assert "emission factor" in r.json()["detail"].lower()

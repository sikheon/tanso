"""Integration tests for Run CRUD + /stats/summary + /emission-factors.

These tests rely on the DB containing some Runs from earlier integration
smoke tests; if the table is empty they verify only the empty-state
contract.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_runs_returns_pagination_envelope() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/runs?limit=5&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_get_missing_run_returns_404() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/runs/9999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_emission_factors_list_returns_15_seed_rows() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/emission-factors")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 15  # seed total
    assert any(ef["fuel_type"] == "electric" and ef["vehicle_class"] == "sedan" for ef in items)


@pytest.mark.asyncio
async def test_stats_summary_returns_aggregate_shape() -> None:
    async with _client() as ac:
        r = await ac.get("/api/v1/stats/summary")
    assert r.status_code == 200
    body = r.json()
    for key in ("total_runs", "total_distance_km", "total_co2_kg", "by_engine", "by_vehicle_class"):
        assert key in body
    assert isinstance(body["by_engine"], list)
    assert isinstance(body["by_vehicle_class"], list)

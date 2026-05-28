"""Unit tests for RoutingAdapter: parallel calls + graceful failure."""

import pytest

from src.routing.adapter import RoutingAdapter
from src.routing.base import RoutingProvider, RoutingProviderError
from src.routing.schemas import (
    EngineName,
    LatLng,
    Objective,
    Route,
    RouteRequest,
)


class _FakeProvider(RoutingProvider):
    def __init__(self, engine: EngineName, routes: list[Route] | None = None, error: Exception | None = None) -> None:
        self.name = engine
        self._routes = routes or []
        self._error = error
        self.call_count = 0

    async def get_routes(self, request: RouteRequest) -> list[Route]:
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return self._routes


def _route(engine: EngineName, dist: float) -> Route:
    return Route(
        engine=engine,
        objective=Objective.RECOMMEND,
        total_distance_m=dist,
        total_duration_s=int(dist / 10),
    )


def _req() -> RouteRequest:
    return RouteRequest(
        origin=LatLng(lat=37.5, lng=126.9),
        destination=LatLng(lat=35.1, lng=129.0),
    )


@pytest.mark.asyncio
async def test_adapter_aggregates_routes_from_all_providers() -> None:
    p1 = _FakeProvider(EngineName.KAKAO, [_route(EngineName.KAKAO, 1000)])
    p2 = _FakeProvider(EngineName.ORS, [_route(EngineName.ORS, 1100), _route(EngineName.ORS, 1200)])
    adapter = RoutingAdapter([p1, p2])

    result = await adapter.get_all_routes(_req())

    assert len(result.routes) == 3
    assert {r.engine for r in result.routes} == {EngineName.KAKAO, EngineName.ORS}
    assert result.per_engine[EngineName.KAKAO].ok
    assert result.per_engine[EngineName.ORS].ok
    assert result.any_success is True
    assert result.warnings == []


@pytest.mark.asyncio
async def test_adapter_one_provider_failure_does_not_break_others() -> None:
    p1 = _FakeProvider(EngineName.KAKAO, [_route(EngineName.KAKAO, 1000)])
    p2 = _FakeProvider(EngineName.ORS, error=RoutingProviderError("ORS down"))
    adapter = RoutingAdapter([p1, p2])

    result = await adapter.get_all_routes(_req())

    assert len(result.routes) == 1
    assert result.routes[0].engine is EngineName.KAKAO
    assert not result.per_engine[EngineName.ORS].ok
    assert "ORS down" in result.per_engine[EngineName.ORS].error
    assert result.any_success is True
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_adapter_all_providers_fail_yields_empty_with_warnings() -> None:
    p1 = _FakeProvider(EngineName.KAKAO, error=RoutingProviderError("kakao down"))
    p2 = _FakeProvider(EngineName.ORS, error=RoutingProviderError("ors down"))
    adapter = RoutingAdapter([p1, p2])

    result = await adapter.get_all_routes(_req())

    assert result.routes == []
    assert result.any_success is False
    assert len(result.warnings) == 2


@pytest.mark.asyncio
async def test_adapter_unexpected_exception_is_captured() -> None:
    p = _FakeProvider(EngineName.KAKAO, error=RuntimeError("boom"))
    adapter = RoutingAdapter([p])

    result = await adapter.get_all_routes(_req())

    assert result.routes == []
    assert "RuntimeError" in result.per_engine[EngineName.KAKAO].error


def test_adapter_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError):
        RoutingAdapter([])

"""Unit tests for routing common schemas."""

import pytest
from pydantic import ValidationError

from src.routing.schemas import (
    EngineName,
    LatLng,
    Objective,
    Route,
    RouteRequest,
    Segment,
)


def test_latlng_tuple_order_lng_lat() -> None:
    ll = LatLng(lat=37.5, lng=126.9)
    assert ll.as_tuple_lng_lat() == (126.9, 37.5)


def test_latlng_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        LatLng(lat=200, lng=0)


def test_segment_derives_avg_speed() -> None:
    s = Segment(
        seq=0,
        from_point=LatLng(lat=0, lng=0),
        to_point=LatLng(lat=0, lng=1),
        distance_m=50_000,
        duration_s=1800,
    )
    # 50 km in 0.5h = 100 km/h
    assert s.avg_speed_kmh == 100.0


def test_segment_keeps_explicit_speed() -> None:
    s = Segment(
        seq=0,
        from_point=LatLng(lat=0, lng=0),
        to_point=LatLng(lat=0, lng=1),
        distance_m=50_000,
        duration_s=1800,
        avg_speed_kmh=42.5,
    )
    assert s.avg_speed_kmh == 42.5


def test_segment_zero_duration_yields_none_speed() -> None:
    s = Segment(
        seq=0,
        from_point=LatLng(lat=0, lng=0),
        to_point=LatLng(lat=0, lng=1),
        distance_m=0,
        duration_s=0,
    )
    assert s.avg_speed_kmh is None


def test_route_distance_km() -> None:
    r = Route(
        engine=EngineName.KAKAO,
        objective=Objective.RECOMMEND,
        total_distance_m=12_345,
        total_duration_s=60,
    )
    assert r.total_distance_km == pytest.approx(12.345)


def test_request_alternatives_bounds() -> None:
    o = LatLng(lat=0, lng=0)
    d = LatLng(lat=1, lng=1)
    RouteRequest(origin=o, destination=d, alternatives=1)
    RouteRequest(origin=o, destination=d, alternatives=3)
    with pytest.raises(ValidationError):
        RouteRequest(origin=o, destination=d, alternatives=0)
    with pytest.raises(ValidationError):
        RouteRequest(origin=o, destination=d, alternatives=4)

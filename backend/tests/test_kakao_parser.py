"""Unit tests for Kakao response normalization (no real API)."""

import pytest

from src.routing.base import RoutingProviderUnavailable
from src.routing.kakao import _parse_route, _vertexes_to_polyline
from src.routing.schemas import EngineName, Objective


def test_vertexes_chunking() -> None:
    flat = [126.0, 37.0, 127.0, 38.0, 128.0, 39.0]
    poly = _vertexes_to_polyline(flat)
    assert poly == [(37.0, 126.0), (38.0, 127.0), (39.0, 128.0)]


def test_vertexes_empty_or_odd_returns_empty() -> None:
    assert _vertexes_to_polyline([]) == []
    assert _vertexes_to_polyline([126.0, 37.0, 127.0]) == []  # odd count


def test_parse_route_minimal() -> None:
    raw = {
        "result_code": 0,
        "summary": {"distance": 5000, "duration": 600},
        "sections": [
            {
                "distance": 5000,
                "duration": 600,
                "roads": [
                    {
                        "name": "강남대로",
                        "distance": 1200,
                        "duration": 180,
                        "traffic_speed": 24.0,
                        "vertexes": [127.0, 37.0, 127.01, 37.01, 127.02, 37.02],
                    },
                    {
                        "name": "올림픽대로",
                        "distance": 3800,
                        "duration": 420,
                        "traffic_speed": 65.0,
                        "vertexes": [127.02, 37.02, 128.0, 37.5],
                    },
                ],
            }
        ],
    }
    route = _parse_route(raw, priority="recommend", index=0)
    assert route.engine is EngineName.KAKAO
    assert route.objective is Objective.RECOMMEND
    assert route.total_distance_m == 5000
    assert route.total_duration_s == 600
    assert len(route.segments) == 2
    assert route.segments[0].road_type == "강남대로"
    assert route.segments[0].avg_speed_kmh == 24.0
    assert route.segments[1].road_type == "올림픽대로"
    # Polyline = 3 + 2 = 5 points
    assert len(route.polyline) == 5
    assert route.polyline[0] == (37.0, 127.0)


def test_parse_route_alternative_index_tags_alternative() -> None:
    raw = {
        "result_code": 0,
        "summary": {"distance": 100, "duration": 10},
        "sections": [
            {
                "roads": [
                    {
                        "name": "x",
                        "distance": 100,
                        "duration": 10,
                        "vertexes": [127.0, 37.0, 127.01, 37.01],
                    }
                ]
            }
        ],
    }
    alt = _parse_route(raw, priority="recommend", index=1)
    assert alt.objective is Objective.ALTERNATIVE


def test_parse_route_failure_code_raises() -> None:
    raw = {"result_code": 104, "result_msg": "출발지/도착지가 너무 가깝습니다"}
    with pytest.raises(RoutingProviderUnavailable):
        _parse_route(raw, priority="recommend", index=0)


def test_parse_route_drops_segments_with_too_few_vertexes() -> None:
    raw = {
        "result_code": 0,
        "summary": {"distance": 100, "duration": 10},
        "sections": [
            {
                "roads": [
                    {"name": "bad", "vertexes": [127.0, 37.0]},  # 1 point - dropped
                    {
                        "name": "good",
                        "distance": 100,
                        "duration": 10,
                        "vertexes": [127.0, 37.0, 127.01, 37.01],
                    },
                ]
            }
        ],
    }
    route = _parse_route(raw, priority="recommend", index=0)
    assert len(route.segments) == 1
    assert route.segments[0].road_type == "good"

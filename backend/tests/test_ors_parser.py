"""Unit tests for OpenRouteService GeoJSON normalization (no real API)."""

import pytest

from src.routing.base import RoutingProviderUnavailable
from src.routing.ors import _parse_feature
from src.routing.schemas import EngineName, Objective


def _sample_feature() -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [127.0, 37.0],
                [127.01, 37.01],
                [127.02, 37.02],
                [127.10, 37.10],
                [128.0, 37.5],
            ],
        },
        "properties": {
            "summary": {"distance": 5000.5, "duration": 600},
            "segments": [
                {
                    "distance": 5000.5,
                    "duration": 600,
                    "steps": [
                        {
                            "distance": 1200,
                            "duration": 180,
                            "name": "Gangnam-daero",
                            "way_points": [0, 2],
                        },
                        {
                            "distance": 3800.5,
                            "duration": 420,
                            "name": "Olympic-daero",
                            "way_points": [2, 4],
                        },
                    ],
                }
            ],
        },
    }


def test_parse_feature_basic() -> None:
    route = _parse_feature(_sample_feature(), priority="recommend", index=0)
    assert route.engine is EngineName.ORS
    assert route.objective is Objective.RECOMMEND
    assert route.total_distance_m == pytest.approx(5000.5)
    assert route.total_duration_s == 600
    assert len(route.polyline) == 5
    assert route.polyline[0] == (37.0, 127.0)  # converted lng/lat -> lat/lng
    assert len(route.segments) == 2
    assert route.segments[0].road_type == "Gangnam-daero"
    # avg speed derived: 1.2 km / (180/3600 h) = 24.0 km/h
    assert route.segments[0].avg_speed_kmh == pytest.approx(24.0, rel=0.01)


def test_parse_feature_index_tags_alternative() -> None:
    route = _parse_feature(_sample_feature(), priority="recommend", index=2)
    assert route.objective is Objective.ALTERNATIVE


def test_parse_feature_empty_geometry_raises() -> None:
    bad = {"geometry": {"coordinates": []}, "properties": {"summary": {}}}
    with pytest.raises(RoutingProviderUnavailable):
        _parse_feature(bad, priority="recommend", index=0)


def test_parse_feature_skips_steps_with_invalid_waypoints() -> None:
    feat = _sample_feature()
    feat["properties"]["segments"][0]["steps"].insert(
        0,
        {"distance": 0, "duration": 0, "way_points": [0, 0]},  # same index -> dropped
    )
    feat["properties"]["segments"][0]["steps"].insert(
        0,
        {"distance": 0, "duration": 0, "way_points": [0, 99]},  # out of range -> dropped
    )
    route = _parse_feature(feat, priority="recommend", index=0)
    assert len(route.segments) == 2  # only the two valid ones

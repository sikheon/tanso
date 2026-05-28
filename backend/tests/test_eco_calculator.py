"""Unit tests for EmissionCalculator."""

import pytest

from src.eco.calculator import EmissionCalculator
from src.eco.factors import EcoFactorBook, EmissionFactorView, SpeedBinView
from src.routing.schemas import EngineName, LatLng, Objective, Route, Segment


def _book() -> EcoFactorBook:
    return EcoFactorBook(
        emissions=[
            EmissionFactorView("gasoline", "sedan", 100.0, source="test"),
            EmissionFactorView("diesel", "truck_1t", 200.0, source="test"),
        ],
        speed_bins=[
            SpeedBinView(0, 40, 1.2, "all"),
            SpeedBinView(40, 80, 1.0, "all"),
            SpeedBinView(80, 999, 1.1, "all"),
        ],
    )


def _segment(seq: int, dist_m: float, dur_s: int, speed: float | None = None) -> Segment:
    p = LatLng(lat=0, lng=0)
    q = LatLng(lat=0, lng=1)
    return Segment(
        seq=seq, from_point=p, to_point=q,
        distance_m=dist_m, duration_s=dur_s, avg_speed_kmh=speed,
    )


def _route(engine: EngineName, segments: list[Segment]) -> Route:
    total_dist = sum(s.distance_m for s in segments)
    total_dur = sum(s.duration_s for s in segments)
    return Route(
        engine=engine,
        objective=Objective.RECOMMEND,
        total_distance_m=total_dist,
        total_duration_s=total_dur,
        segments=segments,
    )


def test_single_segment_at_neutral_speed() -> None:
    """10 km × 100 g/km × 1.0 multiplier = 1000 g."""
    calc = EmissionCalculator(_book())
    route = _route(EngineName.KAKAO, [_segment(0, 10000, 600, speed=60.0)])
    result = calc.calculate(route, "gasoline", "sedan")
    assert result.total_co2_g == pytest.approx(1000.0)
    assert result.base_g_per_km == 100.0
    assert result.engine_has_live_traffic is True
    assert result.segments[0].speed_multiplier == 1.0


def test_low_speed_increases_emissions() -> None:
    """10 km × 100 g/km × 1.2 multiplier (slow bin) = 1200 g."""
    calc = EmissionCalculator(_book())
    route = _route(EngineName.KAKAO, [_segment(0, 10000, 1800, speed=20.0)])
    result = calc.calculate(route, "gasoline", "sedan")
    assert result.total_co2_g == pytest.approx(1200.0)


def test_multiple_segments_sum() -> None:
    """5 km @ 60 km/h (×1.0) + 5 km @ 25 km/h (×1.2)
       = 5 × 100 + 5 × 100 × 1.2 = 500 + 600 = 1100 g."""
    calc = EmissionCalculator(_book())
    route = _route(
        EngineName.KAKAO,
        [_segment(0, 5000, 300, speed=60), _segment(1, 5000, 720, speed=25)],
    )
    result = calc.calculate(route, "gasoline", "sedan")
    assert result.total_co2_g == pytest.approx(1100.0)
    assert len(result.segments) == 2


def test_truck_uses_truck_factor() -> None:
    calc = EmissionCalculator(_book())
    route = _route(EngineName.ORS, [_segment(0, 10000, 600, speed=60.0)])
    result = calc.calculate(route, "diesel", "truck_1t")
    # 10 km × 200 g/km × 1.0 = 2000 g
    assert result.total_co2_g == pytest.approx(2000.0)
    assert result.base_g_per_km == 200.0
    assert result.engine_has_live_traffic is False


def test_avg_g_per_km_property() -> None:
    calc = EmissionCalculator(_book())
    route = _route(EngineName.KAKAO, [_segment(0, 10000, 600, speed=60.0)])
    result = calc.calculate(route, "gasoline", "sedan")
    assert result.avg_g_per_km == pytest.approx(100.0)


def test_route_with_no_segments_uses_total_fallback() -> None:
    """Some engines may return only summary without segments."""
    calc = EmissionCalculator(_book())
    route = Route(
        engine=EngineName.ORS,
        objective=Objective.RECOMMEND,
        total_distance_m=10000,
        total_duration_s=600,  # avg 60 km/h → mult 1.0
        segments=[],
    )
    result = calc.calculate(route, "gasoline", "sedan")
    # 10 km × 100 g/km × 1.0 = 1000 g
    assert result.total_co2_g == pytest.approx(1000.0)
    assert result.segments == []

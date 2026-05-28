"""Unit tests for Min-Max normalization + weighted scoring."""

import pytest

from src.eco.normalizer import (
    NormalizedRoute,
    Weights,
    rank_recommend,
    score_candidates,
)
from src.routing.schemas import EngineName, LatLng, Objective, Route


def _route(engine: EngineName, dist_m: float, dur_s: int) -> Route:
    return Route(
        engine=engine,
        objective=Objective.RECOMMEND,
        total_distance_m=dist_m,
        total_duration_s=dur_s,
    )


def test_weights_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        Weights(distance=-0.1, duration=0.5, co2=0.6)
    with pytest.raises(ValueError):
        Weights(distance=1.5, duration=-0.5, co2=0)


def test_weights_rejects_bad_sum() -> None:
    with pytest.raises(ValueError):
        Weights(distance=0.5, duration=0.5, co2=0.5)  # sum = 1.5


def test_weights_balanced_sums_to_one() -> None:
    w = Weights.balanced()
    assert abs(w.distance + w.duration + w.co2 - 1.0) < 1e-9


def test_score_single_route_yields_zero_norms() -> None:
    routes = [_route(EngineName.KAKAO, 10000, 600)]
    scored = score_candidates(routes, [1000.0], Weights.balanced())
    assert len(scored) == 1
    assert scored[0].d_norm == 0
    assert scored[0].t_norm == 0
    assert scored[0].e_norm == 0
    assert scored[0].score == 0


def test_score_two_routes_min_max() -> None:
    """Best on every axis = score 0, worst on every axis = score 1."""
    routes = [
        _route(EngineName.KAKAO, 10000, 600),   # all minima
        _route(EngineName.ORS, 20000, 1200),    # all maxima
    ]
    scored = score_candidates(routes, [1000.0, 2000.0], Weights.balanced())
    assert scored[0].d_norm == 0
    assert scored[0].t_norm == 0
    assert scored[0].e_norm == 0
    assert scored[0].score == pytest.approx(0.0)
    assert scored[1].d_norm == 1
    assert scored[1].t_norm == 1
    assert scored[1].e_norm == 1
    assert scored[1].score == pytest.approx(1.0)


def test_score_mixed_winners() -> None:
    """A route that wins on CO2 but loses on time, with co2-heavy weights, should win."""
    r_fast = _route(EngineName.KAKAO, 30000, 1000)  # short time, long distance, ?
    r_eco = _route(EngineName.ORS, 32000, 1200)     # 2km longer, 200s slower, less CO2
    weights = Weights(distance=0.1, duration=0.1, co2=0.8)
    scored = score_candidates([r_fast, r_eco], [5000.0, 4500.0], weights)
    ranked = rank_recommend(scored)
    assert ranked[0].route is r_eco


def test_score_length_mismatch_raises() -> None:
    routes = [_route(EngineName.KAKAO, 1, 1)]
    with pytest.raises(ValueError):
        score_candidates(routes, [1.0, 2.0], Weights.balanced())


def test_score_empty_input_returns_empty() -> None:
    assert score_candidates([], [], Weights.balanced()) == []


def test_rank_recommend_ascending() -> None:
    routes = [
        _route(EngineName.KAKAO, 12000, 700),
        _route(EngineName.ORS, 10000, 600),    # all minima
        _route(EngineName.ORS, 15000, 1000),   # all maxima
    ]
    scored = score_candidates(routes, [1300, 1000, 1700], Weights.balanced())
    ranked = rank_recommend(scored)
    assert ranked[0].route.total_distance_m == 10000
    assert ranked[-1].route.total_distance_m == 15000

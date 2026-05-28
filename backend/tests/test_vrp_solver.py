"""Unit tests for VRPSolver — deterministic small-N instances."""

import pytest

from src.routing.schemas import LatLng
from src.vrp.matrix import VRPMatrices
from src.vrp.schemas import VRPObjective
from src.vrp.solver import VRPSolver


def _ll(i: int) -> LatLng:
    return LatLng(lat=37.5 + i * 0.01, lng=126.97 + i * 0.01)


def _square_matrices() -> VRPMatrices:
    """4-node symmetric grid: depot(0) at corner, jobs(1,2,3) at other corners.

    Layout (square of side 10):
        0 ---10--- 1
        |          |
       10         10
        |          |
        3 ---10--- 2

    Optimal tour starting/ending at 0 visits 0->1->2->3->0 (perimeter, total 40)
    or its reverse. Diagonal costs sqrt(200) ≈ 14.14, scaled to 14.
    """
    INF = 0  # unused (i==j)
    D = [
        [INF, 10, 14, 10],
        [10, INF, 10, 14],
        [14, 10, INF, 10],
        [10, 14, 10, INF],
    ]
    locations = [_ll(i) for i in range(4)]
    dist = [[float(v) for v in row] for row in D]
    dur = [[int(v) for v in row] for row in D]
    co2 = [[float(v) for v in row] for row in D]
    return VRPMatrices(
        locations=locations, distance_m=dist, duration_s=dur, co2_g=co2
    )


def test_solver_returns_all_jobs_visited() -> None:
    m = _square_matrices()
    solver = VRPSolver(time_limit_s=2)
    out = solver.solve(m, VRPObjective.DISTANCE)
    assert out.result.feasible
    # Jobs are indices 0,1,2 (since depot=node 0, jobs=nodes 1,2,3)
    assert sorted(out.result.visit_order) == [0, 1, 2]


def test_solver_perimeter_tour_total_40() -> None:
    m = _square_matrices()
    out = VRPSolver(time_limit_s=2).solve(m, VRPObjective.DISTANCE)
    # Perimeter tour: 4 sides × 10 = 40
    assert out.result.total_distance_m == pytest.approx(40.0)


def test_solver_minimum_instance_one_job() -> None:
    """Depot + 1 job => trip 0->1->0."""
    locations = [_ll(0), _ll(1)]
    D = [[0, 50], [50, 0]]
    m = VRPMatrices(
        locations=locations,
        distance_m=[[float(v) for v in row] for row in D],
        duration_s=[[int(v) for v in row] for row in D],
        co2_g=[[float(v) for v in row] for row in D],
    )
    out = VRPSolver(time_limit_s=2).solve(m, VRPObjective.DISTANCE)
    assert out.result.visit_order == [0]
    assert out.result.total_distance_m == 100  # 50 out + 50 back


def test_solver_rejects_single_location() -> None:
    locations = [_ll(0)]
    m = VRPMatrices(
        locations=locations, distance_m=[[0.0]], duration_s=[[0]], co2_g=[[0.0]]
    )
    with pytest.raises(ValueError):
        VRPSolver(time_limit_s=2).solve(m, VRPObjective.DISTANCE)


def test_objectives_can_yield_different_orders() -> None:
    """Pick a matrix where the distance-optimal and CO2-optimal paths differ."""
    locations = [_ll(i) for i in range(4)]
    # Distance matrix: prefers 0->1->2->3
    dist = [
        [0, 1, 5, 5],
        [1, 0, 1, 5],
        [5, 1, 0, 1],
        [5, 5, 1, 0],
    ]
    # CO2 matrix: arcs 0->1 and 1->2 are unusually high (e.g., uphill)
    co2 = [
        [0, 100, 5, 5],
        [100, 0, 100, 5],
        [5, 100, 0, 1],
        [5, 5, 1, 0],
    ]
    m = VRPMatrices(
        locations=locations,
        distance_m=[[float(v) for v in row] for row in dist],
        duration_s=[[int(v) for v in row] for row in dist],
        co2_g=[[float(v) for v in row] for row in co2],
    )
    solver = VRPSolver(time_limit_s=2)
    dist_result = solver.solve(m, VRPObjective.DISTANCE).result
    co2_result = solver.solve(m, VRPObjective.CO2).result
    # Both visit all 3 jobs
    assert sorted(dist_result.visit_order) == [0, 1, 2]
    assert sorted(co2_result.visit_order) == [0, 1, 2]
    # Total CO2 for the CO2-optimal route must be <= the distance-optimal route's CO2
    assert co2_result.total_co2_g <= dist_result.total_co2_g


def test_solver_reports_aggregate_totals_across_all_matrices() -> None:
    m = _square_matrices()
    out = VRPSolver(time_limit_s=2).solve(m, VRPObjective.DISTANCE).result
    # All three matrices equal in this fixture -> same totals
    assert out.total_distance_m == pytest.approx(out.total_duration_s)
    assert out.total_distance_m == pytest.approx(out.total_co2_g)


def test_solver_invalid_time_limit_rejected() -> None:
    with pytest.raises(ValueError):
        VRPSolver(time_limit_s=0)

"""OR-Tools VRP solver wrapper.

Given pre-computed distance / duration / CO₂ matrices and an objective,
returns the optimal visit order for a single vehicle starting and
returning to the depot (matrix index 0).

PRD §FR-4.2 settings:
  - First solution: PATH_CHEAPEST_ARC
  - Local search: GUIDED_LOCAL_SEARCH
  - Time limit: 10s (configurable)

OR-Tools requires integer arc costs, so float CO₂/distance values are
multiplied by 100 and rounded — preserving 2 decimal precision while
staying within int32 bounds for realistic city-scale problems.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.vrp.matrix import VRPMatrices
from src.vrp.schemas import VRPObjective, VRPRouteResult

logger = logging.getLogger(__name__)

_COST_SCALE = 100  # preserve 2 decimals when casting to int


def _select_matrix(matrices: VRPMatrices, objective: VRPObjective) -> list[list[float]]:
    if objective is VRPObjective.DISTANCE:
        return matrices.distance_m
    if objective is VRPObjective.DURATION:
        # duration_s is already int — cast for type uniformity
        return [[float(v) for v in row] for row in matrices.duration_s]
    if objective is VRPObjective.CO2:
        return matrices.co2_g
    raise ValueError(f"Unknown objective: {objective}")


@dataclass
class SolveOutcome:
    result: VRPRouteResult
    elapsed_ms: int


class VRPSolver:
    def __init__(self, time_limit_s: int = 10) -> None:
        if time_limit_s < 1:
            raise ValueError("time_limit_s must be >= 1")
        self._time_limit_s = time_limit_s

    def solve(
        self,
        matrices: VRPMatrices,
        objective: VRPObjective,
    ) -> SolveOutcome:
        cost_matrix = _select_matrix(matrices, objective)
        n = matrices.size
        if n < 2:
            raise ValueError("Matrix must have at least 2 locations (depot + 1 job)")

        # Single vehicle, depot at index 0
        manager = pywrapcp.RoutingIndexManager(n, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def cost_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(round(cost_matrix[from_node][to_node] * _COST_SCALE))

        transit_idx = routing.RegisterTransitCallback(cost_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_params.time_limit.seconds = self._time_limit_s

        t0 = time.perf_counter()
        solution = routing.SolveWithParameters(search_params)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if solution is None:
            return SolveOutcome(
                result=VRPRouteResult(
                    objective=objective,
                    visit_order=[],
                    total_distance_m=0,
                    total_duration_s=0,
                    total_co2_g=0,
                    feasible=False,
                    status="NO_SOLUTION",
                ),
                elapsed_ms=elapsed_ms,
            )

        # Extract route as node indices (excluding depot start)
        index = routing.Start(0)
        path_nodes: list[int] = []
        while not routing.IsEnd(index):
            path_nodes.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        # path_nodes = [0, j_a, j_b, ..., j_z] (depot + jobs in order)
        # Convert to job indices (0-based, depot stripped). Note routing.IsEnd
        # excludes the return-to-depot node, so we don't strip it from the end.

        job_visit_order = [n - 1 for n in path_nodes[1:]]  # subtract 1 to map node->job

        # Compute aggregate totals across all matrices using the full path
        # (depot -> j_a -> j_b -> ... -> j_z -> depot)
        full_path = path_nodes + [0]  # close the loop back to depot
        total_d = 0.0
        total_t = 0
        total_c = 0.0
        for i in range(len(full_path) - 1):
            a, b = full_path[i], full_path[i + 1]
            total_d += matrices.distance_m[a][b]
            total_t += matrices.duration_s[a][b]
            total_c += matrices.co2_g[a][b]

        return SolveOutcome(
            result=VRPRouteResult(
                objective=objective,
                visit_order=job_visit_order,
                total_distance_m=total_d,
                total_duration_s=total_t,
                total_co2_g=total_c,
                feasible=True,
                status="OK",
            ),
            elapsed_ms=elapsed_ms,
        )

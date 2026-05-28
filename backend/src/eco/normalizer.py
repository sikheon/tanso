"""Min-Max (Ideal-Nadir) normalization for multi-objective route scoring.

Implements the "Weighting Method with Normalization" from
  Demir, E., Bektaş, T., & Laporte, G. (2014).
  "The bi-objective Pollution-Routing Problem." EJOR 232(3), 464-478.

Given a set of candidate routes, each with three observed objectives
(distance, duration, CO₂), we map each objective to [0, 1] via

    norm(x) = (x - x_min) / (x_max - x_min)

so a value of 0 means "best in this set on this axis" and 1 means "worst".
The final score is the weighted sum   α·d_norm + β·t_norm + γ·e_norm,
which is to be **minimized**. Weights must sum to 1.0 ± 0.01.

When the candidate set has only one route, normalization is impossible
and every axis returns 0 (the lone route is trivially "best").
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.routing.schemas import Route

_WEIGHT_SUM_TOLERANCE = 0.01


@dataclass(frozen=True)
class Weights:
    distance: float
    duration: float
    co2: float

    def __post_init__(self) -> None:
        for v, name in (
            (self.distance, "distance"),
            (self.duration, "duration"),
            (self.co2, "co2"),
        ):
            if v < 0 or v > 1:
                raise ValueError(f"Weight '{name}' must be in [0,1], got {v}")
        s = self.distance + self.duration + self.co2
        if abs(s - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"Weights must sum to 1.0 ± {_WEIGHT_SUM_TOLERANCE}, got {s:.4f}"
            )

    @classmethod
    def balanced(cls) -> "Weights":
        return cls(distance=1 / 3, duration=1 / 3, co2=1 / 3)


@dataclass(frozen=True)
class NormalizedRoute:
    """Wraps a Route with its [0,1]-normalized objectives + weighted score."""

    route: Route
    total_co2_g: float
    d_norm: float
    t_norm: float
    e_norm: float
    score: float  # = α·d_norm + β·t_norm + γ·e_norm

    @property
    def engine(self) -> str:
        return self.route.engine.value

    @property
    def objective(self) -> str:
        return self.route.objective.value


def _safe_norm(value: float, lo: float, hi: float) -> float:
    if math.isclose(lo, hi):
        return 0.0
    return (value - lo) / (hi - lo)


def score_candidates(
    routes: list[Route],
    co2_by_route_index: list[float],
    weights: Weights,
) -> list[NormalizedRoute]:
    """Score `routes[i]` using its corresponding `co2_by_route_index[i]`.

    The caller computes CO₂ via EmissionCalculator first (since CO₂
    depends on vehicle choice, not just routing engine), then hands the
    parallel arrays here. This decoupling keeps the normalizer pure.
    """
    if not routes:
        return []
    if len(routes) != len(co2_by_route_index):
        raise ValueError(
            f"routes ({len(routes)}) and co2 array ({len(co2_by_route_index)}) "
            "must have the same length"
        )

    distances = [r.total_distance_m for r in routes]
    durations = [float(r.total_duration_s) for r in routes]
    co2s = list(co2_by_route_index)

    d_lo, d_hi = min(distances), max(distances)
    t_lo, t_hi = min(durations), max(durations)
    e_lo, e_hi = min(co2s), max(co2s)

    result: list[NormalizedRoute] = []
    for r, co2 in zip(routes, co2s, strict=True):
        d_n = _safe_norm(r.total_distance_m, d_lo, d_hi)
        t_n = _safe_norm(float(r.total_duration_s), t_lo, t_hi)
        e_n = _safe_norm(co2, e_lo, e_hi)
        score = (
            weights.distance * d_n
            + weights.duration * t_n
            + weights.co2 * e_n
        )
        result.append(
            NormalizedRoute(
                route=r,
                total_co2_g=co2,
                d_norm=d_n,
                t_norm=t_n,
                e_norm=e_n,
                score=score,
            )
        )
    return result


def rank_recommend(scored: list[NormalizedRoute]) -> list[NormalizedRoute]:
    """Return scored routes sorted ascending by score (best first)."""
    return sorted(scored, key=lambda nr: nr.score)

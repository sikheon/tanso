"""CO₂ emission calculator.

Per segment:
  co2_g = (distance_m / 1000) × emission_factor.g_per_km × speed_bin_multiplier

Speed-bin multiplier follows PRD §FR-3.2 (COPERT-simplified):
  - Kakao routes: engine_has_live_traffic=True → multiplier from bins
    marked 'all' or 'dynamic_only'
  - ORS routes:   engine_has_live_traffic=False → multiplier from bins
    marked 'all' or 'static_only'
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eco.factors import EcoFactorBook
from src.routing.schemas import EngineName, Route, Segment


@dataclass
class SegmentEmission:
    seq: int
    distance_m: float
    duration_s: int
    avg_speed_kmh: float | None
    speed_multiplier: float
    grade_multiplier: float
    co2_g: float


# Grade-based correction coefficients (per 1 % of grade).
# Uphill burns more fuel; downhill burns less (and never less than the floor
# below). Magnitudes are conservative midpoints of the published HBEFA / COPERT
# heavy-duty grade response curves.
_UPHILL_FACTOR = 0.06
_DOWNHILL_FACTOR = 0.03
_GRADE_MULT_MIN = 0.6
_GRADE_MULT_MAX = 1.6


def _grade_multiplier(grade_pct: float | None) -> float:
    if grade_pct is None:
        return 1.0
    if grade_pct >= 0:
        mult = 1.0 + _UPHILL_FACTOR * grade_pct
    else:
        # grade_pct is negative; subtract the downhill credit
        mult = 1.0 + _DOWNHILL_FACTOR * grade_pct
    return max(_GRADE_MULT_MIN, min(_GRADE_MULT_MAX, mult))


@dataclass
class RouteEmission:
    total_co2_g: float
    segments: list[SegmentEmission]
    base_g_per_km: float
    engine_has_live_traffic: bool

    @property
    def avg_g_per_km(self) -> float:
        total_km = sum(s.distance_m for s in self.segments) / 1000.0
        return self.total_co2_g / total_km if total_km > 0 else 0.0


# Engines whose ETA already incorporates live traffic — see FR-3.2 note
_LIVE_TRAFFIC_ENGINES = {EngineName.KAKAO}


class EmissionCalculator:
    """Computes per-segment + total CO₂ for a Route given a vehicle.

    The caller passes (fuel_type, vehicle_class); we don't depend on the
    Vehicle ORM model here so the calculator stays unit-testable without DB.
    """

    def __init__(self, book: EcoFactorBook) -> None:
        self._book = book

    def calculate(
        self,
        route: Route,
        fuel_type: str,
        vehicle_class: str,
    ) -> RouteEmission:
        ef = self._book.emission_factor(fuel_type, vehicle_class)
        live = route.engine in _LIVE_TRAFFIC_ENGINES

        segments: list[SegmentEmission] = []
        total = 0.0
        for s in route.segments:
            mult = self._book.speed_multiplier(
                s.avg_speed_kmh, engine_has_live_traffic=live
            )
            grade_mult = _grade_multiplier(s.grade_pct)
            co2 = (s.distance_m / 1000.0) * ef.g_per_km * mult * grade_mult
            segments.append(
                SegmentEmission(
                    seq=s.seq,
                    distance_m=s.distance_m,
                    duration_s=s.duration_s,
                    avg_speed_kmh=s.avg_speed_kmh,
                    speed_multiplier=mult,
                    grade_multiplier=grade_mult,
                    co2_g=co2,
                )
            )
            total += co2

        # Fallback: if a route has no segments (rare), compute on totals
        if not route.segments and route.total_distance_m > 0:
            avg_speed = self._derive_avg_speed(route)
            mult = self._book.speed_multiplier(
                avg_speed, engine_has_live_traffic=live
            )
            total = (route.total_distance_m / 1000.0) * ef.g_per_km * mult

        return RouteEmission(
            total_co2_g=total,
            segments=segments,
            base_g_per_km=ef.g_per_km,
            engine_has_live_traffic=live,
        )

    @staticmethod
    def _derive_avg_speed(route: Route) -> float | None:
        if route.total_duration_s <= 0:
            return None
        return (route.total_distance_m / 1000.0) / (route.total_duration_s / 3600.0)

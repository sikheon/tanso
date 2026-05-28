"""Common schemas for routing requests/responses.

All RoutingProvider implementations must accept `RouteRequest` and return
a list of `Route` objects with the same shape, regardless of the upstream
API. This is the contract that downstream Eco-Analyzer / VRP solver depend on.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LatLng(BaseModel):
    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    def as_tuple_lng_lat(self) -> tuple[float, float]:
        """Return (lng, lat) — the order used by Kakao/ORS APIs."""
        return self.lng, self.lat


class EngineName(str, Enum):
    KAKAO = "kakao"
    ORS = "ors"


class Objective(str, Enum):
    RECOMMEND = "recommend"
    FASTEST = "fastest"
    SHORTEST = "shortest"
    ALTERNATIVE = "alternative"


class Segment(BaseModel):
    """One arc of a route (between two waypoints or two road shape points)."""

    seq: int
    from_point: LatLng
    to_point: LatLng
    distance_m: float = Field(ge=0)
    duration_s: int = Field(ge=0)
    avg_speed_kmh: float | None = Field(default=None, ge=0)
    road_type: str | None = None
    elevation_gain_m: float | None = Field(default=None, ge=0)
    elevation_loss_m: float | None = Field(default=None, ge=0)
    grade_pct: float | None = Field(
        default=None,
        description="Net grade in percent over the segment ((Δelev / distance) × 100). "
        "Positive = uphill, negative = downhill.",
    )

    @model_validator(mode="after")
    def _derive_speed(self) -> "Segment":
        if self.avg_speed_kmh is None and self.duration_s > 0:
            self.avg_speed_kmh = round(
                (self.distance_m / 1000.0) / (self.duration_s / 3600.0), 2
            )
        return self


class Route(BaseModel):
    """A single route candidate returned by a routing engine."""

    engine: EngineName
    objective: Objective
    total_distance_m: float = Field(ge=0)
    total_duration_s: int = Field(ge=0)
    segments: list[Segment] = Field(default_factory=list)
    polyline: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Ordered (lat, lng) coordinates for map rendering",
    )
    warnings: list[str] = Field(default_factory=list)
    raw_response: dict[str, Any] | None = Field(default=None, exclude=True)

    @property
    def total_distance_km(self) -> float:
        return self.total_distance_m / 1000.0


class RouteRequest(BaseModel):
    """Input to every RoutingProvider."""

    origin: LatLng
    destination: LatLng
    waypoints: list[LatLng] = Field(default_factory=list, max_length=30)
    alternatives: int = Field(default=1, ge=1, le=3)
    priority: Literal["recommend", "time", "distance"] = "recommend"
    avoid: list[Literal["toll", "motorway", "ferry"]] = Field(default_factory=list)

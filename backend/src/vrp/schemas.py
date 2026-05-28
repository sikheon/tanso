"""VRP request/result schemas."""

from __future__ import annotations

from datetime import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.routing.schemas import LatLng


class VRPObjective(str, Enum):
    DISTANCE = "distance"
    DURATION = "duration"
    CO2 = "co2"


class VRPJob(BaseModel):
    """One delivery stop in a VRP request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str | None = None
    location: LatLng
    address: str | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None
    service_time_min: int = Field(default=0, ge=0)
    constraints: list[dict[str, Any]] = Field(default_factory=list)


class VRPRequest(BaseModel):
    depot: LatLng
    jobs: list[VRPJob] = Field(min_length=1, max_length=20)
    fuel_type: str = "gasoline"
    vehicle_class: str = "sedan"
    objectives: list[VRPObjective] = Field(
        default_factory=lambda: [
            VRPObjective.DISTANCE,
            VRPObjective.DURATION,
            VRPObjective.CO2,
        ],
        min_length=1,
    )
    solver_time_limit_s: int = Field(default=10, ge=1, le=60)
    matrix_engine: Literal["ors", "kakao"] = "ors"


class VRPRouteResult(BaseModel):
    """A single solver output for one objective."""

    objective: VRPObjective
    visit_order: list[int] = Field(
        description="Indices into request.jobs in visit sequence (depot excluded)"
    )
    total_distance_m: float
    total_duration_s: int
    total_co2_g: float
    feasible: bool = True
    status: str = "OK"


class VRPResponse(BaseModel):
    results: list[VRPRouteResult]
    matrix_size: int
    solver_time_ms: int
    warnings: list[str] = Field(default_factory=list)

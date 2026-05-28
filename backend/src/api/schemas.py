"""Pydantic schemas for the REST API layer.

These are the wire formats used by FastAPI. They build on internal domain
schemas in `src.routing.schemas` and `src.vrp.schemas` but stay independent
so we can evolve the API surface without touching the solver core.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.routing.schemas import EngineName, LatLng

# ───────────────────────────────────────────────────────────────────
# Common
# ───────────────────────────────────────────────────────────────────


class WeightsDTO(BaseModel):
    distance: float = Field(ge=0, le=1)
    duration: float = Field(ge=0, le=1)
    co2: float = Field(ge=0, le=1)


class VehicleSnapshot(BaseModel):
    """Frozen-in-time view of a vehicle, stored on Run."""

    id: int | None = None
    plate: str | None = None
    model: str | None = None
    fuel_type: str
    vehicle_class: str
    year_produced: int | None = None
    emission_factor_g_per_km: float
    emission_factor_source: str | None = None


class PointWithAddress(LatLng):
    address: str | None = None


# ───────────────────────────────────────────────────────────────────
# Route / Segment (response side)
# ───────────────────────────────────────────────────────────────────


class SegmentDTO(BaseModel):
    seq: int
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    distance_m: float
    duration_s: int
    avg_speed_kmh: float | None = None
    speed_bin_mult: float | None = None
    co2_g: float
    road_type: str | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    grade_pct: float | None = None


class RouteDTO(BaseModel):
    id: int | None = None
    engine: str
    objective: str
    total_distance_m: float
    total_duration_s: int
    total_co2_g: float
    is_recommended: bool = False
    score: float | None = None
    polyline: list[tuple[float, float]] = Field(default_factory=list)
    segments: list[SegmentDTO] | None = None  # detail view only


class RunSummaryFigure(BaseModel):
    distance_km: float
    duration_min: int
    co2_g: float


# ───────────────────────────────────────────────────────────────────
# P2P
# ───────────────────────────────────────────────────────────────────


class P2POptions(BaseModel):
    engines: list[Literal["kakao", "ors"]] = Field(default=["kakao", "ors"])
    alternatives_per_engine: int = Field(default=2, ge=1, le=3)
    weights: WeightsDTO | None = None  # None ⇒ balanced
    generate_narrative: bool = True
    label: str | None = None


class P2PRequest(BaseModel):
    origin: PointWithAddress
    destination: PointWithAddress
    waypoints: list[PointWithAddress] = Field(default_factory=list, max_length=10)
    vehicle_id: int
    options: P2POptions = Field(default_factory=P2POptions)


class P2PResponse(BaseModel):
    run_id: int
    status: Literal["pending", "running", "done", "failed"]
    mode: Literal["p2p"] = "p2p"
    vehicle: VehicleSnapshot
    weights: WeightsDTO
    routes: list[RouteDTO]
    narrative: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


# ───────────────────────────────────────────────────────────────────
# VRP
# ───────────────────────────────────────────────────────────────────


class VRPJobDTO(BaseModel):
    id: int | None = None
    seq: int | None = None
    label: str | None = None
    location: LatLng
    address: str | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None
    service_time_min: int = 0
    constraints: list[dict[str, Any]] = Field(default_factory=list)


class VRPOptions(BaseModel):
    matrix_engine: Literal["ors", "kakao"] = "ors"
    objectives: list[Literal["distance", "duration", "co2"]] = Field(
        default=["distance", "duration", "co2"], min_length=1
    )
    solver_time_limit_s: int = Field(default=10, ge=1, le=60)
    weights: WeightsDTO | None = None
    generate_narrative: bool = True
    label: str | None = None


class VRPRequest(BaseModel):
    depot: PointWithAddress
    jobs: list[VRPJobDTO] = Field(min_length=1, max_length=20)
    vehicle_id: int
    options: VRPOptions = Field(default_factory=VRPOptions)


class VRPResultDTO(BaseModel):
    objective: Literal["distance", "duration", "co2"]
    visit_order_job_ids: list[int]
    visit_order_polyline: list[tuple[float, float]] = Field(default_factory=list)
    total_distance_m: float
    total_duration_s: int
    total_co2_g: float
    is_recommended: bool = False
    solve_ms: int
    feasible: bool = True
    status: str = "OK"


class VRPSolverInfo(BaseModel):
    time_limit_s: int
    metaheuristic: str
    matrix_engine: str


class VRPResponse(BaseModel):
    run_id: int
    status: Literal["pending", "running", "done", "failed"]
    mode: Literal["vrp"] = "vrp"
    depot: PointWithAddress
    jobs: list[VRPJobDTO]
    vehicle: VehicleSnapshot
    results: list[VRPResultDTO]
    narrative: str | None = None
    solver: VRPSolverInfo
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


# ───────────────────────────────────────────────────────────────────
# Parse (natural-language → structured outline)
# ───────────────────────────────────────────────────────────────────


class ParseRequest(BaseModel):
    text: str = Field(min_length=4, max_length=4000)


class ParsedJobOutline(BaseModel):
    label: str
    raw: str | None = None


class ParseResponse(BaseModel):
    mode: Literal["p2p", "vrp"]
    vehicle_hint: dict[str, str] | None = None
    depot_hint: str | None = None
    jobs_outline: list[ParsedJobOutline] = Field(default_factory=list)
    deadline_hint: str | None = None
    weights: WeightsDTO | None = None
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    llm_trace: dict[str, int] = Field(default_factory=dict)


# ───────────────────────────────────────────────────────────────────
# Recalculate (What-if vehicle)
# ───────────────────────────────────────────────────────────────────


class RecalculateRequest(BaseModel):
    vehicle_id: int


class RecalculateResponse(BaseModel):
    original_run_id: int
    new_run_id: int
    vehicle: VehicleSnapshot
    routes: list[RouteDTO]
    savings_vs_original_g: float
    narrative: str | None = None


# ───────────────────────────────────────────────────────────────────
# Run CRUD
# ───────────────────────────────────────────────────────────────────


class RunListItem(BaseModel):
    id: int
    mode: Literal["p2p", "vrp"]
    label: str | None = None
    vehicle: VehicleSnapshot | None = None
    summary: RunSummaryFigure | None = None
    status: str
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunListItem]
    total: int
    limit: int
    offset: int


class RunPatchRequest(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    notes: str | None = None


# ───────────────────────────────────────────────────────────────────
# Vehicle CRUD
# ───────────────────────────────────────────────────────────────────


class VehicleCreateRequest(BaseModel):
    plate: str | None = Field(default=None, max_length=20)
    model: str | None = Field(default=None, max_length=100)
    fuel_type: str
    vehicle_class: str
    year_produced: int | None = None


class VehicleUpdateRequest(BaseModel):
    plate: str | None = None
    model: str | None = None
    fuel_type: str | None = None
    vehicle_class: str | None = None
    year_produced: int | None = None


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str | None
    model: str | None
    fuel_type: str
    vehicle_class: str
    year_produced: int | None
    emission_factor_g_per_km: float | None = None
    emission_factor_source: str | None = None
    created_at: datetime


# ───────────────────────────────────────────────────────────────────
# Stats
# ───────────────────────────────────────────────────────────────────


class StatsByClass(BaseModel):
    vehicle_class: str
    runs: int
    avg_co2_g_per_km: float


class StatsByEngine(BaseModel):
    engine: str
    recommended_count: int


class StatsSummaryResponse(BaseModel):
    total_runs: int
    total_distance_km: float
    total_co2_kg: float
    total_co2_saved_kg: float
    by_vehicle_class: list[StatsByClass] = Field(default_factory=list)
    by_engine: list[StatsByEngine] = Field(default_factory=list)


# ───────────────────────────────────────────────────────────────────
# Read-only: emission factors
# ───────────────────────────────────────────────────────────────────


class EmissionFactorDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fuel_type: str
    vehicle_class: str
    g_per_km: float
    source: str | None

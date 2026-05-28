"""Structured output schemas for LLM agents."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.eco.normalizer import Weights


class RoutingMode(str, Enum):
    P2P = "p2p"
    VRP = "vrp"


class ExecutionPlan(BaseModel):
    """Output of the Planner agent — decides workflow shape."""

    mode: RoutingMode
    engines: list[Literal["kakao", "ors"]] = Field(min_length=1)
    needs_constraint_extraction: bool = False
    needs_weight_composition: bool = True
    alternatives_per_engine: int = Field(default=2, ge=1, le=3)


class WeightSpec(BaseModel):
    """Output of the Weight Composer."""

    distance: float = Field(ge=0, le=1)
    duration: float = Field(ge=0, le=1)
    co2: float = Field(ge=0, le=1)
    rationale: str = Field(default="")

    @model_validator(mode="after")
    def _normalize_sum(self) -> "WeightSpec":
        s = self.distance + self.duration + self.co2
        if s <= 0:
            raise ValueError("All weights are zero or negative")
        # Allow LLM to be off by up to 0.05; renormalize for downstream use.
        if abs(s - 1.0) > 0.05:
            raise ValueError(
                f"Weights sum {s:.3f} deviates >0.05 from 1.0 — reject and retry"
            )
        # Snap to exact 1.0 by proportional scaling
        scale = 1.0 / s
        object.__setattr__(self, "distance", self.distance * scale)
        object.__setattr__(self, "duration", self.duration * scale)
        object.__setattr__(self, "co2", self.co2 * scale)
        return self

    def to_weights(self) -> Weights:
        return Weights(distance=self.distance, duration=self.duration, co2=self.co2)


class ExtractedConstraint(BaseModel):
    """One structured constraint from free-text notes."""

    site_id: str
    type: Literal[
        "time_window_exclusion",
        "vehicle_dimension",
        "access_note",
        "contact_constraint",
        "note",
    ]
    range: str | None = None
    value: str | None = None
    reason: str | None = None


class ConstraintBatch(BaseModel):
    constraints: list[ExtractedConstraint] = Field(default_factory=list)


class LLMTrace(BaseModel):
    """One record of an LLM call for the run's llm_trace JSON column."""

    agent: str
    model: str
    prompt_chars: int
    response_chars: int
    function_called: str | None = None
    retried: bool = False
    used_fallback: bool = False
    elapsed_ms: int
    raw_response: dict[str, Any] | None = None

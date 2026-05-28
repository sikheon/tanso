"""Unit tests for LLM output Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.llm.schemas import (
    ConstraintBatch,
    ExecutionPlan,
    ExtractedConstraint,
    RoutingMode,
    WeightSpec,
)


# ----- ExecutionPlan -----

def test_execution_plan_minimal() -> None:
    p = ExecutionPlan(
        mode="p2p",
        engines=["kakao"],
        needs_constraint_extraction=False,
    )
    assert p.mode is RoutingMode.P2P
    assert p.engines == ["kakao"]
    assert p.alternatives_per_engine == 2  # default
    assert p.needs_weight_composition is True  # default


def test_execution_plan_engines_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        ExecutionPlan(mode="vrp", engines=[], needs_constraint_extraction=False)


def test_execution_plan_alternatives_bounds() -> None:
    ExecutionPlan(mode="p2p", engines=["kakao"], needs_constraint_extraction=False, alternatives_per_engine=1)
    ExecutionPlan(mode="p2p", engines=["kakao"], needs_constraint_extraction=False, alternatives_per_engine=3)
    with pytest.raises(ValidationError):
        ExecutionPlan(mode="p2p", engines=["kakao"], needs_constraint_extraction=False, alternatives_per_engine=0)
    with pytest.raises(ValidationError):
        ExecutionPlan(mode="p2p", engines=["kakao"], needs_constraint_extraction=False, alternatives_per_engine=4)


# ----- WeightSpec -----

def test_weight_spec_normalizes_close_sum() -> None:
    """LLM often returns 0.34/0.33/0.33 = 1.00; identity normalize OK."""
    w = WeightSpec(distance=0.34, duration=0.33, co2=0.33, rationale="balanced")
    total = w.distance + w.duration + w.co2
    assert total == pytest.approx(1.0, abs=1e-6)


def test_weight_spec_renormalizes_slightly_off_sum() -> None:
    """LLM returns 0.4/0.3/0.32 = 1.02; should snap to exact 1.0."""
    w = WeightSpec(distance=0.40, duration=0.30, co2=0.32, rationale="off by 0.02")
    total = w.distance + w.duration + w.co2
    assert total == pytest.approx(1.0, abs=1e-6)
    # Relative ratios preserved
    assert w.distance == pytest.approx(0.40 / 1.02, abs=1e-4)


def test_weight_spec_rejects_sum_too_far_from_one() -> None:
    with pytest.raises(ValidationError):
        WeightSpec(distance=0.5, duration=0.5, co2=0.5, rationale="sum=1.5")


def test_weight_spec_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        WeightSpec(distance=-0.1, duration=0.6, co2=0.5, rationale="bad")


def test_weight_spec_to_weights_roundtrip() -> None:
    spec = WeightSpec(distance=0.2, duration=0.3, co2=0.5, rationale="eco-leaning")
    w = spec.to_weights()
    assert w.distance == pytest.approx(0.2)
    assert w.duration == pytest.approx(0.3)
    assert w.co2 == pytest.approx(0.5)


# ----- Constraints -----

def test_extracted_constraint_minimal() -> None:
    c = ExtractedConstraint(site_id="site_2", type="time_window_exclusion", range="12:00-13:00")
    assert c.site_id == "site_2"
    assert c.range == "12:00-13:00"


def test_extracted_constraint_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        ExtractedConstraint(site_id="x", type="not_a_known_type")  # type: ignore[arg-type]


def test_constraint_batch_default_empty() -> None:
    cb = ConstraintBatch()
    assert cb.constraints == []

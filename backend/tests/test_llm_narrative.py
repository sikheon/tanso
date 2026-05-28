"""Unit tests for NarrativeAgent's derived-metric enrichment and fallback."""

import pytest

from src.llm.agents.narrative import _enrich_with_derived_metrics, _template_fallback


def test_enrich_adds_pine_equivalents_when_savings_present() -> None:
    out = _enrich_with_derived_metrics({"co2_saved_g": 1800})
    d = out["derived"]
    # 1800 g / 18 g/day = 100 days
    assert d["pine_30y_days_equivalent"] == pytest.approx(100.0, rel=0.01)
    # 1800 g / 6600 g/yr ≈ 0.27 trees
    assert d["pine_30y_trees_yearly"] == pytest.approx(1800 / 6600.0, rel=0.01)


def test_enrich_adds_pct_saved_vs_worst_alternative() -> None:
    payload = {
        "recommended": {"co2_g": 60000},
        "alternatives": [
            {"co2_g": 62000},
            {"co2_g": 65000},
        ],
    }
    out = _enrich_with_derived_metrics(payload)
    d = out["derived"]
    # (65000 - 60000) / 65000 * 100 = 7.69 %
    assert d["co2_saved_pct_vs_worst"] == pytest.approx(7.7, abs=0.1)
    # best_alt = 62000, diff = 2000
    assert d["co2_saved_vs_best_alt_g"] == 2000


def test_enrich_skips_derived_when_no_savings() -> None:
    out = _enrich_with_derived_metrics({"recommended": {"co2_g": 100}})
    assert "derived" not in out


def test_enrich_does_not_mutate_input() -> None:
    payload = {"co2_saved_g": 1000}
    out = _enrich_with_derived_metrics(payload)
    assert "derived" not in payload  # input untouched
    assert "derived" in out


def test_template_fallback_uses_recommended_fields() -> None:
    text = _template_fallback({
        "recommended": {
            "engine": "ors", "objective": "recommend",
            "distance_km": 398.4, "duration_min": 269, "co2_g": 60489,
        },
        "co2_saved_g": 2104,
    })
    assert "ors" in text
    assert "398.4" in text
    assert "269" in text
    assert "60489" in text
    assert "2104" in text
    # Pine conversion: 2104/18 = 116.888...
    assert "116" in text


def test_template_fallback_handles_missing_savings() -> None:
    text = _template_fallback({"recommended": {"engine": "kakao", "objective": "recommend"}})
    assert "kakao" in text
    # No crash on missing fields

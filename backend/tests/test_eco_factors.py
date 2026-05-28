"""Unit tests for EcoFactorBook (in-memory factor lookup)."""

import pytest

from src.eco.factors import EcoFactorBook, EmissionFactorView, SpeedBinView


def _book() -> EcoFactorBook:
    emissions = [
        EmissionFactorView(fuel_type="gasoline", vehicle_class="sedan", g_per_km=145.0, source="test"),
        EmissionFactorView(fuel_type="diesel", vehicle_class="truck_1t", g_per_km=215.0, source="test"),
    ]
    speed_bins = [
        SpeedBinView(speed_min_kmh=0, speed_max_kmh=10, multiplier=1.65, applies_to="all"),
        SpeedBinView(speed_min_kmh=10, speed_max_kmh=40, multiplier=1.10, applies_to="all"),
        SpeedBinView(speed_min_kmh=40, speed_max_kmh=60, multiplier=1.00, applies_to="all"),
        SpeedBinView(speed_min_kmh=60, speed_max_kmh=80, multiplier=0.95, applies_to="all"),
        SpeedBinView(speed_min_kmh=80, speed_max_kmh=120, multiplier=1.05, applies_to="all"),
        SpeedBinView(speed_min_kmh=120, speed_max_kmh=999, multiplier=1.40, applies_to="static_only"),
    ]
    return EcoFactorBook(emissions, speed_bins)


def test_emission_factor_lookup() -> None:
    book = _book()
    ef = book.emission_factor("gasoline", "sedan")
    assert ef.g_per_km == 145.0


def test_emission_factor_unknown_key_raises() -> None:
    book = _book()
    with pytest.raises(KeyError):
        book.emission_factor("unicorn-fuel", "sedan")


def test_speed_multiplier_none_or_zero() -> None:
    book = _book()
    assert book.speed_multiplier(None, engine_has_live_traffic=True) == 1.0
    assert book.speed_multiplier(0, engine_has_live_traffic=True) == 1.0
    assert book.speed_multiplier(-5, engine_has_live_traffic=True) == 1.0


def test_speed_multiplier_typical_speeds() -> None:
    book = _book()
    assert book.speed_multiplier(5, engine_has_live_traffic=False) == 1.65
    assert book.speed_multiplier(25, engine_has_live_traffic=False) == 1.10
    assert book.speed_multiplier(50, engine_has_live_traffic=False) == 1.00
    assert book.speed_multiplier(70, engine_has_live_traffic=False) == 0.95
    assert book.speed_multiplier(100, engine_has_live_traffic=False) == 1.05


def test_speed_multiplier_skips_static_only_when_live_traffic() -> None:
    book = _book()
    # 130 km/h sits in the 'static_only' bin. With live traffic, that
    # bin is skipped and we fall through to multiplier=1.0 (no match).
    assert book.speed_multiplier(130, engine_has_live_traffic=True) == 1.0
    # ORS-like (no live traffic) DOES apply the static bin
    assert book.speed_multiplier(130, engine_has_live_traffic=False) == 1.40


def test_speed_multiplier_out_of_all_bins() -> None:
    book = _book()
    # 200 km/h is above the static-only bin's upper bound (999) — actually still inside.
    # Use a case truly outside: build a book with limited bins.
    sparse = EcoFactorBook(
        emissions=[],
        speed_bins=[SpeedBinView(0, 40, 1.1, "all")],
    )
    assert sparse.speed_multiplier(100, engine_has_live_traffic=False) == 1.0

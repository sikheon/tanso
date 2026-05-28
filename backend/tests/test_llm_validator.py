"""Unit tests for the narrative hallucination guard."""

import pytest

from src.llm.validator import (
    collect_allowed_numbers,
    extract_numbers,
    is_close_to_any,
    validate_narrative,
)


def test_extract_numbers_picks_int_float_negative() -> None:
    nums = extract_numbers("거리 398.4km, 시간 269분, CO₂ 60489g, 절감 -120")
    assert nums == [398.4, 269.0, 60489.0, -120.0]


def test_extract_numbers_handles_thousands_separator() -> None:
    nums = extract_numbers("CO₂는 60,489g 이고, 다른 경로는 62,593g 입니다")
    assert 60489.0 in nums
    assert 62593.0 in nums


def test_extract_numbers_ignores_inside_identifiers() -> None:
    nums = extract_numbers("variable_42 또는 x123 는 식별자입니다")
    # variable_42 and x123 should NOT be parsed (negative lookbehind for letter/_)
    assert 42.0 not in nums
    assert 123.0 not in nums


def test_collect_allowed_numbers_flattens_nested() -> None:
    src = {
        "a": 1,
        "b": [2.0, 3, {"c": 4.5}],
        "d": {"e": {"f": [5, 6]}},
        "skip_str": "hello",
        "skip_bool": True,
    }
    nums = sorted(collect_allowed_numbers(src))
    assert nums == [1.0, 2.0, 3.0, 4.5, 5.0, 6.0]


def test_is_close_to_any_tolerance() -> None:
    allowed = [100.0]
    assert is_close_to_any(100.0, allowed, 0.05)
    assert is_close_to_any(104.99, allowed, 0.05)  # within 5%
    assert not is_close_to_any(106, allowed, 0.05)  # outside


def test_validate_narrative_passes_when_all_match() -> None:
    src = {"distance_km": 398.4, "duration_min": 269, "co2_g": 60489}
    text = "거리 398.4 km, 시간 269분, CO₂ 60489 g 입니다."
    ok, off = validate_narrative(text, src)
    assert ok and off == []


def test_validate_narrative_small_ints_pass_through() -> None:
    """Bullet counts, percentages, '30년생' rhetoric should not trip the guard."""
    src = {"co2_g": 60489}
    text = "60489 g의 CO₂이며, 80% 절감되어 30년생 소나무 5그루 효과입니다."
    ok, off = validate_narrative(text, src)
    assert ok, f"unexpectedly offending: {off}"


def test_validate_narrative_fails_on_big_invented_number() -> None:
    src = {"co2_g": 60489}
    text = "CO₂ 99999 g 입니다."  # 99999 not in source, > passthrough
    ok, off = validate_narrative(text, src)
    assert not ok
    assert 99999.0 in off


def test_validate_narrative_allows_thousand_separator_match() -> None:
    """LLM often writes 60,489 instead of 60489; should still match the source."""
    src = {"co2_g": 60489}
    text = "CO₂ 약 60,489 g 입니다."
    ok, _ = validate_narrative(text, src)
    assert ok


def test_validate_narrative_uses_derived_metrics() -> None:
    """Pre-computed conversions (pine_days) should make those numbers allowed."""
    src = {
        "co2_saved_g": 2104,
        "derived": {"pine_30y_days_equivalent": 116.9},
    }
    text = "절감된 CO₂ 2104 g은 30년생 소나무 1그루가 약 116.9일치 흡수량입니다."
    ok, off = validate_narrative(text, src)
    assert ok, f"unexpectedly offending: {off}"

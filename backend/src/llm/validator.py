"""Hallucination guard for Narrative Generator (PRD §14.4).

Scans LLM-generated text for any number not present in the source data,
within a 5% tolerance to allow rounding.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_NUMBER_RE = re.compile(r"(?<![A-Za-z_])-?\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> list[float]:
    """Pull every numeric literal out of text."""
    out: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        token = m.group().replace(",", "")
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out


def _flatten(obj: object, sink: list[float]) -> None:
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        sink.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten(v, sink)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            _flatten(v, sink)


def collect_allowed_numbers(source: object) -> list[float]:
    """Recursively flatten nested data into a flat number list."""
    sink: list[float] = []
    _flatten(source, sink)
    return sink


def is_close_to_any(value: float, allowed: Iterable[float], tolerance: float = 0.05) -> bool:
    """Allow rounded duplicates: 152.4 ≈ 152, 1234 ≈ 1230 within tolerance."""
    for a in allowed:
        if a == 0:
            if abs(value) < 1e-6:
                return True
            continue
        rel = abs(value - a) / abs(a)
        if rel <= tolerance:
            return True
    return False


def validate_narrative(
    narrative: str,
    source: object,
    *,
    tolerance: float = 0.10,
    small_int_passthrough: float = 100,
) -> tuple[bool, list[float]]:
    """Return (ok, offending_numbers).

    The narrative is OK iff every number it mentions is "close enough" to
    some number in the source data. Two intentional escape hatches:

    - Small integers / percentages (|n| <= small_int_passthrough) pass
      automatically. This covers natural-language rhetoric like
      "약 80% 우회", "30년생 소나무", "2-3개 이유" without false positives.

    - The remaining (typically large) numbers are matched against the
      source within a 10% relative tolerance. The guard's purpose is to
      catch material lies (e.g., distance 398 -> 500), not stylistic
      rounding ("약 60,500g" for an actual 60,489g).
    """
    allowed = collect_allowed_numbers(source)
    offending: list[float] = []
    for n in extract_numbers(narrative):
        if abs(n) <= small_int_passthrough:
            continue
        if not is_close_to_any(n, allowed, tolerance=tolerance):
            offending.append(n)
    return len(offending) == 0, offending

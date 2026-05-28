"""Open-Elevation enrichment for routes without native elevation data (e.g. Kakao).

Open-Elevation is a free public API that takes batch (lat, lng) and returns
elevation in meters (SRTM-derived). It can be flaky, so this module is
best-effort: on any failure, segments keep their `None` elevation fields and
the calculator simply skips the grade adjustment.

Reference: https://github.com/Jorl17/open-elevation
"""

from __future__ import annotations

import logging
from typing import Iterable

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.routing.schemas import Route, Segment

logger = logging.getLogger(__name__)

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

# Round coords to ~11m precision so we can dedupe nearby road-shape endpoints
# and keep the request payload small.
_PRECISION = 4


def _round_key(lat: float, lng: float) -> tuple[float, float]:
    return round(lat, _PRECISION), round(lng, _PRECISION)


def _collect_endpoints(routes: Iterable[Route]) -> list[tuple[float, float]]:
    """Unique rounded (lat, lng) pairs across every segment endpoint."""
    seen: set[tuple[float, float]] = set()
    out: list[tuple[float, float]] = []
    for r in routes:
        for s in r.segments:
            for lat, lng in (
                (float(s.from_point.lat), float(s.from_point.lng)),
                (float(s.to_point.lat), float(s.to_point.lng)),
            ):
                k = _round_key(lat, lng)
                if k not in seen:
                    seen.add(k)
                    out.append(k)
    return out


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _post_batch(
    client: httpx.AsyncClient, points: list[tuple[float, float]]
) -> list[float]:
    body = {
        "locations": [{"latitude": lat, "longitude": lng} for lat, lng in points],
    }
    r = await client.post(OPEN_ELEVATION_URL, json=body)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if len(results) != len(points):
        raise RuntimeError(
            f"Open-Elevation returned {len(results)} results for {len(points)} points"
        )
    return [float(item.get("elevation", 0.0)) for item in results]


async def fetch_elevations(
    points: list[tuple[float, float]],
    *,
    timeout: float = 10.0,
    batch_size: int = 100,
) -> dict[tuple[float, float], float]:
    """Look up elevation (meters) for each unique (lat, lng) key.

    Splits into batches of `batch_size` to stay polite to the public API.
    Returns an empty dict if the call fails for any reason — callers must
    treat missing keys as "no elevation data".
    """
    if not points:
        return {}
    result: dict[tuple[float, float], float] = {}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for i in range(0, len(points), batch_size):
                chunk = points[i : i + batch_size]
                elevations = await _post_batch(client, chunk)
                for key, ele in zip(chunk, elevations):
                    result[key] = ele
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "open_elevation.failed",
            extra={"err": str(e), "points": len(points)},
        )
        return {}
    return result


def _apply_to_segment(
    s: Segment, elevations: dict[tuple[float, float], float]
) -> None:
    """Mutate `s` in place, populating elevation_gain/loss/grade from endpoint elevations.

    Endpoint-based (no intermediate samples), so on roads that go up then
    down within one segment we will under-report gain/loss — but the net
    grade is still correct for CO₂ adjustment, which is what the calculator
    actually uses.
    """
    from_key = _round_key(float(s.from_point.lat), float(s.from_point.lng))
    to_key = _round_key(float(s.to_point.lat), float(s.to_point.lng))
    if from_key not in elevations or to_key not in elevations:
        return
    delta = elevations[to_key] - elevations[from_key]
    if delta > 0:
        s.elevation_gain_m = round(delta, 2)
        s.elevation_loss_m = 0.0
    else:
        s.elevation_gain_m = 0.0
        s.elevation_loss_m = round(-delta, 2)
    if s.distance_m > 0:
        s.grade_pct = round((delta / float(s.distance_m)) * 100.0, 2)


async def enrich_routes_with_open_elevation(routes: list[Route]) -> None:
    """Best-effort: populate elevation fields on every segment of `routes`.

    No-op if the public API fails or returns nothing useful.
    """
    points = _collect_endpoints(routes)
    if not points:
        return
    elevations = await fetch_elevations(points)
    if not elevations:
        return
    for r in routes:
        for s in r.segments:
            _apply_to_segment(s, elevations)

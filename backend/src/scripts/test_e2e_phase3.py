"""End-to-end smoke test for Phase 3.

Flow:
  1. Load EcoFactorBook from DB (real seed data)
  2. Call KakaoProvider for 서울역 → 부산역 (real API)
  3. Compute CO₂ for each route × 5 vehicle types (no extra API calls)
  4. Score with Min-Max normalization + balanced weights
  5. Print ranking + per-segment speed-bin sanity check
"""

from __future__ import annotations

import asyncio
import sys

from src.core import asyncio_compat  # noqa: F401
from src.core.config import get_settings
from src.core.db import AsyncSessionLocal
from src.eco import (
    EcoFactorBook,
    EmissionCalculator,
    Weights,
    rank_recommend,
    score_candidates,
)
from src.routing.kakao import KakaoProvider
from src.routing.schemas import LatLng, RouteRequest


VEHICLES_TO_COMPARE = [
    ("gasoline", "sedan"),
    ("diesel", "truck_1t"),
    ("lpg", "sedan"),
    ("hybrid", "sedan"),
    ("electric", "sedan"),
]


async def main() -> int:
    settings = get_settings()
    if not settings.kakao_rest_api_key or settings.kakao_rest_api_key.startswith("__"):
        print("SKIP: KAKAO_REST_API_KEY not set")
        return 1

    # 1. Load factor book
    print("[1/4] Loading EcoFactorBook from DB...")
    async with AsyncSessionLocal() as session:
        book = await EcoFactorBook.load(session)
    print(f"      loaded {len(book._emissions)} emission factors, "
          f"{len(book._speed_bins)} speed bins")

    # 2. Get a Kakao route
    print("\n[2/4] Fetching route: 서울역 → 부산역 (Kakao)...")
    provider = KakaoProvider(settings.kakao_rest_api_key)
    try:
        req = RouteRequest(
            origin=LatLng(lat=37.5547, lng=126.972),
            destination=LatLng(lat=35.1147, lng=129.0413),
            alternatives=1,
        )
        routes = await provider.get_routes(req)
    finally:
        await provider.close()
    route = routes[0]
    print(f"      got {route.total_distance_km:.1f} km, "
          f"{route.total_duration_s // 60} min, "
          f"{len(route.segments)} segments")

    # 3. Calculate CO2 for each vehicle profile
    print("\n[3/4] Computing CO₂ across 5 vehicle profiles...")
    calc = EmissionCalculator(book)
    co2_by_vehicle: dict[tuple[str, str], float] = {}
    for fuel, klass in VEHICLES_TO_COMPARE:
        result = calc.calculate(route, fuel, klass)
        co2_by_vehicle[(fuel, klass)] = result.total_co2_g
        print(
            f"      {fuel:>8} / {klass:>10}: "
            f"{result.total_co2_g:>10,.0f} g  "
            f"(base {result.base_g_per_km:.0f} g/km, "
            f"avg {result.avg_g_per_km:.1f} g/km after bin correction)"
        )

    # 4. Normalize across the 5 vehicle "candidates" (treating each as a Route)
    #    Real use case is multiple Routes for one vehicle, but this proves the
    #    normalizer plumbing end-to-end.
    print("\n[4/4] Min-Max normalization with co2-heavy weights...")
    fake_routes = [route] * len(VEHICLES_TO_COMPARE)
    co2_list = [co2_by_vehicle[v] for v in VEHICLES_TO_COMPARE]
    weights = Weights(distance=0.1, duration=0.1, co2=0.8)
    scored = score_candidates(fake_routes, co2_list, weights)
    ranked = rank_recommend(scored)
    for i, nr in enumerate(ranked, 1):
        fuel, klass = VEHICLES_TO_COMPARE[fake_routes.index(nr.route)]
        # Find which vehicle this score belongs to (by matching co2)
        for v, c in co2_by_vehicle.items():
            if c == nr.total_co2_g:
                fuel, klass = v
                break
        print(
            f"      #{i}  {fuel}/{klass}: "
            f"co2={nr.total_co2_g:,.0f}g  e_norm={nr.e_norm:.3f}  "
            f"score={nr.score:.3f}"
        )

    # Sanity: speed bin coverage
    print("\nSanity check - segment speed distribution:")
    speeds = [s.avg_speed_kmh for s in route.segments if s.avg_speed_kmh]
    if speeds:
        bins = {"<10": 0, "10-40": 0, "40-80": 0, "80+": 0}
        for sp in speeds:
            if sp < 10: bins["<10"] += 1
            elif sp < 40: bins["10-40"] += 1
            elif sp < 80: bins["40-80"] += 1
            else: bins["80+"] += 1
        print(f"  {bins}")

    print("\n[OK] Phase 3 end-to-end smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

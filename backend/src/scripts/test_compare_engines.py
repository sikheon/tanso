"""End-to-end multi-engine comparison via RoutingAdapter.

Calls Kakao + ORS in parallel for the same OD pair, computes CO₂ for
each, normalizes objectives with Min-Max, and prints a ranking.
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
from src.routing.adapter import RoutingAdapter
from src.routing.kakao import KakaoProvider
from src.routing.ors import ORSProvider
from src.routing.schemas import LatLng, RouteRequest


async def main() -> int:
    settings = get_settings()
    if not settings.kakao_rest_api_key or settings.kakao_rest_api_key.startswith("__"):
        print("SKIP: KAKAO_REST_API_KEY not set")
        return 1
    if not settings.ors_api_key or settings.ors_api_key.startswith("__"):
        print("SKIP: ORS_API_KEY not set")
        return 1

    print("[1/4] Loading EcoFactorBook from DB...")
    async with AsyncSessionLocal() as session:
        book = await EcoFactorBook.load(session)
    print(f"      ok ({len(book._emissions)} emission factors)")

    print("\n[2/4] Multi-engine call: 서울역 → 부산역")
    providers = [
        KakaoProvider(settings.kakao_rest_api_key),
        ORSProvider(settings.ors_api_key),
    ]
    adapter = RoutingAdapter(providers)
    try:
        req = RouteRequest(
            origin=LatLng(lat=37.5547, lng=126.972),
            destination=LatLng(lat=35.1147, lng=129.0413),
            alternatives=2,  # ORS will auto-fallback to 1 (route > 100km)
        )
        multi = await adapter.get_all_routes(req)
    finally:
        await adapter.close()

    if multi.warnings:
        print("      warnings:")
        for w in multi.warnings:
            print(f"        - {w}")
    for engine, pr in multi.per_engine.items():
        print(
            f"      {engine.value}: "
            f"{'OK' if pr.ok else 'FAIL'} ({len(pr.routes)} routes)"
        )

    if not multi.routes:
        print("\n[!] No usable routes from any engine")
        return 2

    # 3. CO2 calculation for a fixed vehicle (gasoline sedan demo)
    print("\n[3/4] CO₂ calculation (gasoline / sedan)...")
    calc = EmissionCalculator(book)
    co2_per_route: list[float] = []
    for r in multi.routes:
        result = calc.calculate(r, "gasoline", "sedan")
        co2_per_route.append(result.total_co2_g)
        print(
            f"      [{r.engine.value:>5}/{r.objective.value:>11}] "
            f"{r.total_distance_km:>6.1f} km  "
            f"{r.total_duration_s // 60:>4} min  "
            f"{result.total_co2_g:>9,.0f} g CO₂  "
            f"(avg {result.avg_g_per_km:.1f} g/km)"
        )

    # 4. Min-Max normalize + rank with CO2-heavy weights
    print("\n[4/4] Normalized score (weights: dist=0.1, time=0.3, co2=0.6)...")
    weights = Weights(distance=0.1, duration=0.3, co2=0.6)
    scored = score_candidates(multi.routes, co2_per_route, weights)
    ranked = rank_recommend(scored)
    for i, nr in enumerate(ranked, 1):
        crown = " 🌱 RECOMMENDED" if i == 1 else ""
        print(
            f"      #{i}  [{nr.engine}/{nr.objective}]  "
            f"d={nr.d_norm:.2f}  t={nr.t_norm:.2f}  "
            f"e={nr.e_norm:.2f}  score={nr.score:.3f}{crown}"
        )

    # 5. Engine-comparison delta
    if len(multi.routes) >= 2:
        best = ranked[0]
        worst = ranked[-1]
        co2_delta = worst.total_co2_g - best.total_co2_g
        co2_pct = (co2_delta / worst.total_co2_g) * 100 if worst.total_co2_g else 0
        print(
            f"\n      CO₂ 차이: {co2_delta:,.0f} g "
            f"({co2_pct:.1f}% saved by choosing best route)"
        )
        # Pine-tree equivalent: 30-year pine absorbs ~6.6 kg CO₂/yr ≈ 18 g/day
        pine_days = co2_delta / 18.0
        print(f"      ≈ 30년생 소나무 1그루 {pine_days:.1f}일치 흡수량")

    print("\n[OK] Multi-engine comparison complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

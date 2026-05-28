"""Integration smoke test for ORSProvider (real API call)."""

from __future__ import annotations

import asyncio
import sys

from src.core import asyncio_compat  # noqa: F401
from src.core.config import get_settings
from src.routing.ors import ORSProvider
from src.routing.schemas import LatLng, RouteRequest


async def main() -> int:
    s = get_settings()
    if not s.ors_api_key or s.ors_api_key.startswith("__"):
        print("SKIP: ORS_API_KEY not set in .env yet")
        return 0

    provider = ORSProvider(s.ors_api_key)
    try:
        req = RouteRequest(
            origin=LatLng(lat=37.5547, lng=126.972),        # 서울역
            destination=LatLng(lat=35.1147, lng=129.0413),  # 부산역
            alternatives=2,
            priority="recommend",
        )
        routes = await provider.get_routes(req)
        print(f"Got {len(routes)} route(s):\n")
        for r in routes:
            print(
                f"  [{r.engine.value}/{r.objective.value}] "
                f"{r.total_distance_km:.1f} km, "
                f"{r.total_duration_s // 60} min, "
                f"{len(r.segments)} segments, "
                f"{len(r.polyline)} polyline pts"
            )
            if r.segments:
                seg0 = r.segments[0]
                segN = r.segments[-1]
                print(
                    f"    first: '{seg0.road_type or '?'}' "
                    f"({seg0.distance_m:.0f}m, {seg0.avg_speed_kmh} km/h)"
                )
                print(
                    f"    last:  '{segN.road_type or '?'}' "
                    f"({segN.distance_m:.0f}m, {segN.avg_speed_kmh} km/h)"
                )
            print()
    finally:
        await provider.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""End-to-end VRP scenario.

Scenario: 1톤 디젤 트럭이 강남구 차고지에서 출발해 5곳 배송 후 복귀.
   Builds distance matrix via ORS, then runs OR-Tools with 3 objectives.
"""

from __future__ import annotations

import asyncio
import sys

from src.core import asyncio_compat  # noqa: F401
from src.core.config import get_settings
from src.core.db import AsyncSessionLocal
from src.eco.factors import EcoFactorBook
from src.routing.schemas import LatLng
from src.vrp import ORSMatrixBuilder, VRPJob, VRPObjective, VRPRequest, VRPSolver


# 강남구 일대 실제 좌표 (시연용)
DEPOT = LatLng(lat=37.5172, lng=127.0473)  # 강남구청 부근

JOBS = [
    VRPJob(label="고객A — 역삼동",    location=LatLng(lat=37.5006, lng=127.0367)),
    VRPJob(label="고객B — 삼성동",    location=LatLng(lat=37.5145, lng=127.0566)),
    VRPJob(label="고객C — 청담동",    location=LatLng(lat=37.5234, lng=127.0473)),
    VRPJob(label="고객D — 압구정동",  location=LatLng(lat=37.5273, lng=127.0286)),
    VRPJob(label="고객E — 도곡동",    location=LatLng(lat=37.4906, lng=127.0431)),
]


def _format_route(visit_order: list[int]) -> str:
    chain = ["depot"] + [f"#{i+1}.{JOBS[i].label.split(' — ')[1]}" for i in visit_order] + ["depot"]
    return " → ".join(chain)


async def main() -> int:
    settings = get_settings()
    if not settings.ors_api_key or settings.ors_api_key.startswith("__"):
        print("SKIP: ORS_API_KEY not set")
        return 1

    print(f"[1/4] Loading EcoFactorBook...")
    async with AsyncSessionLocal() as session:
        book = await EcoFactorBook.load(session)

    request = VRPRequest(
        depot=DEPOT,
        jobs=JOBS,
        fuel_type="diesel",
        vehicle_class="truck_1t",
        objectives=[VRPObjective.DISTANCE, VRPObjective.DURATION, VRPObjective.CO2],
        solver_time_limit_s=5,
    )

    print(f"\n[2/4] Building distance matrix ({len(JOBS)+1}×{len(JOBS)+1}) via ORS...")
    builder = ORSMatrixBuilder(settings.ors_api_key, book)
    try:
        matrices = await builder.build(request)
    finally:
        await builder.close()
    print(f"      built {matrices.size}×{matrices.size} matrices")
    print(
        f"      sample arc depot→{JOBS[0].label.split(' — ')[1]}: "
        f"{matrices.distance_m[0][1]:.0f} m, "
        f"{matrices.duration_s[0][1]} s, "
        f"{matrices.co2_g[0][1]:.1f} g CO₂"
    )

    print(f"\n[3/4] Running OR-Tools for 3 objectives...")
    solver = VRPSolver(time_limit_s=request.solver_time_limit_s)
    outcomes = {obj: solver.solve(matrices, obj) for obj in request.objectives}

    print(f"\n[4/4] Results (1톤 디젤 트럭, 강남 5곳 배송):\n")
    print(f"{'Objective':<10} {'Solve(ms)':<10} {'거리':<10} {'시간':<10} {'CO₂':<14} 방문 순서")
    for obj in request.objectives:
        out = outcomes[obj]
        r = out.result
        print(
            f"{obj.value:<10} {out.elapsed_ms:<10} "
            f"{r.total_distance_m / 1000:>5.2f} km   "
            f"{r.total_duration_s // 60:>3} min   "
            f"{r.total_co2_g:>9,.0f} g   "
            f"{_format_route(r.visit_order)}"
        )

    # CO2 savings of co2-min vs distance-min
    dist_r = outcomes[VRPObjective.DISTANCE].result
    co2_r = outcomes[VRPObjective.CO2].result
    co2_saved = dist_r.total_co2_g - co2_r.total_co2_g
    dist_added = (co2_r.total_distance_m - dist_r.total_distance_m)
    if abs(co2_saved) > 0.5:
        sign = "절감" if co2_saved > 0 else "증가"
        print(
            f"\n   CO₂ 최소 경로 vs 거리 최소 경로: "
            f"CO₂ {abs(co2_saved):,.0f} g {sign} "
            f"(거리는 {dist_added / 1000:+.2f} km 변화)"
        )
        if co2_saved > 0:
            pine_days = co2_saved / 18.0
            print(f"   ≈ 30년생 소나무 1그루 {pine_days:.1f}일치 흡수량")
    else:
        print("\n   세 목적함수 결과가 일치 — 이 지오메트리에서는 trade-off 없음")

    print("\n[OK] Phase 4 VRP end-to-end smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

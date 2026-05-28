"""What-if recalculation — swap vehicle on an existing Run without re-routing.

Reuses the original Run's persisted route segments (and their avg_speed /
distance) to recompute CO₂ for a different vehicle. Creates a new Run row
linked to the original via parsed_request["recalculated_from"] so we keep
the full history.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import RecalculateResponse, RouteDTO, VehicleSnapshot
from src.eco import EcoFactorBook
from src.eco.calculator import _grade_multiplier
from src.models import Route, RouteSegment, Run
from src.services import run_service
from src.services.routing_service import _generate_narrative
from src.services.vehicle_service import get_vehicle, vehicle_to_snapshot

logger = logging.getLogger(__name__)


class RecalculateError(Exception):
    pass


async def recalculate_with_vehicle(
    session: AsyncSession,
    *,
    original_run_id: int,
    new_vehicle_id: int,
) -> RecalculateResponse:
    original = await run_service.get_run(session, original_run_id)
    if original.status != "done":
        raise RecalculateError(
            f"Original run {original_run_id} is not in 'done' state (status={original.status})"
        )
    if not original.routes:
        raise RecalculateError(f"Original run {original_run_id} has no routes to recompute")

    new_vehicle = await get_vehicle(session, new_vehicle_id)
    new_snapshot = vehicle_to_snapshot(new_vehicle)
    book = await EcoFactorBook.load(session)

    # Engine-aware live-traffic flag matches what was used originally per route
    LIVE_TRAFFIC_ENGINES = {"kakao"}
    ef = book.emission_factor(new_snapshot["fuel_type"], new_snapshot["vehicle_class"])

    # Create new Run referencing the original
    new_run = await run_service.create_run(
        session,
        mode=original.mode,
        user_input_text=original.user_input_text,
        parsed_request={
            "recalculated_from": original_run_id,
            "original_request": original.parsed_request,
        },
        vehicle_id=new_vehicle.id,
        vehicle_snapshot=new_snapshot,
        llm_weights=original.llm_weights,
        label=(original.label + " (recalc)") if original.label else None,
    )

    # Recompute each segment + route total
    route_dtos: list[RouteDTO] = []
    new_routes_for_narrative: list[Route] = []
    recommended_new_route: Route | None = None
    best_co2_so_far: float | None = None

    for orig_route in original.routes:
        new_route = Route(
            run_id=new_run.id,
            engine=orig_route.engine,
            objective=orig_route.objective,
            visit_order=orig_route.visit_order,
            total_distance_m=float(orig_route.total_distance_m),
            total_duration_s=int(orig_route.total_duration_s),
            total_co2_g=0.0,  # will fill in
            is_recommended=False,
        )
        session.add(new_route)
        await session.flush()

        engine_live = orig_route.engine in LIVE_TRAFFIC_ENGINES
        total_co2 = 0.0
        for orig_seg in orig_route.segments:
            speed = float(orig_seg.avg_speed_kmh) if orig_seg.avg_speed_kmh is not None else None
            mult = book.speed_multiplier(speed, engine_has_live_traffic=engine_live)
            grade = float(orig_seg.grade_pct) if orig_seg.grade_pct is not None else None
            grade_mult = _grade_multiplier(grade)
            co2 = (float(orig_seg.distance_m) / 1000.0) * ef.g_per_km * mult * grade_mult
            total_co2 += co2
            session.add(
                RouteSegment(
                    route_id=new_route.id,
                    seq=orig_seg.seq,
                    from_lat=orig_seg.from_lat,
                    from_lng=orig_seg.from_lng,
                    to_lat=orig_seg.to_lat,
                    to_lng=orig_seg.to_lng,
                    distance_m=float(orig_seg.distance_m),
                    duration_s=int(orig_seg.duration_s),
                    avg_speed_kmh=float(orig_seg.avg_speed_kmh) if orig_seg.avg_speed_kmh is not None else None,
                    speed_bin_mult=mult,
                    co2_g=co2,
                    road_type=orig_seg.road_type,
                    elevation_gain_m=orig_seg.elevation_gain_m,
                    elevation_loss_m=orig_seg.elevation_loss_m,
                    grade_pct=orig_seg.grade_pct,
                )
            )
        new_route.total_co2_g = total_co2
        new_routes_for_narrative.append(new_route)

        if best_co2_so_far is None or total_co2 < best_co2_so_far:
            best_co2_so_far = total_co2
            recommended_new_route = new_route

        # Rebuild polyline from segments so the frontend can re-draw the
        # original route shape under the new vehicle.
        polyline: list[tuple[float, float]] = []
        for seg in orig_route.segments:
            if not polyline:
                polyline.append((float(seg.from_lat), float(seg.from_lng)))
            polyline.append((float(seg.to_lat), float(seg.to_lng)))

        route_dtos.append(
            RouteDTO(
                id=new_route.id,
                engine=orig_route.engine,
                objective=orig_route.objective,
                total_distance_m=float(orig_route.total_distance_m),
                total_duration_s=int(orig_route.total_duration_s),
                total_co2_g=total_co2,
                is_recommended=False,  # set below
                polyline=polyline,
                segments=None,
            )
        )

    if recommended_new_route is not None:
        recommended_new_route.is_recommended = True
        for dto in route_dtos:
            if dto.id == recommended_new_route.id:
                dto.is_recommended = True

    # Original recommended route's CO₂ vs new vehicle's recommended CO₂
    orig_recommended = next(
        (r for r in original.routes if r.is_recommended),
        original.routes[0],
    )
    savings = float(orig_recommended.total_co2_g) - (recommended_new_route.total_co2_g if recommended_new_route else 0.0)

    # Narrative — best effort
    narrative, llm_trace = await _generate_narrative(
        recommended_new_route,
        new_routes_for_narrative,
        new_snapshot,
    ) if recommended_new_route else (None, None)

    await run_service.finalize_run(
        session, new_run,
        narrative=narrative, status="done", llm_trace=llm_trace,
    )
    await session.commit()

    return RecalculateResponse(
        original_run_id=original_run_id,
        new_run_id=new_run.id,
        vehicle=VehicleSnapshot(**new_snapshot),
        routes=sorted(route_dtos, key=lambda d: (not d.is_recommended, d.total_co2_g)),
        savings_vs_original_g=savings,
        narrative=narrative,
    )

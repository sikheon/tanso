"""P2P routing service — Adapter + Eco + Normalizer + DB persistence."""

from __future__ import annotations

import logging
from datetime import time as _time

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import P2PRequest, P2PResponse, RouteDTO, VehicleSnapshot, WeightsDTO
from src.core.config import get_settings
from src.eco import EcoFactorBook, EmissionCalculator, Weights, rank_recommend, score_candidates
from src.llm import GeminiClient, NarrativeAgent
from src.models import Route, RouteSegment, Run
from src.routing.adapter import RoutingAdapter
from src.routing.kakao import KakaoProvider
from src.routing.ors import ORSProvider
from src.routing.schemas import EngineName, RouteRequest
from src.services import run_service
from src.services.vehicle_service import get_vehicle, vehicle_to_snapshot

logger = logging.getLogger(__name__)


def _build_adapter(engines: list[str]) -> RoutingAdapter:
    settings = get_settings()
    providers = []
    if "kakao" in engines:
        if not settings.kakao_rest_api_key:
            raise RuntimeError("KAKAO_REST_API_KEY missing — cannot use 'kakao' engine")
        providers.append(KakaoProvider(settings.kakao_rest_api_key))
    if "ors" in engines:
        if not settings.ors_api_key:
            raise RuntimeError("ORS_API_KEY missing — cannot use 'ors' engine")
        providers.append(ORSProvider(settings.ors_api_key))
    if not providers:
        raise ValueError("At least one engine must be specified")
    return RoutingAdapter(providers)


async def _generate_narrative(
    recommended_route: Route, all_routes: list[Route], vehicle_snapshot: dict
) -> tuple[str | None, dict | None]:
    settings = get_settings()
    if not settings.enable_llm_narrative or not settings.gemini_api_key:
        return None, None

    alts = [r for r in all_routes if r is not recommended_route]
    worst_co2 = max((float(r.total_co2_g) for r in alts), default=float(recommended_route.total_co2_g))
    saved = max(0.0, worst_co2 - float(recommended_route.total_co2_g))

    payload = {
        "recommended": {
            "engine": recommended_route.engine,
            "objective": recommended_route.objective,
            "distance_km": round(float(recommended_route.total_distance_m) / 1000.0, 1),
            "duration_min": int(recommended_route.total_duration_s) // 60,
            "co2_g": round(float(recommended_route.total_co2_g)),
        },
        "alternatives": [
            {
                "engine": r.engine,
                "objective": r.objective,
                "distance_km": round(float(r.total_distance_m) / 1000.0, 1),
                "duration_min": int(r.total_duration_s) // 60,
                "co2_g": round(float(r.total_co2_g)),
            }
            for r in alts
        ],
        "co2_saved_g": round(saved),
        "vehicle": f"{vehicle_snapshot['fuel_type']} / {vehicle_snapshot['vehicle_class']}",
    }
    try:
        agent = NarrativeAgent(GeminiClient(settings.gemini_api_key, model=settings.gemini_model))
        outcome = await agent.generate(payload)
        return outcome.text, {"narrative_ms": outcome.trace.elapsed_ms, "used_fallback": outcome.used_fallback}
    except Exception as e:  # noqa: BLE001
        logger.warning("narrative.generate_failed", extra={"err": str(e)})
        return None, {"narrative_error": str(e)}


def _weights_or_default(weights: WeightsDTO | None) -> Weights:
    if weights is None:
        return Weights.balanced()
    return Weights(distance=weights.distance, duration=weights.duration, co2=weights.co2)


async def execute_p2p(session: AsyncSession, request: P2PRequest) -> P2PResponse:
    # 1. Vehicle + snapshot
    vehicle = await get_vehicle(session, request.vehicle_id)
    snapshot = vehicle_to_snapshot(vehicle)

    # 2. Eco factors
    book = await EcoFactorBook.load(session)

    # 3. Create Run (running status)
    run = await run_service.create_run(
        session,
        mode="p2p",
        user_input_text=None,
        parsed_request=request.model_dump(mode="json"),
        vehicle_id=vehicle.id,
        vehicle_snapshot=snapshot,
        llm_weights=request.options.weights.model_dump() if request.options.weights else None,
        label=request.options.label,
    )

    # 4. Routing call
    adapter = _build_adapter([e for e in request.options.engines])
    try:
        route_req = RouteRequest(
            origin={"lat": request.origin.lat, "lng": request.origin.lng},
            destination={"lat": request.destination.lat, "lng": request.destination.lng},
            waypoints=[
                {"lat": w.lat, "lng": w.lng} for w in (request.waypoints or [])
            ],
            alternatives=request.options.alternatives_per_engine,
        )
        multi = await adapter.get_all_routes(route_req)
    finally:
        await adapter.close()

    if not multi.any_success:
        await run_service.finalize_run(
            session, run,
            narrative=None,
            status="failed",
            error_message="; ".join(multi.warnings) or "All engines failed",
        )
        await session.commit()
        raise RuntimeError("All routing engines failed: " + "; ".join(multi.warnings))

    # 5. Compute CO₂ per route
    calc = EmissionCalculator(book)
    enriched: list[tuple] = []  # (RouteSchema, total_co2_g, segment_emissions)
    for r in multi.routes:
        emission = calc.calculate(
            r,
            fuel_type=snapshot["fuel_type"],
            vehicle_class=snapshot["vehicle_class"],
        )
        enriched.append((r, emission.total_co2_g, emission.segments))

    # 6. Normalize + rank
    weights = _weights_or_default(request.options.weights)
    scored = score_candidates(
        [t[0] for t in enriched], [t[1] for t in enriched], weights,
    )
    ranked = rank_recommend(scored)
    best_score_route = ranked[0].route

    # 7. Persist routes + segments
    route_dtos: list[RouteDTO] = []
    route_idx_to_id: dict[int, int] = {}
    recommended_orm: Route | None = None
    for idx, (route_schema, total_co2, seg_emissions) in enumerate(enriched):
        is_rec = route_schema is best_score_route
        scored_match = next(s for s in scored if s.route is route_schema)
        orm = Route(
            run_id=run.id,
            engine=route_schema.engine.value,
            objective=route_schema.objective.value,
            total_distance_m=float(route_schema.total_distance_m),
            total_duration_s=int(route_schema.total_duration_s),
            total_co2_g=float(total_co2),
            is_recommended=is_rec,
        )
        session.add(orm)
        await session.flush()
        route_idx_to_id[idx] = orm.id
        if is_rec:
            recommended_orm = orm

        for se in seg_emissions:
            seg_schema = route_schema.segments[se.seq] if se.seq < len(route_schema.segments) else None
            if seg_schema is None:
                continue
            session.add(
                RouteSegment(
                    route_id=orm.id,
                    seq=se.seq,
                    from_lat=seg_schema.from_point.lat,
                    from_lng=seg_schema.from_point.lng,
                    to_lat=seg_schema.to_point.lat,
                    to_lng=seg_schema.to_point.lng,
                    distance_m=float(se.distance_m),
                    duration_s=int(se.duration_s),
                    avg_speed_kmh=float(se.avg_speed_kmh) if se.avg_speed_kmh is not None else None,
                    speed_bin_mult=float(se.speed_multiplier),
                    co2_g=float(se.co2_g),
                    road_type=seg_schema.road_type,
                    elevation_gain_m=seg_schema.elevation_gain_m,
                    elevation_loss_m=seg_schema.elevation_loss_m,
                    grade_pct=seg_schema.grade_pct,
                )
            )

        route_dtos.append(
            RouteDTO(
                id=orm.id,
                engine=route_schema.engine.value,
                objective=route_schema.objective.value,
                total_distance_m=float(route_schema.total_distance_m),
                total_duration_s=int(route_schema.total_duration_s),
                total_co2_g=float(total_co2),
                is_recommended=is_rec,
                score=scored_match.score,
                polyline=route_schema.polyline[:],
                segments=None,  # detail comes via GET /runs/{id}
            )
        )

    # 8. Narrative (best-effort)
    narrative = None
    llm_trace: dict | None = None
    if request.options.generate_narrative and recommended_orm is not None:
        narrative, narrative_trace = await _generate_narrative(
            recommended_orm,
            [r for r in await _refresh_routes(session, run.id)],
            snapshot,
        )
        llm_trace = narrative_trace

    # 9. Finalize
    await run_service.finalize_run(
        session, run,
        narrative=narrative, status="done", llm_trace=llm_trace,
    )
    await session.commit()
    await session.refresh(run)

    return P2PResponse(
        run_id=run.id,
        status="done",
        vehicle=VehicleSnapshot(**snapshot),
        weights=WeightsDTO(
            distance=weights.distance, duration=weights.duration, co2=weights.co2
        ),
        routes=sorted(
            route_dtos, key=lambda d: (not d.is_recommended, d.score or 0.0)
        ),
        narrative=narrative,
        warnings=multi.warnings,
        created_at=run.created_at,
    )


async def _refresh_routes(session: AsyncSession, run_id: int) -> list[Route]:
    from sqlalchemy import select
    stmt = select(Route).where(Route.run_id == run_id)
    return list((await session.execute(stmt)).scalars().all())

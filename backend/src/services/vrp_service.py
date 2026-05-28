"""VRP service — Matrix + OR-Tools + Eco + DB persistence."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    VRPJobDTO,
    VRPRequest,
    VRPResponse,
    VRPResultDTO,
    VRPSolverInfo,
    VehicleSnapshot,
)
from src.core.config import get_settings
from src.eco import EcoFactorBook
from src.models import Job, Route, Run
from src.routing.schemas import LatLng
from src.services import run_service
from src.services.vehicle_service import get_vehicle, vehicle_to_snapshot
from src.vrp import (
    ORSMatrixBuilder,
    VRPJob as SolverJob,
    VRPObjective,
    VRPRequest as SolverRequest,
    VRPSolver,
)

logger = logging.getLogger(__name__)


async def execute_vrp(session: AsyncSession, request: VRPRequest) -> VRPResponse:
    settings = get_settings()
    if not settings.ors_api_key:
        raise RuntimeError("ORS_API_KEY required for VRP matrix")

    # 1. Vehicle + snapshot
    vehicle = await get_vehicle(session, request.vehicle_id)
    snapshot = vehicle_to_snapshot(vehicle)
    book = await EcoFactorBook.load(session)

    # 2. Build Run (status=running) + persist depot/jobs
    run = await run_service.create_run(
        session,
        mode="vrp",
        user_input_text=None,
        parsed_request=request.model_dump(mode="json"),
        vehicle_id=vehicle.id,
        vehicle_snapshot=snapshot,
        llm_weights=request.options.weights.model_dump() if request.options.weights else None,
        label=request.options.label,
    )

    # Save depot as job seq=0, then user jobs as 1..N
    job_records: list[Job] = []
    depot_job = Job(
        run_id=run.id, seq=0, label="depot",
        lat=request.depot.lat, lng=request.depot.lng,
        address=request.depot.address, is_depot=True,
    )
    session.add(depot_job)
    job_records.append(depot_job)
    for i, j in enumerate(request.jobs, start=1):
        rec = Job(
            run_id=run.id, seq=i, label=j.label,
            lat=j.location.lat, lng=j.location.lng,
            address=j.address,
            time_window_start=j.time_window_start,
            time_window_end=j.time_window_end,
            service_time_min=j.service_time_min,
            constraints_json=j.constraints or None,
        )
        session.add(rec)
        job_records.append(rec)
    await session.flush()

    # 3. Build solver request + matrix
    solver_request = SolverRequest(
        depot=request.depot,
        jobs=[
            SolverJob(
                label=j.label,
                location=LatLng(lat=j.location.lat, lng=j.location.lng),
                address=j.address,
                time_window_start=j.time_window_start,
                time_window_end=j.time_window_end,
                service_time_min=j.service_time_min,
                constraints=j.constraints or [],
            )
            for j in request.jobs
        ],
        fuel_type=snapshot["fuel_type"],
        vehicle_class=snapshot["vehicle_class"],
        objectives=[VRPObjective(o) for o in request.options.objectives],
        solver_time_limit_s=request.options.solver_time_limit_s,
        matrix_engine=request.options.matrix_engine,
    )

    builder = ORSMatrixBuilder(settings.ors_api_key, book)
    try:
        matrices = await builder.build(solver_request)
    finally:
        await builder.close()

    # 4. Solve for each objective
    solver = VRPSolver(time_limit_s=request.options.solver_time_limit_s)
    results: list[VRPResultDTO] = []
    persisted_routes: list[Route] = []
    best_co2: float | None = None
    best_route: Route | None = None

    job_ids_by_solver_idx = {i + 1: rec.id for i, rec in enumerate(job_records[1:])}

    for obj in solver_request.objectives:
        outcome = solver.solve(matrices, obj)
        r = outcome.result
        # Map solver node indices (1..N) -> persisted job DB ids
        visit_job_ids = [job_ids_by_solver_idx[idx] for idx in r.visit_order if idx in job_ids_by_solver_idx]

        # Persist as a Route row (single per objective)
        orm_route = Route(
            run_id=run.id,
            engine="or_tools_vrp",
            objective=f"{obj.value}_min",
            visit_order=visit_job_ids,
            total_distance_m=r.total_distance_m,
            total_duration_s=r.total_duration_s,
            total_co2_g=r.total_co2_g,
            is_recommended=False,
        )
        session.add(orm_route)
        await session.flush()
        persisted_routes.append(orm_route)

        if r.feasible and (best_co2 is None or r.total_co2_g < best_co2):
            best_co2 = r.total_co2_g
            best_route = orm_route

        results.append(
            VRPResultDTO(
                objective=obj.value,
                visit_order_job_ids=visit_job_ids,
                visit_order_polyline=[],  # detailed polyline omitted for MVP
                total_distance_m=r.total_distance_m,
                total_duration_s=r.total_duration_s,
                total_co2_g=r.total_co2_g,
                is_recommended=False,
                solve_ms=outcome.elapsed_ms,
                feasible=r.feasible,
                status=r.status,
            )
        )

    if best_route is not None:
        best_route.is_recommended = True
        for res in results:
            if (
                res.total_co2_g == float(best_route.total_co2_g)
                and res.objective == best_route.objective.replace("_min", "")
            ):
                res.is_recommended = True

    # 5. Finalize Run
    await run_service.finalize_run(
        session, run, narrative=None, status="done",
    )
    await session.commit()
    await session.refresh(run)

    jobs_out = [
        VRPJobDTO(
            id=rec.id,
            seq=rec.seq,
            label=rec.label,
            location=LatLng(lat=float(rec.lat), lng=float(rec.lng)),
            address=rec.address,
            time_window_start=rec.time_window_start,
            time_window_end=rec.time_window_end,
            service_time_min=rec.service_time_min,
            constraints=rec.constraints_json or [],
        )
        for rec in job_records[1:]  # skip depot
    ]

    return VRPResponse(
        run_id=run.id,
        status="done",
        depot=request.depot,
        jobs=jobs_out,
        vehicle=VehicleSnapshot(**snapshot),
        results=results,
        narrative=None,
        solver=VRPSolverInfo(
            time_limit_s=request.options.solver_time_limit_s,
            metaheuristic="GUIDED_LOCAL_SEARCH",
            matrix_engine=request.options.matrix_engine,
        ),
        warnings=[],
        created_at=run.created_at,
    )

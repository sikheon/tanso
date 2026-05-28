"""Run CRUD router."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    RecalculateRequest,
    RecalculateResponse,
    RouteDTO,
    RunListResponse,
    RunPatchRequest,
    SegmentDTO,
)
from src.core.db import get_db
from src.services import recalc_service, run_service as svc
from src.services.vehicle_service import VehicleNotFoundError

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    mode: Literal["p2p", "vrp"] | None = Query(None),
    vehicle_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RunListResponse:
    items, total = await svc.list_runs(
        db, limit=limit, offset=offset, mode=mode, vehicle_id=vehicle_id
    )
    return RunListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{run_id}")
async def get_run_detail(run_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Return enough detail to replay the run in the UI (routes + segments)."""
    try:
        run = await svc.get_run(db, run_id)
    except svc.RunNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e

    routes: list[dict] = []
    for r in run.routes:
        segments = [
            SegmentDTO(
                seq=s.seq,
                from_lat=float(s.from_lat),
                from_lng=float(s.from_lng),
                to_lat=float(s.to_lat),
                to_lng=float(s.to_lng),
                distance_m=float(s.distance_m),
                duration_s=int(s.duration_s),
                avg_speed_kmh=float(s.avg_speed_kmh) if s.avg_speed_kmh is not None else None,
                speed_bin_mult=float(s.speed_bin_mult) if s.speed_bin_mult is not None else None,
                co2_g=float(s.co2_g),
                road_type=s.road_type,
                elevation_gain_m=float(s.elevation_gain_m) if s.elevation_gain_m is not None else None,
                elevation_loss_m=float(s.elevation_loss_m) if s.elevation_loss_m is not None else None,
                grade_pct=float(s.grade_pct) if s.grade_pct is not None else None,
            ).model_dump()
            for s in r.segments
        ]
        routes.append(
            RouteDTO(
                id=r.id,
                engine=r.engine,
                objective=r.objective,
                total_distance_m=float(r.total_distance_m),
                total_duration_s=int(r.total_duration_s),
                total_co2_g=float(r.total_co2_g),
                is_recommended=r.is_recommended,
                polyline=[],  # geometry hidden — use segment from/to for now
                segments=segments,
            ).model_dump()
        )

    return {
        "id": run.id,
        "mode": run.mode,
        "label": run.label,
        "notes": run.notes,
        "status": run.status,
        "vehicle_snapshot": run.vehicle_snapshot,
        "weights": run.llm_weights,
        "constraints": run.llm_constraints,
        "narrative": run.narrative_text,
        "routes": routes,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


@router.patch("/{run_id}")
async def patch_run(
    run_id: int,
    payload: RunPatchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        run = await svc.patch_run(db, run_id, payload)
    except svc.RunNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    await db.commit()
    return {"id": run.id, "label": run.label, "notes": run.notes}


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)) -> None:
    try:
        await svc.delete_run(db, run_id)
    except svc.RunNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    await db.commit()


@router.post(
    "/{run_id}/recalculate",
    response_model=RecalculateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def recalculate(
    run_id: int,
    payload: RecalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> RecalculateResponse:
    try:
        return await recalc_service.recalculate_with_vehicle(
            db,
            original_run_id=run_id,
            new_vehicle_id=payload.vehicle_id,
        )
    except svc.RunNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except recalc_service.RecalculateError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

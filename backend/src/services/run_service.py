"""Run CRUD + persistence helpers used by routing/vrp/parse/recalc services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas import RunListItem, RunPatchRequest, RunSummaryFigure, VehicleSnapshot
from src.models import Job, Route, Run


class RunNotFoundError(LookupError):
    pass


async def create_run(
    session: AsyncSession,
    *,
    mode: str,
    user_input_text: str | None,
    parsed_request: dict[str, Any],
    vehicle_id: int | None,
    vehicle_snapshot: dict[str, Any] | None,
    llm_weights: dict[str, Any] | None = None,
    llm_constraints: list[Any] | None = None,
    label: str | None = None,
) -> Run:
    run = Run(
        mode=mode,
        user_input_text=user_input_text,
        parsed_request=parsed_request,
        vehicle_id=vehicle_id,
        vehicle_snapshot=vehicle_snapshot,
        llm_weights=llm_weights,
        llm_constraints=llm_constraints,
        status="running",
        label=label,
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_run(
    session: AsyncSession,
    run: Run,
    *,
    narrative: str | None,
    status: str = "done",
    error_message: str | None = None,
    llm_trace: dict[str, Any] | None = None,
) -> None:
    run.narrative_text = narrative
    run.status = status
    run.error_message = error_message
    run.llm_trace = llm_trace
    run.finished_at = datetime.now(UTC)


async def get_run(session: AsyncSession, run_id: int) -> Run:
    stmt = (
        select(Run)
        .where(Run.id == run_id)
        .options(
            selectinload(Run.jobs),
            selectinload(Run.routes).selectinload(Route.segments),
        )
    )
    run = (await session.execute(stmt)).unique().scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(f"Run {run_id} not found")
    return run


async def patch_run(
    session: AsyncSession, run_id: int, payload: RunPatchRequest
) -> Run:
    run = await get_run(session, run_id)
    if payload.label is not None:
        run.label = payload.label
    if payload.notes is not None:
        run.notes = payload.notes
    await session.flush()
    return run


async def delete_run(session: AsyncSession, run_id: int) -> None:
    run = await get_run(session, run_id)
    await session.delete(run)
    await session.flush()


async def list_runs(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    mode: str | None = None,
    vehicle_id: int | None = None,
) -> tuple[list[RunListItem], int]:
    base = select(Run)
    if mode:
        base = base.where(Run.mode == mode)
    if vehicle_id is not None:
        base = base.where(Run.vehicle_id == vehicle_id)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows_stmt = (
        base.order_by(desc(Run.created_at))
        .offset(offset)
        .limit(limit)
        .options(selectinload(Run.routes))
    )
    runs = list((await session.execute(rows_stmt)).scalars().unique().all())

    items: list[RunListItem] = []
    for r in runs:
        items.append(
            RunListItem(
                id=r.id,
                mode=r.mode,  # type: ignore[arg-type]
                label=r.label,
                vehicle=(VehicleSnapshot(**r.vehicle_snapshot) if r.vehicle_snapshot else None),
                summary=_summary_from_routes(r.routes),
                status=r.status,
                created_at=r.created_at,
            )
        )
    return items, total


def _summary_from_routes(routes: list[Route]) -> RunSummaryFigure | None:
    """Pick the recommended route (or first) for list-view summary numbers."""
    if not routes:
        return None
    pick = next((r for r in routes if r.is_recommended), routes[0])
    return RunSummaryFigure(
        distance_km=float(pick.total_distance_m) / 1000.0,
        duration_min=int(pick.total_duration_s) // 60,
        co2_g=float(pick.total_co2_g),
    )

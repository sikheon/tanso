"""Aggregate statistics across all stored Runs."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import StatsByClass, StatsByEngine, StatsSummaryResponse
from src.models import Route, Run


async def summary(session: AsyncSession) -> StatsSummaryResponse:
    total_runs = (await session.execute(select(func.count(Run.id)))).scalar_one()

    # Sum of total_distance_m and total_co2_g across all 'recommended' routes
    rec_stmt = select(
        func.coalesce(func.sum(Route.total_distance_m), 0),
        func.coalesce(func.sum(Route.total_co2_g), 0),
    ).where(Route.is_recommended.is_(True))
    rec_dist_m, rec_co2_g = (await session.execute(rec_stmt)).one()

    # Savings = sum of (max_co2_per_run - min_co2_per_run) across runs that
    # have >=2 routes (interpreted as the best vs worst trade-off captured)
    savings_stmt = select(
        func.coalesce(
            func.sum(
                select(
                    func.max(Route.total_co2_g) - func.min(Route.total_co2_g)
                )
                .where(Route.run_id == Run.id)
                .correlate(Run)
                .scalar_subquery()
            ),
            0,
        )
    )
    savings_g = (await session.execute(savings_stmt)).scalar_one() or 0

    # By vehicle_class — using vehicle_snapshot JSON
    by_class_rows = (
        await session.execute(
            select(
                Run.vehicle_snapshot["vehicle_class"].as_string().label("vc"),
                func.count(Run.id).label("runs_n"),
                func.coalesce(func.avg(Route.total_co2_g / func.nullif(Route.total_distance_m, 0) * 1000), 0).label("avg_g_per_km"),
            )
            .join(Route, Route.run_id == Run.id)
            .where(Route.is_recommended.is_(True))
            .where(Run.vehicle_snapshot.isnot(None))
            .group_by("vc")
        )
    ).all()
    by_vehicle_class = [
        StatsByClass(
            vehicle_class=row.vc or "unknown",
            runs=int(row.runs_n),
            avg_co2_g_per_km=float(row.avg_g_per_km or 0),
        )
        for row in by_class_rows
    ]

    by_engine_rows = (
        await session.execute(
            select(Route.engine, func.count(Route.id))
            .where(Route.is_recommended.is_(True))
            .group_by(Route.engine)
        )
    ).all()
    by_engine = [
        StatsByEngine(engine=row[0], recommended_count=int(row[1]))
        for row in by_engine_rows
    ]

    return StatsSummaryResponse(
        total_runs=int(total_runs),
        total_distance_km=float(rec_dist_m) / 1000.0,
        total_co2_kg=float(rec_co2_g) / 1000.0,
        total_co2_saved_kg=float(savings_g) / 1000.0,
        by_vehicle_class=by_vehicle_class,
        by_engine=by_engine,
    )

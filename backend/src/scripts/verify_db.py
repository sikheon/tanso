"""Verify database connectivity, PostGIS version, and seed counts.

Usage:
    python -m src.scripts.verify_db
"""

from __future__ import annotations

from src.core import asyncio_compat  # noqa: F401  — must run before psycopg imports

import asyncio
import sys

from sqlalchemy import func, select, text

from src.core.config import get_settings
from src.core.db import AsyncSessionLocal
from src.models import EmissionFactor, SpeedBinFactor, Vehicle


async def main() -> int:
    settings = get_settings()
    print(f"DB URL: {settings.database_url}\n")

    try:
        async with AsyncSessionLocal() as session:
            # 1. Basic SELECT
            v = (await session.execute(text("SELECT version()"))).scalar()
            print(f"[OK] Postgres: {v.split(',')[0]}")

            # 2. PostGIS
            pg = (
                await session.execute(text("SELECT PostGIS_Version()"))
            ).scalar()
            print(f"[OK] PostGIS:  {pg}")

            # 3. Seed counts
            ef = (
                await session.execute(select(func.count()).select_from(EmissionFactor))
            ).scalar()
            sb = (
                await session.execute(select(func.count()).select_from(SpeedBinFactor))
            ).scalar()
            vh = (
                await session.execute(select(func.count()).select_from(Vehicle))
            ).scalar()
            print(
                f"\nSeed counts:\n  emission_factors  : {ef}\n"
                f"  speed_bin_factors : {sb}\n  vehicles          : {vh}"
            )

            if ef == 0 or sb == 0:
                print("\n[!] Seeds appear empty. Run: python -m src.scripts.init_db --skip-create-db")
                return 2

            # 4. Show a sample emission factor row
            row = (
                await session.execute(
                    select(EmissionFactor).where(
                        EmissionFactor.fuel_type == "electric",
                        EmissionFactor.vehicle_class == "sedan",
                    )
                )
            ).scalar()
            if row:
                print(
                    f"\nSample (electric/sedan): {row.g_per_km} g/km — {row.source}"
                )

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        return 1

    print("\n[OK] All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Extended /health endpoint with DB + PostGIS ping."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src import __version__
from src.core.db import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str | dict[str, str]]:
    checks: dict[str, str] = {}
    overall = "ok"

    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"fail: {type(e).__name__}"
        overall = "degraded"

    try:
        pg = (await db.execute(text("SELECT PostGIS_Version()"))).scalar()
        checks["postgis"] = str(pg) if pg else "unknown"
    except Exception as e:
        checks["postgis"] = f"fail: {type(e).__name__}"
        overall = "degraded"

    return {"status": overall, "version": __version__, "checks": checks}

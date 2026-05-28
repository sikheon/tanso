"""Stats summary router (read-only)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import StatsSummaryResponse
from src.core.db import get_db
from src.services import stats_service

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummaryResponse)
async def summary(db: AsyncSession = Depends(get_db)) -> StatsSummaryResponse:
    return await stats_service.summary(db)

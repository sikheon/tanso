"""Emission factor read-only router."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import EmissionFactorDTO
from src.core.db import get_db
from src.models import EmissionFactor

router = APIRouter(prefix="/api/v1/emission-factors", tags=["reference"])


@router.get("", response_model=list[EmissionFactorDTO])
async def list_emission_factors(db: AsyncSession = Depends(get_db)) -> list[EmissionFactor]:
    rows = (await db.execute(
        select(EmissionFactor).order_by(EmissionFactor.fuel_type, EmissionFactor.vehicle_class)
    )).scalars().all()
    return list(rows)

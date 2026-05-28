"""Vehicle CRUD router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    VehicleCreateRequest,
    VehicleResponse,
    VehicleUpdateRequest,
)
from src.core.db import get_db
from src.services import vehicle_service as svc

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(db: AsyncSession = Depends(get_db)) -> list[dict]:
    vehicles = await svc.list_vehicles(db)
    return [svc.vehicle_to_response_dict(v) for v in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        v = await svc.get_vehicle(db, vehicle_id)
    except svc.VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    return svc.vehicle_to_response_dict(v)


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        v = await svc.create_vehicle(db, payload)
    except svc.EmissionFactorNotFoundError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await db.commit()
    await db.refresh(v)
    return svc.vehicle_to_response_dict(v)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        v = await svc.update_vehicle(db, vehicle_id, payload)
    except svc.VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except svc.EmissionFactorNotFoundError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    await db.commit()
    await db.refresh(v)
    return svc.vehicle_to_response_dict(v)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await svc.delete_vehicle(db, vehicle_id)
    except svc.VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    await db.commit()

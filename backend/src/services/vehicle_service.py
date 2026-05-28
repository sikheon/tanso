"""Vehicle CRUD + snapshot helper.

The snapshot helper is what other services (routing/vrp/recalc) call when
they need to freeze a vehicle's identity into a Run record. Centralizing
it here means the snapshot shape stays consistent across every code path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import VehicleCreateRequest, VehicleUpdateRequest
from src.models import EmissionFactor, Vehicle


class VehicleNotFoundError(LookupError):
    pass


class EmissionFactorNotFoundError(LookupError):
    pass


async def list_vehicles(session: AsyncSession) -> list[Vehicle]:
    result = await session.execute(
        select(Vehicle).order_by(Vehicle.id.asc())
    )
    return list(result.scalars().unique().all())


async def get_vehicle(session: AsyncSession, vehicle_id: int) -> Vehicle:
    v = await session.get(Vehicle, vehicle_id)
    if v is None:
        raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
    return v


async def _resolve_emission_factor(
    session: AsyncSession, fuel_type: str, vehicle_class: str
) -> EmissionFactor:
    stmt = (
        select(EmissionFactor)
        .where(
            EmissionFactor.fuel_type == fuel_type,
            EmissionFactor.vehicle_class == vehicle_class,
        )
        .order_by(EmissionFactor.valid_from.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise EmissionFactorNotFoundError(
            f"No emission factor for {fuel_type}/{vehicle_class}"
        )
    return row


async def create_vehicle(
    session: AsyncSession, payload: VehicleCreateRequest
) -> Vehicle:
    ef = await _resolve_emission_factor(session, payload.fuel_type, payload.vehicle_class)
    v = Vehicle(
        plate=payload.plate,
        model=payload.model,
        fuel_type=payload.fuel_type,
        vehicle_class=payload.vehicle_class,
        year_produced=payload.year_produced,
        emission_factor_id=ef.id,
    )
    session.add(v)
    await session.flush()
    await session.refresh(v)
    return v


async def update_vehicle(
    session: AsyncSession, vehicle_id: int, payload: VehicleUpdateRequest
) -> Vehicle:
    v = await get_vehicle(session, vehicle_id)
    data = payload.model_dump(exclude_unset=True)
    fuel_type = data.get("fuel_type", v.fuel_type)
    vehicle_class = data.get("vehicle_class", v.vehicle_class)
    fuel_or_class_changed = (
        ("fuel_type" in data and data["fuel_type"] != v.fuel_type)
        or ("vehicle_class" in data and data["vehicle_class"] != v.vehicle_class)
    )

    for k, val in data.items():
        setattr(v, k, val)

    if fuel_or_class_changed:
        ef = await _resolve_emission_factor(session, fuel_type, vehicle_class)
        v.emission_factor_id = ef.id

    await session.flush()
    await session.refresh(v)
    return v


async def delete_vehicle(session: AsyncSession, vehicle_id: int) -> None:
    v = await get_vehicle(session, vehicle_id)
    await session.delete(v)
    await session.flush()


def vehicle_to_response_dict(vehicle: Vehicle) -> dict[str, Any]:
    """Shape matching `VehicleResponse` (joinedload of emission_factor expected)."""
    ef = vehicle.emission_factor
    return {
        "id": vehicle.id,
        "plate": vehicle.plate,
        "model": vehicle.model,
        "fuel_type": vehicle.fuel_type,
        "vehicle_class": vehicle.vehicle_class,
        "year_produced": vehicle.year_produced,
        "emission_factor_g_per_km": float(ef.g_per_km) if ef else None,
        "emission_factor_source": ef.source if ef else None,
        "created_at": vehicle.created_at,
    }


def vehicle_to_snapshot(vehicle: Vehicle) -> dict[str, Any]:
    """Build the JSON blob that Run.vehicle_snapshot will store.

    Stays decoupled from any further vehicle row mutations or deletions.
    """
    ef = vehicle.emission_factor
    if ef is None:
        raise EmissionFactorNotFoundError(
            f"Vehicle {vehicle.id} has no linked emission factor"
        )
    return {
        "id": vehicle.id,
        "plate": vehicle.plate,
        "model": vehicle.model,
        "fuel_type": vehicle.fuel_type,
        "vehicle_class": vehicle.vehicle_class,
        "year_produced": vehicle.year_produced,
        "emission_factor_g_per_km": float(ef.g_per_km),
        "emission_factor_source": ef.source,
    }

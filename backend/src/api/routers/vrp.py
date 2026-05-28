"""VRP routing router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import VRPRequest, VRPResponse
from src.core.db import get_db
from src.services import vrp_service
from src.services.vehicle_service import VehicleNotFoundError

router = APIRouter(prefix="/api/v1/routes", tags=["routing"])


@router.post("/vrp", response_model=VRPResponse, status_code=status.HTTP_201_CREATED)
async def vrp(payload: VRPRequest, db: AsyncSession = Depends(get_db)) -> VRPResponse:
    try:
        return await vrp_service.execute_vrp(db, payload)
    except VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

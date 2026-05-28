"""P2P routing router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import P2PRequest, P2PResponse
from src.core.db import get_db
from src.services import routing_service
from src.services.vehicle_service import VehicleNotFoundError

router = APIRouter(prefix="/api/v1/routes", tags=["routing"])


@router.post("/p2p", response_model=P2PResponse, status_code=status.HTTP_201_CREATED)
async def p2p(
    payload: P2PRequest,
    db: AsyncSession = Depends(get_db),
) -> P2PResponse:
    try:
        return await routing_service.execute_p2p(db, payload)
    except VehicleNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

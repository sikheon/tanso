"""Natural-language parsing router."""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas import ParseRequest, ParseResponse
from src.services import parse_service

router = APIRouter(prefix="/api/v1", tags=["parse"])


@router.post("/parse", response_model=ParseResponse)
async def parse(payload: ParseRequest) -> ParseResponse:
    try:
        return await parse_service.parse_natural_language(payload)
    except parse_service.ParseError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e

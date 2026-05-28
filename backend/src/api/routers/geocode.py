"""Geocoding proxy — Kakao Local Search by keyword.

Kakao requires the REST API key in the Authorization header, so we cannot
expose it to the browser. This router proxies the request server-side.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from src.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/geocode", tags=["geocode"])

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


@router.get("/search")
async def search_places(
    q: str = Query(..., min_length=1, max_length=80, description="검색어"),
    limit: int = Query(8, ge=1, le=15),
) -> dict:
    settings = get_settings()
    if not settings.kakao_rest_api_key:
        raise HTTPException(503, "KAKAO_REST_API_KEY not configured")

    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(
            KAKAO_KEYWORD_URL,
            params={"query": q, "size": limit},
            headers={"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"},
        )
    if r.status_code == 401:
        raise HTTPException(503, "Kakao auth failed")
    if r.status_code == 429:
        raise HTTPException(429, "Kakao rate limit")
    if not r.is_success:
        raise HTTPException(502, f"Kakao error: {r.status_code}")

    body = r.json()
    items = []
    for d in body.get("documents", []):
        try:
            items.append({
                "name": d.get("place_name") or d.get("address_name"),
                "address": d.get("road_address_name") or d.get("address_name"),
                "category": d.get("category_name"),
                "lat": float(d["y"]),
                "lng": float(d["x"]),
            })
        except (KeyError, TypeError, ValueError):
            continue

    return {"q": q, "count": len(items), "items": items}

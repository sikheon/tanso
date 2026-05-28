"""Ping external APIs to verify env-loaded keys are valid."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from src.core.config import get_settings


async def ping_kakao(settings) -> None:
    print("--- Kakao Mobility ---")
    if not settings.kakao_rest_api_key or settings.kakao_rest_api_key.startswith("__"):
        print("  SKIP: KAKAO_REST_API_KEY not set")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://apis-navi.kakaomobility.com/v1/directions",
            params={
                "origin": "126.9720,37.5547",       # 서울역
                "destination": "129.0413,35.1147",  # 부산역
                "priority": "RECOMMEND",
            },
            headers={"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"},
        )
    print(f"  status: {r.status_code}")
    try:
        body = r.json()
        rt = body["routes"][0]
        summary = rt.get("summary", {})
        print(
            f"  OK: result_code={rt.get('result_code')}, "
            f"distance={summary.get('distance')} m, "
            f"duration={summary.get('duration')} s"
        )
    except Exception:
        print(f"  body: {r.text[:300]}")


async def ping_ors(settings) -> None:
    print("--- OpenRouteService ---")
    if not settings.ors_api_key or settings.ors_api_key.startswith("__"):
        print("  SKIP: ORS_API_KEY not set (waiting for user signup)")
        return
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            headers={
                "Authorization": settings.ors_api_key,
                "Content-Type": "application/json",
            },
            json={"coordinates": [[126.9720, 37.5547], [129.0413, 35.1147]]},
        )
    print(f"  status: {r.status_code}")
    try:
        body = r.json()
        feats = body.get("features", [])
        if feats:
            props = feats[0].get("properties", {}).get("summary", {})
            print(
                f"  OK: distance={props.get('distance')} m, "
                f"duration={props.get('duration')} s"
            )
        else:
            print(f"  body: {json.dumps(body, ensure_ascii=False)[:300]}")
    except Exception:
        print(f"  body: {r.text[:300]}")


async def ping_gemini(settings) -> None:
    print("--- Gemini ---")
    if not settings.gemini_api_key or settings.gemini_api_key.startswith("__"):
        print("  SKIP: GEMINI_API_KEY not set")
        return
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url,
            headers={
                "x-goog-api-key": settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={"contents": [{"parts": [{"text": "Reply with the single word: PONG"}]}]},
        )
    print(f"  status: {r.status_code}")
    try:
        body = r.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        print(f"  OK: response = {text.strip()!r}")
    except Exception:
        print(f"  body: {r.text[:300]}")


async def main() -> int:
    s = get_settings()
    await ping_kakao(s)
    print()
    await ping_ors(s)
    print()
    await ping_gemini(s)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

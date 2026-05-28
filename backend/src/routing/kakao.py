"""Kakao Mobility Directions API client + response normalization.

Reference: https://apis-navi.kakaomobility.com/v1/directions
Response shape (relevant fields):

  routes[].result_code      -> 0 means success
  routes[].summary.distance -> meters
  routes[].summary.duration -> seconds
  routes[].sections[].roads[]
    .name           string
    .distance       meters
    .duration       seconds
    .traffic_speed  km/h (live)
    .traffic_state  1=원활, 2=서행, 3=지체, 4=정체, 6=알수없음
    .vertexes       flat [lng, lat, lng, lat, ...]
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.routing.base import (
    RoutingProvider,
    RoutingProviderError,
    RoutingProviderUnavailable,
)
from src.routing.elevation import enrich_routes_with_open_elevation
from src.routing.schemas import (
    EngineName,
    LatLng,
    Objective,
    Route,
    RouteRequest,
    Segment,
)

logger = logging.getLogger(__name__)

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"

# Map our priority enum -> Kakao's priority enum
_PRIORITY_MAP = {
    "recommend": "RECOMMEND",
    "time": "TIME",
    "distance": "DISTANCE",
}

# Map our objective per priority for response tagging
_OBJECTIVE_FROM_PRIORITY = {
    "recommend": Objective.RECOMMEND,
    "time": Objective.FASTEST,
    "distance": Objective.SHORTEST,
}

# Map Kakao avoid options
_AVOID_MAP = {"toll": "toll", "motorway": "motorway", "ferry": "ferry"}


def _vertexes_to_polyline(vertexes: list[float]) -> list[tuple[float, float]]:
    """Convert Kakao's flat [lng, lat, lng, lat, ...] -> [(lat, lng), ...]."""
    if not vertexes or len(vertexes) % 2 != 0:
        return []
    return [(vertexes[i + 1], vertexes[i]) for i in range(0, len(vertexes), 2)]


def _parse_route(
    raw: dict, priority: str, index: int
) -> Route:
    rc = raw.get("result_code", 0)
    if rc != 0:
        raise RoutingProviderUnavailable(
            f"Kakao returned result_code={rc}: {raw.get('result_msg', 'unknown')}"
        )

    summary = raw.get("summary") or {}
    total_distance = float(summary.get("distance", 0))
    total_duration = int(summary.get("duration", 0))

    segments: list[Segment] = []
    polyline: list[tuple[float, float]] = []
    seq = 0

    for section in raw.get("sections", []) or []:
        for road in section.get("roads", []) or []:
            verts = road.get("vertexes") or []
            if not verts or len(verts) < 4:
                continue
            road_polyline = _vertexes_to_polyline(verts)
            from_lat, from_lng = road_polyline[0]
            to_lat, to_lng = road_polyline[-1]

            road_distance = float(road.get("distance", 0))
            road_duration = int(road.get("duration", 0))
            traffic_speed = road.get("traffic_speed")
            avg_speed = float(traffic_speed) if traffic_speed and traffic_speed > 0 else None

            segments.append(
                Segment(
                    seq=seq,
                    from_point=LatLng(lat=from_lat, lng=from_lng),
                    to_point=LatLng(lat=to_lat, lng=to_lng),
                    distance_m=road_distance,
                    duration_s=road_duration,
                    avg_speed_kmh=avg_speed,
                    road_type=road.get("name"),
                )
            )
            polyline.extend(road_polyline)
            seq += 1

    objective = _OBJECTIVE_FROM_PRIORITY.get(priority, Objective.RECOMMEND)
    if index > 0:
        objective = Objective.ALTERNATIVE

    return Route(
        engine=EngineName.KAKAO,
        objective=objective,
        total_distance_m=total_distance,
        total_duration_s=total_duration,
        segments=segments,
        polyline=polyline,
        raw_response=raw,
    )


class KakaoProvider(RoutingProvider):
    name = EngineName.KAKAO

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RoutingProviderError("KakaoProvider requires a REST API key")
        self._api_key = api_key
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _call(self, params: dict) -> dict:
        client = await self._get_client()
        r = await client.get(
            KAKAO_DIRECTIONS_URL,
            params=params,
            headers={"Authorization": f"KakaoAK {self._api_key}"},
        )
        if r.status_code == 401:
            raise RoutingProviderError(
                "Kakao auth failed (401). Check KAKAO_REST_API_KEY and "
                "ensure '카카오 모빌리티' is enabled on the app."
            )
        if r.status_code == 429:
            raise RoutingProviderError("Kakao rate limit (429). Slow down requests.")
        r.raise_for_status()
        return r.json()

    async def get_routes(self, request: RouteRequest) -> list[Route]:
        origin = f"{request.origin.lng},{request.origin.lat}"
        destination = f"{request.destination.lng},{request.destination.lat}"

        params: dict[str, str | bool | int] = {
            "origin": origin,
            "destination": destination,
            "priority": _PRIORITY_MAP[request.priority],
            "alternatives": "true" if request.alternatives > 1 else "false",
            "road_details": "true",
            "summary": "false",
        }
        if request.waypoints:
            params["waypoints"] = "|".join(
                f"{w.lng},{w.lat}" for w in request.waypoints
            )

        avoid_list = [_AVOID_MAP[a] for a in request.avoid if a in _AVOID_MAP]
        if avoid_list:
            params["avoid"] = ",".join(avoid_list)

        body = await self._call(params)
        raw_routes = body.get("routes") or []
        if not raw_routes:
            raise RoutingProviderUnavailable("Kakao returned no routes")

        parsed: list[Route] = []
        for i, raw in enumerate(raw_routes[: request.alternatives]):
            try:
                parsed.append(_parse_route(raw, request.priority, i))
            except RoutingProviderUnavailable as e:
                logger.warning("kakao.skip_route", extra={"index": i, "reason": str(e)})
        if not parsed:
            raise RoutingProviderUnavailable("Kakao returned only failed routes")

        # Kakao does not return elevation. Enrich via Open-Elevation
        # (best-effort — failure leaves segments unmodified).
        await enrich_routes_with_open_elevation(parsed)
        return parsed

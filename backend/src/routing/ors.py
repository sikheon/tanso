"""OpenRouteService Directions client + GeoJSON normalization.

Reference: https://api.openrouteservice.org/v2/directions/{profile}/geojson

Response (relevant fields):

  features[].geometry.coordinates  [[lng, lat], ...]  full polyline
  features[].properties.summary    { distance: meters, duration: seconds }
  features[].properties.segments[]
    .distance / .duration
    .steps[]
      .distance / .duration
      .name       road name
      .way_points [start_idx, end_idx]   // indices into geometry.coordinates
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
from src.routing.schemas import (
    EngineName,
    LatLng,
    Objective,
    Route,
    RouteRequest,
    Segment,
)

logger = logging.getLogger(__name__)

_DEFAULT_PROFILE = "driving-car"

# ORS "preference" parameter mapping (their term for what we call priority)
_PREFERENCE_MAP = {
    "recommend": "recommended",  # ORS default
    "time": "fastest",
    "distance": "shortest",
}

_OBJECTIVE_FROM_PRIORITY = {
    "recommend": Objective.RECOMMEND,
    "time": Objective.FASTEST,
    "distance": Objective.SHORTEST,
}

_AVOID_MAP = {"toll": "tollways", "motorway": "highways", "ferry": "ferries"}


def _elevation_stats_for_range(
    coords: list[list[float]], start_idx: int, end_idx: int, distance_m: float
) -> tuple[float | None, float | None, float | None]:
    """Sum gain/loss across the polyline slice [start_idx, end_idx]; derive net grade.

    Returns (gain_m, loss_m, grade_pct) or (None, None, None) if elevation data
    is missing (coord length < 3) on either endpoint.
    """
    if start_idx >= len(coords) or end_idx >= len(coords) or start_idx >= end_idx:
        return None, None, None
    if len(coords[start_idx]) < 3 or len(coords[end_idx]) < 3:
        return None, None, None

    gain = 0.0
    loss = 0.0
    prev_ele = coords[start_idx][2]
    for i in range(start_idx + 1, end_idx + 1):
        if len(coords[i]) < 3:
            return None, None, None
        ele = coords[i][2]
        delta = ele - prev_ele
        if delta > 0:
            gain += delta
        else:
            loss += -delta
        prev_ele = ele

    net = coords[end_idx][2] - coords[start_idx][2]
    grade = (net / distance_m) * 100.0 if distance_m > 0 else None
    return round(gain, 2), round(loss, 2), round(grade, 2) if grade is not None else None


def _parse_feature(
    feature: dict, priority: str, index: int
) -> Route:
    props = feature.get("properties") or {}
    summary = props.get("summary") or {}
    total_distance = float(summary.get("distance", 0))
    total_duration = int(summary.get("duration", 0))

    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if not coords:
        raise RoutingProviderUnavailable("ORS feature has empty geometry")

    # Polyline: convert [lng, lat(, ele)] -> (lat, lng). Drop elevation here;
    # elevation is preserved on segments via grade/gain/loss fields below.
    polyline: list[tuple[float, float]] = [(c[1], c[0]) for c in coords]

    segments: list[Segment] = []
    seq = 0
    for ors_segment in props.get("segments", []) or []:
        for step in ors_segment.get("steps", []) or []:
            wp = step.get("way_points") or []
            if len(wp) != 2:
                continue
            start_idx, end_idx = wp[0], wp[1]
            if start_idx >= len(coords) or end_idx >= len(coords) or start_idx == end_idx:
                continue
            from_lng, from_lat = coords[start_idx][0], coords[start_idx][1]
            to_lng, to_lat = coords[end_idx][0], coords[end_idx][1]

            step_distance = float(step.get("distance", 0))
            step_duration = int(step.get("duration", 0))

            gain_m, loss_m, grade_pct = _elevation_stats_for_range(
                coords, start_idx, end_idx, step_distance
            )

            segments.append(
                Segment(
                    seq=seq,
                    from_point=LatLng(lat=from_lat, lng=from_lng),
                    to_point=LatLng(lat=to_lat, lng=to_lng),
                    distance_m=step_distance,
                    duration_s=step_duration,
                    avg_speed_kmh=None,  # derived by model_validator
                    road_type=step.get("name"),
                    elevation_gain_m=gain_m,
                    elevation_loss_m=loss_m,
                    grade_pct=grade_pct,
                )
            )
            seq += 1

    objective = _OBJECTIVE_FROM_PRIORITY.get(priority, Objective.RECOMMEND)
    if index > 0:
        objective = Objective.ALTERNATIVE

    return Route(
        engine=EngineName.ORS,
        objective=objective,
        total_distance_m=total_distance,
        total_duration_s=total_duration,
        segments=segments,
        polyline=polyline,
        raw_response=feature,
    )


class ORSProvider(RoutingProvider):
    name = EngineName.ORS

    def __init__(
        self,
        api_key: str,
        *,
        profile: str = _DEFAULT_PROFILE,
        timeout: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RoutingProviderError("ORSProvider requires an API key")
        self._api_key = api_key
        self._profile = profile
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
    async def _call(self, body: dict) -> dict:
        url = f"https://api.openrouteservice.org/v2/directions/{self._profile}/geojson"
        client = await self._get_client()
        r = await client.post(
            url,
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
            },
            json=body,
        )
        if r.status_code == 403:
            raise RoutingProviderError("ORS auth failed (403). Check ORS_API_KEY.")
        if r.status_code == 429:
            raise RoutingProviderError("ORS rate limit (429). Slow down requests.")
        if r.status_code in (400, 404):
            # Most often: coordinates outside coverage area
            raise RoutingProviderUnavailable(
                f"ORS {r.status_code}: {r.text[:200]}"
            )
        r.raise_for_status()
        return r.json()

    def _build_body(self, request: RouteRequest, use_alternatives: bool) -> dict:
        coordinates: list[list[float]] = [
            [request.origin.lng, request.origin.lat],
        ]
        for w in request.waypoints:
            coordinates.append([w.lng, w.lat])
        coordinates.append([request.destination.lng, request.destination.lat])

        body: dict = {
            "coordinates": coordinates,
            "preference": _PREFERENCE_MAP[request.priority],
            "instructions": True,
            "elevation": True,
        }
        if use_alternatives and request.alternatives > 1 and not request.waypoints:
            # ORS only supports alternatives on simple OD pairs (no via-points)
            # AND when total distance is < ~100 km. We try-and-fallback below.
            body["alternative_routes"] = {
                "target_count": request.alternatives,
                "share_factor": 0.6,
                "weight_factor": 1.4,
            }

        avoid_features = [_AVOID_MAP[a] for a in request.avoid if a in _AVOID_MAP]
        if avoid_features:
            body["options"] = {"avoid_features": avoid_features}
        return body

    @staticmethod
    def _is_alternatives_too_long_error(err: Exception) -> bool:
        msg = str(err).lower()
        return "alternative" in msg and (
            "100000" in msg or "exceed" in msg or "configuration limits" in msg
        )

    async def get_routes(self, request: RouteRequest) -> list[Route]:
        want_alternatives = request.alternatives > 1 and not request.waypoints

        try:
            data = await self._call(self._build_body(request, use_alternatives=True))
        except RoutingProviderUnavailable as e:
            # Fall back without alternatives if ORS rejected the request because
            # the route is too long for alternative_routes (>100 km).
            if want_alternatives and self._is_alternatives_too_long_error(e):
                logger.warning(
                    "ors.fallback_no_alternatives",
                    extra={"reason": "distance > 100km, retrying without alternatives"},
                )
                data = await self._call(self._build_body(request, use_alternatives=False))
            else:
                raise

        features = data.get("features") or []
        if not features:
            raise RoutingProviderUnavailable("ORS returned no features")

        parsed: list[Route] = []
        for i, feature in enumerate(features[: request.alternatives]):
            try:
                parsed.append(_parse_feature(feature, request.priority, i))
            except RoutingProviderUnavailable as e:
                logger.warning("ors.skip_feature", extra={"index": i, "reason": str(e)})
        if not parsed:
            raise RoutingProviderUnavailable("ORS returned only unparseable features")
        return parsed

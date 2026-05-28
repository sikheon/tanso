"""Distance / duration / CO₂ matrix builder for VRP solver.

Uses ORS /v2/matrix/{profile} — one request returns full N×N distance +
duration matrices. CO₂ matrix is derived locally via EmissionCalculator's
speed-bin logic applied to each (i,j) arc.

The ORS Matrix free-tier limit is much lower than Directions (40/min,
500/day), but for VRP we issue exactly one Matrix call per request, so
this is plenty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.eco.factors import EcoFactorBook
from src.routing.base import RoutingProviderError, RoutingProviderUnavailable
from src.routing.schemas import LatLng
from src.vrp.schemas import VRPRequest

logger = logging.getLogger(__name__)

ORS_MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/{profile}"


@dataclass
class VRPMatrices:
    """Three NxN matrices aligned to a single location list.

    Index 0 is the depot; indices 1..N correspond to request.jobs in order.
    """

    locations: list[LatLng]
    distance_m: list[list[float]]
    duration_s: list[list[int]]
    co2_g: list[list[float]]

    @property
    def size(self) -> int:
        return len(self.locations)


def _avg_speed_kmh(dist_m: float, dur_s: int) -> float | None:
    if dur_s <= 0 or dist_m <= 0:
        return None
    return (dist_m / 1000.0) / (dur_s / 3600.0)


def _build_co2_matrix(
    distance_m: list[list[float]],
    duration_s: list[list[int]],
    book: EcoFactorBook,
    fuel_type: str,
    vehicle_class: str,
    *,
    engine_has_live_traffic: bool,
) -> list[list[float]]:
    ef = book.emission_factor(fuel_type, vehicle_class)
    n = len(distance_m)
    out: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d_m = distance_m[i][j]
            d_s = duration_s[i][j]
            speed = _avg_speed_kmh(d_m, d_s)
            mult = book.speed_multiplier(
                speed, engine_has_live_traffic=engine_has_live_traffic
            )
            out[i][j] = (d_m / 1000.0) * ef.g_per_km * mult
    return out


class ORSMatrixBuilder:
    """Builds VRPMatrices via a single ORS Matrix API call."""

    def __init__(
        self,
        api_key: str,
        book: EcoFactorBook,
        *,
        profile: str = "driving-car",
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise RoutingProviderError("ORSMatrixBuilder requires an API key")
        self._api_key = api_key
        self._book = book
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

    async def build(self, request: VRPRequest) -> VRPMatrices:
        # Index 0 = depot, indices 1..N = jobs in their original order
        locations: list[LatLng] = [request.depot] + [j.location for j in request.jobs]

        coords = [[ll.lng, ll.lat] for ll in locations]
        body = {
            "locations": coords,
            "metrics": ["distance", "duration"],
            "units": "m",
        }

        url = ORS_MATRIX_URL.format(profile=self._profile)
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
            raise RoutingProviderError("ORS Matrix auth failed (403). Check ORS_API_KEY.")
        if r.status_code == 429:
            raise RoutingProviderError("ORS Matrix rate limit (429).")
        if r.status_code in (400, 404):
            raise RoutingProviderUnavailable(
                f"ORS Matrix {r.status_code}: {r.text[:200]}"
            )
        r.raise_for_status()
        data = r.json()

        distances = data.get("distances")
        durations = data.get("durations")
        if not distances or not durations:
            raise RoutingProviderUnavailable("ORS Matrix returned empty matrices")

        # ORS may return None for unreachable cells; replace with a large
        # but finite value so OR-Tools doesn't choke (still strongly penalized).
        n = len(distances)
        dist_m: list[list[float]] = [[0.0] * n for _ in range(n)]
        dur_s: list[list[int]] = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                d = distances[i][j]
                t = durations[i][j]
                if d is None or t is None:
                    dist_m[i][j] = 1e9
                    dur_s[i][j] = 10**9
                else:
                    dist_m[i][j] = float(d)
                    dur_s[i][j] = int(t)

        co2_m = _build_co2_matrix(
            dist_m,
            dur_s,
            self._book,
            request.fuel_type,
            request.vehicle_class,
            engine_has_live_traffic=False,  # ORS = static data
        )

        return VRPMatrices(
            locations=locations,
            distance_m=dist_m,
            duration_s=dur_s,
            co2_g=co2_m,
        )

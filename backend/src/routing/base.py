"""Abstract base class for routing providers (Kakao, ORS, future engines)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.routing.schemas import EngineName, Route, RouteRequest


class RoutingProviderError(Exception):
    """Base exception for routing provider failures."""


class RoutingProviderUnavailable(RoutingProviderError):
    """Provider is reachable but returned no usable route (e.g., out-of-area)."""


class RoutingProvider(ABC):
    """Strategy interface implemented by KakaoProvider, ORSProvider, etc."""

    name: EngineName

    @abstractmethod
    async def get_routes(self, request: RouteRequest) -> list[Route]:
        """Return one or more candidate routes for the request.

        Raises:
            RoutingProviderError: on auth/network/parse failure
            RoutingProviderUnavailable: when the engine has no usable result
        """
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - default no-op
        """Release any pooled resources (httpx client, etc.)."""

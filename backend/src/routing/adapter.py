"""Multi-engine routing adapter.

Runs all registered providers in parallel for a single RouteRequest and
returns the combined route list. Failures in one provider don't break
the others — the failure is captured as a `ProviderResult.error` entry
so callers can show partial results + warnings.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from src.routing.base import RoutingProvider, RoutingProviderError
from src.routing.schemas import EngineName, Route, RouteRequest

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Per-engine outcome for a single multi-engine call."""

    engine: EngineName
    routes: list[Route]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class MultiEngineResult:
    routes: list[Route]
    per_engine: dict[EngineName, ProviderResult]

    @property
    def any_success(self) -> bool:
        return any(r.ok for r in self.per_engine.values())

    @property
    def warnings(self) -> list[str]:
        return [
            f"{name.value}: {pr.error}"
            for name, pr in self.per_engine.items()
            if pr.error
        ]


class RoutingAdapter:
    """Aggregates multiple RoutingProviders into one entry point."""

    def __init__(self, providers: list[RoutingProvider]) -> None:
        if not providers:
            raise ValueError("RoutingAdapter requires at least one provider")
        self._providers = providers

    @property
    def providers(self) -> list[RoutingProvider]:
        return list(self._providers)

    async def get_all_routes(self, request: RouteRequest) -> MultiEngineResult:
        results = await asyncio.gather(
            *(self._safe_call(p, request) for p in self._providers),
            return_exceptions=False,
        )
        per_engine: dict[EngineName, ProviderResult] = {pr.engine: pr for pr in results}
        flat: list[Route] = [r for pr in results for r in pr.routes]
        return MultiEngineResult(routes=flat, per_engine=per_engine)

    @staticmethod
    async def _safe_call(
        provider: RoutingProvider, request: RouteRequest
    ) -> ProviderResult:
        try:
            routes = await provider.get_routes(request)
            return ProviderResult(engine=provider.name, routes=routes)
        except RoutingProviderError as e:
            logger.warning(
                "routing.provider_failed",
                extra={"engine": provider.name.value, "reason": str(e)},
            )
            return ProviderResult(engine=provider.name, routes=[], error=str(e))
        except Exception as e:  # noqa: BLE001 — adapter must not crash on one engine
            logger.exception(
                "routing.provider_unexpected",
                extra={"engine": provider.name.value},
            )
            return ProviderResult(
                engine=provider.name,
                routes=[],
                error=f"{type(e).__name__}: {e}",
            )

    async def close(self) -> None:
        await asyncio.gather(
            *(p.close() for p in self._providers), return_exceptions=True
        )

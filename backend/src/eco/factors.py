"""DB-backed loaders for emission factors and speed-bin correction tables.

Loaders are async (SQLAlchemy AsyncSession) but the results are cached in
process memory — these tables are seeded once and effectively immutable.

Use `EcoFactorBook.load(session)` once at startup (or first request) to
populate the in-memory book, then call lookup methods synchronously.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import EmissionFactor, SpeedBinFactor


@dataclass(frozen=True)
class EmissionFactorView:
    fuel_type: str
    vehicle_class: str
    g_per_km: float
    source: str | None


@dataclass(frozen=True)
class SpeedBinView:
    speed_min_kmh: float
    speed_max_kmh: float
    multiplier: float
    applies_to: str  # all | static_only | dynamic_only

    def contains(self, speed_kmh: float) -> bool:
        return self.speed_min_kmh <= speed_kmh < self.speed_max_kmh


class EcoFactorBook:
    """In-memory snapshot of emission_factors + speed_bin_factors."""

    def __init__(
        self,
        emissions: list[EmissionFactorView],
        speed_bins: list[SpeedBinView],
    ) -> None:
        self._emissions: dict[tuple[str, str], EmissionFactorView] = {
            (e.fuel_type, e.vehicle_class): e for e in emissions
        }
        # Sort speed bins ascending by min for stable lookup
        self._speed_bins = sorted(speed_bins, key=lambda b: b.speed_min_kmh)

    @classmethod
    async def load(cls, session: AsyncSession) -> "EcoFactorBook":
        ef_rows = (await session.execute(select(EmissionFactor))).scalars().all()
        sb_rows = (await session.execute(select(SpeedBinFactor))).scalars().all()
        emissions = [
            EmissionFactorView(
                fuel_type=e.fuel_type,
                vehicle_class=e.vehicle_class,
                g_per_km=float(e.g_per_km),
                source=e.source,
            )
            for e in ef_rows
        ]
        speed_bins = [
            SpeedBinView(
                speed_min_kmh=float(b.speed_min_kmh),
                speed_max_kmh=float(b.speed_max_kmh),
                multiplier=float(b.multiplier),
                applies_to=b.applies_to or "all",
            )
            for b in sb_rows
        ]
        return cls(emissions=emissions, speed_bins=speed_bins)

    def emission_factor(self, fuel_type: str, vehicle_class: str) -> EmissionFactorView:
        key = (fuel_type, vehicle_class)
        if key not in self._emissions:
            raise KeyError(
                f"No emission_factor for {fuel_type}/{vehicle_class}. "
                f"Seed missing? Available keys: {sorted(self._emissions.keys())}"
            )
        return self._emissions[key]

    def speed_multiplier(
        self,
        speed_kmh: float | None,
        *,
        engine_has_live_traffic: bool,
    ) -> float:
        """Return the multiplier for a given average speed.

        `engine_has_live_traffic=True` for Kakao: bins marked 'static_only'
        are skipped (they would double-count congestion that's already
        baked into Kakao's ETA).
        """
        if speed_kmh is None or speed_kmh <= 0:
            return 1.0
        applies_filter = (
            ("all", "dynamic_only") if engine_has_live_traffic else ("all", "static_only")
        )
        for b in self._speed_bins:
            if b.applies_to not in applies_filter:
                continue
            if b.contains(speed_kmh):
                return b.multiplier
        return 1.0  # outside any bin — neutral

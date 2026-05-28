"""Emission factor reference data (g CO2/km by fuel/vehicle class)."""

from datetime import date

from sqlalchemy import Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EmissionFactor(Base):
    __tablename__ = "emission_factors"
    __table_args__ = (
        UniqueConstraint("fuel_type", "vehicle_class", "valid_from"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_class: Mapped[str] = mapped_column(String(30), nullable=False)
    g_per_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    source: Mapped[str | None] = mapped_column(String(200))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    def __repr__(self) -> str:
        return (
            f"EmissionFactor({self.fuel_type}/{self.vehicle_class}: "
            f"{self.g_per_km} g/km)"
        )

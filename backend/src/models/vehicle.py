"""Vehicle records with link to emission factor."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.emission_factor import EmissionFactor


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate: Mapped[str | None] = mapped_column(String(20), unique=True)
    model: Mapped[str | None] = mapped_column(String(100))
    fuel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_class: Mapped[str] = mapped_column(String(30), nullable=False)
    year_produced: Mapped[int | None] = mapped_column(Integer)
    emission_factor_id: Mapped[int | None] = mapped_column(
        ForeignKey("emission_factors.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    emission_factor: Mapped[EmissionFactor | None] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"Vehicle(id={self.id}, {self.fuel_type}/{self.vehicle_class})"

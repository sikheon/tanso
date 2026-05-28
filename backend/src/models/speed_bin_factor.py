"""Speed-bin emission multipliers (COPERT-style simplified correction)."""

from sqlalchemy import CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class SpeedBinFactor(Base):
    __tablename__ = "speed_bin_factors"
    __table_args__ = (
        CheckConstraint("speed_min_kmh < speed_max_kmh", name="ck_speed_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    speed_min_kmh: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    speed_max_kmh: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), default="all")

    def __repr__(self) -> str:
        return (
            f"SpeedBin({self.speed_min_kmh}-{self.speed_max_kmh} km/h: "
            f"x{self.multiplier})"
        )

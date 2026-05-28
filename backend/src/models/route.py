"""Route — one route candidate (engine × objective) and its segments."""

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    objective: Mapped[str] = mapped_column(String(20), nullable=False)
    visit_order: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    total_distance_m: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    total_co2_g: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    geometry: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326)
    )
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["Run"] = relationship(back_populates="routes")  # noqa: F821
    segments: Mapped[list["RouteSegment"]] = relationship(  # noqa: F821
        back_populates="route",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RouteSegment.seq",
    )

    def __repr__(self) -> str:
        return (
            f"Route(id={self.id}, {self.engine}/{self.objective}, "
            f"co2={self.total_co2_g}g)"
        )


class RouteSegment(Base):
    __tablename__ = "route_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    from_lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    from_lng: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    to_lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    to_lng: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    distance_m: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_speed_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2))
    speed_bin_mult: Mapped[float | None] = mapped_column(Numeric(4, 2))
    co2_g: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    road_type: Mapped[str | None] = mapped_column(String(30))
    elevation_gain_m: Mapped[float | None] = mapped_column(Numeric(8, 2))
    elevation_loss_m: Mapped[float | None] = mapped_column(Numeric(8, 2))
    grade_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    polyline: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="LINESTRING", srid=4326)
    )

    route: Mapped["Route"] = relationship(back_populates="segments")

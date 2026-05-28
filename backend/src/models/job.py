"""Job — a single delivery point (used in VRP mode)."""

from datetime import time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    lng: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    time_window_start: Mapped[time | None] = mapped_column(Time)
    time_window_end: Mapped[time | None] = mapped_column(Time)
    service_time_min: Mapped[int] = mapped_column(Integer, default=0)
    constraints_json: Mapped[list[Any] | None] = mapped_column(JSON)
    is_depot: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped["Run"] = relationship(back_populates="jobs")  # noqa: F821

    def __repr__(self) -> str:
        return f"Job(id={self.id}, seq={self.seq}, depot={self.is_depot})"

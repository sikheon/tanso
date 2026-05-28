"""Run — a single optimization request and its result envelope."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.vehicle import Vehicle


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_input_text: Mapped[str | None] = mapped_column(Text)
    parsed_request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    llm_weights: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    llm_constraints: Mapped[list[Any] | None] = mapped_column(JSON)
    llm_trace: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    # Snapshot of the vehicle at run creation — survives vehicle deletion
    vehicle_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    narrative_text: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vehicle: Mapped[Vehicle | None] = relationship(lazy="joined")
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    routes: Mapped[list["Route"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"Run(id={self.id}, mode={self.mode}, status={self.status})"

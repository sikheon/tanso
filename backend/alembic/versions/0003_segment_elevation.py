"""Add elevation_gain_m / elevation_loss_m / grade_pct to route_segments.

Revision ID: 0003_segment_elevation
Revises: 0002_run_meta_snapshot
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_segment_elevation"
down_revision: Union[str, None] = "0002_run_meta_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "route_segments",
        sa.Column("elevation_gain_m", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "route_segments",
        sa.Column("elevation_loss_m", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "route_segments",
        sa.Column("grade_pct", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("route_segments", "grade_pct")
    op.drop_column("route_segments", "elevation_loss_m")
    op.drop_column("route_segments", "elevation_gain_m")

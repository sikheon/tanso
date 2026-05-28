"""Add label/notes/vehicle_snapshot to runs; change vehicle_id FK to ON DELETE SET NULL.

Revision ID: 0002_run_meta_snapshot
Revises: 0001_initial
Create Date: 2026-05-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_run_meta_snapshot"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("label", sa.String(200)))
    op.add_column("runs", sa.Column("notes", sa.Text()))
    op.add_column("runs", sa.Column("vehicle_snapshot", sa.JSON()))

    # Re-create the FK with ON DELETE SET NULL so vehicle hard-delete
    # doesn't orphan or fail. Run keeps vehicle_snapshot for analytics.
    op.drop_constraint("runs_vehicle_id_fkey", "runs", type_="foreignkey")
    op.create_foreign_key(
        "runs_vehicle_id_fkey",
        source_table="runs",
        referent_table="vehicles",
        local_cols=["vehicle_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("runs_vehicle_id_fkey", "runs", type_="foreignkey")
    op.create_foreign_key(
        "runs_vehicle_id_fkey",
        source_table="runs",
        referent_table="vehicles",
        local_cols=["vehicle_id"],
        remote_cols=["id"],
    )
    op.drop_column("runs", "vehicle_snapshot")
    op.drop_column("runs", "notes")
    op.drop_column("runs", "label")

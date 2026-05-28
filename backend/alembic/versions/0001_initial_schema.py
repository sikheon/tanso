"""Initial schema — emission_factors, vehicles, speed_bin_factors, runs, jobs, routes, route_segments.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS extension required for geography columns
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "emission_factors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("vehicle_class", sa.String(30), nullable=False),
        sa.Column("g_per_km", sa.Numeric(8, 2), nullable=False),
        sa.Column("source", sa.String(200)),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.UniqueConstraint("fuel_type", "vehicle_class", "valid_from"),
    )

    op.create_table(
        "speed_bin_factors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("speed_min_kmh", sa.Numeric(5, 2), nullable=False),
        sa.Column("speed_max_kmh", sa.Numeric(5, 2), nullable=False),
        sa.Column("multiplier", sa.Numeric(4, 2), nullable=False),
        sa.Column("applies_to", sa.String(20), server_default="all"),
        sa.CheckConstraint("speed_min_kmh < speed_max_kmh", name="ck_speed_range"),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plate", sa.String(20), unique=True),
        sa.Column("model", sa.String(100)),
        sa.Column("fuel_type", sa.String(20), nullable=False),
        sa.Column("vehicle_class", sa.String(30), nullable=False),
        sa.Column("year_produced", sa.Integer()),
        sa.Column("emission_factor_id", sa.Integer(), sa.ForeignKey("emission_factors.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_input_text", sa.Text()),
        sa.Column("parsed_request", sa.JSON(), nullable=False),
        sa.Column("llm_weights", sa.JSON()),
        sa.Column("llm_constraints", sa.JSON()),
        sa.Column("llm_trace", sa.JSON()),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text()),
        sa.Column("narrative_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_runs_created", "runs", ["created_at"], postgresql_ops={"created_at": "DESC"})
    op.create_index("idx_runs_status", "runs", ["status"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(100)),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("time_window_start", sa.Time()),
        sa.Column("time_window_end", sa.Time()),
        sa.Column("service_time_min", sa.Integer(), server_default="0"),
        sa.Column("constraints_json", sa.JSON()),
        sa.Column("is_depot", sa.Boolean(), server_default=sa.false()),
    )

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine", sa.String(20), nullable=False),
        sa.Column("objective", sa.String(20), nullable=False),
        sa.Column("visit_order", sa.ARRAY(sa.Integer())),
        sa.Column("total_distance_m", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_duration_s", sa.Integer(), nullable=False),
        sa.Column("total_co2_g", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_recommended", sa.Boolean(), server_default=sa.false()),
        sa.Column("geometry", Geography(geometry_type="LINESTRING", srid=4326)),
        sa.Column("raw_response", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_routes_run", "routes", ["run_id"])

    op.create_table(
        "route_segments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("from_lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("from_lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("to_lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("to_lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("distance_m", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("avg_speed_kmh", sa.Numeric(6, 2)),
        sa.Column("speed_bin_mult", sa.Numeric(4, 2)),
        sa.Column("co2_g", sa.Numeric(10, 2), nullable=False),
        sa.Column("road_type", sa.String(30)),
        sa.Column("polyline", Geography(geometry_type="LINESTRING", srid=4326)),
    )
    op.create_index("idx_segments_route", "route_segments", ["route_id"])


def downgrade() -> None:
    op.drop_index("idx_segments_route", table_name="route_segments")
    op.drop_table("route_segments")
    op.drop_index("idx_routes_run", table_name="routes")
    op.drop_table("routes")
    op.drop_table("jobs")
    op.drop_index("idx_runs_status", table_name="runs")
    op.drop_index("idx_runs_created", table_name="runs")
    op.drop_table("runs")
    op.drop_table("vehicles")
    op.drop_table("speed_bin_factors")
    op.drop_table("emission_factors")
    # Note: we leave the postgis extension in place (may be used elsewhere)

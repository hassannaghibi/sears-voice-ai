"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-06-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    appliancetype = postgresql.ENUM(
        "washer", "dryer", "refrigerator", "dishwasher", "oven", "hvac", "other",
        name="appliancetype",
    )
    appliancetype.create(op.get_bind(), checkfirst=True)

    appointmentstatus = postgresql.ENUM(
        "pending", "confirmed", "cancelled",
        name="appointmentstatus",
    )
    appointmentstatus.create(op.get_bind(), checkfirst=True)

    callstate = postgresql.ENUM(
        "GREETING", "APPLIANCE_ID", "SYMPTOM_COLLECTION", "DIAGNOSIS",
        "RESOLUTION_CHECK", "SCHEDULING_OFFER", "TECHNICIAN_MATCH", "BOOKING",
        "CONFIRMATION", "CALLBACK_CAPTURE", "TIER3_EMAIL", "COMPLETED", "FAILED",
        name="callstate",
    )
    callstate.create(op.get_bind(), checkfirst=True)

    # technicians
    op.create_table(
        "technicians",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    # service_areas
    op.create_table(
        "service_areas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_areas_zip_code", "service_areas", ["zip_code"])

    # specialties
    op.create_table(
        "specialties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("appliance_type", sa.Enum(name="appliancetype"), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # availability_slots
    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_booked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # appointments
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_phone", sa.String(50), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.Column("appliance_type", sa.Enum(name="appliancetype"), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(name="appointmentstatus"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("call_sid", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["slot_id"], ["availability_slots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_call_sid", "appointments", ["call_sid"])

    # call_sessions
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_sid", sa.String(64), nullable=False),
        sa.Column("state", sa.Enum(name="callstate"), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_sid"),
    )
    op.create_index("ix_call_sessions_call_sid", "call_sessions", ["call_sid"])


def downgrade() -> None:
    op.drop_table("call_sessions")
    op.drop_table("appointments")
    op.drop_table("availability_slots")
    op.drop_table("specialties")
    op.drop_table("service_areas")
    op.drop_table("technicians")

    op.execute("DROP TYPE IF EXISTS callstate")
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS appliancetype")

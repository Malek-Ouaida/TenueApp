"""add wear detected item metadata fields

Revision ID: 0014_fix_wear_metadata
Revises: 0013_phase_08_wear_events
Create Date: 2026-04-11 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_fix_wear_metadata"
down_revision = "0013_wear_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wear_event_detected_items",
        sa.Column("predicted_material", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "wear_event_detected_items",
        sa.Column("predicted_pattern", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "wear_event_detected_items",
        sa.Column("predicted_fit_tags_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "wear_event_detected_items",
        sa.Column("predicted_silhouette", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "wear_event_detected_items",
        sa.Column("predicted_attributes_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wear_event_detected_items", "predicted_attributes_json")
    op.drop_column("wear_event_detected_items", "predicted_silhouette")
    op.drop_column("wear_event_detected_items", "predicted_fit_tags_json")
    op.drop_column("wear_event_detected_items", "predicted_pattern")
    op.drop_column("wear_event_detected_items", "predicted_material")
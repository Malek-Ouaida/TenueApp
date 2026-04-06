"""phase 06 wear logging foundation

Revision ID: 0009_phase_06_wear_logging_foundation
Revises: 0008_closet_similarity_duplicates
Create Date: 2026-04-06 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_phase_06_wear_logging_foundation"
down_revision: str | None = "0008_closet_similarity_duplicates"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "wear_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("wear_date", sa.Date(), nullable=False),
        sa.Column(
            "source",
            string_enum(
                "manual_items",
                "saved_outfit",
                "photo_detected",
                "mixed",
                name="wear_log_source",
            ),
            nullable=False,
        ),
        sa.Column(
            "context",
            string_enum(
                "casual",
                "work",
                "event",
                "travel",
                "gym",
                "lounge",
                name="wear_context",
            ),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "wear_date", name="uq_wear_logs_user_wear_date"),
    )
    op.create_index("ix_wear_logs_user_wear_date", "wear_logs", ["user_id", "wear_date"])

    op.create_table(
        "wear_log_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            string_enum(
                "manual",
                "from_outfit",
                "ai_matched",
                "manual_override",
                name="wear_item_source",
            ),
            nullable=False,
        ),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            string_enum(
                "top",
                "bottom",
                "dress",
                "outerwear",
                "shoes",
                "bag",
                "accessory",
                "other",
                name="wear_item_role",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wear_log_id", "closet_item_id", name="uq_wear_log_items_log_item"),
    )
    op.create_index(
        "ix_wear_log_items_log_sort",
        "wear_log_items",
        ["wear_log_id", "sort_index"],
        unique=False,
    )
    op.create_index(
        "ix_wear_log_items_closet_item",
        "wear_log_items",
        ["closet_item_id"],
        unique=False,
    )

    op.create_table(
        "wear_log_snapshots",
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("items_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("wear_log_id"),
    )


def downgrade() -> None:
    op.drop_table("wear_log_snapshots")
    op.drop_index("ix_wear_log_items_closet_item", table_name="wear_log_items")
    op.drop_index("ix_wear_log_items_log_sort", table_name="wear_log_items")
    op.drop_table("wear_log_items")
    op.drop_index("ix_wear_logs_user_wear_date", table_name="wear_logs")
    op.drop_table("wear_logs")

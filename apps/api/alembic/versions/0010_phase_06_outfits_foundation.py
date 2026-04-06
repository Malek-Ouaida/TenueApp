"""phase 06 outfits foundation

Revision ID: 0010_phase_06_outfits_foundation
Revises: 0009_phase_06_wear_logging_foundation
Create Date: 2026-04-06 18:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_phase_06_outfits_foundation"
down_revision: str | None = "0009_phase_06_wear_logging_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "outfits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "occasion",
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
        sa.Column(
            "season",
            string_enum("summer", "winter", name="outfit_season"),
            nullable=True,
        ),
        sa.Column(
            "source",
            string_enum(
                "manual",
                "derived_from_wear_log",
                "ai_suggested",
                name="outfit_source",
            ),
            nullable=False,
        ),
        sa.Column("is_favorite", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outfits_user_archived_updated",
        "outfits",
        ["user_id", "archived_at", "updated_at", "id"],
        unique=False,
    )

    op.create_table(
        "outfit_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outfit_id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
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
        sa.Column("layer_index", sa.Integer(), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outfit_id", "closet_item_id", name="uq_outfit_items_outfit_item"),
    )
    op.create_index(
        "ix_outfit_items_outfit_sort",
        "outfit_items",
        ["outfit_id", "sort_index"],
        unique=False,
    )

    op.add_column("wear_logs", sa.Column("outfit_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_wear_logs_outfit_id_outfits",
        "wear_logs",
        "outfits",
        ["outfit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_wear_logs_outfit_id", "wear_logs", ["outfit_id"], unique=False)

    op.add_column(
        "wear_log_snapshots",
        sa.Column("outfit_title_snapshot", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wear_log_snapshots", "outfit_title_snapshot")
    op.drop_index("ix_wear_logs_outfit_id", table_name="wear_logs")
    op.drop_constraint("fk_wear_logs_outfit_id_outfits", "wear_logs", type_="foreignkey")
    op.drop_column("wear_logs", "outfit_id")
    op.drop_index("ix_outfit_items_outfit_sort", table_name="outfit_items")
    op.drop_table("outfit_items")
    op.drop_index("ix_outfits_user_archived_updated", table_name="outfits")
    op.drop_table("outfits")

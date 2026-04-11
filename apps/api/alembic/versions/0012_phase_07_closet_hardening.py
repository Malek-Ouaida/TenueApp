"""phase 07 closet hardening

Revision ID: 0012_closet_hardening
Revises: 0011_lookbook_foundation
Create Date: 2026-04-10 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_closet_hardening"
down_revision: str | None = "0011_phase_06_lookbook_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "closet_items",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "closet_item_images",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "closet_item_images",
        sa.Column("archived_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "closet_item_images",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_closet_item_images_archived_by_user_id_users",
        "closet_item_images",
        "users",
        ["archived_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE closet_item_images SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("closet_item_images", "updated_at", nullable=False)

    op.add_column(
        "closet_item_metadata_projection",
        sa.Column("fit_tags", sa.JSON(), nullable=True),
    )
    op.add_column(
        "closet_item_metadata_projection",
        sa.Column("silhouette", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "closet_item_metadata_projection",
        sa.Column("attributes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("closet_item_metadata_projection", "attributes")
    op.drop_column("closet_item_metadata_projection", "silhouette")
    op.drop_column("closet_item_metadata_projection", "fit_tags")

    op.drop_constraint(
        "fk_closet_item_images_archived_by_user_id_users",
        "closet_item_images",
        type_="foreignkey",
    )
    op.drop_column("closet_item_images", "updated_at")
    op.drop_column("closet_item_images", "archived_by_user_id")
    op.drop_column("closet_item_images", "archived_at")
    op.drop_column("closet_items", "archived_at")

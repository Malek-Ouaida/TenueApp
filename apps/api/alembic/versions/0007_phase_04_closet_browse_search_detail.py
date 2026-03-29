"""phase 04 closet browse search detail

Revision ID: 0007_closet_browse_search_detail
Revises: 0006_closet_metadata_extraction
Create Date: 2026-03-29 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_closet_browse_search_detail"
down_revision: str | None = "0006_closet_metadata_extraction"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_closet_items_user_lifecycle_confirmed",
        "closet_items",
        ["user_id", "lifecycle_status", "confirmed_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_closet_items_user_lifecycle_confirmed", table_name="closet_items")

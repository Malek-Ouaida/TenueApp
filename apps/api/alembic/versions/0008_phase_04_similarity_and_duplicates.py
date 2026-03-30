"""phase 04 similarity and duplicates

Revision ID: 0008_closet_similarity_duplicates
Revises: 0007_closet_browse_search_detail
Create Date: 2026-03-30 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_closet_similarity_duplicates"
down_revision: str | None = "0007_closet_browse_search_detail"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_closet_similarity_edges_item_a_decision_type_updated",
        "closet_item_similarity_edges",
        ["item_a_id", "decision_status", "similarity_type", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_closet_similarity_edges_item_b_decision_type_updated",
        "closet_item_similarity_edges",
        ["item_b_id", "decision_status", "similarity_type", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_closet_similarity_edges_item_b_decision_type_updated",
        table_name="closet_item_similarity_edges",
    )
    op.drop_index(
        "ix_closet_similarity_edges_item_a_decision_type_updated",
        table_name="closet_item_similarity_edges",
    )

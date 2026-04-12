from __future__ import annotations

"""lookbook hardening constraints

Revision ID: 0018_lookbook_hardening_constraints
Revises: 0017_full_taxonomy_wear_matching
Create Date: 2026-04-11 17:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_lookbook_hardening_constraints"
down_revision: str | None = "0017_full_taxonomy_wear_matching"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked_defaults AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_num
            FROM lookbooks
            WHERE is_default IS TRUE
        )
        UPDATE lookbooks
        SET is_default = FALSE
        WHERE id IN (
            SELECT id
            FROM ranked_defaults
            WHERE row_num > 1
        )
        """
    )

    op.execute(
        """
        WITH ranked_entries AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY source_wear_log_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_num
            FROM lookbook_entries
            WHERE source_wear_log_id IS NOT NULL
              AND archived_at IS NULL
        )
        UPDATE lookbook_entries
        SET archived_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE id IN (
            SELECT id
            FROM ranked_entries
            WHERE row_num > 1
        )
        """
    )

    op.create_index(
        "uq_lookbooks_user_single_default",
        "lookbooks",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default = 1"),
    )
    op.create_index(
        "uq_lookbook_entries_active_source_wear_log",
        "lookbook_entries",
        ["source_wear_log_id"],
        unique=True,
        postgresql_where=sa.text("source_wear_log_id IS NOT NULL AND archived_at IS NULL"),
        sqlite_where=sa.text("source_wear_log_id IS NOT NULL AND archived_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_lookbook_entries_active_source_wear_log",
        table_name="lookbook_entries",
    )
    op.drop_index(
        "uq_lookbooks_user_single_default",
        table_name="lookbooks",
    )

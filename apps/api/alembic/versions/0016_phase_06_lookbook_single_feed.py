"""phase 06 lookbook single feed

Revision ID: 0016_phase_06_lookbook_single_feed
Revises: ba43d78d42fb
Create Date: 2026-04-11 11:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_phase_06_lookbook_single_feed"
down_revision: str | None = "ba43d78d42fb"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    with op.batch_alter_table("lookbooks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_index(
        "ix_lookbooks_user_default",
        "lookbooks",
        ["user_id", "is_default", "updated_at", "id"],
        unique=False,
    )

    with op.batch_alter_table("lookbook_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_kind",
                string_enum(
                    "gallery_photo",
                    "wear_log",
                    name="lookbook_entry_source_kind",
                ),
                nullable=False,
                server_default="gallery_photo",
            )
        )
        batch_op.add_column(
            sa.Column(
                "intent",
                string_enum(
                    "inspiration",
                    "recreate",
                    "logged",
                    name="lookbook_entry_intent",
                ),
                nullable=False,
                server_default="inspiration",
            )
        )
        batch_op.add_column(
            sa.Column(
                "status",
                string_enum(
                    "draft",
                    "published",
                    name="lookbook_entry_status",
                ),
                nullable=False,
                server_default="published",
            )
        )
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("occasion_tag", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("season_tag", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("style_tag", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_wear_log_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("owned_outfit_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("source_snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_lookbook_entries_source_wear_log",
            "wear_logs",
            ["source_wear_log_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_lookbook_entries_owned_outfit",
            "outfits",
            ["owned_outfit_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        UPDATE lookbook_entries
        SET
            source_kind = 'gallery_photo',
            intent = CASE
                WHEN entry_type = 'outfit' THEN 'recreate'
                ELSE 'inspiration'
            END,
            status = 'published',
            notes = CASE
                WHEN entry_type = 'note' THEN note_text
                ELSE NULL
            END,
            owned_outfit_id = outfit_id,
            published_at = created_at
        """
    )

    op.create_index(
        "ix_lookbook_entries_feed_updated",
        "lookbook_entries",
        ["lookbook_id", "archived_at", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_lookbook_entries_status_updated",
        "lookbook_entries",
        ["lookbook_id", "status", "updated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_lookbook_entries_source_wear_log",
        "lookbook_entries",
        ["source_wear_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_lookbook_entries_owned_outfit",
        "lookbook_entries",
        ["owned_outfit_id"],
        unique=False,
    )

    with op.batch_alter_table("lookbooks") as batch_op:
        batch_op.alter_column("is_default", server_default=None)

    with op.batch_alter_table("lookbook_entries") as batch_op:
        batch_op.alter_column("source_kind", server_default=None)
        batch_op.alter_column("intent", server_default=None)
        batch_op.alter_column("status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_lookbook_entries_owned_outfit", table_name="lookbook_entries")
    op.drop_index("ix_lookbook_entries_source_wear_log", table_name="lookbook_entries")
    op.drop_index("ix_lookbook_entries_status_updated", table_name="lookbook_entries")
    op.drop_index("ix_lookbook_entries_feed_updated", table_name="lookbook_entries")

    with op.batch_alter_table("lookbook_entries") as batch_op:
        batch_op.drop_constraint("fk_lookbook_entries_owned_outfit", type_="foreignkey")
        batch_op.drop_constraint("fk_lookbook_entries_source_wear_log", type_="foreignkey")
        batch_op.drop_column("archived_at")
        batch_op.drop_column("published_at")
        batch_op.drop_column("source_snapshot_json")
        batch_op.drop_column("owned_outfit_id")
        batch_op.drop_column("source_wear_log_id")
        batch_op.drop_column("style_tag")
        batch_op.drop_column("season_tag")
        batch_op.drop_column("occasion_tag")
        batch_op.drop_column("notes")
        batch_op.drop_column("title")
        batch_op.drop_column("status")
        batch_op.drop_column("intent")
        batch_op.drop_column("source_kind")

    op.drop_index("ix_lookbooks_user_default", table_name="lookbooks")
    with op.batch_alter_table("lookbooks") as batch_op:
        batch_op.drop_column("is_default")

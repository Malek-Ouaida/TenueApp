"""phase 06 lookbook foundation

Revision ID: 0011_phase_06_lookbook_foundation
Revises: 0010_phase_06_outfits_foundation
Create Date: 2026-04-06 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_phase_06_lookbook_foundation"
down_revision: str | None = "0010_phase_06_outfits_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "lookbooks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lookbooks_user_updated_id",
        "lookbooks",
        ["user_id", "updated_at", "id"],
        unique=False,
    )

    op.create_table(
        "lookbook_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lookbook_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entry_type",
            string_enum("outfit", "image", "note", name="lookbook_entry_type"),
            nullable=False,
        ),
        sa.Column("outfit_id", sa.Uuid(), nullable=True),
        sa.Column("image_asset_id", sa.Uuid(), nullable=True),
        sa.Column("caption", sa.String(length=280), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "("
            "entry_type = 'outfit' AND outfit_id IS NOT NULL AND image_asset_id IS NULL "
            "AND note_text IS NULL"
            ") OR ("
            "entry_type = 'image' AND outfit_id IS NULL AND image_asset_id IS NOT NULL "
            "AND note_text IS NULL"
            ") OR ("
            "entry_type = 'note' AND outfit_id IS NULL AND image_asset_id IS NULL "
            "AND note_text IS NOT NULL AND caption IS NULL"
            ")",
            name="ck_lookbook_entries_entry_payload",
        ),
        sa.ForeignKeyConstraint(["image_asset_id"], ["media_assets.id"]),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outfit_id"], ["outfits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lookbook_entries_lookbook_sort",
        "lookbook_entries",
        ["lookbook_id", "sort_index"],
        unique=False,
    )

    op.create_table(
        "lookbook_upload_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lookbook_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("staging_bucket", sa.String(length=128), nullable=False),
        sa.Column("staging_key", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            string_enum(
                "pending", "finalized", "expired", "failed", name="lookbook_upload_intent_status"
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lookbook_upload_intents_user_status_created",
        "lookbook_upload_intents",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_lookbook_upload_intents_lookbook_status_expires",
        "lookbook_upload_intents",
        ["lookbook_id", "status", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lookbook_upload_intents_lookbook_status_expires",
        table_name="lookbook_upload_intents",
    )
    op.drop_index(
        "ix_lookbook_upload_intents_user_status_created",
        table_name="lookbook_upload_intents",
    )
    op.drop_table("lookbook_upload_intents")
    op.drop_index("ix_lookbook_entries_lookbook_sort", table_name="lookbook_entries")
    op.drop_table("lookbook_entries")
    op.drop_index("ix_lookbooks_user_updated_id", table_name="lookbooks")
    op.drop_table("lookbooks")

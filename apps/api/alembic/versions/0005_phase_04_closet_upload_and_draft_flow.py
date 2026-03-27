"""phase 04 closet upload and draft flow

Revision ID: 0005_closet_upload_draft
Revises: 0004_closet_schema_lifecycle
Create Date: 2026-03-27 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_closet_upload_draft"
down_revision: str | None = "0004_closet_schema_lifecycle"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "closet_upload_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("staging_bucket", sa.String(length=128), nullable=False),
        sa.Column("staging_key", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            string_enum("pending", "finalized", "expired", "failed", name="upload_intent_status"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_closet_upload_intents_user_status_created",
        "closet_upload_intents",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_closet_upload_intents_item_status_expires",
        "closet_upload_intents",
        ["closet_item_id", "status", "expires_at"],
        unique=False,
    )

    op.create_table(
        "closet_idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("response_status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_closet_idempotency_keys_user_operation_key",
        "closet_idempotency_keys",
        ["user_id", "operation", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_closet_idempotency_keys_user_operation_key",
        table_name="closet_idempotency_keys",
    )
    op.drop_table("closet_idempotency_keys")

    op.drop_index(
        "ix_closet_upload_intents_item_status_expires",
        table_name="closet_upload_intents",
    )
    op.drop_index(
        "ix_closet_upload_intents_user_status_created",
        table_name="closet_upload_intents",
    )
    op.drop_table("closet_upload_intents")

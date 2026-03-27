"""phase 04 closet schema and lifecycle

Revision ID: 0004_closet_schema_lifecycle
Revises: 0003_user_profile_foundation
Create Date: 2026-03-27 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_closet_schema_lifecycle"
down_revision: str | None = "0003_user_profile_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "closet_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "lifecycle_status",
            string_enum(
                "draft",
                "processing",
                "review",
                "confirmed",
                "archived",
                name="lifecycle_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            string_enum(
                "pending",
                "running",
                "completed",
                "completed_with_issues",
                "failed",
                name="processing_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            string_enum("needs_review", "ready_to_confirm", "confirmed", name="review_status"),
            nullable=False,
        ),
        sa.Column("primary_image_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_closet_items_user_lifecycle_review",
        "closet_items",
        ["user_id", "lifecycle_status", "review_status"],
        unique=False,
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "source_kind",
            string_enum(
                "upload",
                "processed",
                "derived",
                "reference",
                name="media_asset_source_kind",
            ),
            nullable=False,
        ),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_checksum", "media_assets", ["checksum"], unique=False)

    op.create_table(
        "closet_item_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            string_enum(
                "original",
                "processed",
                "thumbnail",
                "mask",
                "reference",
                name="closet_item_image_role",
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_closet_item_images_item_role",
        "closet_item_images",
        ["closet_item_id", "role"],
        unique=False,
    )

    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "run_type",
            string_enum(
                "upload_validation",
                "asset_promotion",
                "image_processing",
                "metadata_extraction",
                "normalization_projection",
                "similarity_recompute",
                name="processing_run_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            string_enum(
                "pending",
                "running",
                "completed",
                "completed_with_issues",
                "failed",
                name="processing_run_status",
            ),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "provider_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=True),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=True),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            string_enum("succeeded", "partial", "failed", name="provider_result_status"),
            nullable=False,
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["processing_run_id"], ["processing_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "closet_item_field_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.JSON(), nullable=True),
        sa.Column("normalized_candidate", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("provider_result_id", sa.Uuid(), nullable=True),
        sa.Column(
            "applicability_state",
            string_enum(
                "value",
                "unknown",
                "not_applicable",
                name="applicability_state",
            ),
            nullable=False,
        ),
        sa.Column("conflict_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provider_result_id"], ["provider_results.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "closet_item_field_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("canonical_value", sa.JSON(), nullable=True),
        sa.Column(
            "source",
            string_enum("provider", "user", "system", name="field_source"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "review_state",
            string_enum(
                "pending_user",
                "user_confirmed",
                "user_edited",
                "system_unset",
                name="field_review_state",
            ),
            nullable=False,
        ),
        sa.Column(
            "applicability_state",
            string_enum(
                "value", "unknown", "not_applicable", name="field_state_applicability_state"
            ),
            nullable=False,
        ),
        sa.Column("taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_closet_item_field_states_item_field",
        "closet_item_field_states",
        ["closet_item_id", "field_name"],
        unique=True,
    )

    op.create_table(
        "closet_item_metadata_projection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("subcategory", sa.String(length=64), nullable=True),
        sa.Column("primary_color", sa.String(length=64), nullable=True),
        sa.Column("secondary_colors", sa.JSON(), nullable=True),
        sa.Column("material", sa.String(length=64), nullable=True),
        sa.Column("pattern", sa.String(length=64), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column("occasion_tags", sa.JSON(), nullable=True),
        sa.Column("season_tags", sa.JSON(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_closet_item_metadata_projection_item",
        "closet_item_metadata_projection",
        ["closet_item_id"],
        unique=True,
    )
    op.create_index(
        "ix_closet_meta_proj_user_cat_subcat_color",
        "closet_item_metadata_projection",
        ["user_id", "category", "subcategory", "primary_color"],
        unique=False,
    )

    op.create_table(
        "closet_item_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "actor_type",
            string_enum("user", "system", "worker", name="audit_actor_type"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "closet_item_similarity_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_a_id", sa.Uuid(), nullable=False),
        sa.Column("item_b_id", sa.Uuid(), nullable=False),
        sa.Column(
            "similarity_type",
            string_enum(
                "similar",
                "duplicate_candidate",
                "duplicate",
                name="similarity_type",
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=True),
        sa.Column(
            "decision_status",
            string_enum(
                "pending",
                "dismissed",
                "marked_duplicate",
                name="similarity_decision_status",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("item_a_id <> item_b_id", name="ck_similarity_edge_distinct_items"),
        sa.ForeignKeyConstraint(["item_a_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_b_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_closet_item_similarity_edges_canonical_pair",
        "closet_item_similarity_edges",
        ["item_a_id", "item_b_id", "similarity_type"],
        unique=True,
    )

    op.create_table(
        "closet_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_kind",
            string_enum(
                "upload_validation",
                "asset_promotion",
                "image_processing",
                "metadata_extraction",
                "normalization_projection",
                "similarity_recompute",
                name="closet_job_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            string_enum("pending", "running", "completed", "failed", name="closet_job_status"),
            nullable=False,
        ),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_closet_jobs_status_available_at",
        "closet_jobs",
        ["status", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_closet_jobs_status_available_at", table_name="closet_jobs")
    op.drop_table("closet_jobs")

    op.drop_index(
        "ux_closet_item_similarity_edges_canonical_pair",
        table_name="closet_item_similarity_edges",
    )
    op.drop_table("closet_item_similarity_edges")

    op.drop_table("closet_item_audit_events")

    op.drop_index(
        "ix_closet_meta_proj_user_cat_subcat_color",
        table_name="closet_item_metadata_projection",
    )
    op.drop_index(
        "ux_closet_item_metadata_projection_item",
        table_name="closet_item_metadata_projection",
    )
    op.drop_table("closet_item_metadata_projection")

    op.drop_index(
        "ux_closet_item_field_states_item_field",
        table_name="closet_item_field_states",
    )
    op.drop_table("closet_item_field_states")

    op.drop_table("closet_item_field_candidates")
    op.drop_table("provider_results")
    op.drop_table("processing_runs")

    op.drop_index("ix_closet_item_images_item_role", table_name="closet_item_images")
    op.drop_table("closet_item_images")

    op.drop_index("ix_media_assets_checksum", table_name="media_assets")
    op.drop_table("media_assets")

    op.drop_index("ix_closet_items_user_lifecycle_review", table_name="closet_items")
    op.drop_table("closet_items")

"""phase 08 wear events

Revision ID: 0013_wear_events
Revises: 0012_closet_hardening
Create Date: 2026-04-10 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_wear_events"
down_revision: str | None = "0012_closet_hardening"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def string_enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.add_column("wear_logs", sa.Column("worn_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "wear_logs",
        sa.Column(
            "worn_time_precision",
            string_enum("date_only", "approximate", "exact", name="wear_time_precision"),
            nullable=True,
        ),
    )
    op.add_column("wear_logs", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("wear_logs", sa.Column("timezone_name", sa.String(length=128), nullable=True))
    op.add_column(
        "wear_logs",
        sa.Column(
            "status",
            string_enum("draft", "processing", "needs_review", "confirmed", "failed", name="wear_log_status"),
            nullable=True,
        ),
    )
    op.add_column("wear_logs", sa.Column("vibe", sa.String(length=255), nullable=True))
    op.add_column("wear_logs", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("wear_logs", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("wear_logs", sa.Column("primary_photo_id", sa.Uuid(), nullable=True))
    op.add_column("wear_logs", sa.Column("confirmed_item_count", sa.Integer(), nullable=True))
    op.add_column("wear_logs", sa.Column("combination_fingerprint", sa.String(length=255), nullable=True))
    op.add_column("wear_logs", sa.Column("failure_code", sa.String(length=64), nullable=True))
    op.add_column("wear_logs", sa.Column("failure_summary", sa.Text(), nullable=True))

    op.execute(
        "UPDATE wear_logs "
        "SET worn_at = ((wear_date::timestamp AT TIME ZONE 'UTC') + interval '12 hours') "
        "WHERE worn_at IS NULL"
    )
    op.execute("UPDATE wear_logs SET worn_time_precision = 'date_only' WHERE worn_time_precision IS NULL")
    op.execute(
        "UPDATE wear_logs "
        "SET status = CASE WHEN is_confirmed THEN 'confirmed' ELSE 'draft' END "
        "WHERE status IS NULL"
    )
    op.execute(
        "UPDATE wear_logs SET confirmed_at = created_at "
        "WHERE is_confirmed IS TRUE AND confirmed_at IS NULL"
    )
    op.execute(
        "UPDATE wear_logs SET confirmed_item_count = item_counts.count "
        "FROM ("
        "  SELECT wear_log_id, COUNT(*) AS count "
        "  FROM wear_log_items "
        "  GROUP BY wear_log_id"
        ") AS item_counts "
        "WHERE wear_logs.id = item_counts.wear_log_id"
    )
    op.execute("UPDATE wear_logs SET confirmed_item_count = 0 WHERE confirmed_item_count IS NULL")

    op.alter_column("wear_logs", "worn_at", nullable=False)
    op.alter_column("wear_logs", "worn_time_precision", nullable=False)
    op.alter_column("wear_logs", "status", nullable=False)
    op.alter_column("wear_logs", "confirmed_item_count", nullable=False)

    op.drop_constraint("uq_wear_logs_user_wear_date", "wear_logs", type_="unique")
    op.drop_index("ix_wear_logs_user_wear_date", table_name="wear_logs")
    op.create_index(
        "ix_wear_logs_user_calendar",
        "wear_logs",
        ["user_id", "wear_date", "worn_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_wear_logs_user_status_worn_at",
        "wear_logs",
        ["user_id", "status", "archived_at", "worn_at"],
        unique=False,
    )

    op.add_column("wear_log_items", sa.Column("detected_item_id", sa.Uuid(), nullable=True))
    op.add_column("wear_log_snapshots", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE wear_log_snapshots SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("wear_log_snapshots", "updated_at", nullable=False)

    op.create_table(
        "wear_event_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("thumbnail_asset_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thumbnail_asset_id"], ["media_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_photos_log_position",
        "wear_event_photos",
        ["wear_log_id", "position"],
        unique=False,
    )

    op.create_table(
        "wear_event_upload_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("staging_bucket", sa.String(length=128), nullable=False),
        sa.Column("staging_key", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            string_enum("pending", "finalized", "expired", "failed", name="wear_upload_intent_status"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_upload_intents_user_status_created",
        "wear_event_upload_intents",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_wear_event_upload_intents_log_status_expires",
        "wear_event_upload_intents",
        ["wear_log_id", "status", "expires_at"],
        unique=False,
    )

    op.create_table(
        "wear_event_processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column(
            "run_type",
            string_enum("photo_analysis", name="wear_processing_run_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            string_enum("pending", "running", "completed", "failed", name="wear_processing_status"),
            nullable=False,
        ),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_processing_runs_log_run_type_created",
        "wear_event_processing_runs",
        ["wear_log_id", "run_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "wear_event_provider_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=True),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_model", sa.String(length=128), nullable=True),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            string_enum("succeeded", "partial", "failed", name="wear_provider_result_status"),
            nullable=False,
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["processing_run_id"], ["wear_event_processing_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_provider_results_run_created",
        "wear_event_provider_results",
        ["processing_run_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_wear_event_provider_results_log_task_created",
        "wear_event_provider_results",
        ["wear_log_id", "task_type", "created_at"],
        unique=False,
    )

    op.create_table(
        "wear_event_detected_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False),
        sa.Column(
            "predicted_role",
            string_enum(
                "top",
                "bottom",
                "dress",
                "outerwear",
                "shoes",
                "bag",
                "accessory",
                "other",
                name="wear_detected_item_role",
            ),
            nullable=True,
        ),
        sa.Column("predicted_category", sa.String(length=64), nullable=True),
        sa.Column("predicted_subcategory", sa.String(length=64), nullable=True),
        sa.Column("predicted_colors_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("bbox_json", sa.JSON(), nullable=True),
        sa.Column("crop_asset_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            string_enum("detected", "excluded", "confirmed", name="wear_detected_item_status"),
            nullable=False,
        ),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crop_asset_id"], ["media_assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["processing_run_id"], ["wear_event_processing_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_detected_items_log_sort",
        "wear_event_detected_items",
        ["wear_log_id", "sort_index"],
        unique=False,
    )
    op.create_index(
        "ix_wear_event_detected_items_run_created",
        "wear_event_detected_items",
        ["processing_run_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "wear_event_match_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("detected_item_id", sa.Uuid(), nullable=False),
        sa.Column("closet_item_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["closet_item_id"], ["closet_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["detected_item_id"], ["wear_event_detected_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_match_candidates_detected_rank",
        "wear_event_match_candidates",
        ["detected_item_id", "rank"],
        unique=False,
    )

    op.create_table(
        "wear_event_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wear_log_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_kind",
            string_enum("photo_analysis", name="wear_job_kind"),
            nullable=False,
        ),
        sa.Column(
            "status",
            string_enum("pending", "running", "completed", "failed", name="wear_job_status"),
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
        sa.ForeignKeyConstraint(["wear_log_id"], ["wear_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wear_event_jobs_status_available_at",
        "wear_event_jobs",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_wear_event_jobs_log_kind_status",
        "wear_event_jobs",
        ["wear_log_id", "job_kind", "status"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_wear_log_items_detected_item_id",
        "wear_log_items",
        "wear_event_detected_items",
        ["detected_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_wear_log_items_detected_item_id", "wear_log_items", type_="foreignkey")
    op.drop_table("wear_event_jobs")
    op.drop_table("wear_event_match_candidates")
    op.drop_table("wear_event_detected_items")
    op.drop_index("ix_wear_event_provider_results_log_task_created", table_name="wear_event_provider_results")
    op.drop_index("ix_wear_event_provider_results_run_created", table_name="wear_event_provider_results")
    op.drop_table("wear_event_provider_results")
    op.drop_index("ix_wear_event_processing_runs_log_run_type_created", table_name="wear_event_processing_runs")
    op.drop_table("wear_event_processing_runs")
    op.drop_index("ix_wear_event_upload_intents_log_status_expires", table_name="wear_event_upload_intents")
    op.drop_index("ix_wear_event_upload_intents_user_status_created", table_name="wear_event_upload_intents")
    op.drop_table("wear_event_upload_intents")
    op.drop_index("ix_wear_event_photos_log_position", table_name="wear_event_photos")
    op.drop_table("wear_event_photos")

    op.drop_column("wear_log_snapshots", "updated_at")
    op.drop_column("wear_log_items", "detected_item_id")

    op.drop_index("ix_wear_logs_user_status_worn_at", table_name="wear_logs")
    op.drop_index("ix_wear_logs_user_calendar", table_name="wear_logs")
    op.create_index("ix_wear_logs_user_wear_date", "wear_logs", ["user_id", "wear_date"], unique=False)
    op.create_unique_constraint("uq_wear_logs_user_wear_date", "wear_logs", ["user_id", "wear_date"])

    op.drop_column("wear_logs", "failure_summary")
    op.drop_column("wear_logs", "failure_code")
    op.drop_column("wear_logs", "combination_fingerprint")
    op.drop_column("wear_logs", "confirmed_item_count")
    op.drop_column("wear_logs", "primary_photo_id")
    op.drop_column("wear_logs", "archived_at")
    op.drop_column("wear_logs", "confirmed_at")
    op.drop_column("wear_logs", "vibe")
    op.drop_column("wear_logs", "status")
    op.drop_column("wear_logs", "timezone_name")
    op.drop_column("wear_logs", "captured_at")
    op.drop_column("wear_logs", "worn_time_precision")
    op.drop_column("wear_logs", "worn_at")

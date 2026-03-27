"""phase 04 metadata extraction

Revision ID: 0006_closet_metadata_extraction
Revises: 0005_closet_upload_draft
Create Date: 2026-03-27 18:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_closet_metadata_extraction"
down_revision: str | None = "0005_closet_upload_draft"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_processing_runs_item_run_type_created",
        "processing_runs",
        ["closet_item_id", "run_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_results_run_created",
        "provider_results",
        ["processing_run_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_results_item_task_created",
        "provider_results",
        ["closet_item_id", "task_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_field_candidates_provider_result_created",
        "closet_item_field_candidates",
        ["provider_result_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_closet_jobs_item_kind_status",
        "closet_jobs",
        ["closet_item_id", "job_kind", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_closet_jobs_item_kind_status", table_name="closet_jobs")
    op.drop_index(
        "ix_field_candidates_provider_result_created",
        table_name="closet_item_field_candidates",
    )
    op.drop_index("ix_provider_results_item_task_created", table_name="provider_results")
    op.drop_index("ix_provider_results_run_created", table_name="provider_results")
    op.drop_index("ix_processing_runs_item_run_type_created", table_name="processing_runs")

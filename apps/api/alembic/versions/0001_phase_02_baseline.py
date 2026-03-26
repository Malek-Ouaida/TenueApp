"""Phase 02 baseline migration.

This anchors the Postgres/Alembic workflow before any product-domain schema exists.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_phase_02_baseline"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

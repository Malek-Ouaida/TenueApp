"""phase 05 user profile foundation

Revision ID: 0003_user_profile_foundation
Revises: 0002_phase_03_auth_foundation
Create Date: 2026-03-26 16:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_user_profile_foundation"
down_revision: str | None = "0002_phase_03_auth_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=280), nullable=True))
    op.add_column("users", sa.Column("avatar_path", sa.String(length=512), nullable=True))
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "avatar_path")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
    op.drop_column("users", "username")

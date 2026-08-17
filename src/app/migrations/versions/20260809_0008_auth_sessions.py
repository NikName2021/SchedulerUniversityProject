"""Add local user accounts and server-side sessions.

Revision ID: 20260809_0008
Revises: 20260809_0007
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0008"
down_revision: str | None = "20260809_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'operator')",
            name="ck_user_account_role",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_account_username",
        "user_account",
        ["username"],
        unique=True,
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_session_expires_at",
        "user_session",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_session_token_hash",
        "user_session",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_user_session_user_id",
        "user_session",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_index("ix_user_session_token_hash", table_name="user_session")
    op.drop_index("ix_user_session_expires_at", table_name="user_session")
    op.drop_table("user_session")
    op.drop_index("ix_user_account_username", table_name="user_account")
    op.drop_table("user_account")

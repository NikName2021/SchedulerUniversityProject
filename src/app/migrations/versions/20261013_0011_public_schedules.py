"""Add the authenticated employee catalog of published schedule snapshots.

Revision ID: 20261013_0011
Revises: 20261013_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0011"
down_revision: str | None = "20261013_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_schedule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_task_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("owner_display_name", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("starts_on", sa.DateTime(), nullable=True),
        sa.Column("ends_on", sa.DateTime(), nullable=True),
        sa.Column("groups_json", sa.Text(), nullable=False),
        sa.Column("entries_json", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("edit_revision", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user_account.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_task_id"], ["generation_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_task_id"),
    )
    op.create_index("ix_public_schedule_owner_id", "public_schedule", ["owner_id"])
    op.create_index(
        "ix_public_schedule_published_at", "public_schedule", ["published_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_public_schedule_published_at", table_name="public_schedule")
    op.drop_index("ix_public_schedule_owner_id", table_name="public_schedule")
    op.drop_table("public_schedule")

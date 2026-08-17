"""Add portable offline calculation packages.

Revision ID: 20260809_0007
Revises: 20260720_0006
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0007"
down_revision: str | None = "20260720_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offline_calculation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("job_uuid", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("input_payload_json", sa.Text(), nullable=False),
        sa.Column("result_payload_json", sa.Text(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_uuid"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        "ix_offline_calculation_job_uuid",
        "offline_calculation",
        ["job_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_offline_calculation_job_uuid", table_name="offline_calculation")
    op.drop_table("offline_calculation")

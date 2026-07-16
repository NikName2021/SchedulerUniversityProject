"""Add generation component progress and metrics.

Revision ID: 20260716_0003
Revises: 20260716_0002
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0003"
down_revision: str | None = "20260716_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.add_column(
            sa.Column(
                "total_components", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(
            sa.Column(
                "completed_components", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(
            sa.Column(
                "progress_percent", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(sa.Column("metrics_json", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("celery_workflow_id", sa.String(), nullable=True))

    op.create_table(
        "generation_component",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("component_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("variable_count", sa.Integer(), nullable=False),
        sa.Column("constraint_count", sa.Integer(), nullable=False),
        sa.Column("solve_seconds", sa.Float(), nullable=True),
        sa.Column("objective", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "component_key"),
    )
    op.create_index(
        "ix_generation_component_task_status",
        "generation_component",
        ["task_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_component_task_status", table_name="generation_component"
    )
    op.drop_table("generation_component")
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.drop_column("celery_workflow_id")
        batch_op.drop_column("metrics_json")
        batch_op.drop_column("progress_percent")
        batch_op.drop_column("completed_components")
        batch_op.drop_column("total_components")

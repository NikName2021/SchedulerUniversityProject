"""Add schedule lifecycle, generation locks and diagnostics.

Revision ID: 20260716_0005
Revises: 20260716_0004
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.add_column(sa.Column("parent_task_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "version_number", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch_op.add_column(
            sa.Column(
                "publication_status",
                sa.String(),
                nullable=False,
                server_default="draft",
            )
        )
        batch_op.add_column(sa.Column("published_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("canceled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("edit_revision", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("celery_root_task_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("celery_component_ids_json", sa.String(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_generation_task_parent",
            "generation_task",
            ["parent_task_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        sa.text("UPDATE generation_task SET version_number = id WHERE id IS NOT NULL")
    )

    op.create_table(
        "generation_lock",
        sa.Column("scope_key", sa.String(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("scope_key"),
    )
    op.create_table(
        "generation_issue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=True),
        sa.Column("group_name", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("lesson_number", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_task.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generation_issue_task_kind",
        "generation_issue",
        ["task_id", "kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_issue_task_kind", table_name="generation_issue")
    op.drop_table("generation_issue")
    op.drop_table("generation_lock")
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.drop_constraint("fk_generation_task_parent", type_="foreignkey")
        batch_op.drop_column("celery_component_ids_json")
        batch_op.drop_column("celery_root_task_id")
        batch_op.drop_column("edit_revision")
        batch_op.drop_column("canceled_at")
        batch_op.drop_column("published_at")
        batch_op.drop_column("publication_status")
        batch_op.drop_column("version_number")
        batch_op.drop_column("parent_task_id")

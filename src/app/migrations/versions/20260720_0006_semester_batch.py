"""Group weekly generation tasks into semester runs.

Revision ID: 20260720_0006
Revises: 20260716_0005
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0006"
down_revision: str | None = "20260716_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.add_column(sa.Column("semester_batch_id", sa.String(), nullable=True))
    op.create_index(
        "ix_generation_task_semester_batch_id",
        "generation_task",
        ["semester_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generation_task_semester_batch_id", table_name="generation_task")
    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.drop_column("semester_batch_id")

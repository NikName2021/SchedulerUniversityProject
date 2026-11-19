"""Persist the shared solver context for an active generation task."""

import sqlalchemy as sa
from alembic import op

revision = "20261119_0013"
down_revision = "20261118_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_task", sa.Column("solver_context_json", sa.Text()))


def downgrade() -> None:
    op.drop_column("generation_task", "solver_context_json")

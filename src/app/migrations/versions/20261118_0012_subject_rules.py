"""Add personal, dated subject scheduling rules."""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0012"
down_revision = "20261013_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_schedule_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("week_ids_json", sa.Text(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "owner_id",
            "group_name",
            "subject",
            "scope_key",
            name="uq_subject_rule_scope",
        ),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_subject_rule_dates"),
    )
    op.create_index(
        "ix_subject_schedule_rule_owner_id", "subject_schedule_rule", ["owner_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subject_schedule_rule_owner_id", table_name="subject_schedule_rule"
    )
    op.drop_table("subject_schedule_rule")

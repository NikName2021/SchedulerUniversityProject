"""Add explicit academic weeks and weekly lesson demand.

Revision ID: 20260716_0002
Revises: 20260716_0001
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academic_period",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("period_type", sa.String(), nullable=False),
        sa.Column("education_level", sa.String(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_academic_period_dates"),
    )
    op.create_table(
        "student_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("specialty", sa.String(), nullable=True),
        sa.Column("course", sa.Integer(), nullable=True),
        sa.Column("education_form", sa.String(), nullable=True),
        sa.Column("student_count", sa.Integer(), nullable=False),
        sa.Column("min_weekly_lessons", sa.Integer(), nullable=True),
        sa.Column("max_weekly_lessons", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("student_count >= 0", name="ck_student_group_size"),
    )
    op.create_table(
        "planning_week",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["period_id"], ["academic_period.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_id", "sequence_number"),
        sa.UniqueConstraint("period_id", "starts_on"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_planning_week_dates"),
    )
    op.create_table(
        "weekly_lesson_demand",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("week_id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("lessons_count", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["week_id"], ["planning_week.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("week_id", "stream_id"),
        sa.CheckConstraint("lessons_count >= 0", name="ck_weekly_lesson_demand_count"),
        sa.CheckConstraint(
            "priority >= 1 AND priority <= 10",
            name="ck_weekly_lesson_demand_priority",
        ),
    )

    with op.batch_alter_table("stream_group") as batch_op:
        batch_op.add_column(sa.Column("student_group_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_stream_group_student_group",
            "student_group",
            ["student_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_stream_group_group_name", ["group_name"])

    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.add_column(sa.Column("planning_week_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_generation_task_planning_week",
            "planning_week",
            ["planning_week_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_generation_task_planning_week_id", ["planning_week_id"]
        )

    with op.batch_alter_table("schedule_entry") as batch_op:
        batch_op.add_column(sa.Column("planning_week_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_stream_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_locked", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.create_foreign_key(
            "fk_schedule_entry_planning_week",
            "planning_week",
            ["planning_week_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_schedule_entry_source_stream",
            "stream",
            ["source_stream_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_schedule_entry_teacher_slot",
            ["teacher_id", "date", "lesson_number"],
        )
        batch_op.create_index(
            "ix_schedule_entry_room_slot", ["room_id", "date", "lesson_number"]
        )
        batch_op.create_index(
            "ix_schedule_entry_group_slot", ["group_name", "date", "lesson_number"]
        )

    op.execute(
        sa.text(
            """
            INSERT INTO student_group (name, student_count)
            SELECT group_name, MAX(group_size)
            FROM stream_group
            GROUP BY group_name
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE stream_group
            SET student_group_id = (
                SELECT student_group.id
                FROM student_group
                WHERE student_group.name = stream_group.group_name
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("schedule_entry") as batch_op:
        batch_op.drop_index("ix_schedule_entry_group_slot")
        batch_op.drop_index("ix_schedule_entry_room_slot")
        batch_op.drop_index("ix_schedule_entry_teacher_slot")
        batch_op.drop_constraint("fk_schedule_entry_source_stream", type_="foreignkey")
        batch_op.drop_constraint("fk_schedule_entry_planning_week", type_="foreignkey")
        batch_op.drop_column("is_locked")
        batch_op.drop_column("source_stream_id")
        batch_op.drop_column("planning_week_id")

    with op.batch_alter_table("generation_task") as batch_op:
        batch_op.drop_index("ix_generation_task_planning_week_id")
        batch_op.drop_constraint("fk_generation_task_planning_week", type_="foreignkey")
        batch_op.drop_column("planning_week_id")

    with op.batch_alter_table("stream_group") as batch_op:
        batch_op.drop_index("ix_stream_group_group_name")
        batch_op.drop_constraint("fk_stream_group_student_group", type_="foreignkey")
        batch_op.drop_column("student_group_id")

    op.drop_table("weekly_lesson_demand")
    op.drop_table("planning_week")
    op.drop_table("student_group")
    op.drop_table("academic_period")

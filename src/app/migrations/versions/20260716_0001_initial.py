"""Initial scheduler schema.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    file_type = postgresql.ENUM(
        "STREAMS",
        "TEACHERS_LOAD",
        "ROOMS",
        name="filetype",
        create_type=False,
    )
    if op.get_bind().dialect.name == "postgresql":
        file_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "import_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("file_type", file_type, nullable=False),
        sa.Column("created_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "teacher",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("restrictions_json", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "generation_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("groups_json", sa.String(), nullable=True),
        sa.Column("holidays_json", sa.String(), nullable=True),
        sa.Column("settings_json", sa.String(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generation_task_id"), "generation_task", ["id"], unique=False
    )
    op.create_table(
        "stream",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_batch_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("stream_type", sa.String(), nullable=True),
        sa.Column("lessons_count", sa.Integer(), nullable=True),
        sa.Column("is_ignored", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["import_batch_id"], ["import_batch.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schedule_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("group_name", sa.String(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("stream_type", sa.String(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("room_id", sa.String(), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("lesson_number", sa.Integer(), nullable=True),
        sa.Column("warning", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["generation_task.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_entry_id"), "schedule_entry", ["id"], unique=False
    )
    op.create_table(
        "stream_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(), nullable=False),
        sa.Column("group_size", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("stream_group")
    op.drop_index(op.f("ix_schedule_entry_id"), table_name="schedule_entry")
    op.drop_table("schedule_entry")
    op.drop_table("stream")
    op.drop_index(op.f("ix_generation_task_id"), table_name="generation_task")
    op.drop_table("generation_task")
    op.drop_table("teacher")
    op.drop_table("import_batch")
    if op.get_bind().dialect.name == "postgresql":
        postgresql.ENUM(name="filetype").drop(op.get_bind(), checkfirst=True)

"""Add normalized reference data, availability and rule profiles.

Revision ID: 20260716_0004
Revises: 20260716_0003
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "department",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "activity_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("room_type", sa.String(), nullable=True),
        sa.Column("is_shared_for_groups", sa.Boolean(), nullable=False),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "discipline",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_table(
        "building",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "room_feature",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "rule_profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("education_level", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "room",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=True),
        sa.Column("owner_department_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("room_type", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="ck_room_capacity"),
        sa.ForeignKeyConstraint(["building_id"], ["building.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["owner_department_id"], ["department.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("building_id", "code"),
    )
    op.create_table(
        "rule_setting",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.CheckConstraint("weight >= 1 AND weight <= 10", name="ck_rule_weight"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["rule_profile.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "rule_code"),
    )
    op.create_table(
        "room_feature_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feature_id"], ["room_feature.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "feature_id"),
    )

    with op.batch_alter_table("teacher") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("position", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_teacher_department",
            "department",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("stream") as batch_op:
        batch_op.add_column(sa.Column("discipline_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("activity_type_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("required_room_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("starts_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("ends_on", sa.Date(), nullable=True))
        batch_op.create_foreign_key(
            "fk_stream_discipline",
            "discipline",
            ["discipline_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_stream_activity_type",
            "activity_type",
            ["activity_type_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_stream_required_room",
            "room",
            ["required_room_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("schedule_entry") as batch_op:
        batch_op.add_column(sa.Column("room_ref_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_schedule_entry_room",
            "room",
            ["room_ref_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "stream_feature_requirement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("feature_id", sa.Integer(), nullable=False),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feature_id"], ["room_feature.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_id", "feature_id"),
    )
    op.create_table(
        "availability_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("student_group_id", sa.Integer(), nullable=True),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("rule_kind", sa.String(), nullable=False),
        sa.Column("recurrence", sa.String(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("specific_date", sa.Date(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("lesson_start", sa.Integer(), nullable=False),
        sa.Column("lesson_end", sa.Integer(), nullable=False),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.CheckConstraint(
            "teacher_id IS NOT NULL OR student_group_id IS NOT NULL OR room_id IS NOT NULL OR is_global = true",
            name="ck_availability_has_scope",
        ),
        sa.CheckConstraint(
            "lesson_start >= 1 AND lesson_end >= lesson_start",
            name="ck_availability_lesson_range",
        ),
        sa.CheckConstraint(
            "weight >= 1 AND weight <= 10", name="ck_availability_weight"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["student_group_id"], ["student_group.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_availability_teacher", "availability_rule", ["teacher_id"])
    op.create_index("ix_availability_group", "availability_rule", ["student_group_id"])
    op.create_index("ix_availability_room", "availability_rule", ["room_id"])

    _seed_reference_data()


def _seed_reference_data() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO activity_type
                (code, name, room_type, is_shared_for_groups, color, is_active)
            VALUES
                ('lec', 'Лекция', 'lec', true, '#e6fffa', true),
                ('sem', 'Семинар', 'sem', false, '#e0f2fe', true),
                ('practice', 'Практика', 'sem', false, '#e0f2fe', true),
                ('lab', 'Лабораторная', 'lab', false, '#f3e8ff', true),
                ('exam', 'Зачет', 'sem', false, '#fef3c7', true),
                ('extracurricular', 'Внеучебное мероприятие', 'mixed', true, '#f3f4f6', true)
            """
        )
    )
    op.execute(
        sa.text("INSERT INTO building (code, name) VALUES ('MAIN', 'Основной корпус')")
    )
    op.execute(
        sa.text(
            """
            INSERT INTO room (building_id, code, capacity, room_type, is_active)
            VALUES
                ((SELECT id FROM building WHERE code='MAIN'), '101', 30, 'sem', true),
                ((SELECT id FROM building WHERE code='MAIN'), '102', 20, 'sem', true),
                ((SELECT id FROM building WHERE code='MAIN'), '103', 80, 'lec', true),
                ((SELECT id FROM building WHERE code='MAIN'), '104', 60, 'lec', true),
                ((SELECT id FROM building WHERE code='MAIN'), '105', 15, 'lab', true),
                ((SELECT id FROM building WHERE code='MAIN'), '106', 30, 'sem', true),
                ((SELECT id FROM building WHERE code='MAIN'), '201', 100, 'lec', true),
                ((SELECT id FROM building WHERE code='MAIN'), '202', 40, 'sem', true)
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO discipline (full_name)
            SELECT DISTINCT event_name FROM stream WHERE event_name IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE stream SET discipline_id = (
                SELECT discipline.id FROM discipline
                WHERE discipline.full_name = stream.event_name
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE stream SET activity_type_id = (
                SELECT activity_type.id FROM activity_type
                WHERE activity_type.name = stream.stream_type
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE schedule_entry SET room_ref_id = (
                SELECT room.id FROM room WHERE room.code = schedule_entry.room_id
            )
            WHERE room_id IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO rule_profile
                (name, description, is_default, is_active)
            VALUES
                ('Стандартный', 'Базовый профиль правил университета', true, true)
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO rule_setting
                (profile_id, rule_code, enabled, is_hard, weight)
            VALUES
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'double_booking', true, true, 10),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'unavailable_time', true, true, 10),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'locked_events', true, true, 10),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'room_capacity', true, false, 5),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'room_type', true, false, 5),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'room_features', true, false, 7),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'minimize_windows', true, false, 7),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'lunch_break', true, true, 8),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'lecture_before_practice', true, false, 6),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'late_lessons', true, false, 3),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'teacher_preferences', true, false, 6),
                ((SELECT id FROM rule_profile WHERE name='Стандартный'), 'load_balance', true, false, 5)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_availability_room", table_name="availability_rule")
    op.drop_index("ix_availability_group", table_name="availability_rule")
    op.drop_index("ix_availability_teacher", table_name="availability_rule")
    op.drop_table("availability_rule")
    op.drop_table("stream_feature_requirement")
    with op.batch_alter_table("schedule_entry") as batch_op:
        batch_op.drop_constraint("fk_schedule_entry_room", type_="foreignkey")
        batch_op.drop_column("room_ref_id")
    with op.batch_alter_table("stream") as batch_op:
        batch_op.drop_constraint("fk_stream_required_room", type_="foreignkey")
        batch_op.drop_constraint("fk_stream_activity_type", type_="foreignkey")
        batch_op.drop_constraint("fk_stream_discipline", type_="foreignkey")
        batch_op.drop_column("ends_on")
        batch_op.drop_column("starts_on")
        batch_op.drop_column("required_room_id")
        batch_op.drop_column("activity_type_id")
        batch_op.drop_column("discipline_id")
    with op.batch_alter_table("teacher") as batch_op:
        batch_op.drop_constraint("fk_teacher_department", type_="foreignkey")
        batch_op.drop_column("position")
        batch_op.drop_column("department_id")
    op.drop_table("room_feature_link")
    op.drop_table("rule_setting")
    op.drop_table("room")
    op.drop_table("rule_profile")
    op.drop_table("room_feature")
    op.drop_table("building")
    op.drop_table("discipline")
    op.drop_table("activity_type")
    op.drop_table("department")

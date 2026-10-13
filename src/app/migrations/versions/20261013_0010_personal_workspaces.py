"""Start clean personal workspaces, preserving accounts and login sessions.

The user explicitly requested deleting the old shared working data. Stop the
API and workers before applying this destructive migration. It cannot restore
old data on downgrade. PostgreSQL sequences are preserved; SQLite task IDs are
also kept above the old high-water mark so delayed jobs cannot target new tasks.

Revision ID: 20261013_0010
Revises: 20260817_0009
"""

import sqlalchemy as sa
from alembic import op

revision = "20261013_0010"
down_revision = "20260817_0009"
branch_labels = None
depends_on = None

# Children first, including tables containing references to multiple parents.
TABLES = (
    "schedule_entry",
    "generation_lock",
    "generation_issue",
    "generation_component",
    "generation_task",
    "weekly_lesson_demand",
    "planning_week",
    "academic_period",
    "stream_feature_requirement",
    "stream_group",
    "stream",
    "import_batch",
    "availability_rule",
    "rule_setting",
    "room_feature_link",
    "room",
    "teacher",
    "student_group",
    "discipline",
    "activity_type",
    "rule_profile",
    "room_feature",
    "building",
    "department",
)
PERSONAL_UNIQUES = {
    "department": [("code",), ("name",)],
    "activity_type": [("code",), ("name",)],
    "discipline": [("full_name",), ("external_id",)],
    "building": [("code",), ("name",)],
    "room_feature": [("code",), ("name",)],
    "rule_profile": [("name",)],
    "teacher": [("name",)],
    "student_group": [("name",)],
    "room": [("building_id", "code")],
}
NAMING = {"uq": "uq_%(table_name)s_%(column_0_N_name)s"}


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    max_task_id = connection.scalar(sa.text("SELECT MAX(id) FROM generation_task")) or 0
    op.execute(sa.text("UPDATE generation_task SET parent_task_id = NULL"))
    for name in TABLES:
        op.execute(sa.table(name).delete())

    # No new owner is guessed for formerly shared data. Every new row must have
    # an owner, and identical reference names/codes can exist in different spaces.
    for name in TABLES:
        existing = {
            tuple(item["column_names"]): item["name"]
            for item in inspector.get_unique_constraints(name)
        }
        kwargs = {"sqlite_autoincrement": True} if name == "generation_task" else {}
        with op.batch_alter_table(
            name, naming_convention=NAMING, table_kwargs=kwargs
        ) as batch:
            batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=False))
            batch.create_foreign_key(
                f"fk_{name}_owner",
                "user_account",
                ["owner_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch.create_index(f"ix_{name}_owner_id", ["owner_id"])
            for columns in PERSONAL_UNIQUES.get(name, []):
                old_name = existing[columns] or f"uq_{name}_{'_'.join(columns)}"
                batch.drop_constraint(old_name, type_="unique")
                suffix = "building_code" if name == "room" else columns[0]
                batch.create_unique_constraint(
                    f"uq_{name}_owner_{suffix}", ["owner_id", *columns]
                )

    if connection.dialect.name == "sqlite":
        op.execute(
            sa.text("DELETE FROM sqlite_sequence WHERE name = 'generation_task'")
        )
        connection.execute(
            sa.text(
                "INSERT INTO sqlite_sequence (name, seq) VALUES ('generation_task', :seq)"
            ),
            {"seq": max_task_id},
        )


def downgrade() -> None:
    # Merging private spaces would expose data and may violate old global unique
    # constraints. Restore a pre-migration backup instead of silently merging.
    raise RuntimeError(
        "Personal workspaces cannot be merged; restore a backup to downgrade"
    )

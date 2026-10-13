"""Verify the destructive transition on a disposable database, never app data."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_migration_clears_shared_data_preserves_accounts_and_task_sequence(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source_root = root.parent
    path = tmp_path / "legacy.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{path}",
        "PYTHONPATH": str(root / "app"),
    }

    def migrate(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(root / "alembic.ini"), *args],
            cwd=source_root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    migrate("upgrade", "20260817_0009")
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO user_account (id, username, display_name, password_hash, role, is_active, failed_login_count, password_changed_at, created_at) VALUES (1, 'keeper', 'Keeper', 'hash', 'admin', 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO user_session (user_id, token_hash, csrf_token, created_at, last_seen_at, expires_at) VALUES (1, 'token', 'csrf', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '2027-01-01')"
        )
        db.execute(
            "INSERT INTO generation_task (id, status, version_number, publication_status, edit_revision, total_components, completed_components, progress_percent) VALUES (42, 'running', 1, 'draft', 0, 0, 0, 0)"
        )
        db.execute(
            "INSERT INTO generation_lock (scope_key, task_id, created_at) VALUES ('old', 42, CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO import_batch (filename, file_type) VALUES ('old.csv', 'STREAMS')"
        )
    migrate("upgrade", "head")
    migrate("check")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT username FROM user_account").fetchall() == [
            ("keeper",)
        ]
        assert db.execute("SELECT token_hash FROM user_session").fetchall() == [
            ("token",)
        ]
        tables = [
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in tables:
            if table not in {
                "user_account",
                "user_session",
                "alembic_version",
                "sqlite_sequence",
            }:
                assert db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
                columns = {
                    row[1]: row for row in db.execute(f'PRAGMA table_info("{table}")')
                }
                assert columns["owner_id"][3] == 1
        db.execute(
            "INSERT INTO generation_task (owner_id, status, version_number, publication_status, edit_revision, total_components, completed_components, progress_percent) VALUES (1, 'queued', 1, 'draft', 0, 0, 0, 0)"
        )
        assert db.execute("SELECT id FROM generation_task").fetchone()[0] > 42
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []

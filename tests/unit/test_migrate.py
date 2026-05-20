"""Tests para migrate.py."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.db.migrate import get_existing_columns, migrate_table


class TestMigration:
    """Tests para la migración de schema."""

    def test_get_existing_columns(self):
        """get_existing_columns devuelve las columnas de la tabla."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value REAL)"
            )
            conn.commit()
            conn.close()

            conn = sqlite3.connect(str(db_path))
            cols = get_existing_columns(conn, "test_table")
            conn.close()

            assert "id" in cols
            assert "name" in cols
            assert "value" in cols

    def test_migration_adds_missing_column(self):
        """migrate_table añade columna que no existe."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            conn.commit()

            cols_before = get_existing_columns(conn, "test_table")
            assert "employer_id" not in cols_before

            added = migrate_table(conn, "test_table", [("employer_id", "TEXT")])
            conn.commit()

            assert "employer_id" in added

            cols_after = get_existing_columns(conn, "test_table")
            assert "employer_id" in cols_after

            conn.close()

    def test_migration_idempotent(self):
        """Ejecutar migrate dos veces sobre misma tabla no duplica."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            conn.commit()

            added1 = migrate_table(conn, "test_table", [("col1", "TEXT")])
            conn.commit()

            added2 = migrate_table(conn, "test_table", [("col1", "TEXT")])
            conn.commit()

            assert len(added1) == 1
            assert len(added2) == 0

            conn.close()
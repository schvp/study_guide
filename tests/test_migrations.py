import sqlite3
import unittest
from unittest.mock import patch

import migrations


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")

    def tearDown(self):
        self.database.close()

    def test_fresh_database_applies_ordered_migrations_and_is_idempotent(self):
        migrations.migrate_database(self.database)

        applied = self.database.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(
            applied,
            [
                (1, "create_user_tables"),
                (2, "add_username"),
                (3, "create_course_tables"),
            ],
        )
        user_columns = {
            row[1] for row in self.database.execute("PRAGMA table_info(users)")
        }
        self.assertIn("username", user_columns)
        self.assertTrue(
            self.database.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'chapters'
                """
            ).fetchone()
        )

        migrations.migrate_database(self.database)

        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM schema_migrations"
            ).fetchone()[0],
            3,
        )

    def test_failed_migration_rolls_back_schema_and_version_record(self):
        migrations.migrate_database(self.database)

        def fail_after_ddl(database):
            database.execute("CREATE TABLE should_be_rolled_back (id INTEGER)")
            raise RuntimeError("migration failed")

        with patch.object(
            migrations,
            "MIGRATIONS",
            migrations.MIGRATIONS + ((4, "failing_migration", fail_after_ddl),),
        ):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                migrations.migrate_database(self.database)

        table = self.database.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'should_be_rolled_back'
            """
        ).fetchone()
        self.assertIsNone(table)
        self.assertIsNone(
            self.database.execute(
                "SELECT 1 FROM schema_migrations WHERE version = 4"
            ).fetchone()
        )

    def test_database_newer_than_application_is_rejected(self):
        self.database.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.database.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (99, 'future')"
        )

        with self.assertRaisesRegex(RuntimeError, "newer than this application"):
            migrations.migrate_database(self.database)


if __name__ == "__main__":
    unittest.main()

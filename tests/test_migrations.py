import json
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
                (4, "link_progress_to_chapters"),
                (5, "create_chapter_completion_history"),
                (6, "create_library_materials"),
                (7, "add_user_roles"),
                (8, "add_content_publication_status"),
                (9, "create_assessment_tables"),
                (10, "snapshot_assessment_attempt_questions"),
                (11, "make_assessment_attempts_immutable"),
                (12, "track_assessment_bank_seeding"),
                (13, "add_assessment_difficulty_and_settings"),
                (14, "version_assessment_question_bank"),
                (15, "add_assessment_time_and_attempt_limits"),
                (16, "create_laboratory_attempts"),
                (17, "add_laboratory_attempt_results"),
            ],
        )
        user_columns = {
            row[1] for row in self.database.execute("PRAGMA table_info(users)")
        }
        self.assertIn("username", user_columns)
        for table in ("courses", "chapters"):
            columns = {
                row[1]
                for row in self.database.execute(f"PRAGMA table_info({table})")
            }
            self.assertIn("status", columns)
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
            17,
        )

    def test_assessment_tables_store_questions_and_per_user_attempt_answers(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database)
        self.database.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (1, 'student@example.com', 'hash')"
        )
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        self.database.execute(
            """
            INSERT INTO assessment_questions (
                id, course_id, chapter_id, question_type, prompt, correct_answer, position
            ) VALUES (1, 1, 1, 'single_choice', 'Question?', '"a"', 1)
            """
        )
        self.database.execute(
            """
            INSERT INTO assessment_attempts (id, user_id, course_id, chapter_id, question_count)
            VALUES (1, 1, 1, 1, 1)
            """
        )
        self.database.execute(
            """
            INSERT INTO assessment_attempt_questions (
                attempt_id, question_id, position, question_snapshot
            )
            VALUES (1, 1, 1, '{"question_type":"single_choice","prompt":"Question?","options":[],"correct_answer":"a","tolerance":0,"explanation":""}')
            """
        )
        self.database.execute(
            """
            INSERT INTO assessment_attempt_answers (attempt_id, question_id, answer, is_correct)
            VALUES (1, 1, '"a"', 1)
            """
        )
        self.database.commit()

        self.database.execute("DELETE FROM users WHERE id = 1")
        self.database.commit()
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM assessment_attempts"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM assessment_attempt_answers"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM assessment_attempt_questions"
            ).fetchone()[0],
            0,
        )

    def test_assessment_difficulty_and_chapter_question_count_constraints(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database, through_version=12)
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        migrations.migrate_database(self.database)
        self.assertEqual(
            self.database.execute(
                """
                SELECT questions_per_attempt FROM assessment_chapter_settings
                WHERE chapter_id = 1
                """
            ).fetchone()[0],
            2,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """
                INSERT INTO assessment_questions (
                    course_id, chapter_id, question_type, prompt,
                    correct_answer, position, difficulty
                ) VALUES (1, 1, 'numeric', 'Question?', '1', 1, 'expert')
                """
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """
                UPDATE assessment_chapter_settings
                SET questions_per_attempt = 21 WHERE chapter_id = 1
                """
            )

    def test_assessment_time_and_attempt_limit_constraints(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database, through_version=12)
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        migrations.migrate_database(self.database)

        self.database.execute(
            """
            UPDATE assessment_chapter_settings
            SET time_limit_seconds = 60, max_attempts = 1
            WHERE chapter_id = 1
            """
        )
        for invalid_time in (59, 86401):
            with self.assertRaises(sqlite3.IntegrityError):
                self.database.execute(
                    """
                    UPDATE assessment_chapter_settings
                    SET time_limit_seconds = ? WHERE chapter_id = 1
                    """,
                    (invalid_time,),
                )
        for invalid_attempts in (0, 101):
            with self.assertRaises(sqlite3.IntegrityError):
                self.database.execute(
                    """
                    UPDATE assessment_chapter_settings
                    SET max_attempts = ? WHERE chapter_id = 1
                    """,
                    (invalid_attempts,),
                )

    def test_laboratory_attempts_validate_status_and_cascade(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database)
        self.database.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (1, 'student@example.com', 'hash')"
        )
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        self.database.execute(
            """
            INSERT INTO laboratory_attempts (
                user_id, chapter_id, laboratory_slug
            ) VALUES (1, 1, 'byte-assembly')
            """
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """
                INSERT INTO laboratory_attempts (
                    user_id, chapter_id, laboratory_slug, status
                ) VALUES (1, 1, 'byte-assembly', 'completed')
                """
            )

        self.database.execute(
            """
            UPDATE laboratory_attempts
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )
        self.assertEqual(
            self.database.execute(
                "SELECT status FROM laboratory_attempts WHERE id = 1"
            ).fetchone()[0],
            "completed",
        )

        self.database.execute("DELETE FROM users WHERE id = 1")
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM laboratory_attempts"
            ).fetchone()[0],
            0,
        )
    def test_migration_snapshots_existing_attempts_and_preserves_answers_after_question_deletion(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database, through_version=10)
        self.database.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (1, 'student@example.com', 'hash')"
        )
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        self.database.execute(
            """
            INSERT INTO assessment_questions (
                id, course_id, chapter_id, question_type, prompt,
                correct_answer, position
            ) VALUES (1, 1, 1, 'single_choice', 'Original question?', '"a"', 1)
            """
        )
        self.database.execute(
            """
            INSERT INTO assessment_attempts (id, user_id, course_id, chapter_id, question_count)
            VALUES (1, 1, 1, 1, 1)
            """
        )
        self.database.execute(
            "INSERT INTO assessment_attempt_questions VALUES (1, 1, 1)"
        )
        self.database.execute(
            """
            INSERT INTO assessment_attempt_answers (attempt_id, question_id, answer, is_correct)
            VALUES (1, 1, '"a"', 1)
            """
        )
        self.database.commit()

        migrations.migrate_database(self.database)
        snapshot = self.database.execute(
            """
            SELECT question_snapshot FROM assessment_attempt_questions
            WHERE attempt_id = 1 AND question_id = 1
            """
        ).fetchone()[0]
        self.assertEqual(json.loads(snapshot)["prompt"], "Original question?")
        self.assertEqual(json.loads(snapshot)["difficulty"], "beginner")

        self.database.execute("DELETE FROM assessment_questions WHERE id = 1")
        self.database.commit()
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM assessment_attempt_questions"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM assessment_attempt_answers"
            ).fetchone()[0],
            1,
        )

    def test_user_roles_default_to_student_and_reject_unknown_roles(self):
        migrations.migrate_database(self.database)
        self.database.execute(
            "INSERT INTO users (email, password_hash) VALUES ('student@example.com', 'hash')"
        )
        self.assertEqual(
            self.database.execute(
                "SELECT role FROM users WHERE email = 'student@example.com'"
            ).fetchone()[0],
            "student",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES ('invalid@example.com', 'hash', 'unknown')
                """
            )

    def test_publication_status_defaults_to_published_and_rejects_unknown_values(self):
        migrations.migrate_database(self.database)
        self.database.execute(
            "INSERT INTO courses (slug, title) VALUES ('course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (course_id, position, title) VALUES (1, 1, 'Chapter')"
        )
        self.assertEqual(
            self.database.execute(
                "SELECT status FROM courses WHERE id = 1"
            ).fetchone()[0],
            "published",
        )
        self.assertEqual(
            self.database.execute(
                "SELECT status FROM chapters WHERE id = 1"
            ).fetchone()[0],
            "published",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                "UPDATE courses SET status = 'review' WHERE id = 1"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                "UPDATE chapters SET status = 'review' WHERE id = 1"
            )

    def test_library_materials_are_course_scoped_and_have_resource_fields(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database)
        columns = {
            row[1] for row in self.database.execute(
                "PRAGMA table_info(library_materials)"
            )
        }
        self.assertTrue(
            {
                "course_id",
                "title",
                "description",
                "material_type",
                "resource_url",
                "content",
                "position",
            }.issubset(columns)
        )
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            """
            INSERT INTO library_materials (course_id, title, material_type)
            VALUES (1, 'Reference', 'book')
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                """
                INSERT INTO library_materials (course_id, title, material_type)
                VALUES (99, 'Invalid', 'article')
                """
            )

    def test_progress_references_chapters_and_cascades_on_deletion(self):
        self.database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(self.database)
        self.database.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (1, 'student@example.com', 'hash')"
        )
        self.database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        self.database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        self.database.execute(
            "INSERT INTO chapter_progress (user_id, chapter_id, completed) VALUES (1, 1, 1)"
        )
        self.database.execute(
            "INSERT INTO chapter_completion_history (user_id, chapter_id) VALUES (1, 1)"
        )
        self.database.commit()

        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM chapter_completion_history"
            ).fetchone()[0],
            1,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.database.execute(
                "INSERT INTO chapter_progress (user_id, chapter_id) VALUES (1, 99)"
            )
        self.database.rollback()

        self.database.execute("DELETE FROM chapters WHERE id = 1")
        self.database.commit()
        self.assertEqual(
            self.database.execute(
                "SELECT COUNT(*) FROM chapter_progress"
            ).fetchone()[0],
            0,
        )

    def test_failed_migration_rolls_back_schema_and_version_record(self):
        migrations.migrate_database(self.database)

        def fail_after_ddl(database):
            database.execute("CREATE TABLE should_be_rolled_back (id INTEGER)")
            raise RuntimeError("migration failed")

        with patch.object(
            migrations,
            "MIGRATIONS",
            migrations.MIGRATIONS + ((18, "failing_migration", fail_after_ddl),),
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
                "SELECT 1 FROM schema_migrations WHERE version = 18"
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

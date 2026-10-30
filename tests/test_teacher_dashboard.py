import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app


class TeacherDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "teacher-dashboard-test-secret",
                "DATABASE": os.path.join(self.temp_dir.name, "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        response = self.client.get("/")
        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            response.data,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def login(self, login, password):
        response = self.client.post(
            "/api/auth/login",
            json={"login": login, "password": password},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 200)

    def test_reports_require_teacher_or_admin_role(self):
        self.assertEqual(self.client.get("/teacher/reports").status_code, 401)

        self.login("test", "test")
        self.assertEqual(self.client.get("/teacher/reports").status_code, 403)

        self.client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.login("admin", "admin")
        response = self.client.get("/teacher/reports")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Результаты учащихся".encode(), response.data)
        self.assertIn(b"test@example.com", response.data)

    def test_report_aggregates_student_course_results(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            user_id = database.execute(
                "SELECT id FROM users WHERE username = 'test'"
            ).fetchone()[0]
            database.executemany(
                """
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (?, ?, 1)
                """,
                [(user_id, 1), (user_id, 2)],
            )
            database.execute(
                """
                INSERT INTO assessment_attempts (
                    user_id, course_id, chapter_id, score,
                    question_count, submitted_at
                ) VALUES (?, 1, 1, 3, 4, CURRENT_TIMESTAMP)
                """,
                (user_id,),
            )
            database.executemany(
                """
                INSERT INTO laboratory_attempts (
                    user_id, chapter_id, laboratory_slug, status,
                    completed_at, score, max_score
                ) VALUES (?, 1, 'byte-assembly', 'completed', CURRENT_TIMESTAMP, 1, 1)
                """,
                [(user_id,), (user_id,)],
            )
            database.commit()
        self.login("admin", "admin")

        response = self.client.get("/teacher/reports")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"25%", response.data)
        self.assertIn(b"75%", response.data)
        self.assertIn("2 / 8 глав".encode(), response.data)
        self.assertIn("2 запусков".encode(), response.data)

    def test_report_search_filters_username_and_email(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                INSERT INTO users (email, username, password_hash, role)
                VALUES ('learner@example.com', 'learner', 'hash', 'student')
                """
            )
            database.commit()
        self.login("admin", "admin")

        response = self.client.get("/teacher/reports?q=learner%40example")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"learner@example.com", response.data)
        self.assertNotIn(b"test@example.com", response.data)
        self.assertIn(b'value="learner@example"', response.data)


if __name__ == "__main__":
    unittest.main()

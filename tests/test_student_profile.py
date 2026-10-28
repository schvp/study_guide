import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app


class StudentProfileStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "profile-statistics-test-secret",
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

    def login_demo_user(self):
        response = self.client.post(
            "/api/auth/login",
            json={"login": "test", "password": "test"},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(response.status_code, 200)

    def test_profile_shows_empty_learning_summary(self):
        self.login_demo_user()

        response = self.client.get("/profile")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Результаты обучения".encode(), response.data)
        self.assertIn("Пройдено курса".encode(), response.data)

    def test_profile_aggregates_course_results(self):
        self.login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            user_id = database.execute(
                "SELECT id FROM users WHERE username = 'test'"
            ).fetchone()[0]
            database.executemany(
                """
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (?, ?, 1)
                """,
                [(user_id, 1), (user_id, 2), (user_id, 3)],
            )
            database.executemany(
                """
                INSERT INTO assessment_attempts (
                    user_id, course_id, chapter_id, score,
                    question_count, submitted_at
                ) VALUES (?, 1, 1, ?, ?, CURRENT_TIMESTAMP)
                """,
                [(user_id, 3, 4), (user_id, 2, 2)],
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

        response = self.client.get("/profile")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"38%", response.data)
        self.assertIn(b"88%", response.data)
        self.assertIn(b"100%", response.data)
        self.assertIn("1 / 8".encode(), response.data)
        self.assertIn("2 попыток".encode(), response.data)
        self.assertIn(b"0%", response.data)
        self.assertIn("0 завершённых попыток".encode(), response.data)


if __name__ == "__main__":
    unittest.main()

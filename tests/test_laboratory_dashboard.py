import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app


class LaboratoryDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "laboratory-test-secret",
                "DATABASE": os.path.join(self.temp_dir.name, "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        response = self.client.get("/laboratory")
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

    def test_guest_sees_catalog_with_only_first_laboratory_available(self):
        response = self.client.get("/laboratory")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Интерактивные лабораторные работы".encode(), response.data)
        self.assertIn("Сборка двоичного байта".encode(), response.data)
        self.assertIn("Оперативная и постоянная память".encode(), response.data)
        self.assertIn(b'href="/course/1"', response.data)
        self.assertNotIn(b'href="/course/2"', response.data)

    def test_completion_unlocks_next_laboratory_and_updates_summary(self):
        self.login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            user_id = database.execute(
                "SELECT id FROM users WHERE username = 'test'"
            ).fetchone()[0]
            database.execute(
                """
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (?, 1, 1)
                """,
                (user_id,),
            )
            database.commit()

        response = self.client.get("/laboratory")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/course/2"', response.data)
        self.assertIn("1 / 8".encode(), response.data)
        self.assertIn("Повторить".encode(), response.data)


if __name__ == "__main__":
    unittest.main()

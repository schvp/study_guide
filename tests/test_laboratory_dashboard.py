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

    def test_authenticated_user_can_start_available_laboratory(self):
        self.login_demo_user()

        response = self.client.post(
            "/api/laboratories/byte-assembly/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["status"], "started")
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved = database.execute(
                """
                SELECT laboratory_slug, status
                FROM laboratory_attempts WHERE id = ?
                """,
                (response.get_json()["attempt_id"],),
            ).fetchone()
        self.assertEqual(saved, ("byte-assembly", "started"))

    def test_user_can_complete_started_laboratory_attempt(self):
        self.login_demo_user()
        started = self.client.post(
            "/api/laboratories/byte-assembly/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        ).get_json()

        response = self.client.post(
            f"/api/laboratories/attempts/{started['attempt_id']}/complete",
            headers={"X-CSRF-Token": self.csrf_token()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "completed")
        self.assertEqual(response.get_json()["score"], 1)
        self.assertEqual(response.get_json()["max_score"], 1)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved = database.execute(
                """
                SELECT status, score, max_score, completed_at IS NOT NULL
                FROM laboratory_attempts WHERE id = ?
                """,
                (started["attempt_id"],),
            ).fetchone()
        self.assertEqual(saved, ("completed", 1, 1, 1))

        repeated = self.client.post(
            f"/api/laboratories/attempts/{started['attempt_id']}/complete",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["status"], "completed")

    def test_laboratory_completion_hides_attempts_from_other_users(self):
        self.login_demo_user()
        started = self.client.post(
            "/api/laboratories/byte-assembly/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        ).get_json()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            cursor = database.execute(
                """
                INSERT INTO users (email, username, password_hash)
                VALUES ('other@example.com', 'other', 'hash')
                """
            )
            other_user_id = cursor.lastrowid
            database.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = other_user_id

        response = self.client.post(
            f"/api/laboratories/attempts/{started['attempt_id']}/complete",
            headers={"X-CSRF-Token": self.csrf_token()},
        )

        self.assertEqual(response.status_code, 404)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            status = database.execute(
                "SELECT status FROM laboratory_attempts WHERE id = ?",
                (started["attempt_id"],),
            ).fetchone()[0]
        self.assertEqual(status, "started")

    def test_laboratory_completion_requires_login(self):
        response = self.client.post(
            "/api/laboratories/attempts/1/complete",
            headers={"X-CSRF-Token": self.csrf_token()},
        )

        self.assertEqual(response.status_code, 401)

    def test_laboratory_start_requires_login_and_unlocked_chapter(self):
        guest_response = self.client.post(
            "/api/laboratories/byte-assembly/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(guest_response.status_code, 401)

        self.login_demo_user()
        locked_response = self.client.post(
            "/api/laboratories/octal-conversion/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(locked_response.status_code, 409)

        unknown_response = self.client.post(
            "/api/laboratories/unknown/attempts",
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertEqual(unknown_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

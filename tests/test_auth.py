import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app
from werkzeug.security import check_password_hash


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "test.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE": database_path,
            }
        )
        self.client = self.app.test_client()
        self.csrf_token = self._load_csrf_token()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _load_csrf_token(self):
        response = self.client.get("/")
        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            response.data,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def _post_json(self, path, payload):
        return self.client.post(
            path,
            json=payload,
            headers={"X-CSRF-Token": self.csrf_token},
        )

    def _register(
        self,
        email="student@example.com",
        password="correct-horse",
        username="student",
    ):
        response = self._post_json(
            "/api/auth/register",
            {"email": email, "username": username, "password": password},
        )
        if response.status_code == 201:
            self.csrf_token = self._load_csrf_token()
        return response

    def test_registration_stores_password_hash_and_logs_user_in(self):
        response = self._register("Student@Example.com")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["email"], "student@example.com")
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            email, password_hash = database.execute(
                "SELECT email, password_hash FROM users WHERE email = ?",
                ("student@example.com",),
            ).fetchone()

        self.assertEqual(email, "student@example.com")
        self.assertNotEqual(password_hash, "correct-horse")
        self.assertTrue(check_password_hash(password_hash, "correct-horse"))
        self.assertIn(b"student@example.com", self.client.get("/").data)

    def test_demo_user_is_seeded_and_can_login_with_username(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            email, username, password_hash = database.execute(
                "SELECT email, username, password_hash FROM users WHERE username = ?",
                ("test",),
            ).fetchone()

        self.assertEqual(email, "test@example.com")
        self.assertEqual(username, "test")
        self.assertTrue(check_password_hash(password_hash, "test"))

        response = self._post_json(
            "/api/auth/login",
            {"login": "test", "password": "test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"test@example.com", self.client.get("/").data)

    def test_my_course_is_shown_only_after_login_with_course_contents(self):
        anonymous_page = self.client.get("/").data
        self.assertNotIn(b"href=\"#my-course\"", anonymous_page)
        self.assertNotIn(b"my-course-card", anonymous_page)

        response = self._post_json(
            "/api/auth/login",
            {"login": "test", "password": "test"},
        )

        self.assertEqual(response.status_code, 200)
        page = self.client.get("/").data
        self.assertIn(b'href="#my-course"', page)
        self.assertIn(b'id="my-course"', page)
        self.assertIn("Мой курс".encode(), page)
        self.assertIn("Схемотехника цифровых систем".encode(), page)
        self.assertIn("Содержание курса".encode(), page)
        self.assertEqual(page.count(b'class="chapter"'), 8)

    def test_existing_database_is_migrated_without_losing_users(self):
        database_path = os.path.join(self.temp_dir.name, "legacy.sqlite3")
        with closing(sqlite3.connect(database_path)) as database:
            database.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO users (email, password_hash)
                VALUES ('legacy@example.com', 'legacy-hash');
                """
            )

        create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "migration-secret",
                "DATABASE": database_path,
                "SEED_DEMO_USER": False,
            }
        )

        with closing(sqlite3.connect(database_path)) as database:
            columns = {
                row[1] for row in database.execute("PRAGMA table_info(users)")
            }
            legacy_user = database.execute(
                "SELECT email, password_hash FROM users WHERE email = ?",
                ("legacy@example.com",),
            ).fetchone()

        self.assertIn("username", columns)
        self.assertEqual(legacy_user, ("legacy@example.com", "legacy-hash"))

    def test_duplicate_email_is_rejected_without_case_sensitivity(self):
        self.assertEqual(self._register().status_code, 201)

        response = self._register("STUDENT@example.com")

        self.assertEqual(response.status_code, 409)

    def test_login_and_progress_are_persisted_per_user(self):
        self.assertEqual(self._register().status_code, 201)
        response = self._post_json(
            "/api/progress/2",
            {"completed": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"checked", self.client.get("/").data)

        self.assertEqual(
            self._post_json("/api/auth/logout", {}).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        response = self._post_json(
            "/api/auth/login",
            {"login": "STUDENT@example.com", "password": "correct-horse"},
        )

        self.assertEqual(response.status_code, 200)
        page = self.client.get("/").data
        self.assertIn(b"student@example.com", page)
        self.assertIn(b"checked", page)

    def test_login_rejects_wrong_password(self):
        self.assertEqual(self._register().status_code, 201)
        self._post_json("/api/auth/logout", {})
        self.csrf_token = self._load_csrf_token()

        response = self._post_json(
            "/api/auth/login",
            {"login": "student@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_progress_requires_authentication_and_valid_chapter(self):
        response = self._post_json(
            "/api/progress/1",
            {"completed": True},
        )
        self.assertEqual(response.status_code, 401)

        self.assertEqual(self._register().status_code, 201)
        response = self._post_json(
            "/api/progress/99",
            {"completed": True},
        )
        self.assertEqual(response.status_code, 404)

    def test_authentication_endpoints_require_csrf_token(self):
        response = self.client.post(
            "/api/auth/register",
            json={"email": "student@example.com", "password": "correct-horse"},
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

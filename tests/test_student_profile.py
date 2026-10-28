import os
import re
import tempfile
import unittest

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
        self.assertIn(b"0%", response.data)
        self.assertIn("0 завершённых попыток".encode(), response.data)


if __name__ == "__main__":
    unittest.main()

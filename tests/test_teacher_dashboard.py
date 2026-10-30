import os
import re
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()

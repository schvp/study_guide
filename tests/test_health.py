import os
import tempfile
import unittest

from app import create_app
from migrations import MIGRATIONS


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "health-test-secret",
                "DATABASE": os.path.join(self.temp_dir.name, "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_check_reports_database_and_schema(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "ok",
                "database": "available",
                "schema_version": MIGRATIONS[-1][0],
            },
        )

    def test_responses_include_baseline_security_headers(self):
        response = self.client.get("/")

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
        self.assertEqual(
            response.headers["Permissions-Policy"],
            "camera=(), microphone=(), geolocation=()",
        )


if __name__ == "__main__":
    unittest.main()

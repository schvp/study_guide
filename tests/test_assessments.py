import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
                "DATABASE": os.path.join(self.temp_dir.name, "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()
        self.csrf_token = self._load_csrf_token()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _load_csrf_token(self):
        response = self.client.get("/testing")
        self.assertEqual(response.status_code, 200)
        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"',
            response.data,
        )
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def _post_json(self, path, payload, token=None):
        return self.client.post(
            path,
            json=payload,
            headers={"X-CSRF-Token": token or self.csrf_token},
        )

    def _start_attempt(self, chapter_id=1):
        response = self._post_json(
            f"/api/assessments/{chapter_id}/attempts",
            {},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _login_demo_user(self):
        response = self._post_json(
            "/api/auth/login",
            {"login": "test", "password": "test"},
        )
        self.assertEqual(response.status_code, 200)
        self.csrf_token = self._load_csrf_token()

    def test_testing_page_lists_published_chapter_quizzes(self):
        response = self.client.get("/testing")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Выберите тему".encode(), response.data)
        self.assertIn("Введение в цифровую схемотехнику".encode(), response.data)
        self.assertIn("Запоминающие устройства".encode(), response.data)

        self._login_demo_user()
        response = self.client.get("/testing")
        self.assertIn(b"data-assessment-start", response.data)
        self.assertNotIn(b"correct_answer", response.data)

    def test_guest_cannot_start_attempt_and_csrf_is_required(self):
        unauthorized = self.client.post(
            "/api/assessments/1/attempts",
            json={},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(unauthorized.status_code, 401)

        self._login_demo_user()
        missing_csrf = self.client.post(
            "/api/assessments/1/attempts",
            json={},
        )
        self.assertEqual(missing_csrf.status_code, 400)

    def test_starting_attempt_returns_questions_without_correct_answers(self):
        self._login_demo_user()

        response = self._post_json("/api/assessments/1/attempts", {})

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(len(data["questions"]), 2)
        self.assertTrue(all("correct_answer" not in item for item in data["questions"]))
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            attempt = database.execute(
                "SELECT question_count FROM assessment_attempts WHERE id = ?",
                (data["attempt_id"],),
            ).fetchone()
            question_count = database.execute(
                """
                SELECT COUNT(*) FROM assessment_attempt_questions
                WHERE attempt_id = ?
                """,
                (data["attempt_id"],),
            ).fetchone()[0]
        self.assertEqual(attempt, (2,))
        self.assertEqual(question_count, 2)

    def test_numeric_and_multiple_choice_answers_are_graded_and_saved(self):
        self._login_demo_user()
        attempt = self._start_attempt(chapter_id=2)
        answers = {}
        for question in attempt["questions"]:
            answers[str(question["id"])] = (
                "255"
                if question["question_type"] == "numeric"
                else ["binary", "octal", "hex"]
            )

        response = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual((result["score"], result["question_count"]), (2, 2))
        self.assertTrue(all(item["correct"] for item in result["results"]))
        self.assertTrue(all(item["explanation"] for item in result["results"]))

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved_attempt = database.execute(
                """
                SELECT score, question_count, submitted_at
                FROM assessment_attempts WHERE id = ?
                """,
                (attempt["attempt_id"],),
            ).fetchone()
            saved_answers = database.execute(
                """
                SELECT COUNT(*) FROM assessment_attempt_answers
                WHERE attempt_id = ? AND is_correct = 1
                """,
                (attempt["attempt_id"],),
            ).fetchone()[0]
        self.assertEqual(saved_attempt[:2], (2, 2))
        self.assertIsNotNone(saved_attempt[2])
        self.assertEqual(saved_answers, 2)

        history_page = self.client.get("/testing")
        self.assertIn("2 / 2".encode(), history_page.data)

    def test_incorrect_answer_returns_correct_answer_and_explanation(self):
        self._login_demo_user()
        attempt = self._start_attempt(chapter_id=1)
        answers = {
            str(question["id"]): (
                "4" if question["question_type"] == "single_choice" else "10"
            )
            for question in attempt["questions"]
        }

        response = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["score"], 0)
        self.assertTrue(all(not item["correct"] for item in result["results"]))
        self.assertTrue(all("correct_answer" in item for item in result["results"]))
        self.assertTrue(all(item["explanation"] for item in result["results"]))

    def test_invalid_answers_do_not_submit_attempt(self):
        self._login_demo_user()
        attempt = self._start_attempt()
        question_id = str(attempt["questions"][0]["id"])

        missing = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": {}},
        )
        invalid = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": {question_id: "not-an-option", "999999": "x"}},
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            submitted_at = database.execute(
                "SELECT submitted_at FROM assessment_attempts WHERE id = ?",
                (attempt["attempt_id"],),
            ).fetchone()[0]
        self.assertIsNone(submitted_at)

    def test_attempt_is_private_to_its_owner_and_cannot_be_submitted_twice(self):
        self._login_demo_user()
        attempt = self._start_attempt()
        answers = {
            str(question["id"]): (
                "8" if question["question_type"] == "single_choice" else "11"
            )
            for question in attempt["questions"]
        }

        first_submit = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )
        second_submit = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )
        self.assertEqual(first_submit.status_code, 200)
        self.assertEqual(second_submit.status_code, 409)

        self._post_json("/api/auth/logout", {})
        self.csrf_token = self._load_csrf_token()
        registration = self._post_json(
            "/api/auth/register",
            {
                "email": "other@example.com",
                "username": "other",
                "password": "another-password",
            },
        )
        self.assertEqual(registration.status_code, 201)
        self.csrf_token = self._load_csrf_token()
        unauthorized_owner = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )
        self.assertEqual(unauthorized_owner.status_code, 404)


if __name__ == "__main__":
    unittest.main()

import json
import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

from assessment_bank import INITIAL_QUESTIONS, seed_assessment_questions
from app import create_app
import migrations


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

    def _login_admin(self):
        response = self._post_json(
            "/api/auth/login",
            {"login": "admin", "password": "admin"},
        )
        self.assertEqual(response.status_code, 200)
        self.csrf_token = self._load_csrf_token()

    def _post_form(self, path, payload, token=None):
        return self.client.post(
            path,
            data={"csrf_token": token or self.csrf_token, **payload},
        )

    def _correct_answers(self, attempt):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            snapshots = dict(
                database.execute(
                    """
                    SELECT question_id, question_snapshot
                    FROM assessment_attempt_questions
                    WHERE attempt_id = ?
                    """,
                    (attempt["attempt_id"],),
                ).fetchall()
            )
        answers = {}
        for question in attempt["questions"]:
            snapshot = json.loads(snapshots[question["id"]])
            expected = snapshot["correct_answer"]
            answers[str(question["id"])] = (
                str(expected)
                if snapshot["question_type"] == "numeric"
                else expected
            )
        return answers

    def _incorrect_answers(self, attempt):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            snapshots = dict(
                database.execute(
                    """
                    SELECT question_id, question_snapshot
                    FROM assessment_attempt_questions
                    WHERE attempt_id = ?
                    """,
                    (attempt["attempt_id"],),
                ).fetchall()
            )
        answers = {}
        for question in attempt["questions"]:
            snapshot = json.loads(snapshots[question["id"]])
            expected = snapshot["correct_answer"]
            if snapshot["question_type"] == "numeric":
                answer = str(float(expected) + 1)
            elif snapshot["question_type"] == "multiple_choice":
                expected_values = set(expected)
                answer = [
                    option["value"]
                    for option in snapshot["options"]
                    if option["value"] not in expected_values
                ][:1]
            else:
                answer = next(
                    option["value"]
                    for option in snapshot["options"]
                    if option["value"] != expected
                )
            answers[str(question["id"])] = answer
        return answers

    def test_testing_page_lists_published_chapter_quizzes(self):
        response = self.client.get("/testing")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Выберите тему".encode(), response.data)
        self.assertIn("Введение в цифровую схемотехнику".encode(), response.data)
        self.assertIn("Запоминающие устройства".encode(), response.data)

        self._login_demo_user()
        response = self.client.get("/testing")
        self.assertIn(b"data-assessment-start", response.data)
        self.assertIn("До 2 вопросов из 3".encode(), response.data)
        self.assertNotIn(b"correct_answer", response.data)

    def test_testing_page_shows_attempt_usage_for_limited_quiz(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET max_attempts = 3 WHERE chapter_id = 1
                """
            )
            database.commit()
        self._start_attempt()

        response = self.client.get("/testing")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Использовано попыток: 1 из 3".encode(), response.data)

    def test_testing_page_disables_quiz_after_attempt_limit(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET max_attempts = 1 WHERE chapter_id = 1
                """
            )
            database.commit()
        self._start_attempt()

        response = self.client.get("/testing")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Попытки закончились".encode(), response.data)
        self.assertRegex(
            response.data,
            rb"data-chapter-id=\"1\"\s+disabled aria-disabled=\"true\"",
        )

    def test_removed_seed_questions_are_not_recreated_on_restart(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute("DELETE FROM assessment_questions")
            database.commit()
            database.row_factory = sqlite3.Row
            course_id = database.execute(
                "SELECT id FROM courses WHERE slug = 'digital-circuits'"
            ).fetchone()["id"]
            seed_assessment_questions(database, course_id)
            database.commit()
            question_count = database.execute(
                "SELECT COUNT(*) FROM assessment_questions"
            ).fetchone()[0]
        self.assertEqual(question_count, 0)

    def test_existing_seed_bank_receives_new_levels_without_restoring_removed_questions(self):
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        migrations.migrate_database(database, through_version=12)
        database.execute(
            "INSERT INTO courses (id, slug, title) VALUES (1, 'course', 'Course')"
        )
        database.execute(
            "INSERT INTO chapters (id, course_id, position, title) VALUES (1, 1, 1, 'Chapter')"
        )
        starter = INITIAL_QUESTIONS[0]
        database.execute(
            """
            INSERT INTO assessment_questions (
                course_id, chapter_id, question_type, prompt, options,
                correct_answer, explanation, position
            )
            VALUES (1, 1, ?, ?, ?, ?, ?, 1)
            """,
            (
                starter["question_type"],
                starter["prompt"],
                json.dumps(starter["options"]),
                json.dumps(starter["correct_answer"]),
                starter["explanation"],
            ),
        )
        database.execute(
            "INSERT INTO assessment_bank_seed_state (course_id) VALUES (1)"
        )
        migrations.migrate_database(database)

        seed_assessment_questions(database, 1)

        rows = database.execute(
            """
            SELECT prompt, difficulty FROM assessment_questions
            WHERE chapter_id = 1 ORDER BY position
            """
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["difficulty"], "beginner")
        self.assertEqual(rows[1]["difficulty"], "advanced")
        database.close()

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

    def test_starting_attempt_returns_configured_time_and_attempt_limits(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET time_limit_seconds = 120, max_attempts = 2
                WHERE chapter_id = 1
                """
            )
            database.commit()

        response = self._post_json("/api/assessments/1/attempts", {})

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["time_limit_seconds"], 120)
        self.assertEqual(data["attempts_remaining"], 1)
        self.assertTrue(data["expires_at"])

    def test_starting_attempt_rejects_user_after_maximum_attempts(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET max_attempts = 1 WHERE chapter_id = 1
                """
            )
            database.commit()

        self.assertEqual(self._start_attempt().get("attempt_id"), 1)
        response = self._post_json("/api/assessments/1/attempts", {})

        self.assertEqual(response.status_code, 409)
        self.assertIn("все доступные попытки", response.get_json()["error"])

    def test_expired_attempt_is_closed_without_grading_answers(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET time_limit_seconds = 60 WHERE chapter_id = 1
                """
            )
            database.commit()
        attempt = self._start_attempt()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_attempts
                SET expires_at = '2000-01-01T00:00:00+00:00'
                WHERE id = ?
                """,
                (attempt["attempt_id"],),
            )
            database.commit()

        response = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": {}},
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["expired"])
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved = database.execute(
                "SELECT score, submitted_at FROM assessment_attempts WHERE id = ?",
                (attempt["attempt_id"],),
            ).fetchone()
        self.assertEqual(saved[0], 0)
        self.assertIsNotNone(saved[1])

    def test_attempt_randomly_samples_configured_count_at_selected_difficulty(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET questions_per_attempt = 1 WHERE chapter_id = 1
                """
            )
            database.execute(
                """
                UPDATE assessment_questions SET difficulty = 'advanced'
                WHERE chapter_id = 1
                """
            )
            database.commit()
        no_matches = self._post_json(
            "/api/assessments/1/attempts",
            {"difficulty": "beginner"},
        )
        self.assertEqual(no_matches.status_code, 404)

        attempt = self._start_attempt()
        self.assertEqual(len(attempt["questions"]), 1)
        self.assertEqual(attempt["questions"][0]["difficulty"], "advanced")
        self.assertNotIn("correct_answer", attempt["questions"][0])

        invalid = self._post_json(
            "/api/assessments/1/attempts",
            {"difficulty": "expert"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_numeric_and_multiple_choice_answers_are_graded_and_saved(self):
        self._login_demo_user()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                UPDATE assessment_chapter_settings
                SET questions_per_attempt = 20 WHERE chapter_id = 2
                """
            )
            database.commit()
        attempt = self._start_attempt(chapter_id=2)
        answers = self._correct_answers(attempt)

        response = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual((result["score"], result["question_count"]), (3, 3))
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
        self.assertEqual(saved_attempt[:2], (3, 3))
        self.assertIsNotNone(saved_attempt[2])
        self.assertEqual(saved_answers, 3)

        history_page = self.client.get("/testing")
        self.assertIn("3 / 3".encode(), history_page.data)

    def test_incorrect_answer_returns_correct_answer_and_explanation(self):
        self._login_demo_user()
        attempt = self._start_attempt(chapter_id=1)
        answers = self._incorrect_answers(attempt)

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
        answers = self._correct_answers(attempt)

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

    def test_teacher_question_management_creates_edits_reorders_and_deletes(self):
        self._login_admin()
        page = self.client.get("/content-management")
        self.assertEqual(page.status_code, 200)
        self.assertIn("БАНК ВОПРОСОВ".encode(), page.data)
        self.assertIn("Код правильного варианта".encode(), page.data)

        created = self._post_form(
            "/content-management/chapters/1/assessment-questions",
            {
                "question_type": "single_choice",
                "prompt": "Какое значение соответствует включённому сигналу?",
                "options": "on|Включён\noff|Выключен",
                "correct_answer": "on",
                "tolerance": "0",
                "explanation": "Логическая единица соответствует активному уровню.",
                "position": "1",
                "published": "0",
            },
        )
        self.assertEqual(created.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            question_id, position, published = database.execute(
                """
                SELECT id, position, published FROM assessment_questions
                WHERE prompt = ?
                """,
                ("Какое значение соответствует включённому сигналу?",),
            ).fetchone()
            shifted_position = database.execute(
                "SELECT position FROM assessment_questions WHERE id = 1"
            ).fetchone()[0]
        self.assertEqual((position, published, shifted_position), (1, 0, 2))

        edited = self._post_form(
            f"/content-management/assessment-questions/{question_id}",
            {
                "question_type": "multiple_choice",
                "difficulty": "advanced",
                "prompt": "Выберите оба активных уровня.",
                "options": "high|Высокий\nlow|Низкий",
                "correct_answer": "high, low",
                "tolerance": "0",
                "explanation": "В этой модели оба уровня перечислены как активные.",
                "position": "2",
                "published": "1",
            },
        )
        self.assertEqual(edited.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved = database.execute(
                """
                SELECT question_type, prompt, correct_answer, position, published,
                    difficulty
                FROM assessment_questions WHERE id = ?
                """,
                (question_id,),
            ).fetchone()
        self.assertEqual(
            saved,
            (
                "multiple_choice",
                "Выберите оба активных уровня.",
                '["high", "low"]',
                2,
                1,
                "advanced",
            ),
        )
        settings = self._post_form(
            "/content-management/chapters/1/assessment-settings",
            {"questions_per_attempt": "1"},
        )
        self.assertEqual(settings.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            configured_count = database.execute(
                """
                SELECT questions_per_attempt FROM assessment_chapter_settings
                WHERE chapter_id = 1
                """
            ).fetchone()[0]
        self.assertEqual(configured_count, 1)

        deleted = self._post_form(
            f"/content-management/assessment-questions/{question_id}/delete",
            {},
        )
        self.assertEqual(deleted.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertIsNone(
                database.execute(
                    "SELECT id FROM assessment_questions WHERE id = ?",
                    (question_id,),
                ).fetchone()
            )
            self.assertEqual(
                database.execute(
                    "SELECT MIN(position) FROM assessment_questions WHERE chapter_id = 1"
                ).fetchone()[0],
                1,
            )

    def test_assessment_settings_reject_invalid_question_counts(self):
        self._login_admin()
        response = self._post_form(
            "/content-management/chapters/1/assessment-settings",
            {"questions_per_attempt": "21"},
        )
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.headers["Location"])
        self.assertIn("от 1 до 20 вопросов".encode(), page.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    """
                    SELECT questions_per_attempt FROM assessment_chapter_settings
                    WHERE chapter_id = 1
                    """
                ).fetchone()[0],
                2,
            )

    def test_question_editor_enforces_role_csrf_and_validates_options(self):
        self._login_demo_user()
        student_response = self._post_form(
            "/content-management/chapters/1/assessment-questions",
            {},
        )
        self.assertEqual(student_response.status_code, 403)
        self._post_json("/api/auth/logout", {})
        self.csrf_token = self._load_csrf_token()
        self._login_admin()

        missing_csrf = self.client.post(
            "/content-management/chapters/1/assessment-questions",
            data={"prompt": "No CSRF"},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        invalid_options = self._post_form(
            "/content-management/chapters/1/assessment-questions",
            {
                "question_type": "single_choice",
                "prompt": "Malformed options?",
                "options": "Missing delimiter\nno|No",
                "correct_answer": "yes",
                "position": "3",
                "published": "1",
            },
        )
        self.assertEqual(invalid_options.status_code, 302)
        page = self.client.get(invalid_options.headers["Location"])
        self.assertIn("Проверьте варианты".encode(), page.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertIsNone(
                database.execute(
                    "SELECT id FROM assessment_questions WHERE prompt = 'Malformed options?'"
                ).fetchone()
            )

    def test_editing_or_deleting_question_does_not_change_started_attempt(self):
        self._login_demo_user()
        attempt = self._start_attempt()
        question_ids = [question["id"] for question in attempt["questions"]]
        self._post_json("/api/auth/logout", {})
        self.csrf_token = self._load_csrf_token()
        self._login_admin()
        deleted = self._post_form(
            f"/content-management/assessment-questions/{question_ids[0]}/delete",
            {},
        )
        self.assertEqual(deleted.status_code, 302)

        self._post_json("/api/auth/logout", {})
        self.csrf_token = self._load_csrf_token()
        self._login_demo_user()
        answers = self._correct_answers(attempt)
        submitted = self._post_json(
            f"/api/assessments/attempts/{attempt['attempt_id']}/submit",
            {"answers": answers},
        )

        self.assertEqual(submitted.status_code, 200, submitted.get_json())
        self.assertEqual(submitted.get_json()["score"], 2)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            stored_answers = database.execute(
                """
                SELECT COUNT(*) FROM assessment_attempt_answers
                WHERE attempt_id = ? AND is_correct = 1
                """,
                (attempt["attempt_id"],),
            ).fetchone()[0]
        self.assertEqual(stored_answers, 2)


if __name__ == "__main__":
    unittest.main()

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
            email, password_hash, role = database.execute(
                "SELECT email, password_hash, role FROM users WHERE email = ?",
                ("student@example.com",),
            ).fetchone()

        self.assertEqual(email, "student@example.com")
        self.assertEqual(role, "student")
        self.assertNotEqual(password_hash, "correct-horse")
        self.assertTrue(check_password_hash(password_hash, "correct-horse"))
        self.assertIn(b"student@example.com", self.client.get("/").data)

    def test_demo_user_is_seeded_and_can_login_with_username(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            email, username, password_hash, role = database.execute(
                "SELECT email, username, password_hash, role FROM users WHERE username = ?",
                ("test",),
            ).fetchone()

        self.assertEqual(email, "test@example.com")
        self.assertEqual(username, "test")
        self.assertEqual(role, "student")
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
        self.assertIn(b'href="/courses"', page)
        self.assertIn(b'id="my-course"', page)
        self.assertIn("Мой курс".encode(), page)
        self.assertIn("Схемотехника цифровых систем".encode(), page)
        self.assertIn("Содержание курса".encode(), page)
        self.assertEqual(page.count(b'class="chapter"'), 8)
        self.assertIn(b'data-chapter-search', page)
        self.assertIn('placeholder="Найти раздел курса"'.encode(), page)
        self.assertIn(b'data-search-results', page)
        self.assertIn(b'href="/course/1"', page)
        self.assertEqual(page.count(b'class="chapter-link'), 8)
        self.assertIn(b'is-locked', page)

    def test_course_catalog_lists_courses_and_opens_course_specific_chapters(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                INSERT INTO courses (id, slug, title, description)
                VALUES (2, 'logic-basics', 'Основы логики', 'Отдельный учебный курс')
                """
            )
            database.executemany(
                """
                INSERT INTO chapters (id, course_id, position, title, description)
                VALUES (?, 2, ?, ?, ?)
                """,
                [
                    (101, 1, "Логическое высказывание", "Первый раздел курса"),
                    (102, 2, "Операции логики", "Второй раздел курса"),
                ],
            )
            database.commit()

        catalog = self.client.get("/courses")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("Каталог курсов".encode(), catalog.data)
        self.assertIn("Основы логики".encode(), catalog.data)
        self.assertIn(b'href="/courses/logic-basics"', catalog.data)

        overview = self.client.get("/courses/logic-basics")
        self.assertEqual(overview.status_code, 200)
        self.assertIn("Отдельный учебный курс".encode(), overview.data)
        self.assertIn("Логическое высказывание".encode(), overview.data)
        self.assertIn("Операции логики".encode(), overview.data)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/course/101").status_code, 200)
        self.assertEqual(self.client.get("/course/102").status_code, 403)
        self.assertEqual(
            self._post_json("/api/progress/101", {"completed": True}).status_code,
            200,
        )
        self.assertEqual(self.client.get("/course/102").status_code, 200)

    def test_unknown_course_overview_uses_branded_404(self):
        response = self.client.get("/courses/missing-course")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Страница не найдена".encode(), response.data)

    def test_homepage_and_chapter_page_use_course_data_from_database(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                "UPDATE courses SET title = ? WHERE slug = ?",
                ("Курс из базы", "digital-circuits"),
            )
            database.execute(
                """
                UPDATE chapters
                SET title = ?, description = ?, content = ?
                WHERE id = 1
                """,
                ("Глава из базы", "Описание из базы", "Текст материала из базы"),
            )
            database.commit()

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )

        home_page = self.client.get("/").data
        chapter_page = self.client.get("/course/1").data
        self.assertIn("Курс из базы".encode(), home_page)
        self.assertIn("Глава из базы".encode(), home_page)
        self.assertIn("Курс из базы".encode(), chapter_page)
        self.assertIn("Описание из базы".encode(), chapter_page)
        self.assertIn("Текст материала из базы".encode(), chapter_page)

    def test_first_chapter_is_seeded_with_readable_material(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            description, content = database.execute(
                """
                SELECT description, content FROM chapters
                WHERE position = 1
                """
            ).fetchone()

        self.assertTrue(description)
        self.assertGreater(len(content), 1500)
        self.assertIn("## Цель раздела", content)
        self.assertIn("## Аналоговые и цифровые сигналы", content)
        self.assertIn("## Проверьте себя", content)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        page = self.client.get("/course/1").data
        self.assertIn("Цель раздела".encode(), page)
        self.assertIn("Аналоговые и цифровые сигналы".encode(), page)
        self.assertIn("Проверьте себя".encode(), page)
        self.assertIn("Сколько различных комбинаций".encode(), page)

    def test_first_chapter_material_is_seeded_into_existing_empty_chapter(self):
        database_path = os.path.join(self.temp_dir.name, "empty-chapter.sqlite3")
        with closing(sqlite3.connect(database_path)) as database:
            database.executescript(
                """
                CREATE TABLE courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO courses (slug, title) VALUES (
                    'digital-circuits', 'Схемотехника цифровых систем'
                );
                CREATE TABLE chapters (
                    id INTEGER PRIMARY KEY,
                    course_id INTEGER NOT NULL REFERENCES courses(id),
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (course_id, position),
                    UNIQUE (course_id, title)
                );
                INSERT INTO chapters (id, course_id, position, title)
                VALUES (1, 1, 1, 'Введение в цифровую схемотехнику');
                """
            )

        create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "seed-content-secret",
                "DATABASE": database_path,
                "SEED_DEMO_USER": False,
            }
        )
        with closing(sqlite3.connect(database_path)) as database:
            seeded_content = database.execute(
                "SELECT description, content FROM chapters WHERE id = 1"
            ).fetchone()
        self.assertTrue(seeded_content[0])
        self.assertIn("Цель раздела", seeded_content[1])

        with closing(sqlite3.connect(database_path)) as database:
            database.execute(
                "UPDATE chapters SET content = ? WHERE id = 1",
                ("Авторский материал",),
            )
            database.commit()
        create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "seed-content-secret",
                "DATABASE": database_path,
                "SEED_DEMO_USER": False,
            }
        )
        with closing(sqlite3.connect(database_path)) as database:
            preserved_content = database.execute(
                "SELECT content FROM chapters WHERE id = 1"
            ).fetchone()[0]
        self.assertEqual(preserved_content, "Авторский материал")

    def test_header_and_sidebar_navigation_routes_are_available(self):
        page = self.client.get("/").data
        for label in ["Главная", "Обучение", "Библиотека", "Лаборатория", "Тестирование", "Профиль"]:
            self.assertGreaterEqual(page.count(label.encode()), 2)

        for path, title in [
            ("/library", "Библиотека"),
            ("/laboratory", "Лаборатория"),
            ("/testing", "Тестирование"),
            ("/profile", "Профиль"),
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(title.encode(), response.data)

    def test_library_page_shows_database_materials_and_empty_state(self):
        empty_page = self.client.get("/library")
        self.assertEqual(empty_page.status_code, 200)
        self.assertIn("Материалы библиотеки появятся здесь.".encode(), empty_page.data)

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                INSERT INTO library_materials (
                    course_id, title, description, material_type, resource_url,
                    content, position
                )
                SELECT id, ?, ?, ?, ?, ?, ?
                FROM courses
                WHERE slug = 'digital-circuits'
                """,
                (
                    "Справочник по логике",
                    "Дополнительное описание",
                    "book",
                    "https://example.org/reference",
                    "Текст из библиотеки",
                    1,
                ),
            )
            database.commit()

        populated_page = self.client.get("/library")
        self.assertEqual(populated_page.status_code, 200)
        self.assertIn("Справочник по логике".encode(), populated_page.data)
        self.assertIn("Дополнительное описание".encode(), populated_page.data)
        self.assertIn("book".encode(), populated_page.data)
        self.assertIn("Текст из библиотеки".encode(), populated_page.data)
        self.assertIn("https://example.org/reference".encode(), populated_page.data)

    def test_unknown_routes_show_branded_404_page(self):
        response = self.client.get("/this-page-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Страница не найдена".encode(), response.data)
        self.assertIn("Похоже, схема разомкнулась".encode(), response.data)
        self.assertIn(b'href="/">', response.data)
        self.assertIn(b'href="/#contents"', response.data)

    def test_unknown_route_404_page_keeps_signed_in_navigation(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )

        response = self.client.get("/another-missing-page")

        self.assertEqual(response.status_code, 404)
        self.assertIn(b"test@example.com", response.data)
        self.assertIn(b'href="/#my-course"', response.data)

    def test_profile_navigation_shows_account_after_login(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )

        response = self.client.get("/profile")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"test@example.com", response.data)
        self.assertIn("разделов пройдено".encode(), response.data)
        self.assertIn("Учащийся".encode(), response.data)
        self.assertIn(b'aria-current="page">', response.data)

    def test_registration_cannot_choose_a_privileged_role(self):
        response = self._post_json(
            "/api/auth/register",
            {
                "email": "privilege@example.com",
                "username": "privilege",
                "password": "correct-horse",
                "role": "admin",
            },
        )

        self.assertEqual(response.status_code, 201)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            role = database.execute(
                "SELECT role FROM users WHERE email = ?",
                ("privilege@example.com",),
            ).fetchone()[0]
        self.assertEqual(role, "student")

    def test_content_management_requires_login_and_privileged_role(self):
        anonymous_response = self.client.get("/content-management")
        self.assertEqual(anonymous_response.status_code, 401)
        self.assertIn("Требуется вход".encode(), anonymous_response.data)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        student_profile = self.client.get("/profile")
        self.assertNotIn(b'href="/content-management"', student_profile.data)

        student_response = self.client.get("/content-management")
        self.assertEqual(student_response.status_code, 403)
        self.assertIn("Недостаточно прав".encode(), student_response.data)

    def test_teacher_and_admin_can_open_content_management(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        for role in ("teacher", "admin"):
            with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
                database.execute(
                    "UPDATE users SET role = ? WHERE username = 'test'",
                    (role,),
                )
                database.commit()

            profile = self.client.get("/profile")
            self.assertIn(b'href="/content-management"', profile.data)
            response = self.client.get("/content-management")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Управление контентом".encode(), response.data)

    def test_chapter_completion_is_recorded_once_and_shown_in_profile(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        first_completion = self._post_json(
            "/api/progress/1",
            {"completed": True},
        )
        repeated_completion = self._post_json(
            "/api/progress/1",
            {"completed": True},
        )

        self.assertEqual(first_completion.status_code, 200)
        self.assertEqual(repeated_completion.status_code, 200)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            history = database.execute(
                """
                SELECT chapters.title,
                    strftime(
                        '%d.%m.%Y %H:%M',
                        history.completed_at,
                        'localtime'
                    )
                FROM chapter_completion_history AS history
                JOIN chapters ON chapters.id = history.chapter_id
                WHERE history.user_id = (
                    SELECT id FROM users WHERE username = 'test'
                )
                """
            ).fetchall()

        self.assertEqual(len(history), 1)
        self.assertTrue(history[0][1])

        profile = self.client.get("/profile")
        self.assertIn("Пройденные разделы".encode(), profile.data)
        self.assertIn(history[0][0].encode(), profile.data)
        self.assertIn(history[0][1].encode(), profile.data)

    def test_chapter_pages_are_locked_in_sequence_until_previous_is_completed(self):
        anonymous_response = self.client.get("/course/1")
        self.assertEqual(anonymous_response.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/course/1").status_code, 200)
        self.assertEqual(self.client.get("/course/2").status_code, 403)

        response = self._post_json(
            "/api/progress/1",
            {"completed": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/course/2").status_code, 200)
        self.assertEqual(self.client.get("/course/3").status_code, 403)

    def test_progress_cannot_skip_chapters_or_be_unmarked(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        skipped = self._post_json(
            "/api/progress/2",
            {"completed": True},
        )
        unmarked = self._post_json(
            "/api/progress/1",
            {"completed": False},
        )

        self.assertEqual(skipped.status_code, 403)
        self.assertEqual(unmarked.status_code, 400)

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
                CREATE TABLE chapter_progress (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    chapter_id INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, chapter_id)
                );
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (1, 1, 1);
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
                "SELECT email, password_hash, role FROM users WHERE email = ?",
                ("legacy@example.com",),
            ).fetchone()
            seeded_course = database.execute(
                "SELECT title FROM courses WHERE slug = ?",
                ("digital-circuits",),
            ).fetchone()
            seeded_chapters = database.execute(
                """
                SELECT id, position, title FROM chapters
                ORDER BY position
                """
            ).fetchall()
            legacy_progress = database.execute(
                "SELECT chapter_id, completed FROM chapter_progress WHERE user_id = 1"
            ).fetchone()
            migration_history = database.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
            progress_foreign_keys = database.execute(
                "PRAGMA foreign_key_list(chapter_progress)"
            ).fetchall()
            legacy_history = database.execute(
                """
                SELECT chapter_id, completed_at
                FROM chapter_completion_history
                WHERE user_id = 1
                """
            ).fetchone()
            legacy_progress_updated_at = database.execute(
                "SELECT updated_at FROM chapter_progress WHERE user_id = 1"
            ).fetchone()[0]

        self.assertIn("username", columns)
        self.assertEqual(
            legacy_user,
            ("legacy@example.com", "legacy-hash", "student"),
        )
        self.assertEqual(seeded_course, ("Схемотехника цифровых систем",))
        self.assertEqual(len(seeded_chapters), 8)
        self.assertEqual(seeded_chapters[0], (1, 1, "Введение в цифровую схемотехнику"))
        self.assertEqual(legacy_progress, (1, 1))
        self.assertEqual(
            migration_history,
            [(1,), (2,), (3,), (4,), (5,), (6,), (7,)],
        )
        self.assertEqual(legacy_history, (1, legacy_progress_updated_at))
        self.assertIn(
            ("chapters", "chapter_id", "id", "CASCADE"),
            [
                (row[2], row[3], row[4], row[6])
                for row in progress_foreign_keys
            ],
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
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
                1,
            )
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM chapters").fetchone()[0],
                8,
            )

    def test_duplicate_email_is_rejected_without_case_sensitivity(self):
        self.assertEqual(self._register().status_code, 201)

        response = self._register("STUDENT@example.com")

        self.assertEqual(response.status_code, 409)

    def test_login_and_progress_are_persisted_per_user(self):
        self.assertEqual(self._register().status_code, 201)
        first_response = self._post_json(
            "/api/progress/1",
            {"completed": True},
        )
        response = self._post_json("/api/progress/2", {"completed": True})
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong data-progress-count>2</strong>", self.client.get("/").data)

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
        self.assertIn(b'href="/course/1"', page)
        self.assertIn(b'href="/course/2"', page)
        self.assertEqual(self.client.get("/course/3").status_code, 200)

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

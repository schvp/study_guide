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

    def _set_demo_user_role(self, role):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                "UPDATE users SET role = ? WHERE username = 'test'",
                (role,),
            )
            database.commit()

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

    def test_demo_admin_is_seeded_with_admin_role_and_can_login(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            email, username, password_hash, role = database.execute(
                """
                SELECT email, username, password_hash, role
                FROM users WHERE username = ?
                """,
                ("admin",),
            ).fetchone()

        self.assertEqual(email, "admin@example.com")
        self.assertEqual(username, "admin")
        self.assertEqual(role, "admin")
        self.assertTrue(check_password_hash(password_hash, "admin"))
        self.assertIn(
            "администратор admin / admin".encode(),
            self.client.get("/").data,
        )

        login_response = self._post_json(
            "/api/auth/login",
            {"login": "admin", "password": "admin"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/content-management").status_code, 200)

    def test_demo_admin_seed_can_be_disabled(self):
        database_path = os.path.join(self.temp_dir.name, "no-demo-admin.sqlite3")
        app_without_demo_admin = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "no-demo-admin-secret",
                "DATABASE": database_path,
                "SEED_DEMO_ADMIN": False,
            }
        )

        with closing(sqlite3.connect(app_without_demo_admin.config["DATABASE"])) as database:
            admin = database.execute(
                "SELECT id FROM users WHERE username = 'admin'"
            ).fetchone()

        self.assertIsNone(admin)

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

    def test_second_chapter_is_seeded_from_versioned_course_material(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            title, description, content = database.execute(
                """
                SELECT title, description, content
                FROM chapters
                WHERE course_id = 1 AND position = 2
                """
            ).fetchone()

        self.assertEqual(title, "Системы счисления и кодирование информации")
        self.assertTrue(description)
        self.assertIn("## Позиционная запись числа", content)
        self.assertIn("110101₂", content)
        self.assertIn("45₁₀ = 101101₂", content)
        self.assertIn("173₁₀ = AD₁₆", content)
        self.assertIn("## Проверьте себя", content)
        self.assertIn("156₁₀ = 10011100₂", content)
        self.assertIn("## Восьмеричная и шестнадцатеричная системы", content)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        page = self.client.get("/course/2")
        self.assertEqual(page.status_code, 403)
        self.assertIn("Раздел пока закрыт".encode(), page.data)
        self.assertEqual(
            self._post_json("/api/progress/1", {"completed": True}).status_code,
            200,
        )
        page = self.client.get("/course/2")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Позиционная запись числа".encode(), page.data)
        self.assertIn("Читаем остатки снизу вверх".encode(), page.data)
        self.assertIn("110101₂".encode(), page.data)

    def test_third_chapter_is_seeded_and_accessible_in_course_sequence(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            title, description, content = database.execute(
                """
                SELECT title, description, content
                FROM chapters
                WHERE course_id = 1 AND position = 3
                """
            ).fetchone()

        self.assertEqual(title, "Основы булевой алгебры")
        self.assertTrue(description)
        self.assertIn("## Операция НЕ", content)
        self.assertIn("## Операция И", content)
        self.assertIn("## Основные законы булевой алгебры", content)
        self.assertIn("2³ = 8 строк", content)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/course/3").status_code, 403)
        for chapter_id in (1, 2):
            response = self._post_json(
                f"/api/progress/{chapter_id}",
                {"completed": True},
            )
            self.assertEqual(response.status_code, 200)
        page = self.client.get("/course/3")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Булева алгебра".encode(), page.data)
        self.assertIn("Операция ИЛИ".encode(), page.data)

    def test_fourth_chapter_introduces_logic_gates_after_prior_chapters(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            title, content = database.execute(
                """
                SELECT title, content FROM chapters
                WHERE course_id = 1 AND position = 4
                """
            ).fetchone()

        self.assertEqual(title, "Логические элементы")
        self.assertIn("## Элементы NAND и NOR", content)
        self.assertIn("¬(A ∧ A) = ¬A", content)
        self.assertIn("2⁴ = 16 строк", content)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/course/4").status_code, 403)
        for chapter_id in (1, 2, 3):
            response = self._post_json(
                f"/api/progress/{chapter_id}",
                {"completed": True},
            )
            self.assertEqual(response.status_code, 200)
        page = self.client.get("/course/4")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Элементы NAND и NOR".encode(), page.data)
        self.assertIn("Исключающее ИЛИ".encode(), page.data)

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
                """
                UPDATE chapters
                SET description = ?, content = ''
                WHERE id = 1
                """,
                ("Моё описание",),
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
            preserved_description, reseeded_content = database.execute(
                "SELECT description, content FROM chapters WHERE id = 1"
            ).fetchone()
        self.assertEqual(preserved_description, "Моё описание")
        self.assertIn("Цель раздела", reseeded_content)

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
            database.execute(
                """
                INSERT INTO library_materials (
                    course_id, title, material_type, resource_url, position
                )
                SELECT id, 'Старая ссылка', 'link', 'javascript:alert(1)', 2
                FROM courses
                WHERE slug = 'digital-circuits'
                """
            )
            database.commit()

        populated_page = self.client.get("/library")
        self.assertEqual(populated_page.status_code, 200)
        self.assertIn("Справочник по логике".encode(), populated_page.data)
        self.assertIn("Дополнительное описание".encode(), populated_page.data)
        self.assertIn("Книга".encode(), populated_page.data)
        self.assertIn("Текст из библиотеки".encode(), populated_page.data)
        self.assertIn(
            b'href="https://example.org/reference"',
            populated_page.data,
        )
        self.assertIn("javascript:alert(1)".encode(), populated_page.data)
        self.assertNotIn(b'href="javascript:alert(1)"', populated_page.data)

    def test_library_material_management_creates_edits_reorders_and_deletes(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.executemany(
                """
                INSERT INTO library_materials (
                    course_id, title, material_type, position
                )
                VALUES (1, ?, 'article', ?)
                """,
                [("Первая запись", 1), ("Вторая запись", 2)],
            )
            database.commit()

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        token = self.csrf_token

        created = self.client.post(
            "/content-management/courses/1/library-materials",
            data={
                "csrf_token": token,
                "title": "Справочник по логике",
                "description": "Полезное дополнение",
                "material_type": "book",
                "resource_url": "https://example.org/reference",
                "content": "  Содержимое со значимыми пробелами  ",
                "position": "2",
            },
        )
        self.assertEqual(created.status_code, 302)
        self.assertEqual(
            created.headers["Location"],
            "/content-management?course_id=1",
        )

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            created_record = database.execute(
                """
                SELECT id, title, description, material_type, resource_url,
                    content, position
                FROM library_materials
                WHERE title = 'Справочник по логике'
                """
            ).fetchone()
            created_id = created_record[0]
            created_order = database.execute(
                """
                SELECT title, position FROM library_materials
                WHERE course_id = 1 ORDER BY position, id
                """
            ).fetchall()
        self.assertEqual(
            created_record[1:],
            (
                "Справочник по логике",
                "Полезное дополнение",
                "book",
                "https://example.org/reference",
                "  Содержимое со значимыми пробелами  ",
                2,
            ),
        )
        self.assertEqual(
            created_order,
            [
                ("Первая запись", 1),
                ("Справочник по логике", 2),
                ("Вторая запись", 3),
            ],
        )

        edited = self.client.post(
            f"/content-management/library-materials/{created_id}",
            data={
                "csrf_token": token,
                "title": "Обновлённый справочник",
                "description": "Новое описание",
                "material_type": "link",
                "resource_url": "https://example.org/updated",
                "content": "Обновлённый материал",
                "position": "1",
            },
        )
        self.assertEqual(edited.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            updated_material = database.execute(
                """
                SELECT title, description, material_type, resource_url,
                    content, position
                FROM library_materials WHERE id = ?
                """,
                (created_id,),
            ).fetchone()
        self.assertEqual(
            updated_material,
            (
                "Обновлённый справочник",
                "Новое описание",
                "link",
                "https://example.org/updated",
                "Обновлённый материал",
                1,
            ),
        )

        library_page = self.client.get("/library")
        self.assertIn("Обновлённый справочник".encode(), library_page.data)
        self.assertIn(b'href="https://example.org/updated"', library_page.data)
        self.assertNotIn("Справочник по логике".encode(), library_page.data)

        deleted = self.client.post(
            "/content-management/library-materials/2/delete",
            data={"csrf_token": token},
        )
        self.assertEqual(deleted.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            remaining = database.execute(
                """
                SELECT title, position FROM library_materials
                WHERE course_id = 1 ORDER BY position, id
                """
            ).fetchall()
        self.assertEqual(
            remaining,
            [("Обновлённый справочник", 1), ("Первая запись", 2)],
        )

    def test_library_material_management_validates_input_roles_and_csrf(self):
        missing_login = self.client.post(
            "/content-management/courses/1/library-materials",
            data={"title": "Материал", "material_type": "article", "position": "1"},
        )
        self.assertEqual(missing_login.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        forbidden = self.client.post(
            "/content-management/courses/1/library-materials",
            data={
                "csrf_token": self.csrf_token,
                "title": "Материал",
                "material_type": "article",
                "position": "1",
            },
        )
        self.assertEqual(forbidden.status_code, 403)

        self._set_demo_user_role("admin")
        invalid_csrf = self.client.post(
            "/content-management/courses/1/library-materials",
            data={
                "title": "Материал",
                "material_type": "article",
                "position": "1",
            },
        )
        self.assertEqual(invalid_csrf.status_code, 400)

        for values, expected_message in [
            (
                {"title": " ", "material_type": "article", "position": "1"},
                "Укажите название материала.",
            ),
            (
                {"title": "Материал", "material_type": "unknown", "position": "1"},
                "Выберите тип материала.",
            ),
            (
                {
                    "title": "Материал",
                    "material_type": "article",
                    "resource_url": "javascript:alert(1)",
                    "position": "1",
                },
                "Укажите корректную ссылку",
            ),
            (
                {"title": "Материал", "material_type": "article", "position": "0"},
                "Позиция материала должна быть",
            ),
        ]:
            response = self.client.post(
                "/content-management/courses/1/library-materials",
                data={"csrf_token": self.csrf_token, **values},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected_message.encode(), response.data)

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM library_materials").fetchone()[0],
                0,
            )

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

    def test_profile_can_reset_current_course_progress_and_preserve_history(self):
        anonymous_post = self.client.post(
            "/profile/progress/reset",
            data={"csrf_token": self.csrf_token},
        )
        self.assertEqual(anonymous_post.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        self.assertEqual(
            self._post_json("/api/progress/1", {"completed": True}).status_code,
            200,
        )
        self.assertEqual(
            self._post_json("/api/progress/2", {"completed": True}).status_code,
            200,
        )
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            user_id = database.execute(
                "SELECT id FROM users WHERE username = 'test'"
            ).fetchone()[0]
            database.execute(
                """
                INSERT INTO courses (id, slug, title, status)
                VALUES (2, 'other-course', 'Другой курс', 'published')
                """
            )
            database.execute(
                """
                INSERT INTO chapters (id, course_id, position, title, status)
                VALUES (101, 2, 1, 'Глава другого курса', 'published')
                """
            )
            database.execute(
                """
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (?, 101, 1)
                """,
                (user_id,),
            )
            database.execute(
                """
                INSERT INTO chapter_completion_history (user_id, chapter_id)
                VALUES (?, 101)
                """,
                (user_id,),
            )
            database.commit()

        profile = self.client.get("/profile")
        self.assertIn("Сбросить прогресс курса".encode(), profile.data)
        self.assertIn(b'action="/profile/progress/reset"', profile.data)
        self.assertIn(b'name="csrf_token"', profile.data)

        missing_csrf = self.client.post("/profile/progress/reset")
        self.assertEqual(missing_csrf.status_code, 400)

        reset = self.client.post(
            "/profile/progress/reset",
            data={"csrf_token": self.csrf_token},
        )
        self.assertEqual(reset.status_code, 302)
        self.assertEqual(reset.headers["Location"], "/profile")
        profile_after_reset = self.client.get("/profile", follow_redirects=True)
        self.assertIn(
            "История завершённых глав сохранена".encode(),
            profile_after_reset.data,
        )
        self.assertIn("Пройденные разделы".encode(), profile_after_reset.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            current_course_progress = database.execute(
                """
                SELECT COUNT(*)
                FROM chapter_progress
                WHERE user_id = ? AND chapter_id IN (
                    SELECT chapters.id FROM chapters
                    JOIN courses ON courses.id = chapters.course_id
                    WHERE courses.slug = 'digital-circuits'
                )
                """,
                (user_id,),
            ).fetchone()[0]
            other_course_progress = database.execute(
                """
                SELECT completed FROM chapter_progress
                WHERE user_id = ? AND chapter_id = 101
                """,
                (user_id,),
            ).fetchone()[0]
            retained_history = database.execute(
                """
                SELECT chapter_id FROM chapter_completion_history
                WHERE user_id = ? ORDER BY chapter_id
                """,
                (user_id,),
            ).fetchall()
        self.assertEqual(current_course_progress, 0)
        self.assertEqual(other_course_progress, 1)
        self.assertEqual(retained_history, [(1,), (2,), (101,)])
        self.assertEqual(self.client.get("/course/1").status_code, 200)
        self.assertEqual(self.client.get("/course/2").status_code, 403)

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

    def test_admin_can_manage_user_roles(self):
        anonymous = self.client.get("/admin/users")
        self.assertEqual(anonymous.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        profile = self.client.get("/profile")
        self.assertIn(b'href="/admin/users"', profile.data)
        page = self.client.get("/admin/users")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Пользователи и роли".encode(), page.data)
        self.assertIn(b"test@example.com", page.data)
        self.assertIn(b"admin@example.com", page.data)
        self.assertIn(b'value="student" selected', page.data)
        target_user_id = self._user_id_for_username("test")
        admin_user_id = self._user_id_for_username("admin")
        self.assertIn(
            f'action="/admin/users/{target_user_id}/role"'.encode(),
            page.data,
        )
        self.assertNotIn(
            f'action="/admin/users/{admin_user_id}/role"'.encode(),
            page.data,
        )

        changed = self.client.post(
            f"/admin/users/{target_user_id}/role",
            data={"csrf_token": self.csrf_token, "role": "teacher"},
        )
        self.assertEqual(changed.status_code, 302)
        self.assertEqual(changed.headers["Location"], "/admin/users")
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT role FROM users WHERE id = ?",
                    (target_user_id,),
                ).fetchone()[0],
                "teacher",
            )

    def test_admin_user_role_updates_validate_csrf_and_protect_admin_access(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        target_user_id = self._user_id_for_username("test")
        admin_user_id = self._user_id_for_username("admin")

        invalid_csrf = self.client.post(
            f"/admin/users/{target_user_id}/role",
            data={"role": "teacher"},
        )
        self.assertEqual(invalid_csrf.status_code, 400)

        invalid_role = self.client.post(
            f"/admin/users/{target_user_id}/role",
            data={"csrf_token": self.csrf_token, "role": "owner"},
            follow_redirects=True,
        )
        self.assertEqual(invalid_role.status_code, 200)
        self.assertIn("Выберите допустимую роль".encode(), invalid_role.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT role FROM users WHERE id = ?",
                    (target_user_id,),
                ).fetchone()[0],
                "student",
            )

        self_change = self.client.post(
            f"/admin/users/{admin_user_id}/role",
            data={"csrf_token": self.csrf_token, "role": "teacher"},
            follow_redirects=True,
        )
        self.assertEqual(self_change.status_code, 200)
        self.assertIn("Нельзя изменить собственную роль".encode(), self_change.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT role FROM users WHERE username = 'admin'"
                ).fetchone()[0],
                "admin",
            )

        missing_user = self.client.post(
            "/admin/users/9999/role",
            data={"csrf_token": self.csrf_token, "role": "teacher"},
        )
        self.assertEqual(missing_user.status_code, 404)

    def test_student_cannot_access_user_role_management(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        self.assertEqual(self.client.get("/admin/users").status_code, 403)
        admin_user_id = self._user_id_for_username("admin")
        self.assertEqual(
            self.client.post(
                f"/admin/users/{admin_user_id}/role",
                data={"csrf_token": self.csrf_token, "role": "teacher"},
            ).status_code,
            403,
        )

    def _user_id_for_username(self, username):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            return database.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()[0]

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
            self.assertIn("Создать курс".encode(), response.data)
            self.assertIn("Редактирование курсов".encode(), response.data)
            self.assertIn("Схемотехника цифровых систем".encode(), response.data)
            self.assertIn(b'name="title"', response.data)
            self.assertIn(b'name="slug"', response.data)
            self.assertIn(b'action="/content-management/courses"', response.data)
            self.assertIn(b'name="csrf_token"', response.data)
            self.assertIn("Главы курса".encode(), response.data)
            self.assertIn("Добавить главу".encode(), response.data)
            self.assertIn("Введение в цифровую схемотехнику".encode(), response.data)
            self.assertIn(b'name="position"', response.data)
            self.assertIn(b'name="content"', response.data)
            self.assertIn(
                b'action="/content-management/courses/1/chapters"',
                response.data,
            )
            self.assertIn(
                b'action="/content-management/chapters/1"',
                response.data,
            )
            self.assertIn("Материалы библиотеки".encode(), response.data)
            self.assertIn("Добавить материал".encode(), response.data)
            self.assertIn(
                b'action="/content-management/courses/1/library-materials"',
                response.data,
            )
            self.assertIn(b'name="material_type"', response.data)
            self.assertIn(b'maxlength="100000"', response.data)

    def test_chapter_management_interface_groups_chapters_by_course(self):
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                INSERT INTO courses (id, slug, title, description)
                VALUES (2, 'logic-basics', 'Основы логики', 'Отдельный курс')
                """
            )
            database.execute(
                """
                INSERT INTO chapters (
                    id, course_id, position, title, description, content
                )
                VALUES (101, 2, 1, 'Логическое высказывание', 'Описание', 'Материал')
                """
            )
            database.commit()

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        management_page = self.client.get("/content-management")

        self.assertEqual(management_page.status_code, 200)
        self.assertIn("Основы логики".encode(), management_page.data)
        self.assertIn("Логическое высказывание".encode(), management_page.data)
        self.assertIn("Системы счисления и кодирование информации".encode(), management_page.data)
        self.assertIn("Описание".encode(), management_page.data)
        self.assertIn("Материал".encode(), management_page.data)

    def test_chapter_management_creates_chapter_at_position_and_shifts_following(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        response = self.client.post(
            "/content-management/courses/1/chapters",
            data={
                "csrf_token": self.csrf_token,
                "title": "Новая глава",
                "position": "2",
                "description": "Краткое описание",
                "content": "Учебный материал",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "/content-management?course_id=1",
        )
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            chapters = database.execute(
                """
                SELECT position, title, description, content
                FROM chapters
                WHERE course_id = 1
                ORDER BY position
                LIMIT 3
                """
            ).fetchall()
        self.assertEqual(
            [chapter[:2] for chapter in chapters],
            [
                (1, "Введение в цифровую схемотехнику"),
                (2, "Новая глава"),
                (3, "Системы счисления и кодирование информации"),
            ],
        )
        self.assertTrue(chapters[0][2])
        self.assertTrue(chapters[0][3])
        self.assertEqual(
            chapters[1][2:],
            ("Краткое описание", "Учебный материал"),
        )
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT status FROM chapters WHERE title = ?",
                    ("Новая глава",),
                ).fetchone()[0],
                "draft",
            )

    def test_chapter_management_edits_content_and_reorders_without_changing_id(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            database.execute(
                """
                INSERT INTO chapter_progress (user_id, chapter_id, completed)
                VALUES (
                    (SELECT id FROM users WHERE username = 'admin'), 2, 1
                )
                """
            )
            database.execute(
                """
                INSERT INTO chapter_completion_history (user_id, chapter_id)
                VALUES ((SELECT id FROM users WHERE username = 'admin'), 2)
                """
            )
            database.commit()

        response = self.client.post(
            "/content-management/chapters/2",
            data={
                "csrf_token": self.csrf_token,
                "title": "Системы счисления",
                "position": "1",
                "description": "Обновлённое описание",
                "content": "Обновлённый материал",
            },
        )
        self.assertEqual(response.status_code, 302)

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            order = database.execute(
                "SELECT id, position, title FROM chapters WHERE course_id = 1 ORDER BY position"
            ).fetchall()
            chapter_details = database.execute(
                "SELECT description, content FROM chapters WHERE id = 2"
            ).fetchone()
            saved_progress = database.execute(
                """
                SELECT completed FROM chapter_progress
                WHERE user_id = (SELECT id FROM users WHERE username = 'admin')
                    AND chapter_id = 2
                """
            ).fetchone()
            saved_history = database.execute(
                """
                SELECT COUNT(*) FROM chapter_completion_history
                WHERE user_id = (SELECT id FROM users WHERE username = 'admin')
                    AND chapter_id = 2
                """
            ).fetchone()[0]
            saved_status = database.execute(
                "SELECT status FROM chapters WHERE id = 2"
            ).fetchone()[0]

        self.assertEqual(order[0], (2, 1, "Системы счисления"))
        self.assertEqual(order[1], (1, 2, "Введение в цифровую схемотехнику"))
        self.assertEqual(
            chapter_details,
            ("Обновлённое описание", "Обновлённый материал"),
        )
        self.assertEqual(saved_status, "published")
        self.assertEqual(saved_progress, (1,))
        self.assertEqual(saved_history, 1)

    def test_chapter_management_rejects_invalid_duplicate_and_missing_data(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()

        for payload, expected_message in [
            (
                {"title": "   ", "position": "1"},
                "Укажите название главы.",
            ),
            (
                {"title": "Неверная позиция", "position": "0"},
                "Позиция главы должна быть",
            ),
            (
                {
                    "title": "введение в цифровую схемотехнику",
                    "position": "1",
                },
                "уже есть глава с таким названием",
            ),
            (
                {"title": "Не число", "position": "first"},
                "Укажите целое число для позиции главы.",
            ),
            (
                {
                    "title": "Слишком большой материал",
                    "position": "1",
                    "content": "x" * 100001,
                },
                "не длиннее 100000 символов",
            ),
        ]:
            response = self.client.post(
                "/content-management/courses/1/chapters",
                data={"csrf_token": self.csrf_token, **payload},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected_message.encode(), response.data)

        duplicate_edit = self.client.post(
            "/content-management/chapters/2",
            data={
                "csrf_token": self.csrf_token,
                "title": "Введение в цифровую схемотехнику",
                "position": "2",
                "description": "",
                "content": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(duplicate_edit.status_code, 200)
        self.assertIn("уже есть глава с таким названием".encode(), duplicate_edit.data)

        missing_chapter = self.client.post(
            "/content-management/chapters/9999",
            data={
                "csrf_token": self.csrf_token,
                "title": "Не существует",
                "position": "1",
            },
        )
        self.assertEqual(missing_chapter.status_code, 404)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT COUNT(*) FROM chapters WHERE course_id = 1"
                ).fetchone()[0],
                8,
            )

    def test_chapter_management_posts_require_role_and_csrf(self):
        guest_response = self.client.post(
            "/content-management/courses/1/chapters",
            data={
                "csrf_token": self.csrf_token,
                "title": "Глава гостя",
                "position": "1",
            },
        )
        self.assertEqual(guest_response.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        student_response = self.client.post(
            "/content-management/courses/1/chapters",
            data={
                "csrf_token": self.csrf_token,
                "title": "Глава учащегося",
                "position": "1",
            },
        )
        self.assertEqual(student_response.status_code, 403)

        self._set_demo_user_role("admin")
        missing_csrf = self.client.post(
            "/content-management/courses/1/chapters",
            data={"title": "Нет CSRF", "position": "1"},
        )
        self.assertEqual(missing_csrf.status_code, 400)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute(
                    "SELECT COUNT(*) FROM chapters WHERE course_id = 1"
                ).fetchone()[0],
                8,
            )

    def test_course_management_creates_and_updates_courses(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self._set_demo_user_role("teacher")
        self.csrf_token = self._load_csrf_token()
        form_token = self.csrf_token

        created = self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": form_token,
                "title": "Основы электроники",
                "slug": "osnovy-elektroniki",
                "description": "Вводный курс",
            },
        )
        self.assertEqual(created.status_code, 302)
        self.assertEqual(created.headers["Location"], "/content-management")

        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            course_id, title, description, status = database.execute(
                "SELECT id, title, description, status FROM courses WHERE slug = ?",
                ("osnovy-elektroniki",),
            ).fetchone()
        self.assertEqual((title, description), ("Основы электроники", "Вводный курс"))
        self.assertEqual(status, "draft")

        updated = self.client.post(
            f"/content-management/courses/{course_id}",
            data={
                "csrf_token": form_token,
                "title": "Основы электроники и схем",
                "slug": "osnovy-elektroniki-i-shem",
                "description": "Обновлённое описание",
            },
        )
        self.assertEqual(updated.status_code, 302)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            saved = database.execute(
                "SELECT title, slug, description, status FROM courses WHERE id = ?",
                (course_id,),
            ).fetchone()
        self.assertEqual(
            saved,
            (
                "Основы электроники и схем",
                "osnovy-elektroniki-i-shem",
                "Обновлённое описание",
                "draft",
            ),
        )

    def test_drafts_stay_private_until_course_and_chapter_are_published(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "admin", "password": "admin"},
            ).status_code,
            200,
        )
        self.csrf_token = self._load_csrf_token()
        form_token = self.csrf_token

        self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": form_token,
                "title": "Черновой курс",
                "slug": "draft-course",
                "description": "Пока не опубликован",
            },
        )
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            course_id = database.execute(
                "SELECT id FROM courses WHERE slug = 'draft-course'"
            ).fetchone()[0]

        self.client.post(
            f"/content-management/courses/{course_id}/chapters",
            data={
                "csrf_token": form_token,
                "title": "Черновая глава",
                "position": "1",
                "content": "Скрытый материал",
            },
        )
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            chapter_id = database.execute(
                "SELECT id FROM chapters WHERE course_id = ?",
                (course_id,),
            ).fetchone()[0]

        catalog = self.client.get("/courses")
        self.assertNotIn("Черновой курс".encode(), catalog.data)
        self.assertEqual(self.client.get("/courses/draft-course").status_code, 404)
        self.assertEqual(self.client.get(f"/course/{chapter_id}").status_code, 404)
        self.assertEqual(
            self._post_json(
                f"/api/progress/{chapter_id}",
                {"completed": True},
            ).status_code,
            404,
        )
        management = self.client.get("/content-management")
        self.assertIn("Черновой курс".encode(), management.data)
        self.assertIn("Черновая глава".encode(), management.data)

        self.client.post(
            f"/content-management/courses/{course_id}",
            data={
                "csrf_token": form_token,
                "title": "Черновой курс",
                "slug": "draft-course",
                "description": "Опубликованный курс",
                "status": "published",
            },
        )
        overview = self.client.get("/courses/draft-course")
        self.assertEqual(overview.status_code, 200)
        self.assertNotIn("Черновая глава".encode(), overview.data)
        self.assertEqual(self.client.get(f"/course/{chapter_id}").status_code, 404)
        self.assertEqual(
            self._post_json(
                f"/api/progress/{chapter_id}",
                {"completed": True},
            ).status_code,
            404,
        )

        self.client.post(
            f"/content-management/chapters/{chapter_id}",
            data={
                "csrf_token": form_token,
                "title": "Черновая глава",
                "position": "1",
                "content": "Опубликованный материал",
                "status": "published",
            },
        )
        overview = self.client.get("/courses/draft-course")
        self.assertIn("Черновая глава".encode(), overview.data)
        self.assertEqual(self.client.get(f"/course/{chapter_id}").status_code, 200)

    def test_course_management_rejects_invalid_and_duplicate_data(self):
        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        self._set_demo_user_role("admin")
        self.csrf_token = self._load_csrf_token()
        form_token = self.csrf_token

        invalid = self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": form_token,
                "title": "Некорректный курс",
                "slug": "Invalid Slug",
                "description": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("Адрес курса должен содержать".encode(), invalid.data)

        duplicate = self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": form_token,
                "title": "Дубликат",
                "slug": "digital-circuits",
                "description": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn("такой адрес уже используется".encode(), duplicate.data)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
                1,
            )

    def test_course_management_posts_require_role_and_csrf(self):
        guest_post = self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": self.csrf_token,
                "title": "Гостевой",
                "slug": "guest-course",
            },
        )
        self.assertEqual(guest_post.status_code, 401)

        self.assertEqual(
            self._post_json(
                "/api/auth/login",
                {"login": "test", "password": "test"},
            ).status_code,
            200,
        )
        student_post = self.client.post(
            "/content-management/courses",
            data={
                "csrf_token": self.csrf_token,
                "title": "Курс учащегося",
                "slug": "student-course",
            },
        )
        self.assertEqual(student_post.status_code, 403)
        self._set_demo_user_role("teacher")

        invalid_csrf = self.client.post(
            "/content-management/courses",
            data={
                "title": "Запрос без CSRF",
                "slug": "no-csrf-course",
            },
        )
        self.assertEqual(invalid_csrf.status_code, 400)
        with closing(sqlite3.connect(self.app.config["DATABASE"])) as database:
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
                1,
            )

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
            [(1,), (2,), (3,), (4,), (5,), (6,), (7,), (8,)],
        )
        with closing(sqlite3.connect(database_path)) as database:
            self.assertEqual(
                database.execute(
                    "SELECT status FROM courses WHERE slug = ?",
                    ("digital-circuits",),
                ).fetchone()[0],
                "published",
            )
            self.assertEqual(
                database.execute(
                    "SELECT DISTINCT status FROM chapters"
                ).fetchall(),
                [("published",)],
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

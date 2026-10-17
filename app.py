import os
import re
import secrets
import sqlite3
from functools import wraps
from urllib.parse import urlsplit

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from migrations import migrate_database


COURSE_SLUG = "digital-circuits"
COURSE_TITLE = "Схемотехника цифровых систем"
COURSE_DESCRIPTION = (
    "Пособие знакомит с принципами построения цифровых устройств "
    "и помогает увидеть связь между математической логикой и аппаратной реализацией."
)
INITIAL_CHAPTERS = [
    "Введение в цифровую схемотехнику",
    "Системы счисления и кодирование информации",
    "Основы булевой алгебры",
    "Логические элементы",
    "Комбинационные цифровые устройства",
    "Триггеры",
    "Регистры и счётчики",
    "Запоминающие устройства",
]
FIRST_CHAPTER_DESCRIPTION = (
    "Познакомьтесь с цифровыми сигналами, логическими состояниями "
    "и принципами, на которых строятся цифровые устройства."
)
FIRST_CHAPTER_CONTENT = """## Цель раздела

В этом разделе вы познакомитесь с языком цифровой схемотехники: узнаете, чем цифровые сигналы отличаются от аналоговых, что обозначают логические 0 и 1 и как из простых логических операций строятся электронные устройства.

После изучения вы сможете объяснить понятия «сигнал», «бит» и «логическое состояние», привести примеры цифровых устройств и различать комбинационные и последовательностные схемы.

## Что изучает цифровая схемотехника

Цифровая схемотехника рассматривает электронные устройства, которые обрабатывают информацию, представленную конечным набором условных состояний. В двоичных системах таких состояний два: 0 и 1. Их можно хранить, передавать, сравнивать и преобразовывать с помощью электрических схем.

В основе цифрового устройства лежат физические компоненты — транзисторы, соединённые так, чтобы выполнять заданные логические функции. Сами по себе транзисторы не «понимают» числа или команды: нужное поведение возникает благодаря способу их соединения и правилам представления данных.

## Аналоговые и цифровые сигналы

Аналоговый сигнал может принимать непрерывный диапазон значений. Например, напряжение на выходе датчика температуры постепенно меняется вслед за изменением температуры.

Цифровой сигнал используют для различения ограниченного числа состояний. В простейшем случае схеме важно определить, относится ли напряжение к низкому или высокому уровню. Эти уровни условно интерпретируются как логический 0 и логическая 1.

Логический уровень — это не одно универсальное значение напряжения. Допустимые диапазоны зависят от семейства микросхем, напряжения питания и электрических характеристик входа. При проектировании цифровых схем нужно сверяться с документацией на компоненты, а не считать, что любому устройству подходят одинаковые уровни.

Цифровой сигнал тоже является физическим сигналом и подвержен шумам, задержкам и искажениям. Разделение диапазона напряжений на области 0 и 1 помогает схеме устойчиво распознавать данные, но не устраняет эти эффекты полностью.

## Бит и двоичное представление

Бит — минимальная единица информации, которая может принимать одно из двух значений: 0 или 1. Несколько битов позволяют представить больше вариантов. Например, два бита образуют четыре комбинации: 00, 01, 10 и 11; три бита — уже восемь комбинаций.

Чтобы представить буквы, целые числа, изображения или команды, системе нужны правила кодирования — соответствие между наборами битов и значениями, которые они обозначают. Одни и те же биты могут означать разные вещи в разных кодировках и контекстах.

## Логические операции и схемы

Логический элемент получает одно или несколько входных состояний и формирует выходное состояние по определённому правилу. Например, элемент И выдаёт 1, только когда все его входы равны 1; элемент ИЛИ выдаёт 1, когда хотя бы один вход равен 1; элемент НЕ меняет 0 на 1, а 1 на 0.

Соединяя логические элементы, можно строить схемы для вычислений и управления. Схема, выход которой определяется текущими входными сигналами, называется комбинационной. Примеры таких устройств — сумматоры и дешифраторы.

Последовательностная схема учитывает не только текущие входы, но и своё состояние, сохранённое ранее. Такие схемы могут помнить данные и реагировать на последовательность событий. К ним относятся триггеры, регистры и счётчики — эти устройства рассматриваются в следующих главах.

## Где встречаются цифровые системы

Цифровые схемы работают внутри компьютеров, телефонов, бытовой техники, измерительных приборов, сетевого оборудования и систем управления. В одном устройстве могут сочетаться цифровые узлы, аналоговые схемы и программное обеспечение.

Например, датчик может выдать аналоговый сигнал, преобразователь — представить его в виде числа, а цифровая схема или процессор — обработать результат и принять решение. Это показывает, как цифровая схемотехника связана с другими областями электроники и вычислительной техники.

## Ключевые понятия

Сигнал — физическое изменение, с помощью которого передают или представляют информацию.

Логический уровень — диапазон электрических значений, распознаваемый цифровой схемой как 0 или 1.

Бит — единица информации с двумя возможными значениями.

Логический элемент — электронный узел, выполняющий логическую операцию над входными сигналами.

Комбинационная схема зависит от текущих входов; последовательностная схема также зависит от сохранённого состояния.

## Проверьте себя

1. Чем аналоговый сигнал отличается от цифрового?

2. Почему логические 0 и 1 нельзя всегда отождествлять с одними и теми же точными напряжениями?

3. Сколько различных комбинаций можно представить двумя битами?

4. Чем комбинационная схема отличается от последовательностной?

Ответы: аналоговый сигнал изменяется непрерывно, а цифровой распознаётся как одно из ограниченного числа состояний; допустимые напряжения определяются характеристиками конкретной схемы; два бита дают четыре комбинации; последовательностная схема дополнительно хранит состояние."""

APP_SECTIONS = {
    "library": {
        "title": "Библиотека",
        "description": "Дополнительные материалы и справочные ресурсы по цифровой схемотехнике.",
        "status": "Подборка материалов появится здесь.",
    },
    "laboratory": {
        "title": "Лаборатория",
        "description": "Практические задания для закрепления тем курса.",
        "status": "Интерактивные лабораторные работы готовятся.",
    },
    "testing": {
        "title": "Тестирование",
        "description": "Проверяйте знания по мере прохождения курса.",
        "status": "Тесты по разделам курса появятся здесь.",
    },
}
USER_ROLE_LABELS = {
    "student": "Учащийся",
    "teacher": "Преподаватель",
    "admin": "Администратор",
}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
COURSE_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LIBRARY_MATERIAL_TYPES = {
    "article": "Статья",
    "book": "Книга",
    "video": "Видео",
    "link": "Ссылка",
    "file": "Файл",
}


def is_http_resource_url(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed_url = urlsplit(value)
        hostname = parsed_url.hostname
    except ValueError:
        return False
    return (
        parsed_url.scheme in {"http", "https"}
        and bool(hostname)
        and parsed_url.username is None
        and parsed_url.password is None
    )
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
DEMO_USERNAME = "test"
DEMO_EMAIL = "test@example.com"
DEMO_PASSWORD = "test"
DEMO_ADMIN_USERNAME = "admin"
DEMO_ADMIN_EMAIL = "admin@example.com"
DEMO_ADMIN_PASSWORD = "admin"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "study_guide.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower()
        in {"1", "true"},
        SEED_DEMO_USER=os.environ.get("SEED_DEMO_USER", "1").lower()
        not in {"0", "false", "no"},
        SEED_DEMO_ADMIN=os.environ.get("SEED_DEMO_ADMIN", "1").lower()
        not in {"0", "false", "no"},
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    def close_db(_error=None):
        database = g.pop("db", None)
        if database is not None:
            database.close()

    def init_db():
        database = get_db()
        migrate_database(database, through_version=3)
        if app.config["SEED_DEMO_USER"]:
            database.execute(
                """
                INSERT OR IGNORE INTO users (email, username, password_hash)
                VALUES (?, ?, ?)
                """,
                (
                    DEMO_EMAIL,
                    DEMO_USERNAME,
                    generate_password_hash(DEMO_PASSWORD),
                ),
            )
        course = database.execute(
            "SELECT id FROM courses WHERE slug = ?",
            (COURSE_SLUG,),
        ).fetchone()
        if course is None:
            cursor = database.execute(
                "INSERT INTO courses (slug, title, description) VALUES (?, ?, ?)",
                (COURSE_SLUG, COURSE_TITLE, COURSE_DESCRIPTION),
            )
            course_id = cursor.lastrowid
        else:
            course_id = course["id"]

        chapter_count = database.execute(
            "SELECT COUNT(*) FROM chapters WHERE course_id = ?",
            (course_id,),
        ).fetchone()[0]
        if chapter_count == 0:
            database.executemany(
                """
                INSERT INTO chapters (
                    id, course_id, position, title, description, content
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chapter_id,
                        course_id,
                        chapter_id,
                        title,
                        FIRST_CHAPTER_DESCRIPTION if chapter_id == 1 else "",
                        FIRST_CHAPTER_CONTENT if chapter_id == 1 else "",
                    )
                    for chapter_id, title in enumerate(INITIAL_CHAPTERS, 1)
                ],
            )
        else:
            database.execute(
                """
                UPDATE chapters
                SET description = ?, content = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE course_id = ?
                    AND position = 1
                    AND content = ''
                """,
                (FIRST_CHAPTER_DESCRIPTION, FIRST_CHAPTER_CONTENT, course_id),
            )
        database.commit()
        migrate_database(database)
        if app.config["SEED_DEMO_ADMIN"]:
            database.execute(
                """
                INSERT OR IGNORE INTO users (email, username, password_hash, role)
                VALUES (?, ?, ?, 'admin')
                """,
                (
                    DEMO_ADMIN_EMAIL,
                    DEMO_ADMIN_USERNAME,
                    generate_password_hash(DEMO_ADMIN_PASSWORD),
                ),
            )
            database.commit()

    def get_course():
        return get_db().execute(
            """
            SELECT id, slug, title, description
            FROM courses
            WHERE slug = ? AND status = 'published'
            """,
            (COURSE_SLUG,),
        ).fetchone()

    def get_course_by_slug(slug):
        return get_db().execute(
            """
            SELECT id, slug, title, description
            FROM courses
            WHERE slug = ? AND status = 'published'
            """,
            (slug,),
        ).fetchone()

    def get_course_chapters(course_id):
        return get_db().execute(
            """
            SELECT id, course_id, position, title, description, content
            FROM chapters
            WHERE course_id = ? AND status = 'published'
            ORDER BY position, id
            """,
            (course_id,),
        ).fetchall()

    def get_managed_course_chapters(course_id):
        return get_db().execute(
            """
            SELECT id, course_id, position, title, description, content, status
            FROM chapters
            WHERE course_id = ?
            ORDER BY position, id
            """,
            (course_id,),
        ).fetchall()

    def current_user():
        user_id = session.get("user_id")
        if user_id is None:
            return None
        return get_db().execute(
            "SELECT id, email, username, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    def roles_required(*allowed_roles):
        def decorate(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                user = current_user()
                if user is None:
                    return render_template(
                        "403.html",
                        current_user=None,
                        message="Войдите в аккаунт, чтобы открыть этот раздел.",
                    ), 401
                if user["role"] not in allowed_roles:
                    return render_template(
                        "403.html",
                        current_user=user,
                        message="Для этого раздела нужны права преподавателя или администратора.",
                    ), 403
                return view(*args, **kwargs)

            return wrapped

        return decorate

    def csrf_is_valid():
        token = request.headers.get("X-CSRF-Token", "") or request.form.get(
            "csrf_token", ""
        )
        session_token = session.get("csrf_token", "")
        return bool(token and session_token and secrets.compare_digest(token, session_token))

    def csrf_protected(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not csrf_is_valid():
                return jsonify(error="Сессия устарела. Обновите страницу и попробуйте снова."), 400
            return view(*args, **kwargs)

        return wrapped

    def json_payload():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None
        return payload

    @app.teardown_appcontext
    def teardown_db(_error=None):
        close_db(_error)

    with app.app_context():
        init_db()

    @app.before_request
    def ensure_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.get("/")
    def home():
        user = current_user()
        course = get_course()
        if course is None:
            return redirect(url_for("course_catalog"))
        chapters = get_course_chapters(course["id"])
        completed_chapters = set()
        accessible_chapters = set()
        if user is not None:
            rows = get_db().execute(
                """
                SELECT progress.chapter_id
                FROM chapter_progress AS progress
                JOIN chapters ON chapters.id = progress.chapter_id
                WHERE progress.user_id = ?
                    AND progress.completed = 1
                    AND chapters.status = 'published'
                """,
                (user["id"],),
            ).fetchall()
            completed_chapters = {row["chapter_id"] for row in rows}
            for chapter in chapters:
                if all(
                    previous["id"] in completed_chapters
                    for previous in chapters
                    if previous["position"] < chapter["position"]
                ):
                    accessible_chapters.add(chapter["id"])

        return render_template(
            "index.html",
            course=course,
            chapters=chapters,
            current_user=user,
            completed_chapters=completed_chapters,
            accessible_chapters=accessible_chapters,
            csrf_token=session["csrf_token"],
            demo_user_enabled=app.config["SEED_DEMO_USER"],
            demo_admin_enabled=app.config["SEED_DEMO_ADMIN"],
        )

    @app.get("/courses")
    def course_catalog():
        courses = get_db().execute(
            """
            SELECT courses.id, courses.slug, courses.title, courses.description,
                COUNT(chapters.id) AS chapter_count
            FROM courses
            LEFT JOIN chapters
                ON chapters.course_id = courses.id
                AND chapters.status = 'published'
            WHERE courses.status = 'published'
            GROUP BY courses.id
            ORDER BY courses.title COLLATE NOCASE, courses.id
            """
        ).fetchall()
        return render_template(
            "courses.html",
            courses=courses,
            current_user=current_user(),
            active_nav="learning",
            csrf_token=session["csrf_token"],
        )

    @app.get("/courses/<slug>")
    def course_overview(slug):
        course = get_course_by_slug(slug)
        if course is None:
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        chapters = get_course_chapters(course["id"])
        user = current_user()
        completed_chapters = set()
        if user is not None:
            completed_chapters = {
                row["chapter_id"]
                for row in get_db().execute(
                    """
                    SELECT progress.chapter_id
                    FROM chapter_progress AS progress
                    JOIN chapters ON chapters.id = progress.chapter_id
                    WHERE progress.user_id = ?
                        AND progress.completed = 1
                        AND chapters.course_id = ?
                        AND chapters.status = 'published'
                    """,
                    (user["id"], course["id"]),
                ).fetchall()
            }
        accessible_chapters = set()
        for chapter in chapters:
            if all(
                previous["id"] in completed_chapters
                for previous in chapters
                if previous["position"] < chapter["position"]
            ):
                accessible_chapters.add(chapter["id"])

        return render_template(
            "course_overview.html",
            course=course,
            chapters=chapters,
            current_user=user,
            completed_chapters=completed_chapters,
            accessible_chapters=accessible_chapters,
            active_nav="learning",
            csrf_token=session["csrf_token"],
        )

    def render_app_section(active_nav):
        user = current_user()
        course = get_course()
        if active_nav == "profile":
            completion_history = (
                get_db()
                .execute(
                    """
                    SELECT chapters.id AS chapter_id, chapters.title,
                        strftime(
                            '%d.%m.%Y %H:%M',
                            history.completed_at,
                            'localtime'
                        ) AS completed_at
                    FROM chapter_completion_history AS history
                    JOIN chapters ON chapters.id = history.chapter_id
                    WHERE history.user_id = ?
                        AND chapters.course_id = ?
                        AND chapters.status = 'published'
                    ORDER BY history.completed_at DESC, chapters.position DESC
                    """,
                    (user["id"], course["id"]),
                )
                .fetchall()
                if user and course
                else []
            )
            return render_template(
                "section.html",
                active_nav=active_nav,
                section={
                    "title": "Профиль",
                    "description": "Учётная запись и прогресс обучения.",
                    "status": None,
                },
                current_user=user,
                user_role_label=USER_ROLE_LABELS[user["role"]] if user else None,
                can_manage_content=(
                    user is not None and user["role"] in {"teacher", "admin"}
                ),
                chapters_count=(
                    get_db().execute(
                        """
                        SELECT COUNT(*) FROM chapters
                        WHERE course_id = ? AND status = 'published'
                        """,
                        (course["id"],),
                    ).fetchone()[0]
                    if course
                    else 0
                ),
                completed_count=(
                    get_db()
                    .execute(
                        """
                        SELECT COUNT(*)
                        FROM chapter_progress AS progress
                        JOIN chapters ON chapters.id = progress.chapter_id
                        WHERE progress.user_id = ?
                            AND progress.completed = 1
                            AND chapters.course_id = ?
                            AND chapters.status = 'published'
                        """,
                        (user["id"], course["id"]),
                    )
                    .fetchone()[0]
                    if user and course
                    else 0
                ),
                completion_history=completion_history,
                csrf_token=session["csrf_token"],
            )
        if active_nav == "library":
            library_materials = get_db().execute(
                """
                SELECT id, title, description, material_type, resource_url, content
                FROM library_materials
                WHERE course_id = ?
                ORDER BY position, id
                """,
                (course["id"],),
            ).fetchall() if course else []
            library_materials = [
                {
                    **dict(material),
                    "safe_resource_url": (
                        material["resource_url"]
                        if is_http_resource_url(material["resource_url"])
                        else None
                    ),
                }
                for material in library_materials
            ]
            return render_template(
                "section.html",
                active_nav=active_nav,
                section=APP_SECTIONS[active_nav],
                current_user=user,
                library_materials=library_materials,
                library_material_types=LIBRARY_MATERIAL_TYPES,
                csrf_token=session["csrf_token"],
            )
        return render_template(
            "section.html",
            active_nav=active_nav,
            section=APP_SECTIONS[active_nav],
            current_user=user,
            chapters_count=(
                get_db().execute(
                    """
                    SELECT COUNT(*) FROM chapters
                    WHERE course_id = ? AND status = 'published'
                    """,
                    (course["id"],),
                ).fetchone()[0]
                if course
                else 0
            ),
            completed_count=0,
            csrf_token=session["csrf_token"],
        )

    @app.get("/library")
    def library():
        return render_app_section("library")

    @app.get("/laboratory")
    def laboratory():
        return render_app_section("laboratory")

    @app.get("/testing")
    def testing():
        return render_app_section("testing")

    @app.get("/profile")
    def profile():
        return render_app_section("profile")

    @app.get("/admin/users")
    @roles_required("admin")
    def admin_users():
        users = get_db().execute(
            """
            SELECT id, email, username, role, created_at
            FROM users
            ORDER BY
                CASE role
                    WHEN 'admin' THEN 0
                    WHEN 'teacher' THEN 1
                    ELSE 2
                END,
                email COLLATE NOCASE
            """
        ).fetchall()
        return render_template(
            "admin_users.html",
            users=users,
            current_user=current_user(),
            active_nav="profile",
            role_labels=USER_ROLE_LABELS,
            csrf_token=session["csrf_token"],
        )

    @app.post("/admin/users/<int:user_id>/role")
    @roles_required("admin")
    @csrf_protected
    def update_user_role(user_id):
        role = request.form.get("role", "")
        if role not in USER_ROLE_LABELS:
            flash("Выберите допустимую роль пользователя.", "error")
            return redirect(url_for("admin_users"))

        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        target_user = database.execute(
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target_user is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        if user_id == current_user()["id"] and role != target_user["role"]:
            database.rollback()
            flash("Нельзя изменить собственную роль.", "error")
            return redirect(url_for("admin_users"))

        if target_user["role"] == "admin" and role != "admin":
            admin_count = database.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin'"
            ).fetchone()[0]
            if admin_count <= 1:
                database.rollback()
                flash("Нельзя снять роль последнего администратора.", "error")
                return redirect(url_for("admin_users"))

        database.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, user_id),
        )
        database.commit()
        flash("Роль пользователя обновлена.", "success")
        return redirect(url_for("admin_users"))

    @app.get("/content-management")
    @roles_required("teacher", "admin")
    def content_management():
        return render_content_management()

    def render_content_management():
        courses = get_db().execute(
            """
            SELECT courses.id, courses.slug, courses.title, courses.description,
                courses.status, COUNT(chapters.id) AS chapter_count
            FROM courses
            LEFT JOIN chapters ON chapters.course_id = courses.id
            GROUP BY courses.id
            ORDER BY courses.title COLLATE NOCASE, courses.id
            """
        ).fetchall()
        chapter_rows = get_db().execute(
            """
            SELECT id, course_id, position, title, description, content, status
            FROM chapters
            ORDER BY course_id, position, id
            """
        ).fetchall()
        chapters_by_course = {}
        for chapter in chapter_rows:
            chapters_by_course.setdefault(chapter["course_id"], []).append(chapter)
        material_rows = get_db().execute(
            """
            SELECT id, course_id, title, description, material_type,
                resource_url, content, position
            FROM library_materials
            ORDER BY course_id, position, id
            """
        ).fetchall()
        materials_by_course = {}
        for material in material_rows:
            materials_by_course.setdefault(material["course_id"], []).append(material)
        selected_course_id = request.args.get("course_id", type=int)
        return render_template(
            "content_management.html",
            courses=courses,
            chapters_by_course=chapters_by_course,
            materials_by_course=materials_by_course,
            library_material_types=LIBRARY_MATERIAL_TYPES,
            selected_course_id=selected_course_id,
            current_user=current_user(),
            active_nav="learning",
            csrf_token=session["csrf_token"],
        )

    def chapter_form_values(chapter_count, creating, existing_status="published"):
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        content = request.form.get("content", "")
        status = request.form.get("status", "draft" if creating else existing_status)
        try:
            position = int(request.form.get("position", ""))
        except ValueError:
            return None, "Укажите целое число для позиции главы."
        if not title:
            return None, "Укажите название главы."
        if len(title) > 200:
            return None, "Название главы должно быть не длиннее 200 символов."
        if len(description) > 2000:
            return None, "Описание главы должно быть не длиннее 2000 символов."
        if len(content) > 100000:
            return None, "Учебный материал должен быть не длиннее 100000 символов."
        if status not in {"draft", "published"}:
            return None, "Выберите статус главы."
        max_position = chapter_count + 1 if creating else chapter_count
        if position < 1 or position > max_position:
            return None, f"Позиция главы должна быть от 1 до {max_position}."
        return (title, position, description, content, status), None

    def reorder_chapters(course_id, chapter_ids):
        max_position = get_db().execute(
            "SELECT COALESCE(MAX(position), 0) FROM chapters WHERE course_id = ?",
            (course_id,),
        ).fetchone()[0]
        offset = max_position + len(chapter_ids) + 1
        get_db().execute(
            """
            UPDATE chapters
            SET position = position + ?, updated_at = CURRENT_TIMESTAMP
            WHERE course_id = ?
            """,
            (offset, course_id),
        )
        for position, chapter_id in enumerate(chapter_ids, 1):
            get_db().execute(
                """
                UPDATE chapters
                SET position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND course_id = ?
                """,
                (position, chapter_id, course_id),
            )

    def redirect_to_course_management(course_id):
        return redirect(url_for("content_management", course_id=course_id))

    def library_material_form_values(material_count, creating):
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        material_type = request.form.get("material_type", "")
        resource_url = request.form.get("resource_url", "").strip()
        content = request.form.get("content", "")
        try:
            position = int(request.form.get("position", ""))
        except ValueError:
            return None, "Укажите целое число для позиции материала."
        if not title:
            return None, "Укажите название материала."
        if len(title) > 200:
            return None, "Название материала должно быть не длиннее 200 символов."
        if len(description) > 2000:
            return None, "Описание материала должно быть не длиннее 2000 символов."
        if material_type not in LIBRARY_MATERIAL_TYPES:
            return None, "Выберите тип материала."
        if len(resource_url) > 2048:
            return None, "Ссылка должна быть не длиннее 2048 символов."
        if resource_url and not is_http_resource_url(resource_url):
            return None, "Укажите корректную ссылку, начинающуюся с http:// или https://."
        if len(content) > 100000:
            return None, "Содержимое материала должно быть не длиннее 100000 символов."
        max_position = material_count + 1 if creating else material_count
        if position < 1 or position > max_position:
            return None, f"Позиция материала должна быть от 1 до {max_position}."
        return (
            title,
            description,
            material_type,
            resource_url or None,
            content,
            position,
        ), None

    def reorder_library_materials(course_id, material_ids):
        for position, material_id in enumerate(material_ids, 1):
            get_db().execute(
                """
                UPDATE library_materials
                SET position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND course_id = ?
                """,
                (position, material_id, course_id),
            )

    def course_form_values(existing_status="draft"):
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", existing_status)
        if not title:
            return None, "Укажите название курса."
        if len(title) > 160:
            return None, "Название курса должно быть не длиннее 160 символов."
        if not COURSE_SLUG_PATTERN.fullmatch(slug) or len(slug) > 100:
            return None, "Адрес курса должен содержать латинские строчные буквы, цифры и дефисы."
        if len(description) > 2000:
            return None, "Описание курса должно быть не длиннее 2000 символов."
        if status not in {"draft", "published"}:
            return None, "Выберите статус курса."
        return (title, slug, description, status), None

    @app.post("/content-management/courses")
    @roles_required("teacher", "admin")
    @csrf_protected
    def create_course():
        values, error = course_form_values()
        if error:
            flash(error, "error")
            return redirect(url_for("content_management"))

        try:
            get_db().execute(
                """
                INSERT INTO courses (title, slug, description, status)
                VALUES (?, ?, ?, ?)
                """,
                values,
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("Не удалось создать курс: такой адрес уже используется.", "error")
            return redirect(url_for("content_management"))

        flash("Курс создан.", "success")
        return redirect(url_for("content_management"))

    @app.post("/content-management/courses/<int:course_id>")
    @roles_required("teacher", "admin")
    @csrf_protected
    def edit_course(course_id):
        course = get_db().execute(
            "SELECT id, status FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        if course is None:
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        values, error = course_form_values(course["status"])
        if error:
            flash(error, "error")
            return redirect(url_for("content_management"))

        try:
            get_db().execute(
                """
                UPDATE courses
                SET title = ?, slug = ?, description = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*values, course_id),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("Не удалось сохранить курс: такой адрес уже используется.", "error")
            return redirect(url_for("content_management"))

        flash("Изменения курса сохранены.", "success")
        return redirect(url_for("content_management"))

    @app.post("/content-management/courses/<int:course_id>/chapters")
    @roles_required("teacher", "admin")
    @csrf_protected
    def create_chapter(course_id):
        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        course = database.execute(
            "SELECT id FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        if course is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        chapters = get_managed_course_chapters(course_id)
        values, error = chapter_form_values(len(chapters), creating=True)
        if error:
            database.rollback()
            flash(error, "error")
            return redirect_to_course_management(course_id)
        title, position, description, content, status = values
        if any(chapter["title"].casefold() == title.casefold() for chapter in chapters):
            database.rollback()
            flash("В этом курсе уже есть глава с таким названием.", "error")
            return redirect_to_course_management(course_id)

        try:
            max_position = max(
                (chapter["position"] for chapter in chapters),
                default=0,
            )
            cursor = database.execute(
                """
                INSERT INTO chapters (
                    course_id, position, title, description, content, status
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (course_id, max_position + 1, title, description, content, status),
            )
            chapter_ids = [chapter["id"] for chapter in chapters]
            chapter_ids.insert(position - 1, cursor.lastrowid)
            reorder_chapters(course_id, chapter_ids)
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            flash("Не удалось создать главу: проверьте её название и позицию.", "error")
            return redirect_to_course_management(course_id)

        flash("Глава создана.", "success")
        return redirect_to_course_management(course_id)

    @app.post("/content-management/chapters/<int:chapter_id>")
    @roles_required("teacher", "admin")
    @csrf_protected
    def edit_chapter(chapter_id):
        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        chapter = database.execute(
            """
            SELECT id, course_id, position, status
            FROM chapters
            WHERE id = ?
            """,
            (chapter_id,),
        ).fetchone()
        if chapter is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        course_id = chapter["course_id"]
        chapters = get_managed_course_chapters(course_id)
        values, error = chapter_form_values(
            len(chapters),
            creating=False,
            existing_status=chapter["status"],
        )
        if error:
            database.rollback()
            flash(error, "error")
            return redirect_to_course_management(course_id)
        title, position, description, content, status = values
        if any(
            item["id"] != chapter_id
            and item["title"].casefold() == title.casefold()
            for item in chapters
        ):
            database.rollback()
            flash("В этом курсе уже есть глава с таким названием.", "error")
            return redirect_to_course_management(course_id)

        try:
            database.execute(
                """
                UPDATE chapters
                SET title = ?, description = ?, content = ?, status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, description, content, status, chapter_id),
            )
            chapter_ids = [
                item["id"] for item in chapters if item["id"] != chapter_id
            ]
            chapter_ids.insert(position - 1, chapter_id)
            reorder_chapters(course_id, chapter_ids)
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            flash("Не удалось сохранить главу: проверьте её название и позицию.", "error")
            return redirect_to_course_management(course_id)

        flash("Изменения главы сохранены.", "success")
        return redirect_to_course_management(course_id)

    @app.post("/content-management/courses/<int:course_id>/library-materials")
    @roles_required("teacher", "admin")
    @csrf_protected
    def create_library_material(course_id):
        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        course = database.execute(
            "SELECT id FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        if course is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        materials = database.execute(
            """
            SELECT id FROM library_materials
            WHERE course_id = ?
            ORDER BY position, id
            """,
            (course_id,),
        ).fetchall()
        values, error = library_material_form_values(len(materials), creating=True)
        if error:
            database.rollback()
            flash(error, "error")
            return redirect_to_course_management(course_id)
        title, description, material_type, resource_url, content, position = values

        cursor = database.execute(
            """
            INSERT INTO library_materials (
                course_id, title, description, material_type,
                resource_url, content, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                title,
                description,
                material_type,
                resource_url,
                content,
                len(materials) + 1,
            ),
        )
        material_ids = [material["id"] for material in materials]
        material_ids.insert(position - 1, cursor.lastrowid)
        reorder_library_materials(course_id, material_ids)
        database.commit()
        flash("Материал библиотеки добавлен.", "success")
        return redirect_to_course_management(course_id)

    @app.post("/content-management/library-materials/<int:material_id>")
    @roles_required("teacher", "admin")
    @csrf_protected
    def edit_library_material(material_id):
        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        material = database.execute(
            """
            SELECT id, course_id
            FROM library_materials
            WHERE id = ?
            """,
            (material_id,),
        ).fetchone()
        if material is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        course_id = material["course_id"]
        materials = database.execute(
            """
            SELECT id FROM library_materials
            WHERE course_id = ?
            ORDER BY position, id
            """,
            (course_id,),
        ).fetchall()
        values, error = library_material_form_values(len(materials), creating=False)
        if error:
            database.rollback()
            flash(error, "error")
            return redirect_to_course_management(course_id)
        title, description, material_type, resource_url, content, position = values

        database.execute(
            """
            UPDATE library_materials
            SET title = ?, description = ?, material_type = ?,
                resource_url = ?, content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, description, material_type, resource_url, content, material_id),
        )
        material_ids = [
            item["id"] for item in materials if item["id"] != material_id
        ]
        material_ids.insert(position - 1, material_id)
        reorder_library_materials(course_id, material_ids)
        database.commit()
        flash("Изменения материала библиотеки сохранены.", "success")
        return redirect_to_course_management(course_id)

    @app.post("/content-management/library-materials/<int:material_id>/delete")
    @roles_required("teacher", "admin")
    @csrf_protected
    def delete_library_material(material_id):
        database = get_db()
        database.execute("BEGIN IMMEDIATE")
        material = database.execute(
            "SELECT id, course_id FROM library_materials WHERE id = ?",
            (material_id,),
        ).fetchone()
        if material is None:
            database.rollback()
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        course_id = material["course_id"]
        database.execute(
            "DELETE FROM library_materials WHERE id = ?",
            (material_id,),
        )
        remaining_materials = database.execute(
            """
            SELECT id FROM library_materials
            WHERE course_id = ?
            ORDER BY position, id
            """,
            (course_id,),
        ).fetchall()
        reorder_library_materials(
            course_id,
            [item["id"] for item in remaining_materials],
        )
        database.commit()
        flash("Материал библиотеки удалён.", "success")
        return redirect_to_course_management(course_id)

    @app.errorhandler(404)
    def page_not_found(_error):
        return render_template(
            "404.html",
            current_user=current_user(),
        ), 404

    @app.get("/course/<int:chapter_id>")
    def course_chapter(chapter_id):
        chapter_by_id = get_db().execute(
            """
            SELECT id, course_id, position, title, description, content
            FROM chapters
            WHERE id = ? AND status = 'published'
            """,
            (chapter_id,),
        ).fetchone()
        if chapter_by_id is None:
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404
        course = get_db().execute(
            """
            SELECT id, slug, title, description
            FROM courses
            WHERE id = ? AND status = 'published'
            """,
            (chapter_by_id["course_id"],),
        ).fetchone()
        if course is None:
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404
        chapters = get_course_chapters(course["id"])

        user = current_user()
        if user is None:
            return render_template(
                "chapter.html",
                chapter=chapter_by_id,
                chapter_id=chapter_id,
                current_user=None,
                access_state="login_required",
                course=course,
                csrf_token=session["csrf_token"],
            ), 401

        database = get_db()
        completed_rows = database.execute(
            """
            SELECT chapter_id FROM chapter_progress
            WHERE user_id = ? AND completed = 1
            """,
            (user["id"],),
        ).fetchall()
        completed_chapters = {row["chapter_id"] for row in completed_rows}
        if any(
            previous["id"] not in completed_chapters
            for previous in chapters
            if previous["position"] < chapter_by_id["position"]
        ):
            return render_template(
                "chapter.html",
                chapter=chapter_by_id,
                chapter_id=chapter_id,
                current_user=user,
                access_state="locked",
                course=course,
                csrf_token=session["csrf_token"],
            ), 403

        next_chapter = next(
            (
                chapter
                for chapter in chapters
                if chapter["position"] > chapter_by_id["position"]
            ),
            None,
        )
        return render_template(
            "chapter.html",
            chapter=chapter_by_id,
            chapter_id=chapter_id,
            current_user=user,
            access_state="available",
            completed=chapter_id in completed_chapters,
            next_chapter_id=next_chapter["id"] if next_chapter else None,
            next_chapter_accessible=(
                next_chapter is not None
                and all(
                    previous["id"] in completed_chapters
                    for previous in chapters
                    if previous["position"] < next_chapter["position"]
                )
            ),
            course=course,
            csrf_token=session["csrf_token"],
        )

    @app.post("/api/auth/register")
    @csrf_protected
    def register():
        payload = json_payload()
        if payload is None:
            return jsonify(error="Некорректный запрос."), 400

        email = payload.get("email")
        username = payload.get("username")
        password = payload.get("password")
        if (
            not isinstance(email, str)
            or not isinstance(username, str)
            or not isinstance(password, str)
        ):
            return jsonify(error="Укажите логин, электронную почту и пароль."), 400

        email = email.strip().casefold()
        username = username.strip().casefold()
        if not USERNAME_PATTERN.fullmatch(username):
            return jsonify(
                error="Логин должен содержать 3–32 символа: латинские буквы, цифры, точку, дефис или подчёркивание."
            ), 400
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            return jsonify(error="Укажите корректный адрес электронной почты."), 400
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            return jsonify(
                error=f"Пароль должен содержать от {MIN_PASSWORD_LENGTH} до {MAX_PASSWORD_LENGTH} символов."
            ), 400

        database = get_db()
        try:
            cursor = database.execute(
                "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
                (email, username, generate_password_hash(password)),
            )
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            return jsonify(error="Такой логин или адрес почты уже используется."), 409

        session.clear()
        session["user_id"] = cursor.lastrowid
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(email=email), 201

    @app.post("/api/auth/login")
    @csrf_protected
    def login():
        payload = json_payload()
        if payload is None:
            return jsonify(error="Некорректный запрос."), 400

        login_value = payload.get("login")
        password = payload.get("password")
        if not isinstance(login_value, str) or not isinstance(password, str):
            return jsonify(error="Укажите логин или электронную почту и пароль."), 400

        login_value = login_value.strip().casefold()
        if len(password) > MAX_PASSWORD_LENGTH:
            return jsonify(error="Неверная почта или пароль."), 401
        user = get_db().execute(
            """
            SELECT id, email, password_hash FROM users
            WHERE email = ? OR username = ?
            """,
            (login_value, login_value),
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="Неверная почта или пароль."), 401

        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(email=user["email"])

    @app.post("/api/auth/logout")
    @csrf_protected
    def logout():
        session.clear()
        return jsonify(success=True)

    @app.post("/api/progress/<int:chapter_id>")
    @csrf_protected
    def update_progress(chapter_id):
        user = current_user()
        if user is None:
            return jsonify(error="Войдите, чтобы сохранять прогресс обучения."), 401
        chapter = get_db().execute(
            """
            SELECT chapters.id, chapters.course_id, chapters.position
            FROM chapters
            JOIN courses ON courses.id = chapters.course_id
            WHERE chapters.id = ?
                AND chapters.status = 'published'
                AND courses.status = 'published'
            """,
            (chapter_id,),
        ).fetchone()
        if chapter is None:
            return jsonify(error="Такого раздела не существует."), 404
        course = get_db().execute(
            "SELECT id FROM courses WHERE id = ?",
            (chapter["course_id"],),
        ).fetchone()
        chapters = get_course_chapters(course["id"])

        payload = json_payload()
        if payload is None or payload.get("completed") is not True:
            return jsonify(error="Некорректное значение прогресса."), 400

        completed_chapters = {
            row["chapter_id"]
            for row in get_db().execute(
                """
                SELECT chapter_id FROM chapter_progress
                WHERE user_id = ? AND completed = 1
                """,
                (user["id"],),
            ).fetchall()
        }
        if any(
            previous["id"] not in completed_chapters
            for previous in chapters
            if previous["position"] < chapter["position"]
        ):
            return jsonify(error="Сначала завершите предыдущие разделы курса."), 403

        get_db().execute(
            """
            INSERT INTO chapter_progress (user_id, chapter_id, completed)
            VALUES (?, ?, ?)
            ON CONFLICT (user_id, chapter_id) DO UPDATE SET
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user["id"], chapter_id, int(payload["completed"])),
        )
        get_db().execute(
            """
            INSERT OR IGNORE INTO chapter_completion_history (user_id, chapter_id)
            VALUES (?, ?)
            """,
            (user["id"], chapter_id),
        )
        get_db().commit()
        return jsonify(chapter_id=chapter_id, completed=payload["completed"])

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

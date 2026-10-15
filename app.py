import os
import re
import secrets
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, render_template, request, session
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

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
DEMO_USERNAME = "test"
DEMO_EMAIL = "test@example.com"
DEMO_PASSWORD = "test"


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

    def get_course():
        return get_db().execute(
            "SELECT id, slug, title, description FROM courses WHERE slug = ?",
            (COURSE_SLUG,),
        ).fetchone()

    def get_course_chapters(course_id):
        return get_db().execute(
            """
            SELECT id, course_id, position, title, description, content
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
            "SELECT id, email, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    def csrf_is_valid():
        token = request.headers.get("X-CSRF-Token", "")
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
        chapters = get_course_chapters(course["id"])
        completed_chapters = set()
        accessible_chapters = set()
        if user is not None:
            rows = get_db().execute(
                "SELECT chapter_id FROM chapter_progress WHERE user_id = ? AND completed = 1",
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
        )

    def render_app_section(active_nav):
        user = current_user()
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
                    ORDER BY history.completed_at DESC, chapters.position DESC
                    """,
                    (user["id"], get_course()["id"]),
                )
                .fetchall()
                if user
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
                chapters_count=get_db().execute(
                    "SELECT COUNT(*) FROM chapters WHERE course_id = ?",
                    (get_course()["id"],),
                ).fetchone()[0],
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
                        """,
                        (user["id"], get_course()["id"]),
                    )
                    .fetchone()[0]
                    if user
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
                (get_course()["id"],),
            ).fetchall()
            return render_template(
                "section.html",
                active_nav=active_nav,
                section=APP_SECTIONS[active_nav],
                current_user=user,
                library_materials=library_materials,
                csrf_token=session["csrf_token"],
            )
        return render_template(
            "section.html",
            active_nav=active_nav,
            section=APP_SECTIONS[active_nav],
            current_user=user,
            chapters_count=get_db().execute(
                "SELECT COUNT(*) FROM chapters WHERE course_id = ?",
                (get_course()["id"],),
            ).fetchone()[0],
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

    @app.errorhandler(404)
    def page_not_found(_error):
        return render_template(
            "404.html",
            current_user=current_user(),
        ), 404

    @app.get("/course/<int:chapter_id>")
    def course_chapter(chapter_id):
        course = get_course()
        chapters = get_course_chapters(course["id"])
        chapter_by_id = next(
            (chapter for chapter in chapters if chapter["id"] == chapter_id),
            None,
        )
        if chapter_by_id is None:
            return render_template(
                "404.html",
                current_user=current_user(),
            ), 404

        user = current_user()
        if user is None:
            return render_template(
                "chapter.html",
                chapter=chapter_by_id,
                chapter_id=chapter_id,
                current_user=None,
                access_state="login_required",
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
        course = get_course()
        chapters = get_course_chapters(course["id"])
        chapter = next(
            (chapter for chapter in chapters if chapter["id"] == chapter_id),
            None,
        )
        if chapter is None:
            return jsonify(error="Такого раздела не существует."), 404

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

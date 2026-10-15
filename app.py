import os
import re
import secrets
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


CHAPTERS = [
    "Введение в цифровую схемотехнику",
    "Системы счисления и кодирование информации",
    "Основы булевой алгебры",
    "Логические элементы",
    "Комбинационные цифровые устройства",
    "Триггеры",
    "Регистры и счётчики",
    "Запоминающие устройства",
]

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
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                username TEXT UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chapter_progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                chapter_id INTEGER NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, chapter_id)
            );
            """
        )
        user_columns = {
            row["name"] for row in database.execute("PRAGMA table_info(users)")
        }
        if "username" not in user_columns:
            database.execute("ALTER TABLE users ADD COLUMN username TEXT")
        database.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_nocase "
            "ON users(username COLLATE NOCASE)"
        )
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
        database.commit()

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
        completed_chapters = set()
        accessible_chapters = set()
        if user is not None:
            rows = get_db().execute(
                "SELECT chapter_id FROM chapter_progress WHERE user_id = ? AND completed = 1",
                (user["id"],),
            ).fetchall()
            completed_chapters = {row["chapter_id"] for row in rows}
            for chapter_id in range(1, len(CHAPTERS) + 1):
                if all(
                    previous_id in completed_chapters
                    for previous_id in range(1, chapter_id)
                ):
                    accessible_chapters.add(chapter_id)

        return render_template(
            "index.html",
            chapters=CHAPTERS,
            current_user=user,
            completed_chapters=completed_chapters,
            accessible_chapters=accessible_chapters,
            csrf_token=session["csrf_token"],
            demo_user_enabled=app.config["SEED_DEMO_USER"],
        )

    def render_app_section(active_nav):
        user = current_user()
        if active_nav == "profile":
            return render_template(
                "section.html",
                active_nav=active_nav,
                section={
                    "title": "Профиль",
                    "description": "Учётная запись и прогресс обучения.",
                    "status": None,
                },
                current_user=user,
                chapters_count=len(CHAPTERS),
                completed_count=(
                    get_db()
                    .execute(
                        """
                        SELECT COUNT(*) FROM chapter_progress
                        WHERE user_id = ? AND completed = 1
                        """,
                        (user["id"],),
                    )
                    .fetchone()[0]
                    if user
                    else 0
                ),
                csrf_token=session["csrf_token"],
            )
        return render_template(
            "section.html",
            active_nav=active_nav,
            section=APP_SECTIONS[active_nav],
            current_user=user,
            chapters_count=len(CHAPTERS),
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

    @app.get("/course/<int:chapter_id>")
    def course_chapter(chapter_id):
        if chapter_id < 1 or chapter_id > len(CHAPTERS):
            return render_template(
                "chapter.html",
                chapter=None,
                current_user=current_user(),
                access_state="not_found",
                csrf_token=session["csrf_token"],
            ), 404

        user = current_user()
        if user is None:
            return render_template(
                "chapter.html",
                chapter=CHAPTERS[chapter_id - 1],
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
            previous_id not in completed_chapters
            for previous_id in range(1, chapter_id)
        ):
            return render_template(
                "chapter.html",
                chapter=CHAPTERS[chapter_id - 1],
                chapter_id=chapter_id,
                current_user=user,
                access_state="locked",
                csrf_token=session["csrf_token"],
            ), 403

        next_chapter_id = chapter_id + 1 if chapter_id < len(CHAPTERS) else None
        return render_template(
            "chapter.html",
            chapter=CHAPTERS[chapter_id - 1],
            chapter_id=chapter_id,
            current_user=user,
            access_state="available",
            completed=chapter_id in completed_chapters,
            next_chapter_id=next_chapter_id,
            next_chapter_accessible=(
                next_chapter_id is not None
                and all(
                    previous_id in completed_chapters
                    for previous_id in range(1, next_chapter_id)
                )
            ),
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
        if chapter_id < 1 or chapter_id > len(CHAPTERS):
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
            previous_id not in completed_chapters
            for previous_id in range(1, chapter_id)
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
        get_db().commit()
        return jsonify(chapter_id=chapter_id, completed=payload["completed"])

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

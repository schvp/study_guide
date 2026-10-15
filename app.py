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

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "study_guide.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower()
        in {"1", "true"},
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
        database.commit()

    def current_user():
        user_id = session.get("user_id")
        if user_id is None:
            return None
        return get_db().execute(
            "SELECT id, email FROM users WHERE id = ?",
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
        if user is not None:
            rows = get_db().execute(
                "SELECT chapter_id FROM chapter_progress WHERE user_id = ? AND completed = 1",
                (user["id"],),
            ).fetchall()
            completed_chapters = {row["chapter_id"] for row in rows}

        return render_template(
            "index.html",
            chapters=CHAPTERS,
            current_user=user,
            completed_chapters=completed_chapters,
            csrf_token=session["csrf_token"],
        )

    @app.post("/api/auth/register")
    @csrf_protected
    def register():
        payload = json_payload()
        if payload is None:
            return jsonify(error="Некорректный запрос."), 400

        email = payload.get("email")
        password = payload.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            return jsonify(error="Укажите электронную почту и пароль."), 400

        email = email.strip().casefold()
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            return jsonify(error="Укажите корректный адрес электронной почты."), 400
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            return jsonify(
                error=f"Пароль должен содержать от {MIN_PASSWORD_LENGTH} до {MAX_PASSWORD_LENGTH} символов."
            ), 400

        database = get_db()
        try:
            cursor = database.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, generate_password_hash(password)),
            )
            database.commit()
        except sqlite3.IntegrityError:
            database.rollback()
            return jsonify(error="Аккаунт с такой почтой уже существует."), 409

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

        email = payload.get("email")
        password = payload.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            return jsonify(error="Укажите электронную почту и пароль."), 400

        email = email.strip().casefold()
        if len(password) > MAX_PASSWORD_LENGTH:
            return jsonify(error="Неверная почта или пароль."), 401
        user = get_db().execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email,),
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
        if payload is None or type(payload.get("completed")) is not bool:
            return jsonify(error="Некорректное значение прогресса."), 400

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

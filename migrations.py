import json
import sqlite3


def _create_user_tables(database):
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS chapter_progress (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chapter_id INTEGER NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, chapter_id)
        )
        """
    )


def _add_username(database):
    columns = {row[1] for row in database.execute("PRAGMA table_info(users)")}
    if "username" not in columns:
        database.execute("ALTER TABLE users ADD COLUMN username TEXT")
    database.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_nocase "
        "ON users(username COLLATE NOCASE)"
    )


def _create_course_tables(database):
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (course_id, position),
            UNIQUE (course_id, title)
        )
        """
    )


def _link_progress_to_chapters(database):
    database.execute(
        """
        CREATE TABLE chapter_progress_new (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, chapter_id)
        )
        """
    )
    database.execute(
        """
        INSERT INTO chapter_progress_new (
            user_id, chapter_id, completed, updated_at
        )
        SELECT user_id, chapter_id, completed, updated_at
        FROM chapter_progress
        """
    )
    database.execute("DROP TABLE chapter_progress")
    database.execute(
        "ALTER TABLE chapter_progress_new RENAME TO chapter_progress"
    )


def _create_chapter_completion_history(database):
    database.execute(
        """
        CREATE TABLE chapter_completion_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, chapter_id)
        )
        """
    )
    database.execute(
        """
        INSERT INTO chapter_completion_history (
            user_id, chapter_id, completed_at
        )
        SELECT user_id, chapter_id, updated_at
        FROM chapter_progress
        WHERE completed = 1
        """
    )


def _create_library_materials(database):
    database.execute(
        """
        CREATE TABLE library_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            material_type TEXT NOT NULL DEFAULT 'article'
                CHECK (material_type IN ('article', 'book', 'video', 'link', 'file')),
            resource_url TEXT,
            content TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    database.execute(
        """
        CREATE INDEX idx_library_materials_course_position
        ON library_materials(course_id, position, id)
        """
    )


def _add_user_roles(database):
    database.execute(
        """
        ALTER TABLE users
        ADD COLUMN role TEXT NOT NULL DEFAULT 'student'
            CHECK (role IN ('student', 'teacher', 'admin'))
        """
    )


def _add_content_publication_status(database):
    database.execute(
        """
        ALTER TABLE courses
        ADD COLUMN status TEXT NOT NULL DEFAULT 'published'
            CHECK (status IN ('draft', 'published'))
        """
    )
    database.execute(
        """
        ALTER TABLE chapters
        ADD COLUMN status TEXT NOT NULL DEFAULT 'published'
            CHECK (status IN ('draft', 'published'))
        """
    )


def _create_assessment_tables(database):
    database.execute(
        """
        CREATE TABLE assessment_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            question_type TEXT NOT NULL
                CHECK (question_type IN ('single_choice', 'multiple_choice', 'numeric')),
            prompt TEXT NOT NULL,
            options TEXT NOT NULL DEFAULT '[]',
            correct_answer TEXT NOT NULL,
            tolerance REAL NOT NULL DEFAULT 0 CHECK (tolerance >= 0),
            explanation TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL,
            published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (chapter_id, position)
        )
        """
    )
    database.execute(
        """
        CREATE INDEX idx_assessment_questions_course_chapter
        ON assessment_questions(course_id, chapter_id, published, position)
        """
    )
    database.execute(
        """
        CREATE TABLE assessment_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            score INTEGER NOT NULL DEFAULT 0 CHECK (score >= 0),
            question_count INTEGER NOT NULL CHECK (question_count > 0),
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            submitted_at TEXT
        )
        """
    )
    database.execute(
        """
        CREATE INDEX idx_assessment_attempts_user
        ON assessment_attempts(user_id, submitted_at DESC, id DESC)
        """
    )
    database.execute(
        """
        CREATE TABLE assessment_attempt_answers (
            attempt_id INTEGER NOT NULL
                REFERENCES assessment_attempts(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL
                REFERENCES assessment_questions(id) ON DELETE CASCADE,
            answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
            PRIMARY KEY (attempt_id, question_id)
        )
        """
    )


def _snapshot_assessment_attempt_questions(database):
    database.execute(
        """
        CREATE TABLE assessment_attempt_questions (
            attempt_id INTEGER NOT NULL
                REFERENCES assessment_attempts(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL
                REFERENCES assessment_questions(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            PRIMARY KEY (attempt_id, question_id),
            UNIQUE (attempt_id, position)
        )
        """
    )


def _make_assessment_attempts_immutable(database):
    attempt_questions = database.execute(
        """
        SELECT attempt_questions.attempt_id, attempt_questions.question_id,
            attempt_questions.position, questions.question_type,
            questions.prompt, questions.options, questions.correct_answer,
            questions.tolerance, questions.explanation
        FROM assessment_attempt_questions AS attempt_questions
        JOIN assessment_questions AS questions
            ON questions.id = attempt_questions.question_id
        ORDER BY attempt_questions.attempt_id, attempt_questions.position
        """
    ).fetchall()
    database.execute("ALTER TABLE assessment_attempt_questions RENAME TO assessment_attempt_questions_old")
    database.execute(
        """
        CREATE TABLE assessment_attempt_questions (
            attempt_id INTEGER NOT NULL
                REFERENCES assessment_attempts(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            question_snapshot TEXT NOT NULL,
            PRIMARY KEY (attempt_id, question_id),
            UNIQUE (attempt_id, position)
        )
        """
    )
    database.executemany(
        """
        INSERT INTO assessment_attempt_questions (
            attempt_id, question_id, position, question_snapshot
        )
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                row[0],
                row[1],
                row[2],
                json.dumps(
                    {
                        "question_type": row[3],
                        "prompt": row[4],
                        "options": json.loads(row[5]),
                        "correct_answer": json.loads(row[6]),
                        "tolerance": row[7],
                        "explanation": row[8],
                    },
                    ensure_ascii=False,
                ),
            )
            for row in attempt_questions
        ],
    )
    database.execute("DROP TABLE assessment_attempt_questions_old")

    database.execute("ALTER TABLE assessment_attempt_answers RENAME TO assessment_attempt_answers_old")
    database.execute(
        """
        CREATE TABLE assessment_attempt_answers (
            attempt_id INTEGER NOT NULL
                REFERENCES assessment_attempts(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
            PRIMARY KEY (attempt_id, question_id)
        )
        """
    )
    database.execute(
        """
        INSERT INTO assessment_attempt_answers (
            attempt_id, question_id, answer, is_correct
        )
        SELECT attempt_id, question_id, answer, is_correct
        FROM assessment_attempt_answers_old
        """
    )
    database.execute("DROP TABLE assessment_attempt_answers_old")


def _track_assessment_bank_seeding(database):
    database.execute(
        """
        CREATE TABLE assessment_bank_seed_state (
            course_id INTEGER PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
            seeded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _add_assessment_difficulty_and_settings(database):
    database.execute(
        """
        ALTER TABLE assessment_questions
        ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'beginner'
            CHECK (difficulty IN ('beginner', 'intermediate', 'advanced'))
        """
    )
    database.execute(
        """
        CREATE TABLE assessment_chapter_settings (
            chapter_id INTEGER PRIMARY KEY
                REFERENCES chapters(id) ON DELETE CASCADE,
            questions_per_attempt INTEGER NOT NULL DEFAULT 2
                CHECK (questions_per_attempt BETWEEN 1 AND 20)
        )
        """
    )
    database.execute(
        """
        INSERT INTO assessment_chapter_settings (chapter_id)
        SELECT id FROM chapters
        """
    )


def _version_assessment_question_bank(database):
    database.execute(
        """
        ALTER TABLE assessment_bank_seed_state
        ADD COLUMN bank_version INTEGER NOT NULL DEFAULT 1
        """
    )
    snapshots = database.execute(
        """
        SELECT attempt_id, question_id, question_snapshot
        FROM assessment_attempt_questions
        """
    ).fetchall()
    for attempt_id, question_id, serialized_snapshot in snapshots:
        snapshot = json.loads(serialized_snapshot)
        if "difficulty" not in snapshot:
            snapshot["difficulty"] = "beginner"
            database.execute(
                """
                UPDATE assessment_attempt_questions
                SET question_snapshot = ?
                WHERE attempt_id = ? AND question_id = ?
                """,
                (
                    json.dumps(snapshot, ensure_ascii=False),
                    attempt_id,
                    question_id,
                ),
            )


MIGRATIONS = (
    (1, "create_user_tables", _create_user_tables),
    (2, "add_username", _add_username),
    (3, "create_course_tables", _create_course_tables),
    (4, "link_progress_to_chapters", _link_progress_to_chapters),
    (5, "create_chapter_completion_history", _create_chapter_completion_history),
    (6, "create_library_materials", _create_library_materials),
    (7, "add_user_roles", _add_user_roles),
    (8, "add_content_publication_status", _add_content_publication_status),
    (9, "create_assessment_tables", _create_assessment_tables),
    (10, "snapshot_assessment_attempt_questions", _snapshot_assessment_attempt_questions),
    (11, "make_assessment_attempts_immutable", _make_assessment_attempts_immutable),
    (12, "track_assessment_bank_seeding", _track_assessment_bank_seeding),
    (13, "add_assessment_difficulty_and_settings", _add_assessment_difficulty_and_settings),
    (14, "version_assessment_question_bank", _version_assessment_question_bank),
)


def migrate_database(database, through_version=None):
    database.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    database.commit()

    known_versions = {version for version, _, _ in MIGRATIONS}
    applied_migrations = {
        row[0]: row[1]
        for row in database.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        )
    }
    unknown_versions = set(applied_migrations) - known_versions
    if unknown_versions:
        latest_unknown = max(unknown_versions)
        raise RuntimeError(
            f"Database schema version {latest_unknown} is newer than this application supports."
        )

    for version, name, migration in MIGRATIONS:
        if through_version is not None and version > through_version:
            break
        if version in applied_migrations:
            if applied_migrations[version] != name:
                raise RuntimeError(
                    f"Migration version {version} has unexpected name "
                    f"{applied_migrations[version]!r}."
                )
            continue

        previous_versions = {item[0] for item in MIGRATIONS if item[0] < version}
        if not previous_versions.issubset(applied_migrations):
            raise RuntimeError(
                f"Cannot apply migration {version} before its prerequisites."
            )

        try:
            database.execute("BEGIN IMMEDIATE")
            migration(database)
            database.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )
            database.commit()
            applied_migrations[version] = name
        except sqlite3.Error:
            database.rollback()
            raise
        except Exception:
            database.rollback()
            raise

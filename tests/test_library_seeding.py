import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from app import create_app


class LibrarySeedingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "test.sqlite3")
        self.library_directory = os.path.join(self.temp_dir.name, "library")
        os.makedirs(self.library_directory)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_material(self, title="Сигналы и уровни"):
        metadata = {
            "course": "digital-circuits",
            "slug": "signal-levels",
            "chapter_position": 1,
            "position": 1,
            "title": title,
            "description": "Практический справочник.",
            "category": "fundamentals",
            "difficulty": "basic",
            "material_type": "article",
            "estimated_minutes": 9,
            "content_file": "signal-levels.md",
        }
        with open(
            os.path.join(self.library_directory, "signal-levels.json"),
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False)
        with open(
            os.path.join(self.library_directory, "signal-levels.md"),
            "w",
            encoding="utf-8",
        ) as content_file:
            content_file.write("## Цифровой сигнал\n\nСигнал принимает устойчивые уровни.")

    def create_test_app(self):
        return create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": self.database_path,
                "LIBRARY_MATERIALS_DIRECTORY": self.library_directory,
                "SEED_DEMO_USER": False,
                "SEED_DEMO_ADMIN": False,
            }
        )

    def test_seeds_and_updates_versioned_material(self):
        self.write_material()
        self.create_test_app()

        self.write_material(title="Обновлённые сигналы и уровни")
        self.create_test_app()

        with closing(sqlite3.connect(self.database_path)) as database:
            materials = database.execute(
                """
                SELECT slug, title, category, difficulty, estimated_minutes,
                    status, chapter_id
                FROM library_materials
                """
            ).fetchall()
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0][0], "signal-levels")
        self.assertEqual(materials[0][1], "Обновлённые сигналы и уровни")
        self.assertEqual(materials[0][2:6], ("fundamentals", "basic", 9, "published"))
        self.assertIsNotNone(materials[0][6])


if __name__ == "__main__":
    unittest.main()

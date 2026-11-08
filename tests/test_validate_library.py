import json
import os
import tempfile
import unittest

from validate_library import main, summarize_library


class ValidateLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        metadata = {
            "course": "digital-circuits",
            "slug": "reference",
            "chapter_position": 1,
            "position": 1,
            "title": "Справочник",
            "description": "Описание",
            "category": "fundamentals",
            "difficulty": "basic",
            "material_type": "article",
            "estimated_minutes": 5,
            "content_file": "reference.md",
        }
        with open(
            os.path.join(self.temp_dir.name, "reference.json"),
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(metadata, metadata_file, ensure_ascii=False)
        with open(
            os.path.join(self.temp_dir.name, "reference.md"),
            "w",
            encoding="utf-8",
        ) as content_file:
            content_file.write("Цифровая схема хранит и обрабатывает данные.")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_summarizes_material_count_and_words(self):
        summary = summarize_library(self.temp_dir.name)

        self.assertEqual(summary["materials"], 1)
        self.assertEqual(summary["words"], 6)
        self.assertEqual(summary["courses"]["digital-circuits"], 1)
        self.assertEqual(summary["categories"]["fundamentals"], 1)

    def test_command_reports_invalid_library(self):
        os.remove(os.path.join(self.temp_dir.name, "reference.md"))

        self.assertEqual(main([self.temp_dir.name]), 1)


if __name__ == "__main__":
    unittest.main()

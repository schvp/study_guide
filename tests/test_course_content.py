import json
import os
import tempfile
import unittest

from course_content import load_course_materials


class CourseContentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.content_directory = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_material(self, filename, **overrides):
        material = {
            "course": "digital-circuits",
            "position": 1,
            "title": "Введение",
            "description": "Описание",
            "content": "## Основы\n\nТекст главы.",
        }
        material.update(overrides)
        with open(
            os.path.join(self.content_directory, filename),
            "w",
            encoding="utf-8",
        ) as material_file:
            json.dump(material, material_file, ensure_ascii=False)

    def test_loads_json_materials_in_filename_order(self):
        self.write_material("02-second.json", position=2, title="Вторая глава")
        self.write_material("01-first.json")
        with open(
            os.path.join(self.content_directory, "notes.txt"),
            "w",
            encoding="utf-8",
        ) as ignored_file:
            ignored_file.write("Not course material")

        materials = load_course_materials(self.content_directory)

        self.assertEqual(
            [(item["position"], item["title"]) for item in materials],
            [(1, "Введение"), (2, "Вторая глава")],
        )

    def test_rejects_invalid_json_and_missing_fields(self):
        with open(
            os.path.join(self.content_directory, "broken.json"),
            "w",
            encoding="utf-8",
        ) as broken_file:
            broken_file.write("{")
        with self.assertRaises(json.JSONDecodeError):
            load_course_materials(self.content_directory)

        os.remove(os.path.join(self.content_directory, "broken.json"))
        self.write_material("missing.json")
        with open(
            os.path.join(self.content_directory, "missing.json"),
            "w",
            encoding="utf-8",
        ) as material_file:
            json.dump({"course": "digital-circuits"}, material_file)
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            load_course_materials(self.content_directory)

    def test_rejects_invalid_positions_and_duplicate_chapters(self):
        self.write_material("invalid.json", position=True)
        with self.assertRaisesRegex(ValueError, "invalid field values"):
            load_course_materials(self.content_directory)

        os.remove(os.path.join(self.content_directory, "invalid.json"))
        self.write_material("01.json")
        self.write_material("02.json", title="Дубликат")
        with self.assertRaisesRegex(ValueError, "Duplicate course material"):
            load_course_materials(self.content_directory)


if __name__ == "__main__":
    unittest.main()

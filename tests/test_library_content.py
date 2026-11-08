import json
import os
import tempfile
import unittest

from library_content import load_library_materials


class LibraryContentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_material(self, name="signals", **overrides):
        material = {
            "course": "digital-circuits",
            "slug": name,
            "chapter_position": 1,
            "position": 1,
            "title": "Цифровые сигналы",
            "description": "Справочник по уровням цифровых сигналов.",
            "category": "fundamentals",
            "difficulty": "basic",
            "material_type": "article",
            "estimated_minutes": 8,
            "content_file": f"{name}.md",
        }
        material.update(overrides)
        with open(
            os.path.join(self.temp_dir.name, f"{name}.json"),
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(material, metadata_file, ensure_ascii=False)
        content_file = material.get("content_file")
        if content_file and os.path.basename(content_file) == content_file:
            with open(
                os.path.join(self.temp_dir.name, content_file),
                "w",
                encoding="utf-8",
            ) as markdown_file:
                markdown_file.write("## Основы\n\nПолезный учебный материал.")

    def test_loads_and_normalizes_materials(self):
        self.write_material(
            "advanced-signals",
            slug="advanced-signals",
            position=2,
            difficulty="advanced",
            resource_url="https://example.org/signals",
        )
        self.write_material()

        materials = load_library_materials(self.temp_dir.name)

        self.assertEqual([item["position"] for item in materials], [1, 2])
        self.assertEqual(materials[0]["status"], "published")
        self.assertEqual(materials[0]["resource_url"], "")
        self.assertIn("Полезный учебный материал", materials[0]["content"])

    def test_rejects_missing_and_invalid_fields(self):
        self.write_material(estimated_minutes=0)
        with self.assertRaisesRegex(ValueError, "invalid field values"):
            load_library_materials(self.temp_dir.name)

        os.remove(os.path.join(self.temp_dir.name, "signals.json"))
        self.write_material()
        metadata_path = os.path.join(self.temp_dir.name, "signals.json")
        with open(metadata_path, encoding="utf-8") as metadata_file:
            material = json.load(metadata_file)
        del material["category"]
        with open(metadata_path, "w", encoding="utf-8") as metadata_file:
            json.dump(material, metadata_file)
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            load_library_materials(self.temp_dir.name)

    def test_rejects_unsafe_paths_urls_and_duplicates(self):
        self.write_material(resource_url="javascript:alert(1)")
        with self.assertRaisesRegex(ValueError, "invalid field values"):
            load_library_materials(self.temp_dir.name)

        os.remove(os.path.join(self.temp_dir.name, "signals.json"))
        self.write_material(content_file="../outside.md")
        with self.assertRaisesRegex(ValueError, "invalid field values"):
            load_library_materials(self.temp_dir.name)

        os.remove(os.path.join(self.temp_dir.name, "signals.json"))
        self.write_material()
        self.write_material("second", slug="signals", position=2)
        with self.assertRaisesRegex(ValueError, "Duplicate library material slug"):
            load_library_materials(self.temp_dir.name)

    def test_rejects_missing_directory(self):
        with self.assertRaises(FileNotFoundError):
            load_library_materials(os.path.join(self.temp_dir.name, "missing"))


if __name__ == "__main__":
    unittest.main()

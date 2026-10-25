import unittest

from laboratory_catalog import (
    LABORATORY_DEFINITIONS,
    build_laboratory_catalog,
    get_laboratory_definition,
)


class LaboratoryCatalogTests(unittest.TestCase):
    def test_defines_laboratories_for_all_course_chapters(self):
        self.assertEqual(set(LABORATORY_DEFINITIONS), set(range(1, 9)))
        self.assertEqual(
            len({item["slug"] for item in LABORATORY_DEFINITIONS.values()}),
            8,
        )

    def test_finds_laboratory_definition_by_slug(self):
        definition = get_laboratory_definition("trigger")

        self.assertEqual(definition["position"], 6)
        self.assertEqual(definition["title"], "Исследование D-триггера")
        self.assertIsNone(get_laboratory_definition("unknown-laboratory"))

    def test_builds_catalog_in_chapter_order(self):
        chapters = [
            {"id": 20, "position": 2, "title": "Системы счисления"},
            {"id": 10, "position": 1, "title": "Введение"},
        ]

        catalog = build_laboratory_catalog(chapters)

        self.assertEqual([item["chapter_id"] for item in catalog], [10, 20])
        self.assertEqual(catalog[0]["slug"], "byte-assembly")

    def test_unlocks_laboratories_sequentially(self):
        chapters = [
            {"id": 10, "position": 1, "title": "Введение"},
            {"id": 20, "position": 2, "title": "Системы счисления"},
            {"id": 30, "position": 3, "title": "Булева алгебра"},
        ]

        catalog = build_laboratory_catalog(chapters, completed_chapter_ids={10})

        self.assertTrue(catalog[0]["available"])
        self.assertTrue(catalog[0]["completed"])
        self.assertTrue(catalog[1]["available"])
        self.assertFalse(catalog[1]["completed"])
        self.assertFalse(catalog[2]["available"])

    def test_ignores_chapters_without_laboratory_definition(self):
        chapters = [{"id": 90, "position": 9, "title": "Дополнение"}]

        self.assertEqual(build_laboratory_catalog(chapters), [])


if __name__ == "__main__":
    unittest.main()

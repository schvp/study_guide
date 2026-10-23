import unittest

from course_outline import build_course_outline, find_outline_gaps


class CourseOutlineTests(unittest.TestCase):
    def test_builds_sorted_metadata_without_markdown_body(self):
        materials = [
            {
                "course": "logic",
                "position": 2,
                "title": "Гейты",
                "description": "Базовые элементы",
                "content": "секретный текст",
            },
            {
                "course": "digital-circuits",
                "position": 2,
                "title": "Числа",
                "description": "Системы счисления",
                "content": "длинный текст",
            },
            {
                "course": "logic",
                "position": 1,
                "title": "Алгебра",
                "description": "Основы",
                "content": "ещё текст",
            },
        ]

        self.assertEqual(
            build_course_outline(materials),
            {
                "digital-circuits": [
                    {
                        "position": 2,
                        "title": "Числа",
                        "description": "Системы счисления",
                    }
                ],
                "logic": [
                    {
                        "position": 1,
                        "title": "Алгебра",
                        "description": "Основы",
                    },
                    {
                        "position": 2,
                        "title": "Гейты",
                        "description": "Базовые элементы",
                    },
                ],
            },
        )

    def test_reports_missing_positions_per_course(self):
        materials = [
            {"course": "logic", "position": 1},
            {"course": "logic", "position": 3},
            {"course": "numbers", "position": 1},
            {"course": "numbers", "position": 2},
        ]

        self.assertEqual(find_outline_gaps(materials), {"logic": [2]})

    def test_returns_empty_gaps_for_continuous_course(self):
        materials = [
            {"course": "logic", "position": 1},
            {"course": "logic", "position": 2},
        ]

        self.assertEqual(find_outline_gaps(materials), {})


if __name__ == "__main__":
    unittest.main()

import unittest

from student_statistics import (
    build_chapter_statistics,
    build_student_statistics,
    percentage,
)


class StudentStatisticsTests(unittest.TestCase):
    def test_percentage_handles_empty_and_partial_totals(self):
        self.assertEqual(percentage(0, 0), 0)
        self.assertEqual(percentage(3, 8), 38)
        self.assertEqual(percentage(8, 8), 100)

    def test_summary_aggregates_assessments_and_laboratories(self):
        statistics = build_student_statistics(
            chapters_count=8,
            completed_count=3,
            assessment_scores=[(3, 4), (2, 2), (0, 0)],
            laboratory_slugs=["byte-assembly", "byte-assembly", "octal-conversion"],
        )

        self.assertEqual(statistics["completion_percent"], 38)
        self.assertEqual(statistics["assessment_attempts"], 2)
        self.assertEqual(statistics["assessment_average_percent"], 88)
        self.assertEqual(statistics["assessment_best_percent"], 100)
        self.assertEqual(statistics["laboratory_attempts"], 3)
        self.assertEqual(statistics["laboratory_unique_count"], 2)

    def test_summary_uses_none_for_missing_assessment_results(self):
        statistics = build_student_statistics(8, 0)

        self.assertIsNone(statistics["assessment_average_percent"])
        self.assertIsNone(statistics["assessment_best_percent"])
        self.assertEqual(statistics["laboratory_attempts"], 0)

    def test_chapter_statistics_are_ordered_and_aggregated(self):
        chapters = [
            {"id": 2, "position": 2, "title": "Вторая"},
            {"id": 1, "position": 1, "title": "Первая"},
        ]

        statistics = build_chapter_statistics(
            chapters,
            completed_chapter_ids={1},
            assessment_results=[(1, 1, 2), (1, 2, 2), (2, 0, 0)],
            laboratory_chapter_ids=[1, 1, 2],
        )

        self.assertEqual([item["chapter_id"] for item in statistics], [1, 2])
        self.assertTrue(statistics[0]["completed"])
        self.assertEqual(statistics[0]["assessment_attempts"], 2)
        self.assertEqual(statistics[0]["assessment_best_percent"], 100)
        self.assertEqual(statistics[0]["laboratory_attempts"], 2)
        self.assertFalse(statistics[1]["completed"])
        self.assertIsNone(statistics[1]["assessment_best_percent"])


if __name__ == "__main__":
    unittest.main()

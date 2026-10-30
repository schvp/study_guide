import unittest

from teacher_reports import (
    build_student_report,
    build_teacher_totals,
    filter_student_reports,
)


class TeacherReportTests(unittest.TestCase):
    def test_student_report_normalizes_database_aggregates(self):
        report = build_student_report(
            {
                "user_id": 3,
                "username": "student",
                "email": "student@example.com",
                "completed_count": 3,
                "assessment_attempts": 2,
                "assessment_average": 87.5,
                "laboratory_attempts": 4,
                "laboratory_completed_count": 2,
            },
            chapters_count=8,
        )

        self.assertEqual(report["completion_percent"], 38)
        self.assertEqual(report["assessment_average_percent"], 88)
        self.assertEqual(report["laboratory_completed_count"], 2)

    def test_teacher_totals_handle_students_without_assessments(self):
        totals = build_teacher_totals(
            [
                {"completion_percent": 100, "assessment_average_percent": 90},
                {"completion_percent": 50, "assessment_average_percent": None},
            ]
        )

        self.assertEqual(totals["students_count"], 2)
        self.assertEqual(totals["average_completion_percent"], 75)
        self.assertEqual(totals["average_assessment_percent"], 90)
        self.assertEqual(totals["completed_students_count"], 1)

    def test_report_filter_matches_username_and_email(self):
        reports = [
            {"username": "alpha", "email": "first@example.com"},
            {"username": "beta", "email": "second@example.com"},
        ]

        self.assertEqual(len(filter_student_reports(reports, "ALP")), 1)
        self.assertEqual(len(filter_student_reports(reports, "second@")), 1)
        self.assertEqual(len(filter_student_reports(reports, "")), 2)


if __name__ == "__main__":
    unittest.main()

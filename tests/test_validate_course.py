import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from validate_course import main, validate_course


class ValidateCourseTests(unittest.TestCase):
    def test_validates_repository_materials(self):
        root = os.path.dirname(os.path.dirname(__file__))

        outline, gaps = validate_course(os.path.join(root, "course_materials"))

        self.assertEqual(gaps, {})
        self.assertEqual(len(outline["digital-circuits"]), 8)
        self.assertEqual(outline["digital-circuits"][0]["position"], 1)

    def test_main_reports_invalid_directory(self):
        output = StringIO()
        errors = StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = main(["missing-course-materials"])

        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("Ошибка проверки", errors.getvalue())

    def test_main_prints_summary_for_valid_directory(self):
        root = os.path.dirname(os.path.dirname(__file__))
        output = StringIO()
        with redirect_stdout(output):
            result = main([os.path.join(root, "course_materials")])

        self.assertEqual(result, 0)
        self.assertIn("Курсов: 1", output.getvalue())
        self.assertIn("Глав: 8", output.getvalue())
        self.assertIn("Структура курса корректна.", output.getvalue())


if __name__ == "__main__":
    unittest.main()

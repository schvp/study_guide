import sys
import unittest

from check_project import check_commands


class ProjectCheckRunnerTests(unittest.TestCase):
    def test_full_check_plan_runs_syntax_content_and_tests(self):
        commands = check_commands()

        self.assertEqual(commands[0][:3], [sys.executable, "-m", "compileall"])
        self.assertEqual(commands[1], [sys.executable, "validate_course.py"])
        self.assertEqual(
            commands[2],
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-q",
            ],
        )

    def test_quick_check_plan_skips_test_suite(self):
        commands = check_commands(include_tests=False)

        self.assertEqual(len(commands), 2)
        self.assertNotIn("unittest", [part for command in commands for part in command])


if __name__ == "__main__":
    unittest.main()

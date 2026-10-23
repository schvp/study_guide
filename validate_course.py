"""Validate and summarize course materials from the command line."""

import argparse
import os
import sys

from course_content import load_course_materials
from course_outline import build_course_outline, find_outline_gaps


def validate_course(content_directory):
    """Load materials and return ``(outline, gaps)`` for the directory."""

    materials = load_course_materials(content_directory)
    return build_course_outline(materials), find_outline_gaps(materials)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверить структуру учебных материалов курса."
    )
    parser.add_argument(
        "content_directory",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "course_materials"),
        help="каталог с JSON-описаниями материалов (по умолчанию: course_materials)",
    )
    args = parser.parse_args(argv)

    try:
        outline, gaps = validate_course(args.content_directory)
    except (OSError, ValueError) as error:
        print(f"Ошибка проверки: {error}", file=sys.stderr)
        return 1

    total_chapters = sum(len(chapters) for chapters in outline.values())
    print(f"Курсов: {len(outline)}")
    print(f"Глав: {total_chapters}")
    for course, chapters in outline.items():
        print(f"- {course}: {len(chapters)} глав")

    if gaps:
        for course, missing_positions in gaps.items():
            positions = ", ".join(str(position) for position in missing_positions)
            print(f"Пропущены позиции в {course}: {positions}", file=sys.stderr)
        return 1

    print("Структура курса корректна.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate and summarize versioned library materials."""

import argparse
import os
import re
import sys
from collections import Counter

from library_content import load_library_materials


def summarize_library(content_directory):
    materials = load_library_materials(content_directory)
    words = sum(
        len(re.findall(r"[\wА-Яа-яЁё]+", material["content"], re.UNICODE))
        for material in materials
    )
    return {
        "materials": len(materials),
        "words": words,
        "courses": Counter(material["course"] for material in materials),
        "categories": Counter(material["category"] for material in materials),
        "difficulties": Counter(material["difficulty"] for material in materials),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверить структуру материалов библиотеки."
    )
    parser.add_argument(
        "content_directory",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "library_materials"),
        help="каталог библиотеки (по умолчанию: library_materials)",
    )
    arguments = parser.parse_args(argv)
    try:
        summary = summarize_library(arguments.content_directory)
    except (OSError, ValueError) as error:
        print(f"Ошибка проверки: {error}", file=sys.stderr)
        return 1

    print(f"Материалов: {summary['materials']}")
    print(f"Слов: {summary['words']}")
    for course, count in sorted(summary["courses"].items()):
        print(f"- {course}: {count} материалов")
    print("Структура библиотеки корректна.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Aggregation helpers for teacher-facing course reports."""

import csv
import io

from student_statistics import percentage


def build_teacher_totals(reports):
    """Return high-level values for a collection of student reports."""

    reports = list(reports)
    completion_values = [report["completion_percent"] for report in reports]
    assessment_values = [
        report["assessment_average_percent"]
        for report in reports
        if report["assessment_average_percent"] is not None
    ]
    return {
        "students_count": len(reports),
        "average_completion_percent": (
            round(sum(completion_values) / len(completion_values))
            if completion_values
            else 0
        ),
        "average_assessment_percent": (
            round(sum(assessment_values) / len(assessment_values))
            if assessment_values
            else None
        ),
        "completed_students_count": sum(
            report["completion_percent"] == 100 for report in reports
        ),
    }


def build_student_report(row, chapters_count):
    """Normalize database aggregates for a single student."""

    assessment_average = row["assessment_average"]
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "email": row["email"],
        "completed_count": row["completed_count"],
        "completion_percent": percentage(
            row["completed_count"], chapters_count
        ),
        "assessment_attempts": row["assessment_attempts"],
        "assessment_average_percent": (
            round(assessment_average) if assessment_average is not None else None
        ),
        "laboratory_attempts": row["laboratory_attempts"],
        "laboratory_completed_count": row["laboratory_completed_count"],
    }


def filter_student_reports(reports, query):
    """Filter reports by username or email using a case-insensitive query."""

    normalized = query.strip().casefold()
    if not normalized:
        return list(reports)
    return [
        report
        for report in reports
        if normalized in (report["username"] or "").casefold()
        or normalized in report["email"].casefold()
    ]


def serialize_student_reports_csv(reports, chapters_count):
    """Serialize student reports as a UTF-8 compatible CSV document."""

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "Логин",
            "Email",
            "Пройдено глав",
            "Всего глав",
            "Прогресс, %",
            "Попыток тестов",
            "Средний тест, %",
            "Запусков лабораторных",
            "Завершено лабораторных",
        ]
    )
    for report in reports:
        writer.writerow(
            [
                report["username"] or "",
                report["email"],
                report["completed_count"],
                chapters_count,
                report["completion_percent"],
                report["assessment_attempts"],
                report["assessment_average_percent"]
                if report["assessment_average_percent"] is not None
                else "",
                report["laboratory_attempts"],
                report["laboratory_completed_count"],
            ]
        )
    return output.getvalue()

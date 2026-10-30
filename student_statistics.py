"""Helpers for presenting a student's course statistics."""


def percentage(value, total):
    """Return a whole-number percentage while handling an empty total."""

    if total <= 0:
        return 0
    return round(value * 100 / total)


def build_student_statistics(
    chapters_count,
    completed_count,
    assessment_scores=(),
    laboratory_slugs=(),
):
    """Build summary values from course progress and completed attempts."""

    assessment_percentages = [
        percentage(score, maximum)
        for score, maximum in assessment_scores
        if maximum > 0
    ]
    laboratory_slugs = list(laboratory_slugs)
    return {
        "completion_percent": percentage(completed_count, chapters_count),
        "assessment_attempts": len(assessment_percentages),
        "assessment_average_percent": (
            round(sum(assessment_percentages) / len(assessment_percentages))
            if assessment_percentages
            else None
        ),
        "assessment_best_percent": (
            max(assessment_percentages) if assessment_percentages else None
        ),
        "laboratory_attempts": len(laboratory_slugs),
        "laboratory_unique_count": len(set(laboratory_slugs)),
    }


def build_chapter_statistics(
    chapters,
    completed_chapter_ids=(),
    assessment_results=(),
    laboratory_chapter_ids=(),
):
    """Combine chapter progress with the student's recorded results."""

    completed = set(completed_chapter_ids)
    laboratory_chapter_ids = list(laboratory_chapter_ids)
    assessments_by_chapter = {}
    for chapter_id, score, maximum in assessment_results:
        if maximum <= 0:
            continue
        assessments_by_chapter.setdefault(chapter_id, []).append(
            percentage(score, maximum)
        )

    return [
        {
            "chapter_id": chapter["id"],
            "position": chapter["position"],
            "title": chapter["title"],
            "completed": chapter["id"] in completed,
            "assessment_attempts": len(
                assessments_by_chapter.get(chapter["id"], [])
            ),
            "assessment_best_percent": max(
                assessments_by_chapter.get(chapter["id"], []),
                default=None,
            ),
            "laboratory_attempts": laboratory_chapter_ids.count(chapter["id"]),
        }
        for chapter in sorted(
            chapters,
            key=lambda item: (item["position"], item["id"]),
        )
    ]

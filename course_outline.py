"""Utilities for inspecting the structure of a loaded course.

The web application stores chapter metadata in JSON files.  This module keeps
course-structure checks independent from Flask so they can be used by tests,
maintenance scripts, and future teacher-facing views.
"""


def build_course_outline(materials):
    """Return a deterministic outline grouped by course slug.

    Each item in *materials* is expected to be a mapping returned by
    :func:`course_content.load_course_materials`.  The returned dictionaries
    intentionally contain presentation metadata only; Markdown bodies are not
    copied into the outline.
    """

    outline = {}
    for material in materials:
        course = material["course"]
        outline.setdefault(course, []).append(
            {
                "position": material["position"],
                "title": material["title"],
                "description": material["description"],
            }
        )

    for chapters in outline.values():
        chapters.sort(key=lambda chapter: chapter["position"])
    return dict(sorted(outline.items()))


def find_outline_gaps(materials):
    """Return missing chapter positions for every course.

    Positions are expected to start at one and increase without gaps.  The
    function reports gaps rather than raising so a teacher can fix all issues
    in one pass.
    """

    positions_by_course = {}
    for material in materials:
        positions_by_course.setdefault(material["course"], set()).add(
            material["position"]
        )

    gaps = {}
    for course, positions in sorted(positions_by_course.items()):
        if not positions:
            continue
        expected = set(range(1, max(positions) + 1))
        missing = sorted(expected - positions)
        if missing:
            gaps[course] = missing
    return gaps

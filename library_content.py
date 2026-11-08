import json
import os
import re
from urllib.parse import urlsplit


REQUIRED_FIELDS = {
    "course",
    "slug",
    "chapter_position",
    "position",
    "title",
    "description",
    "category",
    "difficulty",
    "material_type",
    "estimated_minutes",
    "content_file",
}
MATERIAL_TYPES = {"article", "book", "video", "link", "file"}
DIFFICULTIES = {"basic", "intermediate", "advanced"}
PUBLICATION_STATUSES = {"draft", "published"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _is_http_url(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


def load_library_materials(content_directory):
    if not os.path.isdir(content_directory):
        raise FileNotFoundError(
            f"Library materials directory {content_directory!r} does not exist."
        )

    materials = []
    seen_slugs = set()
    seen_positions = set()
    for root, directories, filenames in os.walk(content_directory):
        directories.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as metadata_file:
                material = json.load(metadata_file)
            if not isinstance(material, dict):
                raise ValueError(
                    f"Library material {path!r} must contain a JSON object."
                )

            missing_fields = REQUIRED_FIELDS - material.keys()
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Library material {path!r} is missing required fields: {missing}."
                )

            status = material.get("status", "published")
            resource_url = material.get("resource_url", "")
            if (
                not isinstance(material["course"], str)
                or not SLUG_PATTERN.fullmatch(material["course"])
                or not isinstance(material["slug"], str)
                or not SLUG_PATTERN.fullmatch(material["slug"])
                or not isinstance(material["chapter_position"], int)
                or isinstance(material["chapter_position"], bool)
                or material["chapter_position"] < 1
                or not isinstance(material["position"], int)
                or isinstance(material["position"], bool)
                or material["position"] < 1
                or not isinstance(material["title"], str)
                or not material["title"].strip()
                or not isinstance(material["description"], str)
                or not isinstance(material["category"], str)
                or not SLUG_PATTERN.fullmatch(material["category"])
                or material["difficulty"] not in DIFFICULTIES
                or material["material_type"] not in MATERIAL_TYPES
                or not isinstance(material["estimated_minutes"], int)
                or isinstance(material["estimated_minutes"], bool)
                or not 1 <= material["estimated_minutes"] <= 240
                or status not in PUBLICATION_STATUSES
                or not isinstance(resource_url, str)
                or (resource_url and not _is_http_url(resource_url))
                or not isinstance(material["content_file"], str)
                or not material["content_file"].endswith(".md")
                or os.path.basename(material["content_file"])
                != material["content_file"]
            ):
                raise ValueError(
                    f"Library material {path!r} contains invalid field values."
                )

            content_path = os.path.join(root, material["content_file"])
            with open(content_path, encoding="utf-8") as content_file:
                material["content"] = content_file.read()
            if not material["content"].strip():
                raise ValueError(
                    f"Library material {path!r} has an empty Markdown file."
                )

            slug_key = material["course"], material["slug"]
            position_key = material["course"], material["position"]
            if slug_key in seen_slugs:
                raise ValueError(f"Duplicate library material slug: {slug_key!r}.")
            if position_key in seen_positions:
                raise ValueError(f"Duplicate library material position: {position_key!r}.")
            seen_slugs.add(slug_key)
            seen_positions.add(position_key)
            material["status"] = status
            material["resource_url"] = resource_url
            materials.append(material)

    return sorted(materials, key=lambda item: (item["course"], item["position"]))

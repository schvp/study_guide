import json
import os


REQUIRED_FIELDS = {
    "course",
    "position",
    "title",
    "description",
    "content_file",
}


def load_course_materials(content_directory):
    if not os.path.isdir(content_directory):
        raise FileNotFoundError(
            f"Course materials directory {content_directory!r} does not exist."
        )
    materials = []
    seen_positions = set()
    for root, directories, filenames in os.walk(content_directory):
        directories.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(root, filename)
            with open(path, encoding="utf-8") as content_file:
                material = json.load(content_file)
            if not isinstance(material, dict):
                raise ValueError(
                    f"Course material {path!r} must contain a JSON object."
                )
            missing_fields = REQUIRED_FIELDS - material.keys()
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Course material {path!r} is missing required fields: {missing}."
                )
            if (
                not isinstance(material["course"], str)
                or not material["course"].strip()
                or not isinstance(material["position"], int)
                or isinstance(material["position"], bool)
                or material["position"] < 1
                or not isinstance(material["title"], str)
                or not material["title"].strip()
                or not isinstance(material["description"], str)
                or not isinstance(material["content_file"], str)
                or not material["content_file"].endswith(".md")
                or os.path.basename(material["content_file"])
                != material["content_file"]
            ):
                raise ValueError(
                    f"Course material {path!r} contains invalid field values."
                )

            content_path = os.path.join(root, material["content_file"])
            with open(content_path, encoding="utf-8") as content_file:
                material["content"] = content_file.read()
            if not material["content"].strip():
                raise ValueError(
                    f"Course material {path!r} has an empty Markdown file."
                )

            key = material["course"], material["position"]
            if key in seen_positions:
                raise ValueError(
                    f"Duplicate course material for {key[0]!r}, chapter {key[1]}."
                )
            seen_positions.add(key)
            materials.append(material)
    return materials

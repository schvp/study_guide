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
    materials = []
    seen_positions = set()
    for filename in sorted(os.listdir(content_directory)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(content_directory, filename)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as content_file:
            material = json.load(content_file)
        if not isinstance(material, dict):
            raise ValueError(f"Course material {path!r} must contain a JSON object.")
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
            or os.path.basename(material["content_file"]) != material["content_file"]
        ):
            raise ValueError(f"Course material {path!r} contains invalid field values.")

        content_path = os.path.join(content_directory, material["content_file"])
        with open(content_path, encoding="utf-8") as content_file:
            material["content"] = content_file.read()
        if not material["content"].strip():
            raise ValueError(f"Course material {path!r} has an empty Markdown file.")

        key = material["course"], material["position"]
        if key in seen_positions:
            raise ValueError(
                f"Duplicate course material for {key[0]!r}, chapter {key[1]}."
            )
        seen_positions.add(key)
        materials.append(material)
    return materials

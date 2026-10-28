"""Catalog metadata and progress helpers for interactive laboratories."""


LABORATORY_DEFINITIONS = {
    1: {
        "slug": "byte-assembly",
        "title": "Сборка двоичного байта",
        "description": "Соберите восьмиразрядное слово и проверьте его значение.",
    },
    2: {
        "slug": "octal-conversion",
        "title": "Перевод в восьмеричную систему",
        "description": "Выполните последовательное деление и восстановите запись числа.",
    },
    3: {
        "slug": "boolean-circuit",
        "title": "Синтез булевой схемы",
        "description": "Настройте логические элементы по заданной таблице истинности.",
    },
    4: {
        "slug": "nand-gate",
        "title": "Схема на элементах И-НЕ",
        "description": "Соберите базовую функцию только из универсальных элементов И-НЕ.",
    },
    5: {
        "slug": "multiplexer",
        "title": "Проектирование мультиплексора",
        "description": "Соедините управляющие и информационные входы маршрутизатора.",
    },
    6: {
        "slug": "trigger",
        "title": "Исследование D-триггера",
        "description": "Проследите изменение состояния на фронтах тактового сигнала.",
    },
    7: {
        "slug": "register-counter",
        "title": "Регистр и двоичный счётчик",
        "description": "Передайте последовательность битов и проверьте работу счётчика.",
    },
    8: {
        "slug": "memory",
        "title": "Оперативная и постоянная память",
        "description": "Сравните чтение, запись и сохранение данных после отключения питания.",
    },
}

LABORATORY_BY_SLUG = {
    definition["slug"]: {**definition, "position": position}
    for position, definition in LABORATORY_DEFINITIONS.items()
}


def get_laboratory_definition(slug):
    """Return laboratory metadata by public slug, or ``None`` when unknown."""

    return LABORATORY_BY_SLUG.get(slug)


def build_laboratory_catalog(chapters, completed_chapter_ids=()):
    """Combine published chapters with laboratory metadata and access state."""

    completed = set(completed_chapter_ids)
    ordered_chapters = sorted(chapters, key=lambda item: (item["position"], item["id"]))
    catalog = []
    prior_chapter_ids = []
    for chapter in ordered_chapters:
        definition = LABORATORY_DEFINITIONS.get(chapter["position"])
        if definition is None:
            continue
        catalog.append(
            {
                **definition,
                "chapter_id": chapter["id"],
                "chapter_title": chapter["title"],
                "position": chapter["position"],
                "completed": chapter["id"] in completed,
                "available": all(chapter_id in completed for chapter_id in prior_chapter_ids),
            }
        )
        prior_chapter_ids.append(chapter["id"])
    return catalog

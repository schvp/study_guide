import json


INITIAL_QUESTIONS = (
    {
        "chapter_position": 1,
        "question_type": "single_choice",
        "prompt": "Сколько битов содержит один байт?",
        "options": [
            {"value": "4", "label": "4"},
            {"value": "8", "label": "8"},
            {"value": "16", "label": "16"},
        ],
        "correct_answer": "8",
        "explanation": "В принятой системе один байт состоит из восьми битов.",
    },
    {
        "chapter_position": 1,
        "question_type": "numeric",
        "prompt": "Какое десятичное число записано двоичным кодом 1011?",
        "options": [],
        "correct_answer": 11,
        "explanation": "1011₂ = 8 + 2 + 1 = 11₁₀.",
    },
    {
        "chapter_position": 2,
        "question_type": "numeric",
        "prompt": "Запишите десятичное число 173 в восьмеричной системе.",
        "options": [],
        "correct_answer": 255,
        "explanation": "173₁₀ = 2×64 + 5×8 + 5 = 255₈.",
    },
    {
        "chapter_position": 2,
        "question_type": "multiple_choice",
        "prompt": "Какие записи равны десятичному числу 10?",
        "options": [
            {"value": "binary", "label": "1010₂"},
            {"value": "octal", "label": "12₈"},
            {"value": "hex", "label": "A₁₆"},
            {"value": "other", "label": "1100₂"},
        ],
        "correct_answer": ["binary", "octal", "hex"],
        "explanation": "1010₂, 12₈ и A₁₆ имеют десятичное значение 10.",
    },
    {
        "chapter_position": 3,
        "question_type": "single_choice",
        "prompt": "Чему равно выражение X ∧ 1?",
        "options": [
            {"value": "zero", "label": "0"},
            {"value": "one", "label": "1"},
            {"value": "x", "label": "X"},
        ],
        "correct_answer": "x",
        "explanation": "Единица является нейтральным элементом операции И: X ∧ 1 = X.",
    },
    {
        "chapter_position": 3,
        "question_type": "numeric",
        "prompt": "Сколько строк содержит таблица истинности для двух переменных?",
        "options": [],
        "correct_answer": 4,
        "explanation": "Для n переменных таблица содержит 2ⁿ строк; для двух переменных это 4.",
    },
    {
        "chapter_position": 4,
        "question_type": "single_choice",
        "prompt": "Каков выход элемента НЕ, если на входе 0?",
        "options": [
            {"value": "zero", "label": "0"},
            {"value": "one", "label": "1"},
        ],
        "correct_answer": "one",
        "explanation": "Инвертор меняет логическое значение на противоположное.",
    },
    {
        "chapter_position": 4,
        "question_type": "multiple_choice",
        "prompt": "В каких случаях выход элемента И равен 1?",
        "options": [
            {"value": "00", "label": "A = 0, B = 0"},
            {"value": "01", "label": "A = 0, B = 1"},
            {"value": "10", "label": "A = 1, B = 0"},
            {"value": "11", "label": "A = 1, B = 1"},
        ],
        "correct_answer": ["11"],
        "explanation": "Элемент И выдаёт 1, только когда все его входы равны 1.",
    },
    {
        "chapter_position": 5,
        "question_type": "single_choice",
        "prompt": "Какой элемент формирует бит суммы полусумматора?",
        "options": [
            {"value": "and", "label": "И"},
            {"value": "or", "label": "ИЛИ"},
            {"value": "xor", "label": "Исключающее ИЛИ"},
        ],
        "correct_answer": "xor",
        "explanation": "Бит суммы полусумматора вычисляется как A XOR B.",
    },
    {
        "chapter_position": 5,
        "question_type": "numeric",
        "prompt": "Каково десятичное значение наибольшего беззнакового числа из 3 битов?",
        "options": [],
        "correct_answer": 7,
        "explanation": "Максимум для n битов равен 2ⁿ − 1; для трёх битов это 7.",
    },
    {
        "chapter_position": 6,
        "question_type": "single_choice",
        "prompt": "Когда триггер срабатывает на положительный фронт тактового сигнала?",
        "options": [
            {"value": "rise", "label": "При переходе такта из 0 в 1"},
            {"value": "fall", "label": "При переходе такта из 1 в 0"},
            {"value": "level", "label": "Пока такт удерживается в 1"},
        ],
        "correct_answer": "rise",
        "explanation": "Положительный фронт — это переход сигнала из низкого уровня в высокий.",
    },
    {
        "chapter_position": 6,
        "question_type": "multiple_choice",
        "prompt": "Что происходит с состоянием триггера между активными фронтами такта?",
        "options": [
            {"value": "hold", "label": "Состояние сохраняется"},
            {"value": "toggle", "label": "Состояние всегда инвертируется"},
            {"value": "zero", "label": "Состояние всегда сбрасывается"},
        ],
        "correct_answer": ["hold"],
        "explanation": "Триггер хранит последнее принятое состояние до следующего активного события.",
    },
    {
        "chapter_position": 7,
        "question_type": "numeric",
        "prompt": "Сколько различных состояний может хранить 4-битный регистр?",
        "options": [],
        "correct_answer": 16,
        "explanation": "Четыре бита кодируют 2⁴ = 16 различных комбинаций.",
    },
    {
        "chapter_position": 7,
        "question_type": "single_choice",
        "prompt": "Сколько состояний проходит счётчик по модулю 6 за один полный цикл?",
        "options": [
            {"value": "5", "label": "5"},
            {"value": "6", "label": "6"},
            {"value": "8", "label": "8"},
        ],
        "correct_answer": "6",
        "explanation": "Счётчик по модулю 6 имеет шесть различных состояний в цикле.",
    },
    {
        "chapter_position": 8,
        "question_type": "single_choice",
        "prompt": "Какая память сохраняет данные после отключения питания?",
        "options": [
            {"value": "ram", "label": "Оперативная память RAM"},
            {"value": "rom", "label": "Постоянная память ROM"},
            {"value": "register", "label": "Регистр на триггерах"},
        ],
        "correct_answer": "rom",
        "explanation": "ROM относится к энергонезависимой памяти и сохраняет содержимое без питания.",
    },
    {
        "chapter_position": 8,
        "question_type": "numeric",
        "prompt": "Сколько ячеек адресует 3-битная адресная шина?",
        "options": [],
        "correct_answer": 8,
        "explanation": "Три адресных бита задают 2³ = 8 различных адресов.",
    },
)


def seed_assessment_questions(database, course_id):
    already_seeded = database.execute(
        "SELECT 1 FROM assessment_bank_seed_state WHERE course_id = ?",
        (course_id,),
    ).fetchone()
    if already_seeded:
        return
    existing_questions = database.execute(
        "SELECT 1 FROM assessment_questions WHERE course_id = ? LIMIT 1",
        (course_id,),
    ).fetchone()
    if existing_questions:
        database.execute(
            "INSERT INTO assessment_bank_seed_state (course_id) VALUES (?)",
            (course_id,),
        )
        return
    chapters = {
        row["position"]: row["id"]
        for row in database.execute(
            """
            SELECT id, position FROM chapters
            WHERE course_id = ?
            """,
            (course_id,),
        )
    }
    positions = {}
    for question in INITIAL_QUESTIONS:
        chapter_id = chapters.get(question["chapter_position"])
        if chapter_id is None:
            continue
        position = positions.get(chapter_id, 0) + 1
        positions[chapter_id] = position
        database.execute(
            """
            INSERT OR IGNORE INTO assessment_questions (
                course_id, chapter_id, question_type, prompt, options,
                correct_answer, explanation, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                chapter_id,
                question["question_type"],
                question["prompt"],
                json.dumps(question["options"], ensure_ascii=False),
                json.dumps(question["correct_answer"], ensure_ascii=False),
                question["explanation"],
                position,
            ),
        )
    database.execute(
        "INSERT INTO assessment_bank_seed_state (course_id) VALUES (?)",
        (course_id,),
    )

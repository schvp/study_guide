
from flask import Flask, render_template

app = Flask(__name__)

CHAPTERS = [
    "Введение в цифровую схемотехнику",
    "Системы счисления и кодирование информации",
    "Основы булевой алгебры",
    "Логические элементы",
    "Комбинационные цифровые устройства",
    "Триггеры",
    "Регистры и счётчики",
    "Запоминающие устройства",
]


@app.route("/")
def home():
    return render_template("index.html", chapters=CHAPTERS)


if __name__ == "__main__":
    app.run(debug=True)

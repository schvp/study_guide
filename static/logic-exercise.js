const logicExercise = document.querySelector("[data-logic-exercise]");

if (logicExercise) {
    const gateNames = { and: "∧", or: "∨" };
    const inputValues = { a: 0, b: 0 };
    const rows = Array.from(logicExercise.querySelectorAll("[data-logic-row]"));
    const submitButton = logicExercise.querySelector("[data-logic-submit]");
    const hintButton = logicExercise.querySelector("[data-logic-hint]");
    const hintText = logicExercise.querySelector("[data-logic-hint-text]");
    const status = logicExercise.querySelector("[data-logic-status]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";
    const hints = [
        "Выход должен быть 1 только в строках 01 и 10. Для одинаковых входов 00 и 11 он должен быть 0.",
        "Соберите путь A И ¬B и путь ¬A И B, затем объедините результаты элементов И операцией ИЛИ.",
    ];
    let hintsShown = 0;

    function readCircuit() {
        return {
            first_a_inverted: logicExercise.querySelector(
                '[data-logic-literal="first-a"]',
            ).value === "not-a",
            first_b_inverted: logicExercise.querySelector(
                '[data-logic-literal="first-b"]',
            ).value === "not-b",
            first_gate: logicExercise.querySelector('[data-logic-gate="first"]').value,
            second_a_inverted: logicExercise.querySelector(
                '[data-logic-literal="second-a"]',
            ).value === "not-a",
            second_b_inverted: logicExercise.querySelector(
                '[data-logic-literal="second-b"]',
            ).value === "not-b",
            second_gate: logicExercise.querySelector('[data-logic-gate="second"]').value,
            output_gate: logicExercise.querySelector('[data-logic-gate="output"]').value,
        };
    }

    function gateValue(gate, left, right) {
        return gate === "and" ? Number(left === 1 && right === 1) : Number(left === 1 || right === 1);
    }

    function literalValue(input, inverted, values) {
        return inverted ? 1 - values[input] : values[input];
    }

    function evaluateCircuit(values, circuit) {
        const first = gateValue(
            circuit.first_gate,
            literalValue("a", circuit.first_a_inverted, values),
            literalValue("b", circuit.first_b_inverted, values),
        );
        const second = gateValue(
            circuit.second_gate,
            literalValue("a", circuit.second_a_inverted, values),
            literalValue("b", circuit.second_b_inverted, values),
        );
        return gateValue(circuit.output_gate, first, second);
    }

    function literalName(input, inverted) {
        return `${inverted ? "¬" : ""}${input.toUpperCase()}`;
    }

    function updateExpression(circuit) {
        const expression = logicExercise.querySelector("[data-logic-expression]");
        const first = `(${literalName("a", circuit.first_a_inverted)} ${gateNames[circuit.first_gate]} ${literalName("b", circuit.first_b_inverted)})`;
        const second = `(${literalName("a", circuit.second_a_inverted)} ${gateNames[circuit.second_gate]} ${literalName("b", circuit.second_b_inverted)})`;
        expression.textContent = `${first} ${gateNames[circuit.output_gate]} ${second}`;
    }

    function updateView() {
        const circuit = readCircuit();
        const actual = evaluateCircuit(inputValues, circuit);
        logicExercise.querySelectorAll("[data-logic-input]").forEach((button) => {
            const input = button.dataset.logicInput;
            button.setAttribute("aria-pressed", String(inputValues[input] === 1));
            logicExercise.querySelector(`[data-logic-input-value="${input}"]`).textContent =
                String(inputValues[input]);
        });
        const indicator = logicExercise.querySelector("[data-logic-indicator]");
        indicator.dataset.logicIndicator = String(actual);
        logicExercise.querySelector("[data-logic-indicator-label]").textContent =
            actual === 1 ? "Индикатор включён" : "Индикатор выключен";

        rows.forEach((row) => {
            const values = {
                a: Number(row.dataset.a),
                b: Number(row.dataset.b),
            };
            const rowActual = evaluateCircuit(values, circuit);
            row.querySelector("[data-logic-actual]").textContent = String(rowActual);
            row.dataset.matches = String(rowActual === Number(row.dataset.expected));
            row.removeAttribute("data-error");
        });
        updateExpression(circuit);
    }

    logicExercise.querySelectorAll("[data-logic-input]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = button.dataset.logicInput;
            inputValues[input] = 1 - inputValues[input];
            updateView();
        });
    });

    logicExercise.querySelectorAll("select").forEach((select) => {
        select.addEventListener("change", () => {
            status.textContent = "";
            status.dataset.state = "";
            updateView();
        });
    });

    hintButton.addEventListener("click", () => {
        hintText.textContent = hints[hintsShown];
        hintText.hidden = false;
        hintsShown += 1;
        if (hintsShown === hints.length) {
            hintButton.hidden = true;
        } else {
            hintButton.textContent = "Следующая подсказка";
        }
    });

    submitButton.addEventListener("click", async () => {
        submitButton.disabled = true;
        status.textContent = "Проверяем все четыре комбинации…";
        status.dataset.state = "";

        try {
            const response = await fetch(logicExercise.dataset.submitUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify(readCircuit()),
            });
            let result;
            try {
                result = await response.json();
            } catch {
                throw new Error(`Сервер вернул некорректный ответ (${response.status}).`);
            }

            if (response.status === 422) {
                result.mismatches.forEach(({ a, b }) => {
                    const row = rows.find(
                        (item) => Number(item.dataset.a) === a && Number(item.dataset.b) === b,
                    );
                    if (row) {
                        row.dataset.error = "true";
                    }
                });
                const combinations = result.mismatches
                    .map(({ a, b }) => `${a}${b}`)
                    .join(", ");
                status.textContent = `${result.message} Проверьте входы: ${combinations}.`;
                status.dataset.state = "error";
                hintButton.hidden = false;
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить схему.");
            }

            status.textContent = "Все комбинации совпали с заданием. Открываем следующий раздел…";
            status.dataset.state = "success";
            window.location.reload();
        } catch (error) {
            status.textContent = error instanceof TypeError
                ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                : error.message;
            status.dataset.state = "error";
        } finally {
            submitButton.disabled = false;
        }
    });

    updateView();
}

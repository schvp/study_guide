const gateLab = document.querySelector("[data-gate-lab]");

if (gateLab) {
    const inputValues = { a: 0, b: 0 };
    const gateRows = Array.from(gateLab.querySelectorAll("[data-gate-row]"));
    const checkButton = gateLab.querySelector("[data-gate-check]");
    const hintButton = gateLab.querySelector("[data-gate-hint]");
    const hintText = gateLab.querySelector("[data-gate-hint-text]");
    const status = gateLab.querySelector("[data-gate-status]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";
    const hints = [
        "В первом элементе подайте A на оба входа, а во втором — B на оба входа. NAND с одинаковыми входами работает как инвертор.",
        "Каждый из первых двух NAND создаёт инверсный сигнал. Последний NAND объединяет их по закону де Моргана: ¬(¬A ∧ ¬B) = A ∨ B.",
    ];
    let hintsShown = 0;

    function readCircuit() {
        return {
            first_left: gateLab.querySelector('[data-gate-wire="first_left"]').value,
            first_right: gateLab.querySelector('[data-gate-wire="first_right"]').value,
            first_gate: gateLab.querySelector('[data-gate-type="first"]').value,
            second_left: gateLab.querySelector('[data-gate-wire="second_left"]').value,
            second_right: gateLab.querySelector('[data-gate-wire="second_right"]').value,
            second_gate: gateLab.querySelector('[data-gate-type="second"]').value,
            output_left: gateLab.querySelector('[data-gate-wire="output_left"]').value,
            output_right: gateLab.querySelector('[data-gate-wire="output_right"]').value,
            output_gate: gateLab.querySelector('[data-gate-type="output"]').value,
        };
    }

    function evaluateGate(type, left, right) {
        if (type === "nand") {
            return Number(!(left === 1 && right === 1));
        }
        return Number(!(left === 1 || right === 1));
    }

    function evaluateCircuit(inputs, circuit) {
        const first = evaluateGate(
            circuit.first_gate,
            inputs[circuit.first_left],
            inputs[circuit.first_right],
        );
        const second = evaluateGate(
            circuit.second_gate,
            inputs[circuit.second_left],
            inputs[circuit.second_right],
        );
        const outputs = { first, second };
        const output = evaluateGate(
            circuit.output_gate,
            outputs[circuit.output_left],
            outputs[circuit.output_right],
        );
        return { first, second, output };
    }

    function updateView() {
        const circuit = readCircuit();
        gateLab.querySelectorAll("[data-gate-input]").forEach((button) => {
            const input = button.dataset.gateInput;
            button.setAttribute("aria-pressed", String(inputValues[input] === 1));
            gateLab.querySelector(`[data-gate-input-value="${input}"]`).textContent =
                String(inputValues[input]);
        });

        const current = evaluateCircuit(inputValues, circuit);
        Object.entries(current).forEach(([gate, value]) => {
            gateLab.querySelector(`[data-gate-output="${gate}"]`).textContent =
                String(value);
        });
        const indicator = gateLab.querySelector("[data-gate-indicator]");
        indicator.dataset.gateIndicator = String(current.output);
        gateLab.querySelector("[data-gate-indicator-label]").textContent =
            current.output === 1 ? "Шлюз открыт" : "Шлюз закрыт";

        gateRows.forEach((row) => {
            const inputs = {
                a: Number(row.dataset.a),
                b: Number(row.dataset.b),
            };
            const result = evaluateCircuit(inputs, circuit).output;
            row.querySelector("[data-gate-row-output]").textContent = String(result);
            row.dataset.matches = String(result === Number(row.dataset.expected));
            row.removeAttribute("data-error");
        });
    }

    gateLab.querySelectorAll("[data-gate-input]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = button.dataset.gateInput;
            inputValues[input] = 1 - inputValues[input];
            updateView();
        });
    });

    gateLab.querySelectorAll("select").forEach((select) => {
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

    checkButton.addEventListener("click", async () => {
        checkButton.disabled = true;
        status.textContent = "Проверяем все четыре комбинации…";
        status.dataset.state = "";

        try {
            const response = await fetch(gateLab.dataset.submitUrl, {
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
                    const row = gateRows.find(
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

            status.textContent = "Все комбинации совпали. Шлюз открыт, переходим дальше…";
            status.dataset.state = "success";
            window.location.reload();
        } catch (error) {
            status.textContent = error instanceof TypeError
                ? "Не удалось связаться с сервером. Попробуйте ещё раз."
                : error.message;
            status.dataset.state = "error";
        } finally {
            checkButton.disabled = false;
        }
    });

    updateView();
}

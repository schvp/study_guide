const muxLab = document.querySelector("[data-mux-lab]");

if (muxLab) {
    const inputValues = { d0: 0, d1: 0, s: 0 };
    const rows = Array.from(muxLab.querySelectorAll("[data-mux-row]"));
    const checkButton = muxLab.querySelector("[data-mux-check]");
    const hintButton = muxLab.querySelector("[data-mux-hint]");
    const hintText = muxLab.querySelector("[data-mux-hint-text]");
    const status = muxLab.querySelector("[data-mux-status]");
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";
    const hints = [
        "Сначала получите ¬S инвертором. Для ветви D₀ используйте D₀ И ¬S, а для ветви D₁ — S И D₁.",
        "Объедините выходы двух ветвей через ИЛИ: Y = (¬S ∧ D₀) ∨ (S ∧ D₁). Тогда при S = 0 останется D₀, а при S = 1 — D₁.",
    ];
    let hintsShown = 0;

    function readCircuit() {
        const circuit = {};
        muxLab.querySelectorAll("[data-mux-wire]").forEach((select) => {
            circuit[select.dataset.muxWire] = select.value;
        });
        return circuit;
    }

    function evaluateCircuit(inputs, circuit) {
        const signals = { ...inputs };
        signals.not_s = 1 - inputs[circuit.not_input];
        const zeroTerm = Number(
            Boolean(signals[circuit.zero_left] && signals[circuit.zero_right]),
        );
        const oneTerm = Number(
            Boolean(signals[circuit.one_left] && signals[circuit.one_right]),
        );
        const terms = { zero_term: zeroTerm, one_term: oneTerm };
        const output = Number(
            Boolean(terms[circuit.output_left] || terms[circuit.output_right]),
        );
        return { not_s: signals.not_s, zero_term: zeroTerm, one_term: oneTerm, output };
    }

    function updateView() {
        const circuit = readCircuit();
        muxLab.querySelectorAll("[data-mux-input]").forEach((button) => {
            const input = button.dataset.muxInput;
            button.setAttribute("aria-pressed", String(inputValues[input] === 1));
            muxLab.querySelector(`[data-mux-input-value="${input}"]`).textContent =
                String(inputValues[input]);
        });

        const current = evaluateCircuit(inputValues, circuit);
        Object.entries(current).forEach(([signal, value]) => {
            muxLab.querySelector(`[data-mux-output="${signal}"]`).textContent =
                String(value);
        });
        muxLab.querySelector("[data-mux-indicator]").dataset.muxIndicator =
            String(current.output);
        muxLab.querySelector("[data-mux-indicator-label]").textContent =
            `На выходе: ${current.output}`;

        rows.forEach((row) => {
            const inputs = {
                d0: Number(row.dataset.d0),
                d1: Number(row.dataset.d1),
                s: Number(row.dataset.s),
            };
            const actual = evaluateCircuit(inputs, circuit).output;
            row.querySelector("[data-mux-row-output]").textContent = String(actual);
            row.dataset.matches = String(actual === Number(row.dataset.expected));
            row.removeAttribute("data-error");
        });
        const matchingRows = rows.filter(
            (row) => row.dataset.matches === "true",
        ).length;
        const score = muxLab.querySelector("[data-mux-score]");
        score.textContent = `Совпало комбинаций: ${matchingRows} из ${rows.length}`;
        score.dataset.complete = String(matchingRows === rows.length);
    }

    muxLab.querySelectorAll("[data-mux-input]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = button.dataset.muxInput;
            inputValues[input] = 1 - inputValues[input];
            updateView();
        });
    });

    muxLab.querySelectorAll("[data-mux-wire]").forEach((select) => {
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
        status.textContent = "Проверяем все восемь комбинаций…";
        status.dataset.state = "";

        try {
            const response = await fetch(muxLab.dataset.submitUrl, {
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
                result.mismatches.forEach(({ d0, d1, s }) => {
                    const row = rows.find(
                        (item) => Number(item.dataset.d0) === d0
                            && Number(item.dataset.d1) === d1
                            && Number(item.dataset.s) === s,
                    );
                    if (row) {
                        row.dataset.error = "true";
                    }
                });
                const combinations = result.mismatches
                    .map(({ d0, d1, s }) => `${d0}${d1}${s}`)
                    .join(", ");
                status.textContent = `${result.message} Проверьте D₀D₁S: ${combinations}.`;
                status.dataset.state = "error";
                hintButton.hidden = false;
                return;
            }
            if (!response.ok) {
                throw new Error(result.error || "Не удалось проверить маршрутизатор.");
            }

            status.textContent = "Все комбинации совпали. Маршрутизатор собран!";
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
